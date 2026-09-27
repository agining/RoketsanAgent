#!/usr/bin/env python3
"""HİSAR — edge-case paketi (T9996–T9999) kurulumu.

Repo kökünde çalıştırın:   python apply_edge_cases.py            (önce kontrol eder, sonra uygular)
Sadece kontrol:            python apply_edge_cases.py --check
Veri klasörü farklıysa:    python apply_edge_cases.py --data /yol/data

Ne yapar
  1) Kod: app/ altındaki 9 dosyaya küçük, çapaya (anchor) bağlı eklemeler yapar. Her çapa dosyada TEK satıra
     uymalıdır; biri bile tutmazsa HİÇBİR dosyaya yazılmaz. Satır sonları (CRLF/LF) korunur, her dosyanın
     yanına <dosya>.bak_edgecases yedeği bırakılır. Zaten uygulanmış dosya atlanır (tekrar çalıştırmak güvenli).
  2) Veri: tracks.csv'ye T9996–T9999 izlerini, image_meta.json'a img_999996–img_999999 karelerini,
     detections_sim.json'a bu karelerin tespitlerini ekler; data/images/ altına SENTETİK yer tutucu kare çizer
     (Pillow varsa). Mevcut satırlara dokunmaz.

Sonra sunucuyu YENİDEN BAŞLATIN. /api/reload kullanmayın — o, mevcut karelerin LLM değerlendirme önbelleğini
(assessments.json) ve analist kararlarını siler; yeniden başlatmada önbellek korunur, yalnız yeni 4 kare
değerlendirilmemiş görünür.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
from pathlib import Path

# ============================================================================ kod değişiklikleri
# (işlem, çapa, [bitiş çapası], yeni metin). Çapa eşleşmesi boşluk-duyarsızdır: önce satırın TAMAMI, o tutmazsa
# satırın bir PARÇASI olarak aranır; her iki durumda da tek satıra uymalıdır.
# işlemler: after | before | replace | replace_block (çapa..bitiş dahil)

CONFIG_OPS = [
    ("after", "margin_tol: float = 0.10", '''\
    # --- rutin hat aracı / servis otobüsü (ROUTINE_SHUTTLE) ---
    shuttle_pass_near_m: float = 1500.0   # bu halkaya her giriş bir "üs yakınından geçiş" sayılır
    shuttle_pass_reset_m: float = 1000.0  # yeni geçiş için halkanın en az bu kadar dışına çıkılmış olmalı
    shuttle_min_passes: int = 3           # aynı hattan en az bu kadar geçiş
    shuttle_corridor_m: float = 120.0     # "aynı hat" koridoru (şerit + GPS sapması)
    shuttle_min_overlap_pct: float = 80.0  # iz noktalarının bu yüzdesi hattın başka bir seferiyle aynı koridorda
    shuttle_route_gap_min: int = 30       # örtüşme sayılması için iki sefer arasında en az bu kadar dakika
    shuttle_stop_clear_m: float = 2500.0  # bu mesafe içinde hiç duraklama olmamalı (üs yakınında beklemez)
    # --- duraklama / hat sapması sonrası ani hızlı son etap (FAST_FINAL_APPROACH) ---
    dash_speed_mps: float = 10.0          # son etap ort. hızı; bu veride olağan trafik ≤ ~9.4 m/s
    dash_heading_deg: float = 30.0        # son etapta üsse yönelim (DIRECT_FAST_APPROACH'tan sıkı)
    # --- veri kalitesi: tek örneklik GPS sıçraması ---
    gps_spike_min_speed_mps: float = 12.0  # gidiş ve dönüş bacaklarının ikisi de bu hızın üstünde ...
    gps_spike_return_m: float = 20.0       # ... ve araç bir sonraki örnekte eski noktasına bu kadar yakın dönmüşse'''),
]

DATA_OPS = [
    ("replace", "from dataclasses import dataclass", "from dataclasses import dataclass, field"),
    ("after", "from .geo import angle_diff, bearing_deg, haversine_m, hhmm_to_min", "from .config import settings"),
    ("after", "points: list[TrackPoint]",
     "    outliers: list[TrackPoint] = field(default_factory=list)   # yüklemede ayıklanan GPS sıçramaları"),
    ("replace", "def load_dataset(data_dir: Path) -> Dataset:", '''\
def drop_gps_spikes(points: list[TrackPoint], th) -> tuple[list[TrackPoint], list[TrackPoint]]:
    """Tek örneklik GPS sıçramalarını ayıklar. Araç bir örnekte fiziksel olarak olanaksız bir hızla uzağa
    "zıplayıp" bir sonraki örnekte eski noktasına (gps_spike_return_m içinde) dönüyorsa o örnek ölçüm hatasıdır.
    Gerçek hızlı hareket (ör. ani yaklaşma) geri dönmediği için etkilenmez. Dönen: (temiz noktalar, ayıklananlar)."""
    if len(points) < 3:
        return points, []
    keep, spikes = [points[0]], []
    for i in range(1, len(points) - 1):
        a, b, c = keep[-1], points[i], points[i + 1]
        v_out = haversine_m(a.lat, a.lon, b.lat, b.lon) / max((b.t - a.t) * 60, 1)
        v_back = haversine_m(b.lat, b.lon, c.lat, c.lon) / max((c.t - b.t) * 60, 1)
        if (v_out >= th.gps_spike_min_speed_mps and v_back >= th.gps_spike_min_speed_mps
                and haversine_m(a.lat, a.lon, c.lat, c.lon) <= th.gps_spike_return_m):
            spikes.append(b)
            continue
        keep.append(b)
    keep.append(points[-1])
    return keep, spikes


def load_dataset(data_dir: Path, th=None) -> Dataset:'''),
    ("after", "data_dir = Path(data_dir)", "    th = th or settings.thresholds"),
    ("replace", "track_objs = {tid: Track(tid, sorted(p, key=lambda x: x.t)) for tid, p in tracks.items()}", '''\
    track_objs = {}
    for tid, p in tracks.items():
        pts, spikes = drop_gps_spikes(sorted(p, key=lambda x: x.t), th)   # veri kalitesi: GPS sıçramaları
        track_objs[tid] = Track(tid, pts, spikes)'''),
]

TRACKING_OPS = [
    ("after", "dwell_near_min_min: int = 0", '''\
    # --- rutin hat (servis otobüsü) öznitelikleri — risk.ROUTINE_SHUTTLE
    route_passes: int = 0            # üssün shuttle_pass_near_m halkasına ayrı ayrı giriş sayısı (her sefer = 1 geçiş)
    route_overlap_pct: float = 0.0   # noktaların, izin ≥ shuttle_route_gap_min dk önceki/sonraki yoluyla aynı koridorda olma %'si
    on_route_now: bool = False       # t_ref anındaki konum, izin daha önce kullandığı hat üzerinde mi
    # --- son etap (son duraklamanın bitişinden t_ref'e) — risk.FAST_FINAL_APPROACH
    final_leg_start: str = ""        # son duraklamanın bittiği an (duraklama yoksa iz başlangıcı)
    final_leg_min: int = 0
    final_leg_gain_m: float = 0.0    # son etapta üsse kapanan mesafe
    final_leg_speed_mps: float = 0.0  # son etabın ortalama yer hızı
    final_leg_eta_min: float | None = None  # son etabın kapanma hızıyla üsse varış (bekleme süresi ETA'yı şişirmesin)
    # --- veri kalitesi: yüklemede ayıklanan tek örneklik GPS sıçramaları (data.drop_gps_spikes; t_ref'e kadar)
    gps_outliers: list[dict] = field(default_factory=list)'''),
    ("after", "dwell = sum(b.t - a.t for a, b, da, db in zip(pts, pts[1:], dists, dists[1:])", '''
    # rutin hat: üs yakınından kaç ayrı geçiş, iz kendi hattını ne kadar tekrarlıyor, şu an hat üzerinde mi
    passes, overlap_pct, on_route = _route_pattern(pts, xy, dists, th)

    # son etap: son duraklama bittiğinden bu yana (duraklama yoksa iz başından beri)
    leg_t0 = _hhmm(stops[-1].end) if stops else pts[0].t
    leg = [(p, d) for p, d in zip(pts, dists) if p.t >= leg_t0]
    leg_min = now.t - leg_t0
    leg_path = sum(haversine_m(a.lat, a.lon, b.lat, b.lon) for (a, _), (b, _) in zip(leg, leg[1:]))
    leg_speed = leg_path / (leg_min * 60) if leg_min > 0 else 0.0
    leg_gain = leg[0][1] - dists[-1]
    leg_eta = dists[-1] / (leg_gain / leg_min) if leg_min > 0 and leg_gain > 0 else None

    outliers = [{"time": min_to_hhmm(p.t), "lat": p.lat, "lon": p.lon,
                 "dist_to_base_m": round(haversine_m(blat, blon, p.lat, p.lon), 1)}
                for p in getattr(tr, "outliers", []) if t_ref is None or p.t <= t_ref]'''),
    ("after", "dwell_near_min_min=dwell,", '''\
        route_passes=passes, route_overlap_pct=overlap_pct, on_route_now=on_route,
        final_leg_start=min_to_hhmm(leg_t0), final_leg_min=leg_min, final_leg_gain_m=leg_gain,
        final_leg_speed_mps=leg_speed, final_leg_eta_min=leg_eta, gps_outliers=outliers,'''),
    ("before", "def _hhmm(s: str) -> int:", '''\
def _seg_dist(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    """p noktasının [a, b] doğru parçasına uzaklığı (yerel metre)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    r = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.hypot(p[0] - a[0] - r * dx, p[1] - a[1] - r * dy)


