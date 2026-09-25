"""API ve CLI'ın ortak kullandığı servis: analiz durumu + ajan + değerlendirme önbelleği."""
from __future__ import annotations

import asyncio
import json
import logging
import time

from .agent import AgentService, fallback_assessment
from .config import RISK_ORDER, settings
from .pipeline import Analyzer, WorldState

log = logging.getLogger("roketsan")


class Service:
    def __init__(self):
        self.analyzer: Analyzer | None = None
        self.state: WorldState | None = None
        self.agent: AgentService | None = None
        self.assessments: dict[str, dict] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self.cache_path = settings.output_dir / "assessments.json"

    # ------------------------------------------------------------------ yaşam döngüsü
    def load(self) -> None:
        t0 = time.time()
        self.analyzer = Analyzer()
        self.state = self.analyzer.run()
        log.info("Analiz tamam: %d kare, %d araç, %d rapor (%.2fs)", len(self.state.frames),
                 len(self.state.vehicles), len(self.state.reports), time.time() - t0)
        if settings.llm_enabled:
            if self.agent is None:
                self.agent = AgentService(self.analyzer.ds, self.state)
            else:
                self.agent.update_state(self.analyzer.ds, self.state)
        else:
            log.warning("OPENAI_API_KEY yok — ajan devre dışı, şablon değerlendirmeler kullanılacak.")
        self._load_cache()

    def _load_cache(self) -> None:
        if self.cache_path.exists():
            try:
                self.assessments = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.assessments = {}

    def _save_cache(self) -> None:
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.assessments, ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def ds(self):
        return self.analyzer.ds

    # ------------------------------------------------------------------ değerlendirme
    async def assess(self, frame_id: str, force: bool = False) -> dict:
        if frame_id not in self.state.frames:
            raise KeyError(frame_id)
        if not force and frame_id in self.assessments:
            return self.assessments[frame_id]
        lock = self._locks.setdefault(frame_id, asyncio.Lock())
        async with lock:
            if not force and frame_id in self.assessments:
                return self.assessments[frame_id]
            if self.agent is None:
                res = fallback_assessment(self.state, frame_id)
            else:
                try:
                    res = await self.agent.assess_frame(frame_id)
                except Exception as e:  # LLM hatası pipeline'ı durdurmasın
                    log.exception("Ajan hatası (%s)", frame_id)
                    res = fallback_assessment(self.state, frame_id)
                    res["guardrail_notes"].append(f"LLM hatası: {type(e).__name__}: {e}")
            res["assessed_at"] = time.time()
            self.assessments[frame_id] = res
            self._save_cache()
            return res

    async def assess_many(self, frame_ids: list[str], force: bool = False, concurrency: int = 4) -> dict:
        sem = asyncio.Semaphore(concurrency)

        async def one(fid):
            async with sem:
                return fid, await self.assess(fid, force)
        return dict(await asyncio.gather(*(one(f) for f in frame_ids)))

    # ------------------------------------------------------------------ özetler
    def alerts(self) -> list[dict]:
        rows = []
        for v in self.state.vehicles.values():
            if v["risk_level"] != "DUSUK" and not v["filtered"]:
                f = v.get("features") or {}
                rows.append({"kind": "frame_vehicle", "vehicle_id": v["vehicle_id"], "frame_id": v["frame_id"],
                             "track_id": v["track_id"], "time": v["capture_time"], "zone": v["zone"],
                             "label": v["label"], "risk_level": v["risk_level"], "scenario": v["scenario"],
                             "dist_to_base_m": v["dist_to_base_m"], "eta_min": f.get("eta_min"),
                             "lat": v["lat"], "lon": v["lon"], "reason": v["risk_reasons"][0]})
        for r in self.state.offframe_risk.values():
            if r["risk_level"] != "DUSUK":
                rows.append({"kind": "offframe_track", "vehicle_id": None, "frame_id": None, "track_id": r["track_id"],
                             "time": r["last_time"], "zone": r["zone"], "label": None, "risk_level": r["risk_level"],
                             "scenario": r["scenario"], "dist_to_base_m": r["features"]["dist_now_m"],
                             "eta_min": r["features"].get("eta_min"), "lat": r["lat"], "lon": r["lon"],
                             "reason": r["risk_reasons"][0]})
        return sorted(rows, key=lambda x: (-RISK_ORDER.index(x["risk_level"]), x["time"]))

    def summary(self) -> dict:
        fr = self.state.frames.values()
        return {
            "frames": len(self.state.frames),
            "frame_risk_counts": {l: sum(1 for f in fr if f["risk_level"] == l) for l in RISK_ORDER},
            "vehicles": len(self.state.vehicles),
            "filtered_detections": sum(1 for v in self.state.vehicles.values() if v["filtered"]),
            "missed_detections_recovered": sum(1 for v in self.state.vehicles.values() if v["source"] == "track_only"),
            "offframe_tracks": len(self.state.offframe_track_ids),
            "report_verdicts": {k: sum(1 for r in self.state.reports if r["verdict"] == k)
                                for k in ["destekler", "celisir", "kismen_uyumlu", "dogrulanamaz", "ilgisiz", "manipulasyon"]},
            "assessed_frames": len(self.assessments),
            "llm_enabled": settings.llm_enabled, "model": settings.openai_model if settings.llm_enabled else None,
            "detector": self.state.detector, "generated_at": self.state.generated_at,
        }


service = Service()
