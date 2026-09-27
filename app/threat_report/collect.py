"""Rapor verisi: şüpheli araçların OLGULARI.

Buradaki sözlükler raporun tek doğruluk kaynağıdır — PDF tabloları, grafikler, LLM'e giden olgular ve LLM
yokken yazılan şablon metin hepsi aynı veriden üretilir. Seviyeler service.vehicle_final'den gelir; yani
insan onayı açıksa analist kararı, değilse fusion sonrası doğrulanmış otomatik sonuç raporda aynen görünür.
Bu modül hiçbir şeyi değiştirmez (motor durumu, değerlendirmeler, analist kararları salt okunur).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from ..agent import RULE_LABELS
from ..config import RISK_ORDER, settings
from ..geo import haversine_m, min_to_hhmm, to_local_xy
from ..risk import classify_tracked, explain_tracked, explain_untracked, is_bus
from ..tracking import TrackFeatures, compute_features
from .theme import (REPORT_TZ, RISK_LABELS, THEME_VERSION, risk_label, scenario_label, status_label)


@dataclass
class ReportOptions:
    min_risk: str = "ORTA"                 # bu seviye ve üstü (levels verilmezse)
    levels: list[str] | None = None        # yalnızca bu seviyeler (ör. ["KRITIK"])
    include_offframe: bool = True          # hiçbir kareye bağlanmayan riskli izler
    assess_scope: str = "all"              # all: tüm kareler ilk LLM + fusion'dan geçer · min_risk: motor ≥ min_risk · none
    force_llm: bool = False                # anlatım önbelleğini yok say (kare değerlendirmeleri korunur)
    use_llm: bool = True                   # False → LLM anahtarı olsa da şablon anlatım
    prepared_by: str | None = None

    def selected_levels(self) -> list[str]:
        if self.levels:
            bad = [lv for lv in self.levels if lv not in RISK_ORDER]
            if bad:
                raise ValueError(f"Geçersiz seviye: {bad}. Seçenekler: {RISK_ORDER}")
            return [lv for lv in RISK_ORDER if lv in self.levels]
        if self.min_risk not in RISK_ORDER:
            raise ValueError(f"Geçersiz min_risk: {self.min_risk}. Seçenekler: {RISK_ORDER}")
        return RISK_ORDER[RISK_ORDER.index(self.min_risk):]

    def filter_label(self) -> str:
        lv = self.selected_levels()
        if self.levels:
            return "Yalnızca " + ", ".join(risk_label(x) for x in lv)
        return f"{risk_label(self.min_risk)} ve üstü"

    def filter_key(self) -> str:
        return "-".join(self.selected_levels()) if self.levels else f"min{self.min_risk}"


# ------------------------------------------------------------------ yardımcılar
def _tz():
    try:
        return ZoneInfo(REPORT_TZ)
    except Exception:  # tz verisi yoksa yerel saat
        return None


def fmt_ts(ts: float | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, _tz()).strftime("%d.%m.%Y %H:%M")


def _r(v, nd=1):
    return None if v is None else round(float(v), nd)


def stable_digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def _local_km(ds, lat, lon) -> tuple[float, float]:
    x, y = to_local_xy(lat, lon, ds.base["lat"], ds.base["lon"])
    return round(x / 1000, 4), round(y / 1000, 4)


def _track_points(ds, tr) -> list[dict]:
    out, prev = [], None
    for p in tr.points:
        x, y = _local_km(ds, p.lat, p.lon)
        spd = (haversine_m(prev.lat, prev.lon, p.lat, p.lon) / max((p.t - prev.t) * 60, 1)) if prev else None
        out.append({"t": p.t, "time": min_to_hhmm(p.t), "lat": round(p.lat, 6), "lon": round(p.lon, 6),
                    "x_km": x, "y_km": y, "dist_m": round(ds.dist_to_base(p.lat, p.lon), 1),
                    "speed_mps": _r(spd)})
        prev = p
    return out


def _frame_footprint(ds, meta) -> list[list[float]]:
    c = meta["corner_coordinates"]
    return [list(_local_km(ds, *c[k])) for k in ("top_left", "top_right", "bottom_right", "bottom_left")]


def _features_obj(ds, th, tid: str, t_ref: int) -> TrackFeatures:
    return compute_features(ds.tracks[tid], ds, th, t_ref)


def _nearest_track(svc, lat, lon, t_cap) -> dict | None:
    """İzsiz araç için: çekim anında en yakın iz (neden eşleşmediğini açıklamak için)."""
    best = None
    for tid, tr in svc.ds.tracks.items():
        pos = tr.position_at(t_cap)
        if pos:
            d = haversine_m(lat, lon, *pos)
            if best is None or d < best[1]:
                best = (tid, d)
    if not best:
        return None
    th = settings.thresholds
    holder = next((v["vehicle_id"] for v in svc.state.vehicles.values() if v["track_id"] == best[0]), None)
    out = {"track_id": best[0], "dist_m": round(best[1], 1), "assigned_to": holder,
           "match_radius_m": th.match_radius_m, "hypothesis": None}
    # İz yakınsa (≤ 2× eşleştirme yarıçapı) "bu araç o iz olsaydı" motor ne derdi — yalnızca bilgi amaçlı,
    # nihai seviyeyi DEĞİŞTİRMEZ. Tipik neden: iz daha önceki bir kareye atanmış (bire bir eşleştirme).
    if best[1] <= 2 * th.match_radius_m:
        f = compute_features(svc.ds.tracks[best[0]], svc.ds, th, t_cap)
        scen, risk, reasons = classify_tracked(f, th)
        out["hypothesis"] = {"scenario": scen, "scenario_label": scenario_label(scen), "risk": risk,
                             "reason": reasons[0] if reasons else "", "eta_min": _r(f.eta_min),
                             "approach_last60_m": _r(f.approach_last60_m, 0), "dist_now_m": _r(f.dist_now_m, 0)}
        # grafik için: olası izin çekim anına kadarki kısmı
        out["points"] = [p for p in _track_points(svc.ds, svc.ds.tracks[best[0]]) if p["t"] <= t_cap]
    return out


def _related_reports(st, vid: str | None, tid: str | None) -> list[dict]:
    out = []
    for r in st.reports:
        hit = ((vid and r["matched_vehicle_id"] == vid) or (tid and r["matched_track_id"] == tid)
               or (vid and vid in (r["checks"].get("bolgedeki_tehditler") or [])))
        if hit:
            out.append({"report_id": r["report_id"], "time": r["time"], "source": r["source"],
                        "verdict": r["verdict"], "report_type": r["report_type"], "summary": r["summary"],
                        "text": r["text"], "injection": r["injection_detected"], "checks": r["checks"]})
    return sorted(out, key=lambda x: (x["time"], x["report_id"]))


def _assessment_info(svc, fid: str | None, vid: str | None, tid: str | None) -> dict:
    a = svc.assessments.get(fid) if fid else None
    if not a:
        return {"assessed": False, "llm": False, "model": None, "fusion_status": None, "fusion_model": None}
    note = next((x for x in a.get("vehicles") or [] if x.get("vehicle_id") == vid), None) or {}
    keys = [k for k in (vid, tid) if k]
    fusion = a.get("fusion") or {}
    decision = note.get("decision") or {}
    return {
        "assessed": True, "llm": a.get("model") is not None, "model": a.get("model"),
        "headline": a.get("headline"),
        "explanation": note.get("explanation"), "change_reason": note.get("change_reason"),
        "llm_level": note.get("llm_risk_level"),
        "fusion_status": fusion.get("status"),
        "fusion_model": fusion.get("model") or a.get("fusion_model"),
        "fusion_frame_level": a.get("fusion_risk_level") or fusion.get("frame_proposed_level"),
        "fusion_level": decision.get("fusion_level") or note.get("fusion_risk_level"),
        "fusion_action": decision.get("fusion_action"),
        "fusion_confidence": decision.get("fusion_confidence"),
        "actions": [x for x in a.get("recommended_actions") or [] if any(k in x for k in keys)][:3],
        "guardrail_notes": [n for n in a.get("guardrail_notes") or [] if any(k in n for k in keys)],
        "disagreement": a.get("disagreement"),
    }


def _decision_chain(svc, engine_level, scenario, reasons, margin, fin, assess) -> list[dict]:
    """Motor → ilk LLM → ilk guardrail → fusion → insan onayı → nihai seviye denetim izi."""
    d, rv = fin.get("decision"), fin.get("review")
    conf = (margin or {}).get("confidence", "net")
    chain = [
        {"stage": "Motor kuralı", "level": engine_level,
         "detail": f"{scenario_label(scenario)} ({scenario}). " + (reasons[0] if reasons else "")},
        {"stage": "Motor güveni", "level": None,
         "detail": ("Net — değerler eşiklerden uzak." if conf == "net" else "Sınırda — ")
                   + "; ".join((margin or {}).get("notes") or [])},
    ]

    if not assess.get("assessed"):
        chain.append({"stage": "İlk LLM değerlendirmesi", "level": None,
                      "detail": "Kare henüz değerlendirilmedi; motor seviyesi geçerli."})
    elif not assess.get("llm"):
        chain.append({"stage": "İlk LLM değerlendirmesi", "level": None,
                      "detail": "İlk LLM devre dışıydı; motor şablonu kullanıldı."})
    elif d is None:
        chain.append({"stage": "İlk LLM değerlendirmesi", "level": assess.get("llm_level"),
                      "detail": "Bu araç için geçerli karar kaydı yok; motor seviyesi korunuyor."})
    else:
        llm_lv = d.get("llm_level")
        chain.append({"stage": "İlk LLM değerlendirmesi", "level": llm_lv,
                      "detail": (f"İlk LLM {risk_label(llm_lv)} önerdi. Gerekçe: {d['llm_reason']}" if d.get("llm_reason")
                                 else "İlk LLM motorla aynı seviyeyi verdi." if llm_lv == engine_level
                                 else "İlk LLM bu aracı ayrıca belirtmedi." if llm_lv is None
                                 else f"İlk LLM {risk_label(llm_lv)} önerdi, gerekçe yazmadı.")})

    if d is not None:
        pre = d.get("pre_fusion") or {}
        if pre:
            chain.append({"stage": "İlk guardrail", "level": pre.get("auto_level"),
                          "detail": f"{pre.get('rule_label') or pre.get('rule') or 'İlk karar'}. "
                                    f"Fusion öncesi otomatik seviye {risk_label(pre.get('auto_level'))}."})
        elif not d.get("fusion_action"):
            chain.append({"stage": "İlk guardrail", "level": d.get("auto_level"),
                          "detail": f"{RULE_LABELS.get(d.get('rule'), d.get('rule') or 'Karar')}. "
                                    f"{d.get('note') or ''}".strip()})

        if d.get("fusion_action"):
            proposal = d.get("fusion_level")
            fusion_conf = d.get("fusion_confidence")
            conf_text = f" · güven {fusion_conf:.2f}" if isinstance(fusion_conf, (int, float)) else ""
            explanation = d.get("fusion_explanation") or ""
            chain.append({"stage": "Fusion hakemi", "level": proposal,
                          "detail": f"Bağımsız fusion önerisi {risk_label(proposal)}{conf_text}. {explanation}".strip()})

            action_tr = {
                "ESCALATE": "yükseltme uygulandı", "DEESCALATE": "düşürme uygulandı", "KEEP": "motor seviyesi korundu",
                "REJECTED": "öneri kanıt kapısında reddedildi", "CAPPED_UP": "yükseltme otomatik değişim tavanında sınırlandı",
                "CAPPED_DOWN": "düşürme otomatik değişim tavanında sınırlandı",
            }.get(d.get("fusion_action"), d.get("fusion_action"))
            score = d.get("fusion_net_score")
            score_text = f" Net kanıt skoru {score}." if score is not None else ""
            keys = d.get("fusion_evidence_keys") or []
            consumed = d.get("fusion_consumed_by_engine") or []
            detail = f"{action_tr}; uygulanan otomatik seviye {risk_label(d.get('auto_level'))}.{score_text}"
            if keys:
                detail += f" Doğrulanmış aktif kanıt: {', '.join(keys)}."
            if consumed:
                detail += f" Motorun zaten tükettiği gruplar tekrar sayılmadı: {', '.join(consumed)}."
            chain.append({"stage": "Fusion kanıt kapısı", "level": d.get("auto_level"), "detail": detail})
        else:
            fs = assess.get("fusion_status")
            if fs == "error":
                chain.append({"stage": "Fusion hakemi", "level": None,
                              "detail": "Fusion hata verdi; güvenli fallback olarak ilk motor+LLM kararı korundu."})
            elif fs == "disabled":
                chain.append({"stage": "Fusion hakemi", "level": None,
                              "detail": "Fusion devre dışı; ilk motor+LLM kararı korundu."})
            elif fs == "ok":
                chain.append({"stage": "Fusion hakemi", "level": None,
                              "detail": "Fusion kare düzeyinde çalıştı ancak bu araç için uygulanmış fusion sonucu yok; fallback karar korundu."})
    else:
        fs = assess.get("fusion_status")
        if fs == "error":
            chain.append({"stage": "Fusion hakemi", "level": None,
                          "detail": "Fusion hata verdi; motor/ilk LLM fallback kararı korundu."})
        elif fs == "disabled":
            chain.append({"stage": "Fusion hakemi", "level": None,
                          "detail": "Fusion devre dışı."})
        elif fs == "ok":
            chain.append({"stage": "Fusion hakemi", "level": None,
                          "detail": "Fusion kare düzeyinde çalıştı; bu araç için ayrı uygulanmış sonuç bulunmuyor."})

    if not svc.human_review:
        chain.append({"stage": "İnsan onayı", "level": None,
                      "detail": "Kapalı — fusion varsa doğrulanmış otomatik sonuç, yoksa fallback sonuç uygulandı."})
    elif rv:
        chain.append({"stage": "İnsan onayı", "level": rv["level"],
                      "detail": f"Analist '{rv.get('analyst') or 'analist'}' ({fmt_ts(rv.get('at'))}) "
                                f"{risk_label(rv['level'])} seviyesini seçti."
                                + (f" Not: {rv['note']}" if rv.get("note") else "")})
    elif d and d.get("needs_review"):
        chain.append({"stage": "İnsan onayı", "level": None,
                      "detail": "BEKLİYOR — seçenekler: " + ", ".join(risk_label(x) for x in d.get("options") or [])
                                + ". Karar verilene kadar otomatik/geçici seviye gösterilir."})
    else:
        chain.append({"stage": "İnsan onayı", "level": None,
                      "detail": "Açık; bu karar için ayrıca analist onayı gerekmiyor."})
    chain.append({"stage": "Nihai seviye", "level": fin["level"], "detail": status_label(fin["status"])})
    return chain


def _features_view(f: dict | None) -> dict | None:
    if not f:
        return None
    keys = ("t_start", "t_end", "dist_now_m", "dist_start_m", "dist_min_m", "approach_total_m", "approach_last60_m",
            "closing_speed_mps", "speed_now_mps", "max_speed_mps", "heading_deg", "bearing_to_base_deg",
            "heading_offset_deg", "eta_min", "stops_last60", "stopped_minutes_total", "moving_now",
            "path_length_m", "net_displacement_m", "extent_m", "radius_cv", "angular_sweep_deg", "dist_trend",
            "initial_wait_min", "window_min", "dist_min_time", "approach_to_min_m", "retreat_from_min_m",
            "dwell_near_min_min")
    out = {k: f.get(k) for k in keys}
    out["stops"] = [{"start": s["start"], "end": s["end"], "minutes": s["minutes"],
                     "dist_to_base_m": s["dist_to_base_m"]} for s in f.get("stops") or []]
    return out


# ------------------------------------------------------------------ araç olguları
def _frame_vehicle_facts(svc, vid: str, dmap: dict) -> dict:
    st, ds, th = svc.state, svc.ds, settings.thresholds
    v = st.vehicles[vid]
    fin = svc.vehicle_final(vid, dmap)
    fr = st.frames[v["frame_id"]]
    meta = fr["meta"]
    tid = v["track_id"]
    assess = _assessment_info(svc, v["frame_id"], vid, tid)
    facts = {
        "key": vid, "kind": "frame_vehicle", "vehicle_id": vid, "frame_id": v["frame_id"],
        "capture_time": v["capture_time"], "capture_min": v["capture_min"], "track_id": tid,
        "source": v["source"], "label": v["label"], "confidence": v["confidence"], "bbox": v["bbox"],
        "lat": v["lat"], "lon": v["lon"], "xy_km": list(_local_km(ds, v["lat"], v["lon"])),
        "zone": v["zone"], "dist_to_base_m": v["dist_to_base_m"], "bearing_from_base_deg": v["bearing_from_base_deg"],
        "track_match_m": v["track_match_m"],
        "engine_level": v["risk_level"], "final_level": fin["level"], "status": fin["status"],
        "status_label": status_label(fin["status"]), "scenario": v["scenario"],
        "scenario_label": scenario_label(v["scenario"]), "engine_reasons": v["risk_reasons"],
        "margin": v.get("margin"), "friendly_confirmed_by": v.get("friendly_confirmed_by") or [],
        "features": _features_view(v.get("features")),
        "decision": fin.get("decision"), "review": ({**fin["review"], "at_text": fmt_ts(fin["review"].get("at"))}
                                                    if fin.get("review") else None),
        "assessment": assess,
        "frame": {"frame_id": fr["frame_id"], "capture_time": fr["capture_time"], "zone": fr["zone"],
                  "width_px": meta["width_px"], "height_px": meta["height_px"],
                  "corners": meta["corner_coordinates"], "footprint_km": _frame_footprint(ds, meta),
                  "others": [{"vehicle_id": o, "label": st.vehicles[o]["label"], "bbox": st.vehicles[o]["bbox"],
                              "lat": st.vehicles[o]["lat"], "lon": st.vehicles[o]["lon"]}
                             for o in fr["vehicle_ids"] if o != vid]},
        "related_reports": _related_reports(st, vid, tid),
    }
    if tid:
        tr = ds.tracks[tid]
        fobj = _features_obj(ds, th, tid, v["capture_min"])
        facts["rules"] = explain_tracked(fobj, th, heavy=bool(v.get("heavy")),
                                         bus=is_bus(v["label"], v.get("alt_labels"), th.heavy_alt_min_conf))
        facts["track"] = {"track_id": tid, "points": _track_points(ds, tr), "t_start": min_to_hhmm(tr.t_start),
                          "t_end": min_to_hhmm(tr.t_end), "continues_after_capture": tr.t_end > v["capture_min"]}
        if tr.t_end > v["capture_min"]:
            after = [p for p in facts["track"]["points"] if p["t"] > v["capture_min"]]
            facts["track"]["after_capture"] = {"until": after[-1]["time"], "end_dist_m": after[-1]["dist_m"],
                                               "min_dist_m": min(p["dist_m"] for p in after)}
        facts["nearest_track"] = None
    else:
        facts["rules"] = explain_untracked(v["label"] or "unknown", v["dist_to_base_m"], th)
        facts["track"] = None
        facts["nearest_track"] = _nearest_track(svc, v["lat"], v["lon"], v["capture_min"])
    facts["decision_chain"] = _decision_chain(svc, v["risk_level"], v["scenario"], v["risk_reasons"],
                                              v.get("margin"), fin, assess)
    return facts


def _offframe_facts(svc, tid: str) -> dict:
    st, ds, th = svc.state, svc.ds, settings.thresholds
    r = st.offframe_risk[tid]
    tr = ds.tracks[tid]
    fin = {"level": r["risk_level"], "status": "motor", "decision": None, "review": None}
    assess = {"assessed": False, "llm": False, "model": None}
    facts = {
        "key": f"offframe_{tid}", "kind": "offframe_track", "vehicle_id": None, "frame_id": None,
        "capture_time": r["last_time"], "capture_min": tr.t_end, "track_id": tid, "source": "track_only",
        "label": None, "confidence": None, "bbox": None, "lat": round(r["lat"], 6), "lon": round(r["lon"], 6),
        "xy_km": list(_local_km(ds, r["lat"], r["lon"])), "zone": r["zone"],
        "dist_to_base_m": r["features"]["dist_now_m"], "bearing_from_base_deg": round(ds.bearing_from_base(r["lat"], r["lon"]), 1),
        "track_match_m": None, "engine_level": r["risk_level"], "final_level": r["risk_level"], "status": "motor",
        "status_label": "Motor seviyesi (kare dışı iz — ilk LLM/fusion kare değerlendirmesi yok)",
        "scenario": r["scenario"], "scenario_label": scenario_label(r["scenario"]), "engine_reasons": r["risk_reasons"],
        "margin": r.get("margin"), "friendly_confirmed_by": [], "features": _features_view(r["features"]),
        "decision": None, "review": None, "assessment": assess, "frame": None,
        "related_reports": _related_reports(st, None, tid),
        "rules": explain_tracked(_features_obj(ds, th, tid, tr.t_end), th),
        "track": {"track_id": tid, "points": _track_points(ds, tr), "t_start": min_to_hhmm(tr.t_start),
                  "t_end": min_to_hhmm(tr.t_end), "continues_after_capture": False},
        "nearest_track": None,
    }
    facts["decision_chain"] = _decision_chain(svc, r["risk_level"], r["scenario"], r["risk_reasons"],
                                              r.get("margin"), fin, assess)
    for step in facts["decision_chain"]:
        if step["stage"] == "İlk LLM değerlendirmesi":
            step["detail"] = "İz hiçbir karede görünmediği için ilk LLM/fusion kare değerlendirmesine girmedi."
            break
    return facts


def _sort_key(f: dict):
    eta = (f.get("features") or {}).get("eta_min")
    return (-RISK_ORDER.index(f["final_level"]), eta if eta is not None else 1e9, f["dist_to_base_m"], f["key"])


# ------------------------------------------------------------------ yöntem tabloları
def _dummy_features() -> TrackFeatures:
    return TrackFeatures(track_id="-", t_start="", t_end="", dist_now_m=0, dist_start_m=0, dist_min_m=0,
                         dist_max_m=0, approach_total_m=0, approach_last60_m=0, closing_speed_mps=0,
                         speed_now_mps=0, max_speed_mps=0, heading_deg=None, bearing_to_base_deg=0,
                         heading_offset_deg=0, eta_min=0)


def methodology() -> dict:
    """Motor kuralları + ilk LLM guardrail'i + bağımsız fusion doğrulama politikasını rapora taşır."""
    th = settings.thresholds
    fp = settings.fusion
    rules = [{"scenario": r["scenario"], "label": scenario_label(r["scenario"]), "risk": r["risk"],
              "conds": [f"{c['name']} {c['threshold']}" for c in r["conds"]]}
             for r in explain_tracked(_dummy_features(), th)]
    rules.append({"scenario": "UNTRACKED", "label": scenario_label("UNTRACKED"), "risk": "ORTA",
                  "conds": [f"ağır araç (truck/bus) üsse < {th.untracked_heavy_m:g} m",
                            f"veya herhangi araç üsse < {th.untracked_any_m:g} m"]})
    rules.append({"scenario": "TRANSIT / MOVING_AWAY / PARKED", "label": "Diğer", "risk": "DUSUK",
                  "conds": ["yukarıdaki kuralların hiçbiri eşleşmedi"]})

    # İlk LLM sonrası koruma katmanı geriye dönük/operasyonel fallback olarak korunuyor; nihai otomatik otorite fusion.
    primary_guardrail = [
        ("uzlasi", "İlk LLM = motor", "motor"),
        ("reddedildi", "İlk LLM değişiklik gerekçesi/rapor dayanağı geçersiz", "motor"),
        ("llm_yukseltti", "İlk LLM > motor ve ilk guardrail tavanı içinde", "ilk LLM"),
        ("fazla_yukseltme", "İlk LLM ilk guardrail tavanını aşıyor", "sınırlandırılmış seviye"),
        ("motor_kesin", "İlk LLM < motor, motor ilk guardrail'de net", "motor"),
        ("llm_dusurdu", "İlk LLM < motor ve eski düşürme guardrail koşulları sağlanıyor", "ilk LLM / onay"),
        ("belirsiz", "İlk LLM < motor fakat eski düşürme guardrail koşulları eksik", "motor / onay"),
    ]

    fusion_flow = [
        {"step": "1", "role": "Bağımsız hakem",
         "detail": "Motor ve ilk LLM iki ayrı uzman görüşüdür; fusion hiçbirini ground-truth veya zorunlu alt sınır kabul etmez."},
        {"step": "2", "role": "Bağlam",
         "detail": "Çekim anındaki CURRENT verisi, capture_time'a kadar tüm track HISTORY'si ve güvenli saha raporu bağlamı birlikte değerlendirilir."},
        {"step": "3", "role": "Doğrulanmış kanıt",
         "detail": "Seviye değişikliği yalnız ACTIVE evidence anahtarlarıyla yapılır; aynı olgunun eşik kopyaları tek grupta sayılır."},
        {"step": "4", "role": "Çifte sayımı engelleme",
         "detail": "Motor kuralının zaten kullandığı kanıt grupları fusion değişiklik skorunda tekrar kullanılamaz."},
        {"step": "5", "role": "Net skor",
         "detail": "Destekleyen taze kanıt skoru, katalogdaki tüm aktif karşı kanıt skoru düşülerek değerlendirilir; model karşı kanıtı yazmayarak gizleyemez."},
        {"step": "6", "role": "İki yönlü düzeltme",
         "detail": "Yeterli güven ve net kanıt varsa motor seviyesi hem yükseltilebilir hem düşürülebilir; ilk LLM'in doğrulanmayan değişikliği geri alınabilir."},
        {"step": "7", "role": "KRİTİK korkuluğu",
         "detail": "KRİTİK'e çıkış için yüksek güvene ek olarak kısa ETA, güncel yakınlık ve yönelim/hız gibi imminent CURRENT kanıtı zorunludur."},
        {"step": "8", "role": "Otomatik değişim tavanı",
         "detail": f"Tek çağrıda motor seviyesinden en fazla {fp.max_auto_delta} kademe otomatik değişiklik uygulanır; fazlası sınırlandırılır/onaya taşınabilir."},
    ]

    return {
        "rules": rules,
        "primary_guardrail_table": [{"rule": k, "label": RULE_LABELS[k], "when": w, "result": r}
                                    for k, w, r in primary_guardrail],
        # Eski tüketicileri kırmamak için alan korunur; PDF yeni primary_guardrail_table alanını kullanır.
        "decision_table": [{"rule": k, "label": RULE_LABELS[k], "when": w, "hil_off": r, "hil_on": r}
                           for k, w, r in primary_guardrail],
        "fusion_flow": fusion_flow,
        "fusion_thresholds": {
            "1 kademe min. güven": f"{fp.min_confidence:.2f}",
            "2 kademe min. güven": f"{fp.high_confidence:.2f}",
            "KRİTİK min. güven": f"{fp.critical_min_confidence:.2f}",
            "1 kademe min. net skor": str(fp.one_step_min_score),
            "2 kademe min. net skor": str(fp.two_step_min_score),
            "1 kademe min. bağımsız grup": str(fp.one_step_min_keys),
            "2 kademe min. bağımsız grup": str(fp.two_step_min_keys),
            "KRİTİK güncel tehdit skoru": f"≥ {fp.critical_current_min_score}",
            "KRİTİK düşürme net skoru": f"≥ {fp.critical_downgrade_min_score}",
            "Maks. otomatik kademe": str(fp.max_auto_delta),
        },
        "thresholds": {
            "Tespit güven eşiği": f"{th.min_confidence:.2f}", "İz eşleştirme yarıçapı": f"{th.match_radius_m:g} m",
            "Duraklama": f"{th.stop_radius_m:g} m içinde ≥ {th.stop_min_minutes} dk",
            "Yönelim (üsse doğru)": f"≤ {th.heading_toward_deg:g}°", "Hızlı yaklaşma": f"≥ {th.fast_speed_mps:g} m/s",
            "Kritik ETA": f"≤ {th.critical_eta_min:g} dk", "Rapor eşleşme yarıçapı": f"{th.report_match_radius_m:g} m",
            "Rapor zaman toleransı": f"± {th.report_time_tol_min} dk", "Motor 'sınırda' payı": f"%{th.margin_tol * 100:g}",
        },
    }