def _route_pattern(pts: list, xy: list[tuple[float, float]], dists: list[float],
                   th: Thresholds) -> tuple[int, float, bool]:
    """(üs yakınından ayrı geçiş sayısı, hat tekrarı %, t_ref anında hat üzerinde mi).

    * Geçiş: iz shuttle_pass_near_m halkasına her girişinde bir sayılır. Örnekler arası doğru parçasının üsse en
      yakın noktası kullanılır (5 dk'lık örnekleme geçişi atlamasın). Yeni geçiş için halkanın
      shuttle_pass_reset_m kadar dışına çıkılmış olmalı.
    * Hat tekrarı: nokta, izin kendisinden en az shuttle_route_gap_min dk önceki ya da sonraki bir doğru parçasına
      shuttle_corridor_m içinde (aynı yolun başka seferi). Yalnız t_ref'e kadarki noktalar — gelecek sızıntısı yok.
    * Hat üzerinde: son nokta, en az shuttle_route_gap_min dk önce biten bir parçaya koridor içinde.
    """
    near, reset = th.shuttle_pass_near_m, th.shuttle_pass_near_m + th.shuttle_pass_reset_m
    origin = (0.0, 0.0)                      # xy üsse göre (to_local_xy) → üs orijinde
    inside = dists[0] <= near
    passes = 1 if inside else 0
    for i in range(len(xy) - 1):
        if not inside and _seg_dist(origin, xy[i], xy[i + 1]) <= near:
            passes += 1
            inside = True
        if inside and dists[i + 1] >= reset:
            inside = False

    gap, cor = th.shuttle_route_gap_min, th.shuttle_corridor_m
    segs = [(pts[k].t, pts[k + 1].t, xy[k], xy[k + 1]) for k in range(len(xy) - 1)]

    def on_other_trip(j: int) -> bool:
        tj = pts[j].t
        return any(_seg_dist(xy[j], a, b) <= cor for t0, t1, a, b in segs if t1 <= tj - gap or t0 >= tj + gap)

    overlap = sum(1 for j in range(len(xy)) if on_other_trip(j)) / len(xy) * 100
    return passes, overlap, on_other_trip(len(xy) - 1)

