"""Adım adım izlenebilirlik.

İki katman üretir; React ikisini de "adım kartı" olarak gösterebilir:

  pipeline_steps(state, frame_id)
      Brief'teki 4 adımın (Tespit → Konumlandırma → Hareket analizi → Risk analizi) deterministik
      çıktısı. LLM olmadan da vardır, her çağrıda aynıdır, anında döner.

  TraceBuilder / agent_trace(messages)
      LLM ajanının o kareyi incelerken attığı adımlar, sırasıyla:
        reasoning   → modelin kendi düşünme metni (GLM `reasoning_content`, OpenAI reasoning özeti)
        thought     → modelin araç çağırmadan önce yazdığı kısa gerekçe cümlesi
        tool_call   → hangi araç, hangi argüman, brief'in hangi adımına denk düşüyor
        tool_result → aracın döndürdüğü verinin tek satır özeti + kısaltılmış ham JSON
        answer      → (sohbet) araç çağırmadan yazılan nihai yanıt
"""
from __future__ import annotations

import json
import time
from collections import Counter
from typing import Any, Iterable

# Brief'teki adım anahtarları (UI bu sırayla sütun/kart çizer)
STAGE_ORDER = ["tespit", "konumlandirma", "hareket", "risk"]
STAGE_TITLES = {"tespit": "Tespit", "konumlandirma": "Konumlandırma", "hareket": "Hareket analizi",
                "risk": "Risk analizi"}

# araç → (brief adımı, kartta görünecek başlık)
TOOL_STAGE = {
    "list_frames": ("risk", "Genel bakış"),
    "get_frame_analysis": ("tespit", "Kare analizi (tespit + konum)"),
    "get_zone_overview": ("konumlandirma", "Bölge bağlamı"),
    "get_vehicle_details": ("hareket", "Araç öznitelikleri"),
    "get_track_timeline": ("hareket", "İz zaman çizelgesi"),
    "get_reports_for_frame": ("risk", "Rapor doğrulama"),
    "get_report": ("risk", "Rapor doğrulama"),
    "list_reports": ("risk", "Rapor doğrulama"),
    "get_offframe_alerts": ("risk", "Kare dışı tehditler"),
    "get_risk_policy": ("risk", "Risk kuralları"),
}
STRUCTURED_TOOLS = {"FrameAssessment"}   # yapılandırılmış çıktı "aracı" — iz değil, sonuçtur
PREVIEW_CHARS = 1500


# ====================================================================== 1) deterministik adımlar
def _step(n: int, key: str, summary: str, data: dict) -> dict:
    return {"step": n, "key": key, "title": STAGE_TITLES[key], "summary": summary, "data": data}