# ------------------------------------------------------------------ ana giriş
def collect_report_data(svc, opts: ReportOptions) -> dict:
    st = svc.state
    levels = opts.selected_levels()
    dmap = svc.decision_map()

    vehicles, all_final = [], []
    for vid, v in st.vehicles.items():
        if v["filtered"]:
            continue
        lvl = svc.vehicle_final(vid, dmap)["level"]
        all_final.append(lvl)
        if lvl in levels:
            vehicles.append(_frame_vehicle_facts(svc, vid, dmap))
    for tid, r in st.offframe_risk.items():
        all_final.append(r["risk_level"])
        if opts.include_offframe and r["risk_level"] in levels:
            vehicles.append(_offframe_facts(svc, tid))
    vehicles.sort(key=_sort_key)
    for i, f in enumerate(vehicles, 1):
        f["index"] = i

    # insan onayı listeleri (seçimden bağımsız: tüm bekleyenler görünür)
    rv = svc.list_reviews(status="all")
    pending = [x for x in rv["items"] if x["status"] == "onay_bekliyor" or (x["review"] is None)]
    decided = [x for x in rv["items"] if x["review"] is not None]
    for x in decided:
        x["review"] = {**x["review"], "at_text": fmt_ts(x["review"].get("at"))}
    in_report = {f["vehicle_id"]: f["index"] for f in vehicles if f["vehicle_id"]}
    for x in pending + decided:                 # araç raporda hangi dosyada (ya da filtre dışında)
        x["dossier"] = in_report.get(x["vehicle_id"])
        dx = dmap.get(x["vehicle_id"]) or {}
        x["fusion_level"] = dx.get("fusion_level")
        x["fusion_action"] = dx.get("fusion_action")
        x["fusion_confidence"] = dx.get("fusion_confidence")
        x["fusion_applied_level"] = dx.get("auto_level") if dx.get("fusion_action") else None

    verdict_counts = {k: sum(1 for r in st.reports if r["verdict"] == k)
                      for k in ["destekler", "celisir", "kismen_uyumlu", "dogrulanamaz", "ilgisiz", "manipulasyon"]}
    type_counts: dict[str, int] = {}
    for r in st.reports:
        type_counts[r["report_type"]] = type_counts.get(r["report_type"], 0) + 1
    related_ids = sorted({r["report_id"] for f in vehicles for r in f["related_reports"]})

    frames_assessed = [fid for fid in st.frames if fid in svc.assessments]
    frames_llm = [fid for fid in frames_assessed if svc.assessments[fid].get("model")]
    frames_fusion = [fid for fid in frames_assessed
                     if (svc.assessments[fid].get("fusion") or {}).get("status") == "ok"]
    frames_fusion_error = [fid for fid in frames_assessed
                           if (svc.assessments[fid].get("fusion") or {}).get("status") == "error"]
    fusion_models = sorted({str((svc.assessments[fid].get("fusion") or {}).get("model"))
                            for fid in frames_fusion if (svc.assessments[fid].get("fusion") or {}).get("model")})
    times = [p.t for tr in svc.ds.tracks.values() for p in tr.points]
    now = datetime.now(_tz())

    meta = {
        "report_id": f"TR-{now:%Y%m%d-%H%M%S}-{opts.filter_key()}",
        "generated_at": now.strftime("%d.%m.%Y %H:%M:%S"), "generated_at_iso": now.isoformat(timespec="seconds"),
        "filter_label": opts.filter_label(), "levels": levels, "min_risk": opts.min_risk,
        "include_offframe": opts.include_offframe, "assess_scope": opts.assess_scope,
        "human_review": svc.human_review, "prepared_by": opts.prepared_by,
        "detector": st.detector, "frames_total": len(st.frames), "frames_assessed": len(frames_assessed),
        "frames_llm": len(frames_llm),
        "frames_fusion": len(frames_fusion), "frames_fusion_error": len(frames_fusion_error),
        "assess_model": ", ".join(sorted({str(svc.assessments[f]["model"]) for f in frames_llm})) or None,
        "fusion_model": ", ".join(fusion_models) or None,
        "data_window": f"{min_to_hhmm(min(times))}–{min_to_hhmm(max(times))}" if times else "—",
        "tracks_total": len(svc.ds.tracks), "reports_total": len(st.reports),
        "vehicles_total": len(all_final),
        "base": svc.ds.base,
        "zones": [{"name": z.name, "xy_km": list(_local_km(svc.ds, z.lat, z.lon)), "dist_m": round(z.dist_m)}
                  for z in svc.ds.zones],
        "theme_version": THEME_VERSION,
    }
    counts = {lv: sum(1 for f in vehicles if f["final_level"] == lv) for lv in RISK_ORDER}
    all_counts = {lv: all_final.count(lv) for lv in RISK_ORDER}

    data = {
        "meta": meta, "counts": counts, "all_counts": all_counts, "vehicles": vehicles,
        "reviews": {"enabled": svc.human_review, "pending": pending, "decided": decided,
                    "pending_count": rv["pending_count"]},
        "integrity": {
            "verdict_counts": verdict_counts, "type_counts": dict(sorted(type_counts.items())),
            "related_report_ids": related_ids,
            "manipulation": [{"report_id": r["report_id"], "time": r["time"], "source": r["source"],
                              "span": r["injection_span"], "summary": r["summary"]}
                             for r in st.reports if r["injection_detected"]],
        },
        "methodology": methodology(),
        "risk_labels": RISK_LABELS,
    }
    # aynı girdi → aynı özet: zaman damgası ve rapor no hariç olguların özeti (ekte yazılır)
    data["meta"]["facts_digest"] = stable_digest({k: data[k] for k in ("counts", "vehicles", "reviews", "integrity")}
                                                 | {"levels": levels, "hil": svc.human_review})[:16]
    return data