'''),
]

RISK_OPS = [
    ("after", "DIRECT_FAST_APPROACH → KRITIK", '''\
  FAST_FINAL_APPROACH  → KRITIK  duraklama ya da hat sapmasından SONRA kesintisiz son etap: etap ort. hızı ≥10 m/s
                                 (bu veride olağan trafik ≤~9.4 m/s), üsse ≤30° yönelim, etapta ≥1.5 km kapatma,
                                 son etap hızıyla ETA ≤10 dk (15 dk'lık ETA bekleme süresiyle şişer). Önceki dur-kalklar
                                 aracı olağan trafik gibi gösterse de son etap imminent tehdittir (DIRECT_FAST_APPROACH
                                 ara durak şartı yüzünden bunu kaçırır).
  ROUTINE_SHUTTLE      → DUSUK   otobüs; üs yakınından (≤1.5 km) aynı hat üzerinden ≥3 ayrı geçiş, noktaların ≥%80'i
                                 hattın başka seferleriyle aynı koridorda, çekim anında hat üzerinde ve üssün 2.5 km'si
                                 içinde hiç durmamış → rutin toplu taşıma. Hattan sapma, üs yakınında durma ya da ani
                                 hızlanma muafiyeti kaldırır (KRITIK kurallar zaten bu kuraldan önce değerlendirilir).'''),
    ("after", "TRANSIT / MOVING_AWAY / PARKED → DUSUK", '''
Veri kalitesi: tek örneklik GPS sıçramaları (araç ≥12 m/s ile uzağa "zıplayıp" bir sonraki örnekte eski noktasına
≤20 m dönüyorsa) yüklemede ayıklanır (data.drop_gps_spikes). Ayıklanan nokta gerekçede belirtilir; kural hesabına
girmez. Gerçek hızlı hareket geri dönmediği için etkilenmez.'''),
    ("replace", "def _tracked_rules(f: TrackFeatures, th: Thresholds, heavy: bool = False) -> list[Rule]:", '''\
def is_bus(label: str | None, alt_labels: list[dict] | None = None, min_alt_conf: float = 0.5) -> bool:
    """Otobüs: etiket bus ya da aynı nesneye düşen kopya kutulardan birinde güvenli (≥min_alt_conf) bus etiketi."""
    if label == "bus":
        return True
    return any(a.get("label") == "bus" and (a.get("confidence") or 0) >= min_alt_conf for a in (alt_labels or []))


def _tracked_rules(f: TrackFeatures, th: Thresholds, heavy: bool = False, bus: bool = False) -> list[Rule]:'''),
    ("after", 'near_now = Cond("üsse mesafe", f.dist_now_m, "<=", th.near_arrival_m, " m", nd=0)', '''\
    near_stops = sum(1 for s in f.stops if s.dist_to_base_m <= th.shuttle_stop_clear_m)

    def fast_final_reasons() -> list[str]:
        start = (f"Son duraklama bittikten sonra ({f.final_leg_start})" if f.stops
                 else f"İz başından ({f.final_leg_start}) bu yana")
        out = [f"{start} {f.final_leg_min} dk'dır kesintisiz ve hızla ({f.final_leg_speed_mps:.1f} m/s) üsse doğru "
               f"ilerliyor; bu etapta {f.final_leg_gain_m / 1000:.1f} km kapattı.",
               f"Yönelim sapması {_fmt(f.heading_offset_deg, '°')}, üsse {f.dist_now_m:.0f} m, son etap hızıyla "
               f"ETA ≈ {_fmt(f.final_leg_eta_min, ' dk', 1)}."]
        if intermediate_stops:
            out.append(f"Önceki {len(f.stops)} duraklama nedeniyle araç ara duraklı (olağan trafik) görünüyor; ancak son "
                       f"etap hızı olağan trafiğin üstünde (≥{th.dash_speed_mps:g} m/s). DIRECT_FAST_APPROACH ara durak "
                       "şartı nedeniyle bu aracı kaçırırdı.")
        if f.route_passes >= 2 and f.route_overlap_pct >= th.shuttle_min_overlap_pct and not f.on_route_now:
            prior = f.route_passes - (1 if f.dist_now_m <= th.shuttle_pass_near_m else 0)
            out.append(f"Öncesinde aynı hat üzerinden üs yakınından {prior} kez geçmişti; çekim anında hattın dışında "
                       "— hattan sapma. Rutin hat muafiyeti (ROUTINE_SHUTTLE) uygulanmadı.")
        return out

    def shuttle_reasons() -> list[str]:
        stop_d = [s.dist_to_base_m for s in f.stops]
        return [
            f"Otobüs aynı hattı izliyor: üs yakınından {f.route_passes} ayrı geçiş; noktaların "
            f"%{f.route_overlap_pct:.0f}'i hattın diğer seferleriyle aynı {th.shuttle_corridor_m:.0f} m'lik koridorda "
            "ve çekim anında hat üzerinde.",
            f"Üsse en yakın {f.dist_min_m:.0f} m ({f.dist_min_time}), çekim anında {f.dist_now_m:.0f} m; üssün "
            f"{th.shuttle_stop_clear_m / 1000:g} km'si içinde hiç durmadı"
            + (f", duraklamaları hat uçlarında (üsse ≥{min(stop_d) / 1000:.1f} km)." if stop_d else "."),
            "Rutin toplu taşıma örüntüsü: üs yakınından geçmek bu hattın parçası, tek başına tehdit sayılmadı. "
            "Hattan sapma, üs yakınında durma ya da ani hızlanma olursa muafiyet kalkar.",
        ]'''),
    ("before", "# 3) dışarıdan gelip üssün 1 km'si içine sokulma (gidiş-dönüş dahil)", '''\
        # 2b) duraklama / hat sapmasından sonra kesintisiz ve hızlı son etap. DIRECT_FAST_APPROACH ara durak şartı
        #     nedeniyle kaçırır; hız eşiği olağan trafiğin (≤~9.4 m/s) üstünde → mevcut araçların seviyesi değişmez.
        Rule("FAST_FINAL_APPROACH", "KRITIK", [
            Cond("yönelim sapması", f.heading_offset_deg, "<=", th.dash_heading_deg, "°", nd=0),
            moving,
            Cond("son etap ort. hızı", f.final_leg_speed_mps, ">=", th.dash_speed_mps, " m/s"),
            Cond("son etapta kapanan mesafe", f.final_leg_gain_m, ">=", th.approach_gain_m, " m", nd=0),
            Cond("son etap hızıyla ETA", f.final_leg_eta_min, "<=", th.critical_eta_min, " dk"),
        ], fast_final_reasons),
        # 2c) rutin hat aracı (servis otobüsü): üs yakınından geçmek hattının parçası → aşağıdaki yakınlık
        #     kurallarından muaf. Sapma / üs yakınında durma / ani hızlanma muafiyeti kaldırır.
        Rule("ROUTINE_SHUTTLE", "DUSUK", [
            Cond("otobüs sınıfı", bus, "true", soft=False),
            Cond("üs yakınından ayrı geçiş", f.route_passes, ">=", th.shuttle_min_passes, soft=False),
            Cond("hat tekrarı (aynı koridor)", f.route_overlap_pct, ">=", th.shuttle_min_overlap_pct, "%", nd=0),
            Cond("çekim anında hat üzerinde", f.on_route_now, "true", soft=False),
            Cond(f"üssün {th.shuttle_stop_clear_m / 1000:g} km'si içinde duraklama", near_stops, "==", 0, soft=False),
        ], shuttle_reasons),'''),
    ("replace_block", "def classify_tracked(f: TrackFeatures, th: Thresholds, heavy: bool = False)",
     "return _classify_low(f, th)", '''\
def classify_tracked(f: TrackFeatures, th: Thresholds, heavy: bool = False,
                     bus: bool = False) -> tuple[str, str, list[str]]:
    """(senaryo, risk, gerekçeler)"""
    for rule in _tracked_rules(f, th, heavy, bus):
        if rule.matches():
            return rule.scenario, rule.risk, rule.reasons() + _quality_notes(f, th)
    scen, risk, reasons = _classify_low(f, th)
    return scen, risk, reasons + _quality_notes(f, th)


def _quality_notes(f: TrackFeatures, th: Thresholds) -> list[str]:
    """Veri kalitesi notu: yüklemede ayıklanan GPS sıçramaları (yoksa boş)."""
    if not f.gps_outliers:
        return []
    spots = ", ".join(f"{o['time']} (üsse {o['dist_to_base_m']:.0f} m)" for o in f.gps_outliers)
    return [f"Veri kalitesi: {spots} örneği tek örneklik GPS sıçraması — araç ≥{th.gps_spike_min_speed_mps:g} m/s ile "
            "'zıplayıp' bir sonraki örnekte eski noktasına döndü (fiziksel olarak olanaksız). Nokta analizden "
            "çıkarıldı; yakınlık kurallarına girmedi."]'''),
    ("replace_block", "def tracked_margin(f: TrackFeatures, th: Thresholds, scenario: str, risk: str, heavy: bool = False)",
     "return _margin(drop, rise, max_risk(rise_levels) if rise_levels else None)", '''\
def tracked_margin(f: TrackFeatures, th: Thresholds, scenario: str, risk: str, heavy: bool = False,
                   bus: bool = False) -> dict:
    tol = th.margin_tol
    rules = _tracked_rules(f, th, heavy, bus)
    drop, rise, rise_levels = [], [], []
    matched = next((r for r in rules if r.scenario == scenario), None)
    if matched and risk != "DUSUK":
        drop = [f"{risk}'e kıl payı girdi: {c.describe()}" for c in matched.conds if c.barely(tol)]
    for r in rules:
        if _rank(r.risk) <= _rank(risk):
            continue
        misses = [c for c in r.conds if c.near_miss(tol)]
        if misses and all(c.ok() or c.near_miss(tol) for c in r.conds):
            rise.append(f"Neredeyse {r.risk} ({r.scenario}): " + "; ".join(c.describe() for c in misses))
            rise_levels.append(r.risk)
    # Muafiyet kuralı (ROUTINE_SHUTTLE, DUSUK): muafiyet olmasa hangi üst kural kazanırdı? Muafiyetin kendi
    # koşulu kıl payı sağlandıysa motor sınırdadır; LLM o seviyeye kadar gerekçeyle yükseltebilir.
    info = []
    if matched and matched.risk == "DUSUK":
        waived = next((r for r in rules if _rank(r.risk) > _rank(risk) and r.matches()), None)
        if waived:
            info.append(f"Muafiyet: rutin hat örüntüsü olmasa {waived.scenario} ({waived.risk}) olurdu.")
            shaky = [c for c in matched.conds if c.barely(tol)]
            if shaky:
                rise.append("Muafiyet kıl payı: " + "; ".join(c.describe() for c in shaky))
                rise_levels.append(waived.risk)
    out = _margin(drop, rise, max_risk(rise_levels) if rise_levels else None)
    out["notes"] = out["notes"] + info
    return out'''),
    ("replace", "def explain_tracked(f: TrackFeatures, th: Thresholds, heavy: bool = False) -> list[dict]:",
     "def explain_tracked(f: TrackFeatures, th: Thresholds, heavy: bool = False, bus: bool = False) -> list[dict]:"),
    ("replace", "for r in _tracked_rules(f, th, heavy):", "    for r in _tracked_rules(f, th, heavy, bus):"),
]

PIPELINE_OPS = [
    ("replace", "from .risk import (classify_tracked, classify_untracked, firm_margin, is_heavy, max_risk, tracked_margin,",
     "from .risk import (classify_tracked, classify_untracked, firm_margin, is_bus, is_heavy, max_risk, tracked_margin,"),
    ("after", "heavy = is_heavy(label, alt_labels, self.th.heavy_alt_min_conf)",
     "        bus = is_bus(label, alt_labels, self.th.heavy_alt_min_conf)   # ROUTINE_SHUTTLE için"),
    ("replace", "scen, risk, reasons = classify_tracked(f, self.th, heavy=heavy)",
     "            scen, risk, reasons = classify_tracked(f, self.th, heavy=heavy, bus=bus)"),
    ("replace", "margin = tracked_margin(f, self.th, scen, risk, heavy=heavy)",
     "            margin = tracked_margin(f, self.th, scen, risk, heavy=heavy, bus=bus)"),
]

FUSION_OPS = [
    ("after", '"M_OUTBOUND_FROM_BASE",',
     '    "M_ROUTINE_ROUTE",          # rutin hat (servis otobüsü) — motorun ROUTINE_SHUTTLE kuralıyla aynı olgu'),
    ("after", '"UNTRACKED": {"dist_now"},', '''\
    # Rutin hat: "üs yakınından geçti / şu an yakın / üsse yöneliyor / ETA kısa" olguları hattın parçasıdır. Yükseltme
    # için motorun görmediği ek bir olgu gerekir (hız, üs yakınında durma, tur...).
    "ROUTINE_SHUTTLE": {"dist_now", "dist_min", "radial", "H_APPROACH_THEN_RETREAT", "away", "eta", "C_SHORT_ETA"},'''),
    ("after", '2, "mitigating")', '''\
    # Rutin hat (servis otobüsü): aynı hattı ≥3 kez izledi, çekim anında hat üzerinde ve üs yakınında hiç durmadı.
    _th = settings.thresholds
    add("M_ROUTINE_ROUTE",
        veh.get("label") == "bus"
        and int(f.get("route_passes") or 0) >= _th.shuttle_min_passes
        and float(f.get("route_overlap_pct") or 0) >= _th.shuttle_min_overlap_pct
        and bool(f.get("on_route_now"))
        and not any(float(s.get("dist_to_base_m", 0)) <= _th.shuttle_stop_clear_m for s in stops),
        f"Otobüs aynı hattı izliyor: üs yakınından {int(f.get('route_passes') or 0)} geçiş, noktaların "
        f"%{float(f.get('route_overlap_pct') or 0):.0f}'i aynı koridorda, çekim anında hat üzerinde ve üssün "
        f"{_th.shuttle_stop_clear_m / 1000:g} km'si içinde hiç durmadı.", 2, "mitigating")'''),
    ("after", "counter_facts'e dürüstçe yaz — karşı kanıt skoru zaten katalogdaki tüm aktif anahtarlardan hesaplanır.", '''\
   Ek senaryolar: DIRECT_FAST_APPROACH / FAST_FINAL_APPROACH → KRITIK (FAST_FINAL_APPROACH: duraklama ya da hat
   sapmasından sonra kesintisiz ≥10 m/s son etap; önceki dur-kalklar olağan trafik görüntüsü verse de imminent).
   ROUTINE_SHUTTLE → DUSUK: otobüs aynı hattı ≥3 kez izlemiş, çekim anında hat üzerinde ve üs yakınında hiç durmamış
   (HISTORY.evidence.M_ROUTINE_ROUTE). Bu araçta üs yakınından geçiş/yaklaşma olguları hattın parçasıdır; yükseltme
   için hattan sapma, üs yakınında durma ya da hız gibi motorun görmediği ek bir olgu gerekir.'''),
]

AGENT_OPS = [
    ("after", "uzaklaşan araç çıkış trafiğidir (OUTBOUND). Motorun senaryo tanımları için get_risk_policy'ye bak.", '''\
   Otobüsün aynı hattı ≥3 kez izleyip üs yakınında hiç durmadan geçmesi rutin toplu taşımadır (ROUTINE_SHUTTLE →
   DUSUK). Buna karşılık duraklama ya da hattan sapmadan sonra kesintisiz ve hızlı (≥10 m/s) son etapla üsse yönelen
   araç imminent tehdittir (FAST_FINAL_APPROACH → KRITIK); önceki dur-kalklar onu olağan trafik yapmaz.'''),
    ("after", "noktada bekleme, çekim anında <=2 km, ağır araç, üs etrafında tur. Senaryo tanımları için get_risk_policy.",
     "   Aynı hattı düzenli izleyen otobüs (ROUTINE_SHUTTLE) rutindir; bekleme/hat sapması sonrası ani hızlı son etap\n"
     "   (FAST_FINAL_APPROACH) KRITIK'tir."),
]

THEME_OPS = [
    ("after", '"DIRECT_FAST_APPROACH": "Doğrudan hızlı yaklaşma",', '''\
    "FAST_FINAL_APPROACH": "Bekleme/hat sapması sonrası ani hızlı yaklaşma",
    "ROUTINE_SHUTTLE": "Rutin hat aracı (servis otobüsü)",'''),
    ("after", '"FILTERED_LOW_CONF": "Elendi",', '    "FAST_FINAL_APPROACH": "Ani son hamle", "ROUTINE_SHUTTLE": "Rutin hat",'),
]

COLLECT_OPS = [
    ("replace", "from ..risk import classify_tracked, explain_tracked, explain_untracked",
     "from ..risk import classify_tracked, explain_tracked, explain_untracked, is_bus"),
    # PDF'teki kural tablosu motorla aynı girdiyle çizilsin (ağır/otobüs bilgisi önceden bu çağrıya geçmiyordu)
    ("replace", 'facts["rules"] = explain_tracked(fobj, th)',
     '        facts["rules"] = explain_tracked(fobj, th, heavy=bool(v.get("heavy")),\n'
     '                                         bus=is_bus(v["label"], v.get("alt_labels"), th.heavy_alt_min_conf))'),
]

# (göreli yol, işlemler, "zaten uygulandı" işareti, zorunlu mu)
FILES = [
    ("app/config.py", CONFIG_OPS, "shuttle_min_passes", True),
    ("app/data.py", DATA_OPS, "drop_gps_spikes", True),
    ("app/tracking.py", TRACKING_OPS, "_route_pattern", True),
    ("app/risk.py", RISK_OPS, "ROUTINE_SHUTTLE", True),
    ("app/pipeline.py", PIPELINE_OPS, "is_bus", True),
    ("app/fusion.py", FUSION_OPS, "M_ROUTINE_ROUTE", True),
    ("app/agent.py", AGENT_OPS, "ROUTINE_SHUTTLE", True),
    ("app/threat_report/theme.py", THEME_OPS, "ROUTINE_SHUTTLE", False),
    ("app/threat_report/collect.py", COLLECT_OPS, "is_bus", False),
]


def _norm(s: str) -> str:
    return " ".join(s.split())


def _find(lines: list[str], anchor: str, start: int = 0) -> int:
    a = _norm(anchor)
    exact = [i for i in range(start, len(lines)) if _norm(lines[i]) == a]
    if len(exact) == 1:
        return exact[0]
    part = [i for i in range(start, len(lines)) if a in _norm(lines[i])]
    if len(exact) > 1 or len(part) != 1:
        n = len(exact) if len(exact) > 1 else len(part)
        raise LookupError(f"çapa {n} satıra uydu (1 olmalı): {anchor!r}")
    return part[0]


def patch_text(text: str, ops) -> str:
    lines = text.split("\n")
    for op in ops:
        kind, anchor = op[0], op[1]
        new = op[-1].split("\n")
        i = _find(lines, anchor)
        if kind == "after":
            lines[i + 1:i + 1] = new
        elif kind == "before":
            lines[i:i] = new
        elif kind == "replace":
            lines[i:i + 1] = new
        elif kind == "replace_block":
            j = _find(lines, op[2], i)
            lines[i:j + 1] = new
        else:
            raise ValueError(kind)
    return "\n".join(lines)


def plan_code(root: Path) -> tuple[list[tuple[Path, str, bool]], list[str], list[str]]:
    """(yazılacaklar, atlananlar, hatalar)."""
    todo, skipped, errors = [], [], []
    for rel, ops, marker, required in FILES:
        p = root / rel
        if not p.exists():
            (errors if required else skipped).append(f"{rel}: dosya yok" + ("" if required else " (isteğe bağlı, atlandı)"))
            continue
        raw = p.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        text = raw.replace("\r\n", "\n")
        if marker in text:
            skipped.append(f"{rel}: zaten uygulanmış")
            continue
        try:
            out = patch_text(text, ops)
        except LookupError as e:
            errors.append(f"{rel}: {e}")
            continue
        todo.append((p, out.replace("\n", "\r\n") if crlf else out, crlf))
    return todo, skipped, errors


# ============================================================================ veri
NEW_ROWS = [["T9999", "12:25", 39.928126, 32.909358], ["T9999", "12:30", 39.928143, 32.909332], ["T9999", "12:35", 39.928127, 32.909339], ["T9999", "12:40", 39.927972, 32.887547], ["T9999", "12:45", 39.927788, 32.86572], ["T9999", "12:50", 39.927607, 32.843902], ["T9999", "12:55", 39.927409, 32.822125], ["T9999", "13:00", 39.927224, 32.802649], ["T9999", "13:05", 39.927228, 32.802629], ["T9999", "13:10", 39.927227, 32.802642], ["T9999", "13:15", 39.92723, 32.802639], ["T9999", "13:20", 39.92735, 32.815736], ["T9999", "13:25", 39.927549, 32.837531], ["T9999", "13:30", 39.927747, 32.859344], ["T9999", "13:35", 39.927912, 32.881162], ["T9999", "13:40", 39.928097, 32.90295], ["T9999", "13:45", 39.928122, 32.909355], ["T9999", "13:50", 39.928141, 32.909343], ["T9999", "13:55", 39.928133, 32.909333], ["T9999", "14:00", 39.928041, 32.896273], ["T9999", "14:05", 39.927846, 32.874467], ["T9999", "14:10", 39.927682, 32.85263], ["T9999", "14:15", 39.927499, 32.830838], ["T9999", "14:20", 39.927303, 32.809005], ["T9999", "14:25", 39.927239, 32.802653], ["T9999", "14:30", 39.927231, 32.802637], ["T9999", "14:35", 39.927228, 32.802644], ["T9999", "14:40", 39.927354, 32.815712], ["T9999", "14:45", 39.927538, 32.837524], ["T9999", "14:50", 39.927742, 32.859334], ["T9999", "14:55", 39.927918, 32.881161], ["T9999", "15:00", 39.928075, 32.902947], ["T9999", "15:05", 39.928124, 32.90933], ["T9999", "15:10", 39.928135, 32.909359], ["T9999", "15:15", 39.928021, 32.896247], ["T9999", "15:20", 39.927856, 32.874451], ["T9998", "13:25", 39.927226, 32.802622], ["T9998", "13:30", 39.927229, 32.802627], ["T9998", "13:35", 39.927362, 32.81531], ["T9998", "13:40", 39.92753, 32.836395], ["T9998", "13:45", 39.927723, 32.857506], ["T9998", "13:50", 39.927901, 32.878627], ["T9998", "13:55", 39.928066, 32.89974], ["T9998", "14:00", 39.928129, 32.909349], ["T9998", "14:05", 39.928143, 32.909352], ["T9998", "14:10", 39.928132, 32.909348], ["T9998", "14:15", 39.927961, 32.888256], ["T9998", "14:20", 39.927808, 32.867122], ["T9998", "14:25", 39.92761, 32.846036], ["T9998", "14:30", 39.927444, 32.824929], ["T9998", "14:35", 39.927242, 32.803833], ["T9998", "14:40", 39.92724, 32.802648], ["T9998", "14:45", 39.927225, 32.80263], ["T9998", "14:50", 39.927309, 32.811065], ["T9998", "14:55", 39.927506, 32.832176], ["T9998", "15:00", 39.9277, 32.853274], ["T9998", "15:05", 39.927848, 32.8744], ["T9998", "15:10", 39.928023, 32.895501], ["T9998", "15:15", 39.928136, 32.909347], ["T9998", "15:20", 39.928143, 32.909335], ["T9998", "15:25", 39.928144, 32.909344], ["T9998", "15:30", 39.928137, 32.909349], ["T9998", "15:35", 39.923658, 32.869314], ["T9997", "14:10", 39.899348, 32.765104], ["T9997", "14:15", 39.883159, 32.770991], ["T9997", "14:20", 39.883176, 32.770988], ["T9997", "14:25", 39.883182, 32.77097], ["T9997", "14:30", 39.883177, 32.77099], ["T9997", "14:35", 39.883173, 32.770958], ["T9997", "14:40", 39.869686, 32.78504], ["T9997", "14:45", 39.869691, 32.785037], ["T9997", "14:50", 39.869686, 32.785051], ["T9997", "14:55", 39.869681, 32.785051], ["T9997", "15:00", 39.869684, 32.785041], ["T9997", "15:05", 39.869686, 32.785057], ["T9997", "15:10", 39.869679, 32.78505], ["T9997", "15:15", 39.869688, 32.785047], ["T9997", "15:20", 39.869682, 32.785045], ["T9997", "15:25", 39.891613, 32.813668], ["T9997", "15:30", 39.913558, 32.84226], ["T9996", "13:30", 39.954223, 32.888232], ["T9996", "13:35", 39.954223, 32.888248], ["T9996", "13:40", 39.954227, 32.888246], ["T9996", "13:45", 39.954221, 32.888255], ["T9996", "13:50", 39.954217, 32.888231], ["T9996", "13:55", 39.954213, 32.888236], ["T9996", "14:00", 39.954204, 32.888248], ["T9996", "14:05", 39.954212, 32.888253], ["T9996", "14:10", 39.954224, 32.888234], ["T9996", "14:15", 39.954223, 32.888235], ["T9996", "14:20", 39.954222, 32.888246], ["T9996", "14:25", 39.954211, 32.888233], ["T9996", "14:30", 39.954222, 32.888232], ["T9996", "14:35", 39.954211, 32.888239], ["T9996", "14:40", 39.923639, 32.854819], ["T9996", "14:45", 39.954221, 32.888224], ["T9996", "14:50", 39.954209, 32.888256], ["T9996", "14:55", 39.954213, 32.888222], ["T9996", "15:00", 39.954214, 32.88824], ["T9996", "15:05", 39.954215, 32.888248], ["T9996", "15:10", 39.954218, 32.888232], ["T9996", "15:15", 39.954214, 32.888242], ["T9996", "15:20", 39.95422, 32.888242], ["T9996", "15:25", 39.954206, 32.888234], ["T9996", "15:30", 39.954216, 32.888239]]
NEW_FRAMES = {
 "img_999999": {
  "width_px": 1360,
  "height_px": 765,
  "capture_time": "15:20",
  "corner_coordinates": {
   "top_left": [
    39.928528,
    32.873401
   ],
   "top_right": [
    39.928528,
    32.875901
   ],
   "bottom_left": [
    39.927328,
    32.873401
   ],
   "bottom_right": [
    39.927328,
    32.875901
   ]
  }
 },
 "img_999998": {
  "width_px": 1360,
  "height_px": 765,
  "capture_time": "15:35",
  "corner_coordinates": {
   "top_left": [
    39.92433,
    32.868264
   ],
   "top_right": [
    39.92433,
    32.870764
   ],
   "bottom_left": [
    39.92313,
    32.868264
   ],
   "bottom_right": [
    39.92313,
    32.870764
   ]
  }
 },
 "img_999997": {
  "width_px": 1360,
  "height_px": 765,
  "capture_time": "15:30",
  "corner_coordinates": {
   "top_left": [
    39.91423,
    32.84121
   ],
   "top_right": [
    39.91423,
    32.84371
   ],
   "bottom_left": [
    39.91303,
    32.84121
   ],
   "bottom_right": [
    39.91303,
    32.84371
   ]
  }
 },
 "img_999996": {
  "width_px": 1360,
  "height_px": 765,
  "capture_time": "15:30",
  "corner_coordinates": {
   "top_left": [
    39.954888,
    32.887189
   ],
   "top_right": [
    39.954888,
    32.889689
   ],
   "bottom_left": [
    39.953688,
    32.887189
   ],
   "bottom_right": [
    39.953688,
    32.889689
   ]
  }
 }
}
NEW_DETECTIONS = {"img_999999": [{"label": "bus", "confidence": 0.91, "bbox": [533, 420, 76, 16]}], "img_999998": [{"label": "bus", "confidence": 0.89, "bbox": [534, 417, 74, 22]}], "img_999997": [{"label": "car", "confidence": 0.87, "bbox": [558, 416, 26, 24]}], "img_999996": [{"label": "car", "confidence": 0.84, "bbox": [557, 422, 29, 12]}]}
IMG_HINTS = {"img_999999": [1.0, 0.0, "road"], "img_999998": [-0.989, 0.144, "road"], "img_999997": [0.707, -0.707, "road"], "img_999996": [0.0, 0.0, "park"]}


def plan_data(data: Path) -> tuple[list[tuple[Path, bytes]], list[str], list[str]]:
    todo, skipped, errors = [], [], []
    tracks = data / "tracks.csv"
    if not tracks.exists():
        return [], [], [f"{tracks}: yok (--data ile veri klasörünü verin)"]
    raw = tracks.read_bytes().decode("utf-8-sig")
    have = {r["track_id"] for r in csv.DictReader(io.StringIO(raw))}
    rows = [r for r in NEW_ROWS if r[0] not in have]
    if rows:
        nl = "\r\n" if "\r\n" in raw else "\n"
        buf = io.StringIO()
        csv.writer(buf, lineterminator=nl).writerows(rows)
        body = tracks.read_bytes()
        if body and not body.endswith(b"\n"):
            body += nl.encode()
        todo.append((tracks, body + buf.getvalue().encode("utf-8")))
    else:
        skipped.append("tracks.csv: T9996–T9999 zaten var")
    for name, new, indent in (("image_meta.json", NEW_FRAMES, 1), ("detections_sim.json", NEW_DETECTIONS, None)):
        p = data / name
        if not p.exists():
            errors.append(f"{p}: yok")
            continue
        obj = json.loads(p.read_text(encoding="utf-8-sig"))
        if not isinstance(obj, dict):
            errors.append(f"{name}: beklenen biçim {{id: ...}} sözlüğü")
            continue
        add = {k: v for k, v in new.items() if k not in obj}
        if not add:
            skipped.append(f"{name}: yeni kareler zaten var")
            continue
        obj.update(add)
        todo.append((p, json.dumps(obj, ensure_ascii=False, indent=indent).encode("utf-8")))
    return todo, skipped, errors


def draw_images(data: Path) -> list[str]:
    """SENTETİK yer tutucu kareler (Pillow yoksa atlanır). Mevcut dosyanın üzerine yazmaz."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return ["Pillow yok — yer tutucu görüntüler çizilmedi (arayüz görüntüsüz gösterir)."]
    import random
    out_dir = data / "images"
    out_dir.mkdir(exist_ok=True)
    notes = []
    for fid, meta in NEW_FRAMES.items():
        p = out_dir / f"{fid}.png"
        if any((out_dir / f"{fid}.{e}").exists() for e in ("png", "jpg", "jpeg")):
            continue
        w, h = meta["width_px"], meta["height_px"]
        rnd = random.Random(fid)
        im = Image.new("RGB", (w, h), (126, 138, 116))
        d = ImageDraw.Draw(im)
        for _ in range(60):   # tarla / çatı dokusu
            x, y = rnd.randrange(w), rnd.randrange(h)
            c = rnd.choice([(118, 130, 106), (140, 148, 124), (150, 142, 120), (110, 120, 100)])
            d.rectangle([x, y, x + rnd.randrange(60, 260), y + rnd.randrange(40, 180)], fill=c)
        det = NEW_DETECTIONS[fid][0]
        bx, by, bw, bh = det["bbox"]
        cx, cy = bx + bw / 2, by + bh / 2
        dx, dy, kind = IMG_HINTS[fid]
        if kind == "park":
            d.rectangle([cx - 160, cy - 70, cx + 160, cy + 70], fill=(96, 96, 96))
            for k in range(-150, 160, 40):
                d.line([cx + k, cy - 70, cx + k, cy - 30], fill=(220, 220, 220), width=2)
        else:
            L = 2 * (w + h)
            d.line([cx - dx * L, cy - dy * L, cx + dx * L, cy + dy * L], fill=(78, 78, 78), width=60)
            d.line([cx - dx * L, cy - dy * L, cx + dx * L, cy + dy * L], fill=(200, 200, 160), width=2)
        color = (235, 190, 40) if det["label"] == "bus" else (230, 230, 230)
        d.rectangle([bx, by, bx + bw, by + bh], fill=color, outline=(20, 20, 20), width=2)
        d.rectangle([0, 0, w, 28], fill=(29, 36, 51))
        d.text((10, 8), f"SENTETIK TEST KARESI - {fid} - {meta['capture_time']} - gercek goruntu degildir",
               fill=(255, 255, 255))
        im.save(p)
        notes.append(f"images/{fid}.png çizildi")
    return notes


# ============================================================================ ana akış
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repo kökü (app/ ve data/ burada)")
    ap.add_argument("--data", default=None, help="veri klasörü (varsayılan: $DATA_DIR ya da <root>/data)")
    ap.add_argument("--check", action="store_true", help="yalnız kontrol et, yazma")
    ap.add_argument("--no-images", action="store_true", help="yer tutucu görüntü çizme")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    data = Path(a.data or os.getenv("DATA_DIR") or root / "data").resolve()

    code_todo, code_skip, code_err = plan_code(root)
    data_todo, data_skip, data_err = plan_data(data)
    for s in code_skip + data_skip:
        print("  ·", s)
    if code_err or data_err:
        print("\nUYGULANMADI — şu çapalar/dosyalar tutmadı (hiçbir dosyaya yazılmadı):")
        for e in code_err + data_err:
            print("  ✗", e)
        return 1
    for p, _, crlf in code_todo:
        print(f"  ✓ {p.relative_to(root)} ({'CRLF' if crlf else 'LF'})")
    for p, _ in data_todo:
        print(f"  ✓ {p}")
    if a.check:
        print("\nKontrol tamam: hepsi uygulanabilir (--check nedeniyle yazılmadı).")
        return 0
    for p, text, _ in code_todo:
        bak = p.with_name(p.name + ".bak_edgecases")
        if not bak.exists():
            bak.write_bytes(p.read_bytes())
        p.write_bytes(text.encode("utf-8"))
    for p, body in data_todo:
        bak = p.with_name(p.name + ".bak_edgecases")
        if not bak.exists():
            bak.write_bytes(p.read_bytes())
        p.write_bytes(body)
    if not a.no_images:
        for n in draw_images(data):
            print("  ·", n)
    print("\nTamam. Sunucuyu yeniden başlatın (/api/reload KULLANMAYIN — LLM önbelleğini siler).")
    print("Arama: T9999 · T9998 · T9997 · T9996  —  kareler: img_999999 · img_999998 · img_999997 · img_999996")
    return 0


if __name__ == "__main__":
    sys.exit(main())