def pipeline_steps(state, frame_id: str) -> list[dict]:
    fr = state.frames[frame_id]
    vs = [state.vehicles[v] for v in fr["vehicle_ids"]]
    det = [v for v in vs if v["source"] == "detection"]
    kept = [v for v in det if not v["filtered"]]
    dups = [v for v in det if v["scenario"] == "DUPLICATE_BOX"]
    filt = [v for v in det if v["filtered"] and v["scenario"] != "DUPLICATE_BOX"]
    lowc = [v for v in kept if v.get("low_conf_corroborated")]
    missed = [v for v in vs if v["source"] == "track_only"]
    active = [v for v in vs if not v["filtered"]]

    # ---- 01 Tespit
    by_label = Counter(v["label"] for v in kept)
    s1 = f"{len(det)} kutu → {len(kept)} araç kabul"
    if dups:
        s1 += f", {len(dups)} kopya kutu birleştirildi"
    if lowc:
        s1 += f", {len(lowc)} düşük güvenli kutu izle doğrulanıp kabul edildi"
    if filt:
        s1 += f", {len(filt)} düşük güvenli kutu elendi"
    if missed:
        s1 += f", {len(missed)} araç izden kurtarıldı (model kaçırmış)"
    step1 = _step(1, "tespit", s1, {
        "detector": state.detector,
        "by_label": dict(by_label),
        "detections": [{"vehicle_id": v["vehicle_id"], "label": v["label"], "confidence": v["confidence"],
                        "bbox": v["bbox"], "filtered": v["filtered"], "duplicate_of": v.get("duplicate_of"),
                        "alt_labels": v.get("alt_labels") or [],
                        "low_conf_corroborated": v.get("low_conf_corroborated", False)} for v in det],
        "missed_from_tracks": [{"vehicle_id": v["vehicle_id"], "track_id": v["track_id"]} for v in missed],
    })

    # ---- 02 Konumlandırma
    nearest = min(active, key=lambda v: v["dist_to_base_m"], default=None)
    s2 = f"Kare {fr['zone']} bölgesinde, merkezi üsse {fr['dist_to_base_m'] / 1000:.1f} km"
    if nearest:
        s2 += f"; üsse en yakın araç {nearest['vehicle_id']} ({nearest['dist_to_base_m']:.0f} m)"
    step2 = _step(2, "konumlandirma", s2, {
        "corner_coordinates": fr["meta"]["corner_coordinates"],
        "size_px": [fr["meta"]["width_px"], fr["meta"]["height_px"]],
        "vehicles": [{"vehicle_id": v["vehicle_id"], "lat": v["lat"], "lon": v["lon"], "zone": v["zone"],
                      "dist_to_base_m": v["dist_to_base_m"], "bearing_from_base_deg": v.get("bearing_from_base_deg")}
                     for v in active],
    })

    # ---- 03 Hareket analizi
    tracked = [v for v in active if v["track_id"]]
    rows = []
    for v in tracked:
        f = v.get("features") or {}
        rows.append({"vehicle_id": v["vehicle_id"], "track_id": v["track_id"], "track_match_m": v["track_match_m"],
                     **{k: f.get(k) for k in ("speed_now_mps", "heading_offset_deg", "approach_last60_m", "eta_min",
                                              "stops_last60", "dist_trend")}})
    s3 = f"{len(tracked)}/{len(active)} araç bir hareket kaydına eşlendi"
    approaching = [r for r in rows if (r.get("approach_last60_m") or 0) > 0]
    if approaching:
        top = max(approaching, key=lambda r: r["approach_last60_m"])
        s3 += f"; en hızlı yaklaşan {top['track_id']} (60 dk'da {top['approach_last60_m']:.0f} m"
        s3 += f", ETA ~{top['eta_min']:.0f} dk)" if top.get("eta_min") is not None else ")"
    step3 = _step(3, "hareket", s3, {"tracks": rows})

    # ---- 04 Risk analizi (saha raporları + motor seviyesi)
    reps = [r for r in state.reports if frame_id in r["related_frames"]]
    verdicts = Counter(r["verdict"] for r in reps)
    s4 = f"Kare riski {fr['risk_level']}"
    top_v = state.vehicles.get(fr.get("top_vehicle_id")) if fr.get("top_vehicle_id") else None
    if top_v and top_v["risk_level"] != "DUSUK":
        s4 += f" — {top_v['track_id'] or top_v['vehicle_id']}: {top_v['scenario']}"
    if reps:
        s4 += "; raporlar: " + ", ".join(f"{n} {k}" for k, n in verdicts.items())
    step4 = _step(4, "risk", s4, {
        "frame_risk": fr["risk_level"],
        "vehicles": [{"vehicle_id": v["vehicle_id"], "risk_level": v["risk_level"], "scenario": v["scenario"],
                      "reasons": v["risk_reasons"]} for v in active],
        "reports": [{"report_id": r["report_id"], "time": r["time"], "source": r["source"], "verdict": r["verdict"],
                     "summary": r["summary"], "injection_detected": r["injection_detected"]} for r in reps],
    })
    return [step1, step2, step3, step4]


def steps_as_reasoning(steps: list[dict]) -> list[dict]:
    """LLM reasoning_steps üretmezse (veya LLM kapalıysa) motor adımlarından doldurur."""
    return [{"stage": s["key"], "finding": s["summary"], "evidence": [], "added_by_guardrail": True} for s in steps]


# ====================================================================== 2) ajan izi
def _loads(content: Any) -> Any:
    if isinstance(content, (dict, list)):
        return content
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return None


