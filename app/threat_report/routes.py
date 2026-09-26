"""Tehdit raporu REST uçları (api.py'ye `app.include_router(router)` ile bağlanır).

  POST /api/threat-report                 ← {"min_risk":"YUKSEK"} | {"levels":["KRITIK"]} ...  → özet + indirme adresleri
  GET  /api/threat-report/download?min_risk=KRITIK   → raporu üretip PDF'i doğrudan döndürür (tarayıcı bağlantısı)
  GET  /api/threat-report/preview?min_risk=ORTA      → LLM/PDF olmadan rapora girecek araçlar (arayüz ön izleme)
  GET  /api/threat-report                 → üretilmiş raporların listesi
  GET  /api/threat-report/{rapor_no}      → rapor JSON'u (olgular + anlatımlar)  · rapor_no=latest en sonuncusu
  GET  /api/threat-report/{rapor_no}/pdf  → PDF dosyası
Seviyeler NİHAİ seviyedir: insan onayı açıksa analist kararları ve bekleyen onaylar rapora aynen yansır.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .builder import build_threat_report, list_reports, reports_dir
from .collect import ReportOptions, collect_report_data

Level = Literal["DUSUK", "ORTA", "YUKSEK", "KRITIK"]
Scope = Literal["all", "min_risk", "none"]
_ID_RE = re.compile(r"^TR-\d{8}-\d{6}-[A-Za-z0-9_-]+$")

router = APIRouter(prefix="/api/threat-report", tags=["Tehdit raporu (PDF)"])


class ReportRequest(BaseModel):
    min_risk: Level = Field("ORTA", description="Bu seviye ve üstündeki araçlar (levels verilmezse)")
    levels: list[Level] | None = Field(None, description="Yalnızca bu seviyeler, ör. [\"KRITIK\"]")
    include_offframe: bool = Field(True, description="Hiçbir karede görünmeyen riskli izler de dahil")
    assess_scope: Scope = Field("all", description="all: tüm kareler LLM'den geçer · min_risk · none: önbellek")
    force_llm: bool = Field(False, description="Anlatım önbelleğini yok say, metinleri yeniden üret")
    use_llm: bool = Field(True, description="False → LLM bağlı olsa da deterministik şablon metin")
    prepared_by: str | None = Field(None, description="Kapakta 'Hazırlayan' alanı")

    def options(self) -> ReportOptions:
        return ReportOptions(min_risk=self.min_risk, levels=self.levels, include_offframe=self.include_offframe,
                             assess_scope=self.assess_scope, force_llm=self.force_llm, use_llm=self.use_llm,
                             prepared_by=self.prepared_by)


def _svc():
    from ..service import service
    if service.state is None:
        raise HTTPException(503, "Servis henüz yüklenmedi")
    return service


def _urls(rid: str) -> dict:
    return {"pdf_url": f"/api/threat-report/{rid}/pdf", "json_url": f"/api/threat-report/{rid}"}


def _resolve(report_id: str) -> str:
    if report_id == "latest":
        rows = list_reports()
        if not rows:
            raise HTTPException(404, "Henüz rapor üretilmedi")
        return rows[0]["report_id"]
    if not _ID_RE.match(report_id):
        raise HTTPException(400, "Geçersiz rapor numarası")
    return report_id


@router.post("")
async def create_report(body: ReportRequest):
    """Tüm kareleri (assess_scope) değerlendirir, seçilen seviyedeki araçlar için LLM açıklamalı PDF üretir."""
    s = await build_threat_report(_svc(), body.options())
    return {**{k: v for k, v in s.items() if k not in ("pdf_path", "json_path")}, **_urls(s["report_id"])}


@router.get("/download")
async def download_report(min_risk: Level = "ORTA", levels: list[Level] | None = Query(None),
                          assess_scope: Scope = "all", include_offframe: bool = True, use_llm: bool = True,
                          prepared_by: str | None = None):
    """Raporu üretir ve PDF'i doğrudan döndürür (tarayıcıda açılır)."""
    s = await build_threat_report(_svc(), ReportOptions(min_risk=min_risk, levels=levels, assess_scope=assess_scope,
                                                        include_offframe=include_offframe, use_llm=use_llm,
                                                        prepared_by=prepared_by))
    return FileResponse(s["pdf_path"], media_type="application/pdf", filename=f"{s['report_id']}.pdf",
                        content_disposition_type="inline")


@router.get("/preview")
def preview_report(min_risk: Level = "ORTA", levels: list[Level] | None = Query(None), include_offframe: bool = True):
    """Rapora girecek araçlar (şu anki değerlendirme ve analist kararlarıyla). LLM çağrısı ve PDF yok."""
    d = collect_report_data(_svc(), ReportOptions(min_risk=min_risk, levels=levels, include_offframe=include_offframe))
    return {"meta": {k: d["meta"][k] for k in ("filter_label", "levels", "human_review", "frames_assessed",
                                               "frames_total", "frames_llm", "facts_digest")},
            "counts": d["counts"], "pending_reviews": d["reviews"]["pending_count"],
            "vehicles": [{"index": f["index"], "key": f["key"], "vehicle_id": f["vehicle_id"], "track_id": f["track_id"],
                          "frame_id": f["frame_id"], "label": f["label"], "zone": f["zone"],
                          "final_level": f["final_level"], "engine_level": f["engine_level"], "status": f["status"],
                          "scenario": f["scenario"], "dist_to_base_m": f["dist_to_base_m"],
                          "eta_min": (f.get("features") or {}).get("eta_min")} for f in d["vehicles"]]}


@router.get("")
def reports_index():
    return [{**r, **_urls(r["report_id"])} for r in list_reports()]


@router.get("/{report_id}")
def report_json(report_id: str):
    rid = _resolve(report_id)
    p = reports_dir() / f"{rid}.json"
    if not p.exists():
        raise HTTPException(404, f"{rid} bulunamadı")
    return {**json.loads(p.read_text(encoding="utf-8")), **_urls(rid)}


@router.get("/{report_id}/pdf")
def report_pdf(report_id: str):
    rid = _resolve(report_id)
    p = reports_dir() / f"{rid}.pdf"
    if not p.exists():
        raise HTTPException(404, f"{rid} bulunamadı")
    return FileResponse(p, media_type="application/pdf", filename=f"{rid}.pdf", content_disposition_type="inline")
