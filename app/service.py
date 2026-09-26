"""API ve CLI'ın ortak kullandığı servis: analiz durumu + ajan + değerlendirme önbelleği + ortak karar.

Nihai seviye nasıl belirlenir (her araç için):
  1) "Son söz insanda" AÇIK ve analist bu araç için karar verdiyse → analistin seviyesi
  2) LLM değerlendirmesinde karar varsa → açıkken decision.review_level, kapalıyken decision.auto_level
  3) Hiçbiri yoksa → motorun seviyesi
Motor durumu (self.state) hiç değiştirilmez. Değerlendirmeler ham hâliyle saklanır; ayar değişince LLM yeniden
çalışmaz, sadece present() sonucu değişir. Ayar ve analist kararları outputs/ altında kalıcıdır.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from typing import AsyncIterator

from .agent import AgentService, fallback_assessment
from .config import RISK_ORDER, settings
from .pipeline import Analyzer, WorldState
from .risk import max_risk
from .steps import pipeline_steps

log = logging.getLogger("roketsan")


class ReviewError(Exception):
    """Analist kararı kabul edilemedi. status: API'nin döneceği HTTP kodu."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class Service:
    def __init__(self):
        self.analyzer: Analyzer | None = None
        self.state: WorldState | None = None
        self.agent: AgentService | None = None
        self.assessments: dict[str, dict] = {}
        self.reviews: dict[str, dict] = {}              # vehicle_id → analist kararı
        self.human_review: bool = settings.human_review_default
        self._locks: dict[str, asyncio.Lock] = {}
        self.cache_path = settings.output_dir / "assessments.json"
        self.reviews_path = settings.output_dir / "reviews.json"
        self.runtime_path = settings.output_dir / "runtime_settings.json"

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

    @staticmethod
    def _read_json(path, default):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log.warning("%s okunamadı, varsayılan kullanılıyor", path)
        return default

    @staticmethod
    def _write_json(path, obj) -> None:
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load_cache(self) -> None:
        self.assessments = self._read_json(self.cache_path, {})
        self.reviews = self._read_json(self.reviews_path, {})
        self.human_review = bool(self._read_json(self.runtime_path, {}).get("human_review",
                                                                            settings.human_review_default))

    def _save_cache(self) -> None:
        self._write_json(self.cache_path, self.assessments)

    def clear(self) -> None:
        """Veri değişince: değerlendirmeler ve analist kararları silinir (ayar korunur)."""
        self.assessments, self.reviews = {}, {}
        self._save_cache()
        self._write_json(self.reviews_path, self.reviews)

    @property
    def ds(self):
        return self.analyzer.ds

    def _store(self, frame_id: str, res: dict) -> dict:
        res["assessed_at"] = time.time()
        self.assessments[frame_id] = res
        self._save_cache()
        return res

    # ------------------------------------------------------------------ "son söz insanda" ayarı
    def runtime_settings(self) -> dict:
        return {"human_review": self.human_review}

    def set_human_review(self, enabled: bool) -> dict:
        self.human_review = bool(enabled)
        self._write_json(self.runtime_path, self.runtime_settings())
        log.info("İnsan onayı %s", "AÇIK" if self.human_review else "KAPALI")
        return self.runtime_settings()

    # ------------------------------------------------------------------ nihai seviyeler
    def decision_map(self) -> dict[str, dict]:
        """vehicle_id → karar tablosu çıktısı (tüm değerlendirmelerden). Motor seviyesi o günden beri değiştiyse
        (veri yeniden analiz edildi, eski önbellek) karar geçersiz sayılır."""
        out = {}
        for fid, a in self.assessments.items():
            if fid not in self.state.frames:
                continue
            for v in a.get("vehicles") or []:
                d = v.get("decision")
                veh = self.state.vehicles.get(v.get("vehicle_id"))
                if d and veh and d.get("engine_level") == veh["risk_level"]:
                    out[v["vehicle_id"]] = d
        return out

    def vehicle_final(self, vehicle_id: str, dmap: dict | None = None) -> dict:
        """{"level", "status", "decision", "review"} — status: motor | analist_karari | onay_bekliyor | <kural>"""
        dmap = self.decision_map() if dmap is None else dmap
        engine = self.state.vehicles[vehicle_id]["risk_level"]
        d = dmap.get(vehicle_id)
        review = self.reviews.get(vehicle_id) if self.human_review else None
        if review:
            return {"level": review["level"], "status": "analist_karari", "decision": d, "review": review}
        if d is None:
            return {"level": engine, "status": "motor", "decision": None, "review": None}
        if self.human_review:
            status = "onay_bekliyor" if d["needs_review"] else d["rule"]
            return {"level": d["review_level"], "status": status, "decision": d, "review": None}
        return {"level": d["auto_level"], "status": d["rule"], "decision": d, "review": None}

    def frame_final(self, frame_id: str, dmap: dict | None = None) -> dict:
        """Karenin nihai seviyesi (elenmiş tespitler hariç araçların en yükseği) + sayaçlar."""
        dmap = self.decision_map() if dmap is None else dmap
        fr = self.state.frames[frame_id]
        finals = {v: self.vehicle_final(v, dmap) for v in fr["vehicle_ids"] if not self.state.vehicles[v]["filtered"]}
        levels = [f["level"] for f in finals.values()]
        level = max_risk(levels)
        return {"level": level, "engine_level": fr["risk_level"], "changed": level != fr["risk_level"],
                "counts": {lvl: levels.count(lvl) for lvl in RISK_ORDER},
                "pending_reviews": sum(1 for f in finals.values() if f["status"] == "onay_bekliyor")}

    def with_final_level(self, vehicle: dict, dmap: dict | None = None) -> dict:
        """Araç görünümüne nihai seviyeyi yazar: risk_level = nihai, engine_risk_level = motor."""
        fin = self.vehicle_final(vehicle["vehicle_id"], dmap)
        return {**vehicle, "engine_risk_level": self.state.vehicles[vehicle["vehicle_id"]]["risk_level"],
                "risk_level": fin["level"], "decision_status": fin["status"], "decision": fin["decision"],
                "review": fin["review"]}

    def present(self, frame_id: str, assessment: dict | None) -> dict | None:
        """Saklanan (ham) değerlendirmeyi o anki ayar ve analist kararlarıyla sunar. Ham kayıt değişmez."""
        if assessment is None or frame_id not in self.state.frames:
            return assessment
        dmap = self.decision_map()
        a = copy.deepcopy(assessment)
        for v in a.get("vehicles") or []:
            if v.get("vehicle_id") in self.state.vehicles:
                fin = self.vehicle_final(v["vehicle_id"], dmap)
                v.update(risk_level=fin["level"], decision_status=fin["status"], review=fin["review"])
        ff = self.frame_final(frame_id, dmap)
        a.update(risk_level=ff["level"], engine_risk_level=ff["engine_level"], human_review=self.human_review,
                 pending_reviews=ff["pending_reviews"])
        return a

    def frame_view(self, frame_id: str, include_tracks: bool = True) -> dict:
        """Kare görünümü, nihai seviyelerle (API ve React için)."""
        dmap = self.decision_map()
        view = self.state.frame_view(frame_id, include_tracks=include_tracks, ds=self.ds)
        ff = self.frame_final(frame_id, dmap)
        view.update(engine_risk_level=ff["engine_level"], risk_level=ff["level"], risk_changed=ff["changed"],
                    engine_counts=self.state.frames[frame_id].get("counts"), counts=ff["counts"],
                    pending_reviews=ff["pending_reviews"], human_review=self.human_review)
        view["vehicles"] = [self.with_final_level(v, dmap) for v in view["vehicles"]]
        return view

    # ------------------------------------------------------------------ analist kararları
    def _review_item(self, vehicle_id: str, dmap: dict) -> dict:
        veh = self.state.vehicles[vehicle_id]
        fin = self.vehicle_final(vehicle_id, dmap)
        d = fin["decision"] or dmap.get(vehicle_id)
        reports = {r["report_id"]: r for r in self.state.reports}
        evidence = [{"report_id": rid, "verdict": reports[rid]["verdict"], "source": reports[rid]["source"],
                     "summary": reports[rid]["summary"]} for rid in (d or {}).get("evidence_report_ids", [])
                    if rid in reports]
        return {
            "vehicle_id": vehicle_id, "frame_id": veh["frame_id"], "track_id": veh["track_id"], "zone": veh["zone"],
            "capture_time": veh["capture_time"], "label": veh["label"],
            "current_level": fin["level"], "status": fin["status"],
            "engine_level": veh["risk_level"], "llm_level": (d or {}).get("llm_level"),
            "rule": (d or {}).get("rule"), "rule_label": (d or {}).get("rule_label"),
            "options": (d or {}).get("options") or RISK_ORDER,
            "motor": {"scenario": veh["scenario"], "reasons": veh["risk_reasons"], "margin": veh.get("margin")},
            "llm": {"reason": (d or {}).get("llm_reason"), "evidence": evidence},
            "note": (d or {}).get("note"), "review": self.reviews.get(vehicle_id),
        }

    def list_reviews(self, status: str = "pending", frame_id: str | None = None) -> dict:
        """status: pending (onay bekleyenler) | decided (analistin karar verdikleri) | all"""
        dmap = self.decision_map()
        pending_ids = [vid for vid, d in dmap.items()
                       if d["needs_review"] and vid not in self.reviews and not self.state.vehicles[vid]["filtered"]]
        ids = {"pending": pending_ids, "decided": [v for v in self.reviews if v in self.state.vehicles],
               "all": pending_ids + [v for v in self.reviews if v in self.state.vehicles]}.get(status, pending_ids)
        items = [self._review_item(vid, dmap) for vid in ids
                 if not frame_id or self.state.vehicles[vid]["frame_id"] == frame_id]
        items.sort(key=lambda x: (-RISK_ORDER.index(x["current_level"]), x["capture_time"]))
        return {"human_review": self.human_review,
                # özellik kapalıyken liste bilgi amaçlıdır: seviyeler otomatik kurala göre uygulanıyor
                "items": items, "pending_count": len(pending_ids)}

    def set_review(self, vehicle_id: str, level: str, analyst: str | None = None, note: str | None = None) -> dict:
        if not self.human_review:
            raise ReviewError(409, "İnsan onayı kapalı; önce PUT /api/settings ile açın.")
        veh = self.state.vehicles.get(vehicle_id)
        if veh is None:
            raise ReviewError(404, f"{vehicle_id} bulunamadı")
        if veh["filtered"]:
            raise ReviewError(400, f"{vehicle_id} düşük güvenle elenmiş bir tespit; seviyesi karar dışı.")
        if level not in RISK_ORDER:
            raise ReviewError(400, f"Geçersiz seviye: {level}. Seçenekler: {RISK_ORDER}")
        d = self.decision_map().get(vehicle_id) or {}
        self.reviews[vehicle_id] = {"level": level, "analyst": analyst or "analist", "note": note, "at": time.time(),
                                    "frame_id": veh["frame_id"], "engine_level": veh["risk_level"],
                                    "llm_level": d.get("llm_level"), "rule": d.get("rule")}
        self._write_json(self.reviews_path, self.reviews)
        return {"review": self._review_item(vehicle_id, self.decision_map()),
                "frame": self.frame_final(veh["frame_id"])}

    def delete_review(self, vehicle_id: str) -> dict:
        if vehicle_id not in self.reviews:
            raise ReviewError(404, f"{vehicle_id} için analist kararı yok")
        frame_id = self.reviews.pop(vehicle_id)["frame_id"]
        self._write_json(self.reviews_path, self.reviews)
        return {"vehicle_id": vehicle_id, "frame": self.frame_final(frame_id)}

    # ------------------------------------------------------------------ değerlendirme
    async def assess(self, frame_id: str, force: bool = False) -> dict:
        """Ham değerlendirmeyi üretir/önbellekten verir, o anki ayarla sunar."""
        return self.present(frame_id, await self._assess_raw(frame_id, force))

    async def _assess_raw(self, frame_id: str, force: bool = False) -> dict:
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
            return self._store(frame_id, res)

    async def assess_stream(self, frame_id: str, force: bool = False,
                            delay_ms: int = 0) -> AsyncIterator[dict]:
        """Olay akışı: start → step×4 (motor) → [reasoning|thought|tool_call|tool_result]* → final.
        Önbellekte varsa ajan izi yeniden oynatılır (replay=true); delay_ms demo için adımları aralar."""
        if frame_id not in self.state.frames:
            raise KeyError(frame_id)
        pace = max(delay_ms, 0) / 1000
        cached = None if force else self.assessments.get(frame_id)
        yield {"type": "start", "frame_id": frame_id, "llm_enabled": self.agent is not None,
               "cached": cached is not None, "human_review": self.human_review}

        for s in pipeline_steps(self.state, frame_id):
            if pace:
                await asyncio.sleep(pace)
            yield {"type": "step", **s}

        if cached is not None:
            for ev in cached.get("trace", []):
                if pace:
                    await asyncio.sleep(pace)
                yield {**ev, "replay": True}
            yield {"type": "final", "assessment": self.present(frame_id, cached), "cached": True}
            return

        lock = self._locks.setdefault(frame_id, asyncio.Lock())
        async with lock:
            res = None
            if self.agent is not None:
                try:
                    async for ev in self.agent.assess_frame_stream(frame_id):
                        if ev["type"] == "final":
                            res = ev["assessment"]
                        else:
                            yield ev
                except Exception as e:  # LLM hatası akışı kesmesin → şablona düş
                    log.exception("Ajan hatası (%s)", frame_id)
                    yield {"type": "error", "message": f"{type(e).__name__}: {e}"}
                    res = fallback_assessment(self.state, frame_id)
                    res["guardrail_notes"].append(f"LLM hatası: {type(e).__name__}: {e}")
            if res is None:
                res = fallback_assessment(self.state, frame_id)
            yield {"type": "final", "assessment": self.present(frame_id, self._store(frame_id, res)), "cached": False}

    async def assess_many(self, frame_ids: list[str], force: bool = False, concurrency: int = 4) -> dict:
        sem = asyncio.Semaphore(concurrency)

        async def one(fid):
            async with sem:
                return fid, await self.assess(fid, force)
        return dict(await asyncio.gather(*(one(f) for f in frame_ids)))

    def presented_assessments(self) -> dict:
        return {fid: self.present(fid, a) for fid, a in self.assessments.items()}

    # ------------------------------------------------------------------ özetler
    def alerts(self) -> list[dict]:
        """Riskli araçlar (nihai seviyeye göre) + kare dışı riskli izler, önce en kritik."""
        dmap = self.decision_map()
        rows = []
        for v in self.state.vehicles.values():
            if v["filtered"]:
                continue
            fin = self.vehicle_final(v["vehicle_id"], dmap)
            if fin["level"] == "DUSUK":
                continue
            f = v.get("features") or {}
            d, rv = fin["decision"], fin["review"]
            reason = (f"Analist kararı: {rv.get('note') or rv['level']}" if rv else
                      d["note"] if d and d["rule"] not in ("uzlasi", "llm_belirtmedi") and d["note"] else
                      v["risk_reasons"][0])
            rows.append({"kind": "frame_vehicle", "vehicle_id": v["vehicle_id"], "frame_id": v["frame_id"],
                         "track_id": v["track_id"], "time": v["capture_time"], "zone": v["zone"],
                         "label": v["label"], "risk_level": fin["level"], "engine_risk_level": v["risk_level"],
                         "decision_status": fin["status"], "scenario": v["scenario"],
                         "dist_to_base_m": v["dist_to_base_m"], "eta_min": f.get("eta_min"),
                         "lat": v["lat"], "lon": v["lon"], "reason": reason, "engine_reason": v["risk_reasons"][0]})
        for r in self.state.offframe_risk.values():
            if r["risk_level"] != "DUSUK":
                rows.append({"kind": "offframe_track", "vehicle_id": None, "frame_id": None, "track_id": r["track_id"],
                             "time": r["last_time"], "zone": r["zone"], "label": None, "risk_level": r["risk_level"],
                             "engine_risk_level": r["risk_level"], "decision_status": "motor",
                             "scenario": r["scenario"], "dist_to_base_m": r["features"]["dist_now_m"],
                             "eta_min": r["features"].get("eta_min"), "lat": r["lat"], "lon": r["lon"],
                             "reason": r["risk_reasons"][0], "engine_reason": r["risk_reasons"][0]})
        return sorted(rows, key=lambda x: (-RISK_ORDER.index(x["risk_level"]), x["time"]))

    def summary(self) -> dict:
        dmap = self.decision_map()
        engine = [f["risk_level"] for f in self.state.frames.values()]
        final = [self.frame_final(fid, dmap)["level"] for fid in self.state.frames]
        decided = set(dmap) | {v for v in self.reviews if v in self.state.vehicles}
        statuses = [self.vehicle_final(vid, dmap)["status"] for vid in decided]
        return {
            "frames": len(self.state.frames),
            "frame_risk_counts": {l: final.count(l) for l in RISK_ORDER},
            "engine_frame_risk_counts": {l: engine.count(l) for l in RISK_ORDER},
            "human_review": self.human_review,
            "decisions": {s: statuses.count(s) for s in sorted(set(statuses))},
            "pending_reviews": statuses.count("onay_bekliyor"),
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