def summarize_tool_result(tool: str, obj: Any, raw: str = "") -> str:
    """Araç çıktısının analiste gösterilecek tek satırlık özeti (deterministik, LLM'siz)."""
    if isinstance(obj, dict) and "error" in obj:
        return f"Hata: {obj['error']}"
    try:
        if tool == "get_frame_analysis":
            return (f"{obj['frame_id']} ({obj['capture_time']}, {obj['zone']}): {len(obj['vehicles'])} araç, "
                    f"kare riski {obj['risk_level']}, {len(obj['report_ids'])} ilişkili rapor")
        if tool == "get_vehicle_details":
            s = f"{obj['vehicle_id']}: {obj['risk_level']} ({obj['scenario']}), üsse {obj['dist_to_base_m']:.0f} m"
            eta = (obj.get("features") or {}).get("eta_min")
            return s + (f", ETA ~{eta:.0f} dk" if eta is not None else "")
        if tool == "get_track_timeline":
            tl = obj["timeline"]
            if tl:
                return (f"{obj['track_id']}: {len(tl)} nokta, üsse mesafe {tl[0]['dist_to_base_m']} m → "
                        f"{tl[-1]['dist_to_base_m']} m ({tl[0]['time']}–{tl[-1]['time']})")
            return f"{obj['track_id']}: nokta yok"
        if tool in ("get_reports_for_frame", "list_reports"):
            key = "engine_verdict" if tool == "get_reports_for_frame" else "verdict"
            c = Counter(r.get(key) for r in obj)
            inj = sum(1 for r in obj if r.get("injection_detected"))
            s = f"{len(obj)} rapor" + (": " + ", ".join(f"{n} {k}" for k, n in c.items()) if obj else "")
            return s + (f" — {inj} raporda talimat enjeksiyonu" if inj else "")
        if tool == "get_report":
            return f"{obj['report_id']} ({obj['time']}, {obj['source']}): motor hükmü {obj['engine_verdict']}"
        if tool == "list_frames":
            return f"{len(obj)} kare listelendi"
        if tool == "get_zone_overview":
            return f"{obj['zone']}: {len(obj['frames'])} kare, {len(obj['non_low_vehicles'])} riskli araç"
        if tool == "get_offframe_alerts":
            return f"{len(obj)} kare dışı riskli iz"
        if tool == "get_risk_policy":
            return "Risk motorunun senaryo tanımları ve eşikleri okundu"
    except (KeyError, TypeError, IndexError, ValueError):
        pass
    return (raw[:140] + "…") if len(raw) > 140 else raw


def _ai_texts(m) -> tuple[list[str], list[str]]:
    """AIMessage → (reasoning metinleri, görünür metinler). Sağlayıcıdan bağımsız."""
    reasoning, texts = [], []
    rc = (getattr(m, "additional_kwargs", None) or {}).get("reasoning_content")
    if rc:
        reasoning.append(rc)
    try:
        blocks = m.content_blocks            # langchain-core 1.x standart blokları
    except Exception:
        blocks = [{"type": "text", "text": m.content}] if isinstance(m.content, str) else []
    for b in blocks:
        if b.get("type") == "reasoning" and b.get("reasoning") and b["reasoning"] not in reasoning:
            reasoning.append(b["reasoning"])
        elif b.get("type") == "text" and (b.get("text") or "").strip():
            texts.append(b["text"].strip())
    return reasoning, texts


class TraceBuilder:
    """Mesajları geldikçe olaylara çevirir. Hem toplu (ainvoke sonrası) hem akış (astream) için."""

    def __init__(self):
        self.t0 = time.monotonic()
        self.events: list[dict] = []
        self._tool_names: dict[str, str] = {}

    def _emit(self, ev: dict) -> dict:
        ev = {"seq": len(self.events) + 1, "t_ms": round((time.monotonic() - self.t0) * 1000), **ev}
        self.events.append(ev)
        return ev

    def add(self, messages: Iterable) -> list[dict]:
        out = []
        for m in messages:
            if m.type == "ai":
                reasoning, texts = _ai_texts(m)
                for r in reasoning:
                    out.append(self._emit({"type": "reasoning", "text": r}))
                # araç çağrısıyla gelen metin = ara gerekçe; araçsız metin = nihai yanıt (sohbet modu)
                kind = "thought" if m.tool_calls else "answer"
                for t in texts:
                    out.append(self._emit({"type": kind, "text": t}))
                for tc in m.tool_calls or []:
                    self._tool_names[tc["id"]] = tc["name"]
                    if tc["name"] in STRUCTURED_TOOLS:
                        continue
                    stage, title = TOOL_STAGE.get(tc["name"], ("risk", tc["name"]))
                    out.append(self._emit({"type": "tool_call", "call_id": tc["id"], "tool": tc["name"],
                                           "args": tc["args"], "stage": stage, "title": title}))
            elif m.type == "tool":
                name = m.name or self._tool_names.get(m.tool_call_id, "")
                if name in STRUCTURED_TOOLS:
                    continue
                raw = m.content if isinstance(m.content, str) else json.dumps(m.content, ensure_ascii=False)
                obj = _loads(raw)
                stage, title = TOOL_STAGE.get(name, ("risk", name))
                out.append(self._emit({
                    "type": "tool_result", "call_id": m.tool_call_id, "tool": name, "stage": stage, "title": title,
                    "status": "error" if (isinstance(obj, dict) and "error" in obj) or m.status == "error" else "ok",
                    "summary": summarize_tool_result(name, obj, raw),
                    "preview": raw[:PREVIEW_CHARS] + ("…" if len(raw) > PREVIEW_CHARS else ""),
                }))
        return out


def agent_trace(messages) -> list[dict]:
    tb = TraceBuilder()
    tb.add(messages)
    for ev in tb.events:        # toplu modda zaman bilgisi anlamsız
        ev["t_ms"] = None
    return tb.events
