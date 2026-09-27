"""Retrospective game replay analysis with revision-aware, bounded caching."""
from __future__ import annotations

import copy
from collections import OrderedDict
from dataclasses import asdict
import logging
from pathlib import Path
from threading import RLock
import time
from typing import Any

from ..config import settings
from ..geo import min_to_hhmm
from .builder import SpatialGraphBuilder
from .clustering import RegionMerger
from .config import GraphAnalysisConfig, default_graph_config
from .intelligence import IntelligenceProcessor
from .extraction import report_minute
from .metrics import compute_all_metrics
from .models import GraphAnalysisResult
from .repository import fingerprint, write_json
from .scorer import ExplainableScorer
from .window import clip_tracks
from .assessments import stored_vehicle_feedback, summarize_feedback

log = logging.getLogger(__name__)
GRAPH_CACHE_FILE = "graph_analysis.json"


class GraphAnalysisService:
    def __init__(self, main_service: Any, config: GraphAnalysisConfig | None = None, *,
                 output_dir: Path | None = None, enable_llm: bool = True):
        self.main_service = main_service
        self.config = config or default_graph_config
        self.output_dir = output_dir or settings.output_dir
        self.cache_path = self.output_dir / GRAPH_CACHE_FILE
        self.enable_llm = enable_llm
        self._cache = OrderedDict()
        self._lock = RLock()
        self._bundle = None
        self._current_result = None

    def _determine_track_classifications(self, cfg: GraphAnalysisConfig) -> dict[str, bool]:
        state = self.main_service.state
        decision_map = self.main_service.decision_map()
        levels = {}
        for vehicle in state.vehicles.values():
            if vehicle.get("filtered"):
                continue
            tid = vehicle.get("track_id")
            if tid:
                final = self.main_service.vehicle_final(vehicle["vehicle_id"], decision_map)
                level = final.get("level") or vehicle.get("risk_level")
                if level:
                    levels.setdefault(tid, set()).add(level)
        for tid, risk in state.offframe_risk.items():
            if risk.get("risk_level"):
                levels.setdefault(tid, set()).add(risk["risk_level"])
        return {tid: bool(set(cfg.spatial.threat_risk_levels).intersection(values)) for tid, values in levels.items()}

    def run_analysis(self, force: bool = False, custom_config: GraphAnalysisConfig | None = None, *,
                     start_min: int | None = None, end_min: int | None = None) -> GraphAnalysisResult:
        cfg = custom_config or self.config
        with self._lock:
            tracks = clip_tracks(self.main_service.ds.tracks, start_min, end_min)
            classification = self._determine_track_classifications(cfg)
            unclassified = len(set(tracks) - classification.keys())
            tracks = {tid: track for tid, track in tracks.items() if tid in classification}
            classification = {tid: classification[tid] for tid in tracks}
            reports = []
            feedback = stored_vehicle_feedback(self.main_service, set(tracks), start_min, end_min)
            for raw in self.main_service.ds.reports:
                minute = report_minute(raw.get("time"))
                if minute is not None:
                    if (start_min is not None and minute < start_min) or (end_min is not None and minute > end_min):
                        continue
                reports.append(copy.deepcopy(raw))
            llm = getattr(getattr(self.main_service, "agent", None), "llm", None) if self.enable_llm else None
            revision = fingerprint({"version": 3, "feedback": feedback, "tracks": {tid: [asdict(p) for p in tr.points] for tid, tr in tracks.items()},
                                    "classification": classification, "reports": reports,
                                    "config": asdict(cfg), "window": [start_min, end_min],
                                    "unclassified": unclassified, "llm": llm is not None,
                                    "model": getattr(llm, "model_name", None)})
            if not force and revision in self._cache:
                result, self._bundle = self._cache[revision]
                self._cache.move_to_end(revision)
                self._current_result = result
                return result
            bundle = SpatialGraphBuilder(cfg.spatial).build(tracks, classification)
            baseline = compute_all_metrics(bundle, cfg)
            processor = IntelligenceProcessor(cfg.intelligence, llm=llm,
                                              cache_path=self.output_dir / "intelligence_extractions.json")
            matched, unmatched = processor.process_and_corroborate(
                reports, bundle, require_known_time=start_min is not None or end_min is not None
            )
            ExplainableScorer(cfg).score_all(list(bundle.nodes.values()))
            regions = RegionMerger(cfg.region).merge_high_interest_nodes(list(bundle.nodes.values()), baseline, bundle)
            feedback_by_track = {}
            for record in feedback:
                feedback_by_track.setdefault(record["track_id"], []).append(record)
            for region in regions:
                region_tracks = set().union(*(bundle.node_tracks.get(nid, set()) for nid in region.member_node_ids))
                region.vehicle_assessments = [record for tid in sorted(region_tracks) for record in feedback_by_track.get(tid, [])]
            points = [p.t for tr in tracks.values() for p in tr.points]
            result = GraphAnalysisResult(
                generated_at=time.time(), total_nodes=len(bundle.nodes), total_edges=len(bundle.edges),
                total_trajectories=len(classification), total_threat_trajectories=sum(classification.values()),
                total_normal_trajectories=len(classification) - sum(classification.values()), global_threat_rate=baseline,
                regions=regions, nodes=list(bundle.nodes.values()), edges=bundle.edges,
                unmatched_intelligence=unmatched, matched_intelligence_count=len(matched),
                analysis_start=min_to_hhmm(start_min if start_min is not None else min(points)) if points else None,
                analysis_end=min_to_hhmm(end_min if end_min is not None else max(points)) if points else None,
                data_revision=revision, unclassified_trajectory_count=unclassified,
                region_interest_threshold=cfg.region.min_interest_for_region,
            )
            self._bundle, self._current_result = bundle, result
            self._cache[revision] = result, bundle
            while len(self._cache) > cfg.cache_entries:
                self._cache.popitem(last=False)
            try:
                write_json(self.cache_path, {"schema_version": 2, "summary": result.to_summary_dict(),
                                            "nodes": [node.to_dict() for node in result.nodes],
                                            "edges": [edge.to_dict() for edge in result.edges],
                                            "unmatched_intelligence": [item.model_dump() for item in unmatched]})
            except OSError as exc:
                log.warning("Graph cache could not be saved: %s", type(exc).__name__)
            return result

    def get_regions(self, **window):
        return self.run_analysis(**window).regions

    def summarize_region(self, region_id: str, **window):
        with self._lock:
            region = self.get_region_by_id(region_id, **window)
            if region is None:
                return None
            llm = getattr(getattr(self.main_service, "agent", None), "llm", None) if self.enable_llm else None
            return {"region_id": region_id, **summarize_feedback(
                region.vehicle_assessments, llm, self.output_dir / "graph_vehicle_summaries.json",
                self.config.intelligence.llm_timeout_seconds)}

    def get_region_by_id(self, region_id: str, **window):
        return next((r for r in self.get_regions(**window) if r.region_id == region_id), None)

    def get_nodes(self, **window):
        return self.run_analysis(**window).nodes

    def get_bundle(self):
        if self._bundle is None:
            self.run_analysis()
        return self._bundle
