"""Game simulation graph API; time windows use the dataset's same-day simulation clock."""
from __future__ import annotations

from dataclasses import asdict, replace
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from ..geo import hhmm_to_min
from ..service import service
from .config import GraphAnalysisConfig
from .service import GraphAnalysisService

router = APIRouter(prefix="/api/graph-analysis", tags=["Game Trajectory Graph"])
_graph_service: GraphAnalysisService | None = None
_singleton_lock = Lock()


def get_graph_service() -> GraphAnalysisService:
    global _graph_service
    with _singleton_lock:
        if _graph_service is None:
            _graph_service = GraphAnalysisService(service)
        return _graph_service


def analysis_window(
    start_time: str | None = Query(None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$"),
    end_time: str | None = Query(None, pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$"),
):
    start = hhmm_to_min(start_time) if start_time is not None else None
    end = hhmm_to_min(end_time) if end_time is not None else None
    if start is not None and end is not None and start > end:
        raise HTTPException(422, "Başlangıç zamanı bitiş zamanından sonra olamaz.")
    return {"start_min": start, "end_min": end}


@router.get("")
def get_graph_analysis(window: dict = Depends(analysis_window), svc: GraphAnalysisService = Depends(get_graph_service)):
    return svc.run_analysis(**window).to_summary_dict()


@router.get("/config")
def get_config(svc: GraphAnalysisService = Depends(get_graph_service)):
    return asdict(svc.config)


@router.get("/regions")
def get_regions(min_score: float = Query(0, ge=0, le=1),
                severity: str | None = Query(None, pattern="^(?:DUSUK|ORTA|YUKSEK|KRITIK)$"),
                window: dict = Depends(analysis_window), svc: GraphAnalysisService = Depends(get_graph_service)):
    return [region.to_dict() for region in svc.get_regions(**window)
            if region.interest_score >= min_score and (severity is None or region.severity == severity)]


@router.get("/regions/{region_id}")
def get_region_detail(region_id: str, window: dict = Depends(analysis_window),
                      svc: GraphAnalysisService = Depends(get_graph_service)):
    region = svc.get_region_by_id(region_id, **window)
    if region is None:
        raise HTTPException(404, f"Bölge {region_id} bulunamadı.")
    return region.to_dict()


@router.get("/graph")
def get_graph_topology(window: dict = Depends(analysis_window), svc: GraphAnalysisService = Depends(get_graph_service)):
    result = svc.run_analysis(**window)
    return {"nodes": [node.to_dict() for node in result.nodes], "edges": [edge.to_dict() for edge in result.edges],
            "global_threat_rate": result.global_threat_rate, "total_nodes": result.total_nodes,
            "total_edges": result.total_edges, "data_revision": result.data_revision}


@router.post("/regions/{region_id}/vehicle-summary")
def vehicle_summary(region_id: str, window: dict = Depends(analysis_window),
                    svc: GraphAnalysisService = Depends(get_graph_service)):
    result = svc.summarize_region(region_id, **window)
    if result is None:
        raise HTTPException(404, "Bölge bulunamadı.")
    return result


@router.get("/unmatched-intelligence")
def get_unmatched_intelligence(window: dict = Depends(analysis_window), svc: GraphAnalysisService = Depends(get_graph_service)):
    return [item.model_dump() for item in svc.run_analysis(**window).unmatched_intelligence]


class RecomputeOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = True
    cluster_radius_m: float | None = Field(None, gt=0, le=2000, allow_inf_nan=False)
    min_observation_threshold: int | None = Field(None, ge=1, le=100000)
    config: GraphAnalysisConfig | None = None


@router.post("/recompute")
def recompute_graph_analysis(options: RecomputeOptions | None = None, window: dict = Depends(analysis_window),
                             svc: GraphAnalysisService = Depends(get_graph_service)):
    options = options or RecomputeOptions()
    config = options.config or svc.config
    if options.cluster_radius_m is not None:
        config = replace(config, spatial=replace(config.spatial, cluster_radius_m=options.cluster_radius_m))
    if options.min_observation_threshold is not None:
        config = replace(config, smoothing=replace(config.smoothing, adaptive=False, min_observation_threshold=options.min_observation_threshold))
    result = svc.run_analysis(force=options.force, custom_config=config, **window)
    return {"status": "ok", **result.to_summary_dict()}
