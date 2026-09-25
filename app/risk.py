"""Kural tabanlı risk sınıflandırması. Nihai risk seviyesi BURADAN gelir; LLM ajanı bu seviyeyi
açıklar ve analiste yorum ekler ama düşüremez (rapor içi prompt injection ve eval kararlılığı için).

Senaryolar (README):
  DIRECT_FAST_APPROACH  → KRITIK  uzun bekleme, sonra ara durak olmadan hızla doğrudan üsse
  APPROACH_WITH_STOPS   → YUKSEK  son 60 dk'da ≥1.5 km yaklaşma + birden fazla ≥15 dk duraklama
  LOITER_NEAR_BASE      → YUKSEK  üsse 0.4–3 km'de küçük döngüde tur + duraklama
  FRIENDLY_PATROL       → ORTA    (resmi dost teyidi varsa DUSUK)
  UNTRACKED             → ORTA    ağır araç <2.5 km ya da herhangi araç <1.2 km; aksi halde DUSUK
  APPROACHING           → ORTA    yukarıdakilere uymayan ama üsse yönelmiş yaklaşma
  TRANSIT/MOVING_AWAY/PARKED → DUSUK
"""
from __future__ import annotations

from .config import HEAVY_LABELS, RISK_ORDER, Thresholds
from .tracking import TrackFeatures


def max_risk(levels: list[str]) -> str:
    return max(levels, key=RISK_ORDER.index) if levels else "DUSUK"


def _fmt(v: float | None, unit: str = "", nd: int = 0) -> str:
    return "—" if v is None else f"{v:.{nd}f}{unit}"


def classify_tracked(f: TrackFeatures, th: Thresholds) -> tuple[str, str, list[str]]:
    """(senaryo, risk, gerekçeler)"""
    toward = f.heading_offset_deg is not None and f.heading_offset_deg <= th.heading_toward_deg
    intermediate_stops = len(f.stops) - (1 if f.initial_wait_min else 0)
    ratio = f.path_length_m / max(f.extent_m, 1.0)

    # 1) sabit yarıçaplı devriye (üs etrafında tur)
    if f.radius_cv <= 0.03 and f.angular_sweep_deg >= 180 and f.stopped_minutes_total <= 15 and f.dist_now_m >= th.loiter_min_dist_m:
        return "FRIENDLY_PATROL", "ORTA", [
            f"Üs etrafında sabit yarıçaplı tur (ort. mesafe ~{_fmt(f.dist_now_m, ' m')}, "
            f"değişim katsayısı {f.radius_cv:.3f}, taranan açı {f.angular_sweep_deg:.0f}°).",
            "Resmi dost teyidi yoksa ORTA; teyit gelirse DUSUK'e iner.",
        ]

    # 2) doğrudan hızlı yaklaşma
    if (toward and f.moving_now and f.speed_now_mps >= th.fast_speed_mps and intermediate_stops == 0
            and f.eta_min is not None and f.eta_min <= th.critical_eta_min):
        return "DIRECT_FAST_APPROACH", "KRITIK", [
            f"{f.initial_wait_min} dk bekledikten sonra ara durak olmadan üsse doğru {f.speed_now_mps:.1f} m/s ile ilerliyor.",
            f"Yönelim sapması {_fmt(f.heading_offset_deg, '°')}, üsse mesafe {_fmt(f.dist_now_m, ' m')}, ETA ≈ {_fmt(f.eta_min, ' dk', 1)}.",
        ]

    # 3) duraklamalı yaklaşma
    if (f.approach_last60_m or 0) >= th.approach_min_m and len(f.stops) >= 2 and toward:
        reasons = [
            f"Son 60 dk'da üsse {_fmt(f.approach_last60_m, ' m')} yaklaştı, {len(f.stops)} adet ≥{th.stop_min_minutes} dk duraklama.",
            f"Yönelim sapması {_fmt(f.heading_offset_deg, '°')}, üsse mesafe {_fmt(f.dist_now_m, ' m')}.",
        ]
        if f.eta_min is not None:
            reasons.append(f"Mevcut hızla ETA ≈ {f.eta_min:.1f} dk — yakın takip gerekir.")
        return "APPROACH_WITH_STOPS", "YUKSEK", reasons

    # 4) üs yakınında tur atma
    if (th.loiter_min_dist_m <= f.dist_now_m <= th.loiter_max_dist_m and f.extent_m <= 1500
            and ratio >= 3 and len(f.stops) >= 2):
        return "LOITER_NEAR_BASE", "YUKSEK", [
            f"Üsse {_fmt(f.dist_now_m, ' m')} mesafede ~{_fmt(f.extent_m, ' m')}'lik alanda döngü "
            f"(yol/yer değiştirme oranı {ratio:.1f}).",
            f"{len(f.stops)} duraklama, toplam {f.stopped_minutes_total} dk hareketsiz.",
        ]

    # 5) diğer yönelmiş yaklaşmalar
    if toward and f.moving_now and (f.approach_last60_m or 0) >= 500:
        return "APPROACHING", "ORTA", [
            f"Üsse yönelmiş hareket (sapma {_fmt(f.heading_offset_deg, '°')}), son 60 dk yaklaşma {_fmt(f.approach_last60_m, ' m')}.",
            "Bilinen bir tehdit örüntüsüne uymuyor; izlenmeli.",
        ]

    # 6) düşük risk sınıfları
    if f.path_length_m < 150:
        return "PARKED", "DUSUK", ["İz boyunca hareketsiz (park halinde)."]
    if f.dist_trend == "once_azalip_sonra_artiyor" or (f.heading_offset_deg is not None and f.heading_offset_deg > 90):
        return "TRANSIT", "DUSUK", [
            f"Mesafe trendi: {f.dist_trend}; yönelim sapması {_fmt(f.heading_offset_deg, '°')} (üsse yönelmemiş).",
            "Mesafenin bir süre azalması tek başına tehdit sayılmadı.",
        ]
    if f.dist_trend == "artiyor":
        return "MOVING_AWAY", "DUSUK", ["Üsten uzaklaşıyor."]
    return "PARKED", "DUSUK", ["Hareket ettikten sonra durmuş; üsse yönelim yok."]


def classify_untracked(label: str, dist_m: float, th: Thresholds) -> tuple[str, str, list[str]]:
    heavy = label in HEAVY_LABELS
    if (heavy and dist_m < th.untracked_heavy_m) or dist_m < th.untracked_any_m:
        why = (f"İzi olmayan ağır araç, üsse {dist_m:.0f} m (<{th.untracked_heavy_m:.0f} m)."
               if heavy and dist_m < th.untracked_heavy_m
               else f"İzi olmayan araç, üsse {dist_m:.0f} m (<{th.untracked_any_m:.0f} m).")
        return "UNTRACKED", "ORTA", [why, "Davranış bilinmiyor; ek gözlem önerilir."]
    return "UNTRACKED", "DUSUK", [f"İzi olmayan {label}, üsse {dist_m:.0f} m; eşiklerin dışında."]
