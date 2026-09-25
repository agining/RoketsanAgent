"""React arayüzünün bağlanacağı REST API.

Çalıştırma:  uvicorn app.api:app --reload --port 8000
Swagger:     http://localhost:8000/docs

Seviyeler: yanıtlardaki `risk_level` NİHAİ seviyedir (motor + LLM ortak kararı, açıksa analist kararı);
motorun kendi seviyesi `engine_risk_level`, kararın nasıl çıktığı `decision_status` alanındadır:
  motor · uzlasi · llm_yukseltti · fazla_yukseltme · motor_kesin · llm_dusurdu · belirsiz · reddedildi ·
  llm_belirtmedi · onay_bekliyor · analist_karari

"Son söz insanda" özelliği:
  GET  /api/settings                    → {"human_review": bool}
  PUT  /api/settings                    ← {"human_review": true|false}   (arayüzdeki aç/kapa düğmesi)
  GET  /api/reviews?status=pending      → analist onayı bekleyen kararlar (pending | decided | all)
  POST /api/reviews/{vehicle_id}        ← {"level": "ORTA", "analyst": "ad", "note": "..."}
  DELETE /api/reviews/{vehicle_id}      → analist kararını geri al
Özellik kapalıyken karar tablosunun otomatik sonucu uygulanır ve analist kararları yok sayılır (silinmez).
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .config import RISK_ORDER, settings
from .geo import min_to_hhmm
from .service import ReviewError, service
from .steps import pipeline_steps

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    service.load()
    yield


app = FastAPI(title="Roketsan Aşama 2 — Saha Raporu Ajanı", version="1.1", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


def _frame_or_404(frame_id: str):
    if frame_id not in service.state.frames:
        raise HTTPException(404, f"{frame_id} bulunamadı")


def _sse(events: AsyncIterator[dict]) -> StreamingResponse:
    """Olayları Server-Sent Events olarak yollar: her olay `event: <type>` + `data: <json>`."""
    async def gen():
        async for ev in events:
            yield f"event: {ev['type']}\ndata: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ genel
@app.get("/api/health")
def health():
    return {"status": "ok", "llm_enabled": settings.llm_enabled, "detector": service.state.detector}


@app.get("/api/meta")
def meta():
    """Harita kurulumu için: üs, bölgeler, risk sıralaması, eşikler."""
    ds = service.ds
    return {"base": ds.base,
            "zones": [{"name": z.name, "lat": z.lat, "lon": z.lon, "bearing_deg": round(z.bearing, 1),
                       "dist_m": round(z.dist_m)} for z in ds.zones],
            "risk_levels": RISK_ORDER, "thresholds": settings.thresholds.__dict__}


@app.get("/api/summary")
def summary():
    return service.summary()


@app.get("/api/alerts")
def alerts(min_risk: str = Query("ORTA", enum=RISK_ORDER)):
    """Riskli araçlar (kare içi + kare dışı izler), önce en yüksek risk. Seviye nihai seviyedir."""
    lo = RISK_ORDER.index(min_risk)
    return [a for a in service.alerts() if RISK_ORDER.index(a["risk_level"]) >= lo]


# ------------------------------------------------------------------ kareler
@app.get("/api/frames")
def frames(min_risk: str = Query("DUSUK", enum=RISK_ORDER), zone: str | None = None):
    lo = RISK_ORDER.index(min_risk)
    dmap = service.decision_map()
    out = []
    for f in sorted(service.state.frames.values(), key=lambda x: x["capture_time"]):
        ff = service.frame_final(f["frame_id"], dmap)
        if RISK_ORDER.index(ff["level"]) < lo or (zone and f["zone"] != zone):
            continue
        out.append({"frame_id": f["frame_id"], "capture_time": f["capture_time"], "zone": f["zone"],
                    "risk_level": ff["level"], "engine_risk_level": f["risk_level"], "risk_changed": ff["changed"],
                    "pending_reviews": ff["pending_reviews"], "counts": ff["counts"], "center": f["center"],
                    "dist_to_base_m": f["dist_to_base_m"], "n_vehicles": len(f["vehicle_ids"]),
                    "report_ids": f["report_ids"], "assessed": f["frame_id"] in service.assessments})
    return out


@app.get("/api/frames/{frame_id}")
def frame_detail(frame_id: str, include_tracks: bool = True):
    """Kare + araçlar (bbox, konum, iz, öznitelik, risk) + ilgili raporlar + motor adımları + (varsa) ajan değerlendirmesi."""
    _frame_or_404(frame_id)
    view = service.frame_view(frame_id, include_tracks=include_tracks)
    view["pipeline_steps"] = pipeline_steps(service.state, frame_id)
    view["assessment"] = service.present(frame_id, service.assessments.get(frame_id))
    return view


@app.get("/api/frames/{frame_id}/steps")
def frame_steps(frame_id: str):
    """Adım adım görünüm: motorun 4 adımı + (değerlendirildiyse) LLM gerekçe adımları ve ajan izi."""
    _frame_or_404(frame_id)
    a = service.assessments.get(frame_id) or {}
    return {"frame_id": frame_id, "pipeline_steps": pipeline_steps(service.state, frame_id),
            "reasoning_steps": a.get("reasoning_steps", []), "trace": a.get("trace", []),
            "assessed": bool(a)}


@app.post("/api/frames/{frame_id}/assess")
async def assess(frame_id: str, force: bool = False):
    """LangChain ajanını çalıştırır (sonuç önbelleğe alınır; force=true yeniden üretir).
    Yanıtta `reasoning_steps` (LLM gerekçesi) ve `trace` (sıralı ajan adımları) da bulunur."""
    _frame_or_404(frame_id)
    return await service.assess(frame_id, force=force)


@app.get("/api/frames/{frame_id}/assess/stream")
async def assess_stream(frame_id: str, force: bool = False, delay_ms: int = Query(0, ge=0, le=5000)):
    """Ajanı çalıştırıp adımları canlı yollar (SSE). Olay tipleri:
    start · step (motorun 4 adımı) · reasoning · thought · tool_call · tool_result · error · final.
    Önbellekteyse iz yeniden oynatılır; delay_ms>0 demo için adımları aralar. Tarayıcı: EventSource."""
    _frame_or_404(frame_id)
    return _sse(service.assess_stream(frame_id, force=force, delay_ms=delay_ms))


class AssessAllBody(BaseModel):
    min_risk: str = "DUSUK"
    force: bool = False


@app.post("/api/assess-all")
async def assess_all(body: AssessAllBody):
    # Seçim motor seviyesine göre yapılır (değerlendirme öncesi nihai seviye yoktur). Not: LLM yalnızca
    # değerlendirdiği karelerde yükseltme yapabilir; min_risk=ORTA verilirse DUSUK kareler hiç LLM'e gitmez.
    lo = RISK_ORDER.index(body.min_risk)
    ids = [f for f, fr in service.state.frames.items() if RISK_ORDER.index(fr["risk_level"]) >= lo]
    res = await service.assess_many(ids, force=body.force)
    return {"assessed": list(res)}


@app.get("/api/assessments")
def assessments():
    return service.presented_assessments()


@app.get("/api/images/{frame_id}")
def image(frame_id: str):
    """data/images/ altında placeholder kare varsa servis eder (README: UI geliştirmesi için)."""
    img_dir = settings.data_dir / "images"
    for ext in ("png", "jpg", "jpeg"):
        p = img_dir / f"{frame_id}.{ext}"
        if p.exists():
            return FileResponse(p)
    raise HTTPException(404, "görüntü yok")


# ------------------------------------------------------------------ araçlar & izler
@app.get("/api/vehicles/{vehicle_id}")
def vehicle(vehicle_id: str):
    if vehicle_id not in service.state.vehicles:
        raise HTTPException(404, f"{vehicle_id} bulunamadı")
    return service.with_final_level(service.state.vehicle_view(vehicle_id, include_track=True, ds=service.ds))


@app.get("/api/tracks/{track_id}")
def track(track_id: str):
    tr = service.ds.tracks.get(track_id)
    if not tr:
        raise HTTPException(404, f"{track_id} bulunamadı")
    linked = [v["vehicle_id"] for v in service.state.vehicles.values() if v["track_id"] == track_id]
    return {"track_id": track_id, "vehicle_ids": linked,
            "offframe": service.state.offframe_risk.get(track_id),
            "points": [{"time": min_to_hhmm(p.t), "lat": p.lat, "lon": p.lon,
                        "dist_to_base_m": round(service.ds.dist_to_base(p.lat, p.lon), 1)} for p in tr.points]}


# ------------------------------------------------------------------ raporlar
@app.get("/api/reports")
def reports(verdict: str | None = None, frame_id: str | None = None):
    rs = service.state.reports
    if verdict:
        rs = [r for r in rs if r["verdict"] == verdict]
    if frame_id:
        rs = [r for r in rs if frame_id in r["related_frames"]]
    return rs


@app.get("/api/reports/{report_id}")
def report(report_id: str):
    for r in service.state.reports:
        if r["report_id"] == report_id:
            return r
    raise HTTPException(404, f"{report_id} bulunamadı")


# ------------------------------------------------------------------ "son söz insanda"
class SettingsBody(BaseModel):
    human_review: bool


@app.get("/api/settings")
def get_settings():
    return service.runtime_settings()


@app.put("/api/settings")
def put_settings(body: SettingsBody):
    """Arayüzdeki aç/kapa düğmesi. Değişiklik anında geçerli olur; LLM yeniden çalışmaz."""
    return {**service.set_human_review(body.human_review), "pending_reviews": service.summary()["pending_reviews"]}


@app.get("/api/reviews")
def reviews_list(status: str = Query("pending", enum=["pending", "decided", "all"]), frame_id: str | None = None):
    """Analist onayı bekleyen (ya da karar verilmiş) araçlar: motorun ve LLM'in gerekçeleri yan yana, seçenekler."""
    return service.list_reviews(status=status, frame_id=frame_id)


