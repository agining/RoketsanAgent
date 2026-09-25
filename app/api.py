"""React arayüzünün bağlanacağı REST API.

Çalıştırma:  uvicorn app.api:app --reload --port 8000
Swagger:     http://localhost:8000/docs
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import RISK_ORDER, settings
from .geo import min_to_hhmm
from .service import service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    service.load()
    yield


app = FastAPI(title="Roketsan Aşama 2 — Saha Raporu Ajanı", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_methods=["*"], allow_headers=["*"],
)


def _frame_or_404(frame_id: str):
    if frame_id not in service.state.frames:
        raise HTTPException(404, f"{frame_id} bulunamadı")


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
    """Riskli araçlar (kare içi + kare dışı izler), önce en yüksek risk."""
    lo = RISK_ORDER.index(min_risk)
    return [a for a in service.alerts() if RISK_ORDER.index(a["risk_level"]) >= lo]


# ------------------------------------------------------------------ kareler
@app.get("/api/frames")
def frames(min_risk: str = Query("DUSUK", enum=RISK_ORDER), zone: str | None = None):
    lo = RISK_ORDER.index(min_risk)
    out = []
    for f in sorted(service.state.frames.values(), key=lambda x: x["capture_time"]):
        if RISK_ORDER.index(f["risk_level"]) < lo or (zone and f["zone"] != zone):
            continue
        out.append({"frame_id": f["frame_id"], "capture_time": f["capture_time"], "zone": f["zone"],
                    "risk_level": f["risk_level"], "counts": f["counts"], "center": f["center"],
                    "dist_to_base_m": f["dist_to_base_m"], "n_vehicles": len(f["vehicle_ids"]),
                    "report_ids": f["report_ids"], "assessed": f["frame_id"] in service.assessments})
    return out


@app.get("/api/frames/{frame_id}")
def frame_detail(frame_id: str, include_tracks: bool = True):
    """Kare + araçlar (bbox, konum, iz, öznitelik, risk) + ilgili raporlar + (varsa) ajan değerlendirmesi."""
    _frame_or_404(frame_id)
    view = service.state.frame_view(frame_id, include_tracks=include_tracks, ds=service.ds)
    view["assessment"] = service.assessments.get(frame_id)
    return view


@app.post("/api/frames/{frame_id}/assess")
async def assess(frame_id: str, force: bool = False):
    """LangChain ajanını çalıştırır (sonuç önbelleğe alınır; force=true yeniden üretir)."""
    _frame_or_404(frame_id)
    return await service.assess(frame_id, force=force)


class AssessAllBody(BaseModel):
    min_risk: str = "DUSUK"
    force: bool = False


@app.post("/api/assess-all")
async def assess_all(body: AssessAllBody):
    lo = RISK_ORDER.index(body.min_risk)
    ids = [f for f, fr in service.state.frames.items() if RISK_ORDER.index(fr["risk_level"]) >= lo]
    res = await service.assess_many(ids, force=body.force)
    return {"assessed": list(res)}


@app.get("/api/assessments")
def assessments():
    return service.assessments


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
    return service.state.vehicle_view(vehicle_id, include_track=True, ds=service.ds)


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


# ------------------------------------------------------------------ yönetim
@app.post("/api/reload")
def reload():
    """Veri dosyaları değiştiğinde (ör. gerçek veri geldi) analizi yeniden çalıştırır. Ajan önbelleği temizlenir."""
    service.load()
    service.assessments = {}
    service._save_cache()
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