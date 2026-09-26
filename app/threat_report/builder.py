"""Tehdit raporu hattı:  kareleri değerlendir → olguları topla → anlatım (LLM/önbellek/şablon) → grafikler → PDF.

    data = await build_threat_report(service, ReportOptions(min_risk="YUKSEK"))

Çıktılar outputs/reports/ altında: <rapor_no>.pdf ve aynı adla .json (olgular + anlatımlar; React arayüzü
aynı içeriği buradan gösterebilir). Aynı süreçte iki rapor aynı anda üretilmez (kilit).
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from pathlib import Path

from ..config import RISK_ORDER, settings
from . import charts
from .collect import ReportOptions, collect_report_data
from .narrative import PROMPT_VERSION, NarrativeWriter
from .pdf import render_pdf

log = logging.getLogger("roketsan.report")
_ASYNC_LOCK: asyncio.Lock | None = None
_CHART_LOCK = threading.Lock()          # pyplot iş parçacığı güvenli değil


def reports_dir() -> Path:
    return settings.output_dir / "reports"


def narrative_cache_path() -> Path:
    return settings.output_dir / "report_narratives.json"


def _frames_to_assess(svc, opts: ReportOptions) -> list[str]:
    st = svc.state
    if opts.assess_scope == "none":
        return []
    if opts.assess_scope == "min_risk":
        lo = min(RISK_ORDER.index(lv) for lv in opts.selected_levels())
        return [fid for fid, fr in st.frames.items() if RISK_ORDER.index(fr["risk_level"]) >= lo]
    return list(st.frames)                      # "all": tüm görseller


def _resolve_llm(svc, opts: ReportOptions, llm):
    if not opts.use_llm:
        return None
    if llm is not None:
        return llm
    if svc.agent is not None:
        return svc.agent.llm
    if settings.llm_enabled:
        from ..agent import build_llm
        return build_llm()
    return None


def _render_charts(data: dict) -> dict:
    th, images = settings.thresholds, settings.data_dir / "images"
    out = {"overview_png": None, "frame_png": {}, "path_png": {}, "ts_png": {}}
    with _CHART_LOCK:
        out["overview_png"] = charts.overview_map(data)
        for f in data["vehicles"]:
            out["path_png"][f["key"]] = charts.vehicle_path(f, data["meta"])
            if f["track"]:
                out["ts_png"][f["key"]] = charts.vehicle_timeseries(f, th)
            if f.get("frame"):
                out["frame_png"][f["key"]] = charts.frame_view(f, images)
    return out


def _source_tag(vn: dict, model: str | None) -> str:
    return {"llm": f"LLM ({model})", "cache": f"LLM önbelleği ({model})",
            "template": "deterministik şablon (LLM yok)"}.get(vn["source"], vn["source"])


def _source_text(stats: dict, model: str | None) -> str:
    if not model:
        return "Deterministik şablon — LLM bağlı değil; metinler yalnızca olgulardan üretildi"
    s = f"LLM ({model}) · yeni {stats['llm']} · önbellekten {stats['cache']}"
    if stats["template"]:
        s += f" · şablona düşen {stats['template']}"
    return s


async def build_threat_report(svc, opts: ReportOptions | None = None, llm=None, out_dir: Path | None = None) -> dict:
    global _ASYNC_LOCK
    opts = opts or ReportOptions()
    opts.selected_levels()                      # geçersiz filtreyi erken reddet
    if _ASYNC_LOCK is None:
        _ASYNC_LOCK = asyncio.Lock()
    async with _ASYNC_LOCK:
        t0 = time.time()
        # 1) "tüm görselleri analiz ettikten sonra": değerlendirilmemiş kareler ajandan geçer (önbellekli)
        ids = _frames_to_assess(svc, opts)
        if ids:
            await svc.assess_many(ids)
        # 2) olgular (nihai seviyeler o anki insan onayı ayarı ve analist kararlarıyla)
        data = collect_report_data(svc, opts)
        # 3) anlatım
        model_llm = _resolve_llm(svc, opts, llm)
        writer = NarrativeWriter(model_llm, cache_path=narrative_cache_path(), force=opts.force_llm)
        vs = data["vehicles"]
        results = await asyncio.gather(*(writer.vehicle(f, data["meta"]) for f in vs))
        vnarr = {f["key"]: r for f, r in zip(vs, results)}
        executive = await writer.executive(data, {k: v["narrative"] for k, v in vnarr.items()})
        writer.flush()
        # 4) grafikler + 5) PDF (CPU işi; olay döngüsünü bloklamasın)
        pngs = await asyncio.to_thread(_render_charts, data)
        model = writer.model_name if model_llm is not None else None
        all_notes = executive["notes"] + [f"#{f['index']} {f['track_id'] or f['vehicle_id']}: {n}"
                                          for f in vs for n in vnarr[f["key"]]["notes"]]
        ctx = {**pngs, "vehicle_narr": vnarr, "executive": executive, "thresholds": settings.thresholds,
               "narrative_stats": writer.stats, "narrative_model": model, "prompt_version": PROMPT_VERSION,
               "source_tag": lambda vn: _source_tag(vn, model), "narrative_source_text": _source_text(writer.stats, model),
               "all_notes": all_notes, "elapsed_s": 0.0}
        out_dir = out_dir or reports_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        rid = data["meta"]["report_id"]
        pdf_path, json_path = out_dir / f"{rid}.pdf", out_dir / f"{rid}.json"
        ctx["elapsed_s"] = time.time() - t0
        pages = await asyncio.to_thread(render_pdf, pdf_path, data, ctx)
        elapsed = time.time() - t0
        summary = {
            "report_id": rid, "pdf_path": str(pdf_path), "json_path": str(json_path), "pages": pages,
            "generated_at": data["meta"]["generated_at_iso"], "filter_label": data["meta"]["filter_label"],
            "levels": data["meta"]["levels"], "vehicle_count": len(vs), "counts": data["counts"],
            "human_review": data["meta"]["human_review"], "pending_reviews": data["reviews"]["pending_count"],
            "frames_assessed": data["meta"]["frames_assessed"], "frames_llm": data["meta"]["frames_llm"],
            "narrative_model": model, "narrative_stats": writer.stats, "facts_digest": data["meta"]["facts_digest"],
            "elapsed_s": round(elapsed, 2),
            "vehicles": [{"index": f["index"], "key": f["key"], "vehicle_id": f["vehicle_id"], "track_id": f["track_id"],
                          "final_level": f["final_level"], "engine_level": f["engine_level"], "status": f["status"],
                          "headline": vnarr[f["key"]]["narrative"]["headline"]} for f in vs],
        }
        sidecar = {"summary": summary, "data": _strip_points(data), "executive": executive,
                   "vehicle_narratives": vnarr}
        json_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        log.info("Tehdit raporu hazır: %s (%d araç, %d sayfa, %.1fs)", pdf_path, len(vs), pages, elapsed)
        return summary


def _strip_points(data: dict) -> dict:
    """JSON ekinde iz noktaları kalsın (arayüz haritası için) ama olası iz nokta kopyaları çıkarılsın."""
    out = dict(data)
    out["vehicles"] = []
    for f in data["vehicles"]:
        g = dict(f)
        if g.get("nearest_track"):
            g["nearest_track"] = {k: v for k, v in g["nearest_track"].items() if k != "points"}
        out["vehicles"].append(g)
    return out


def list_reports() -> list[dict]:
    d = reports_dir()
    if not d.exists():
        return []
    rows = []
    for p in sorted(d.glob("TR-*.json"), reverse=True):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))["summary"]
        except (json.JSONDecodeError, KeyError):
            continue
        s = {k: v for k, v in s.items() if k != "vehicles"}
        s["pdf_exists"] = (d / f"{s['report_id']}.pdf").exists()
        rows.append(s)
    return rows