class ReviewBody(BaseModel):
    level: str
    analyst: str | None = None
    note: str | None = None


@app.post("/api/reviews/{vehicle_id}")
def review_decide(vehicle_id: str, body: ReviewBody):
    """Analist kararı: bu araç için nihai seviye. Sadece insan onayı açıkken kabul edilir (kapalıysa 409)."""
    try:
        return service.set_review(vehicle_id, body.level, body.analyst, body.note)
    except ReviewError as e:
        raise HTTPException(e.status, str(e))


@app.delete("/api/reviews/{vehicle_id}")
def review_undo(vehicle_id: str):
    try:
        return service.delete_review(vehicle_id)
    except ReviewError as e:
        raise HTTPException(e.status, str(e))


# ------------------------------------------------------------------ sohbet
class ChatBody(BaseModel):
    message: str
    thread_id: str | None = None
    frame_id: str | None = None


@app.post("/api/chat")
async def chat(body: ChatBody):
    if service.agent is None:
        raise HTTPException(503, "LLM devre dışı (OPENAI_API_KEY tanımlı değil)")
    return await service.agent.chat(body.message, body.thread_id, body.frame_id)


@app.post("/api/chat/stream")
async def chat_stream(body: ChatBody):
    """Sohbet yanıtını adım adım yollar (SSE; POST olduğu için tarayıcıda fetch + ReadableStream)."""
    if service.agent is None:
        raise HTTPException(503, "LLM devre dışı (OPENAI_API_KEY tanımlı değil)")
    return _sse(service.agent.chat_stream(body.message, body.thread_id, body.frame_id))


# ------------------------------------------------------------------ yönetim
@app.post("/api/reload")
def reload():
    """Veri dosyaları değiştiğinde (ör. gerçek veri geldi) analizi yeniden çalıştırır.
    Ajan önbelleği ve analist kararları temizlenir; insan onayı ayarı korunur."""
    service.load()
    service.clear()
    return service.summary()


@app.get("/api/tracking-data", tags=["Tracking"])
def tracking_data():
    ds = service.ds

    return {
        "base": ds.base,
        "zones": [
            {
                "name": z.name,
                "center": [z.lat, z.lon],
            }
            for z in ds.zones
        ],
        "tracks": [
            {
                "id": track_id,
                "points": [
                    {
                        "time": min_to_hhmm(p.t),
                        "lat": p.lat,
                        "lon": p.lon,
                    }
                    for p in track.points
                ],
            }
            for track_id, track in ds.tracks.items()
        ],
    }