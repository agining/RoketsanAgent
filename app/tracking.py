"""İz eşleştirme ve davranış öznitelikleri (mesafe trendi, yaklaşma hızı, duraklamalar,
üsse yönelim açısı, ETA, tur/devriye göstergeleri)."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

from .config import Thresholds
from .data import Dataset, Track
from .geo import angle_diff, bearing_deg, haversine_m, min_to_hhmm, to_local_xy


# ---------------------------------------------------------------- eşleştirme
def match_track(ds: Dataset, lat: float, lon: float, t_capture: int, radius_m: float,
                exclude: set[str] | None = None) -> tuple[str | None, float | None]:
    """Çekim anında (lat,lon)'a en yakın izi bulur. README: kare araçlarının izleri çekim anında
    kutu merkezinde biter; ızgara dışı saat için interpolasyon kullanılır."""
    best, best_d = None, None
    for tid, tr in ds.tracks.items():
        if exclude and tid in exclude:
            continue
        pos = tr.position_at(t_capture)
        if pos is None:
            continue
        d = haversine_m(lat, lon, *pos)
        if d <= radius_m and (best_d is None or d < best_d):
            best, best_d = tid, d
    return best, best_d


def tracks_in_frame_at(ds: Dataset, meta: dict, t_capture: int, margin_m: float = 0.0) -> list[str]:
    """Çekim anında karenin içinde olan izler (kaçırılmış tespitleri yakalamak için)."""
    from .geo import point_in_frame
    out = []
    for tid, tr in ds.tracks.items():
        pos = tr.position_at(t_capture)
        if pos and point_in_frame(pos[0], pos[1], meta, margin_m):
            out.append(tid)
    return out


# ---------------------------------------------------------------- öznitelikler
@dataclass
class StopEvent:
    start: str
    end: str
    minutes: int
    lat: float
    lon: float
    dist_to_base_m: float


@dataclass
class TrackFeatures:
    track_id: str
    t_start: str
    t_end: str
    dist_now_m: float
    dist_start_m: float
    dist_min_m: float
    dist_max_m: float
    approach_total_m: float          # pencere başı - şimdi (pozitif = yaklaştı)
    approach_last60_m: float | None  # 60 dk önce - şimdi
    closing_speed_mps: float         # son 15 dk'daki mesafe azalma hızı
    speed_now_mps: float             # son 10 dk ortalama yer hızı
    max_speed_mps: float
    heading_deg: float | None        # son hareket yönü
    bearing_to_base_deg: float
    heading_offset_deg: float | None  # 0 = tam üsse doğru
    eta_min: float | None
    stops: list[StopEvent] = field(default_factory=list)
    stops_last60: int = 0
    stopped_minutes_total: int = 0
    moving_now: bool = False
    path_length_m: float = 0.0
    net_displacement_m: float = 0.0
    extent_m: float = 0.0            # izin kapladığı alanın köşegeni
    radius_cv: float = 0.0           # üsse mesafe std/ort
    angular_sweep_deg: float = 0.0   # üs etrafında taranan toplam açı
    dist_trend: str = ""             # "azaliyor" / "artiyor" / "once_azalip_sonra_artiyor" / "sabit"
    initial_wait_min: int = 0        # başlangıçtaki hareketsiz süre
    # --- gidiş-dönüş / yakınlık öznitelikleri (hepsi t_ref'e kadar olan noktalardan; gelecek sızıntısı yok)
    window_min: int = 0              # izin t_ref'e kadar kapsadığı süre
    dist_min_time: str = ""          # üsse en yakın olunan an
    approach_to_min_m: float = 0.0   # başlangıç − en yakın mesafe (dışarıdan ne kadar sokuldu)
    retreat_from_min_m: float = 0.0  # şimdi − en yakın mesafe (en yakın noktadan ne kadar geri çekildi)
    dwell_near_min_min: int = 0      # en yakın noktanın dwell_band_m bandında geçen süre
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
    gps_outliers: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, float):
                d[k] = round(v, 1)
        return d


def _stop_events(tr: Track, ds: Dataset, th: Thresholds) -> list[StopEvent]:
    """Bir çapa noktası etrafında stop_radius_m içinde kalan ardışık noktalar = duraklama."""
    pts, events, i = tr.points, [], 0
    while i < len(pts):
        j = i
        while j + 1 < len(pts) and haversine_m(pts[i].lat, pts[i].lon, pts[j + 1].lat, pts[j + 1].lon) <= th.stop_radius_m:
            j += 1
        dur = pts[j].t - pts[i].t
        if dur >= th.stop_min_minutes:
            lat = sum(p.lat for p in pts[i:j + 1]) / (j - i + 1)
            lon = sum(p.lon for p in pts[i:j + 1]) / (j - i + 1)
            events.append(StopEvent(min_to_hhmm(pts[i].t), min_to_hhmm(pts[j].t), dur, round(lat, 6),
                                    round(lon, 6), round(ds.dist_to_base(lat, lon), 1)))
            i = j + 1
        else:
            i += 1
    return events


def compute_features(tr: Track, ds: Dataset, th: Thresholds, t_ref: int | None = None) -> TrackFeatures:
    """t_ref (genelde çekim anı) itibarıyla öznitelikler. İz t_ref'ten sonra devam ediyorsa kesilir."""
    pts = [p for p in tr.points if t_ref is None or p.t <= t_ref]
    if len(pts) < 2:
        pts = tr.points[:2]
    sub = Track(tr.track_id, pts)
    blat, blon = ds.base["lat"], ds.base["lon"]
    dists = [haversine_m(blat, blon, p.lat, p.lon) for p in pts]
    now = pts[-1]

    seg = [haversine_m(a.lat, a.lon, b.lat, b.lon) for a, b in zip(pts, pts[1:])]
    seg_speed = [s / max((b.t - a.t) * 60, 1) for s, a, b in zip(seg, pts, pts[1:])]

    def dist_at(dt_min: int) -> float | None:
        pos = sub.position_at(now.t - dt_min)
        return haversine_m(blat, blon, *pos) if pos else None

    d60 = dist_at(th.approach_window_min)
    d15 = dist_at(15) or dists[0]
    closing = (d15 - dists[-1]) / (15 * 60) if d15 is not None else 0.0

    # son hareket yönü: son 15 dk içinde anlamlı yer değiştirme varsa
    heading = None
    for back in (5, 10, 15, 20):
        pos = sub.position_at(now.t - back)
        if pos and haversine_m(pos[0], pos[1], now.lat, now.lon) > th.stop_radius_m:
            heading = bearing_deg(pos[0], pos[1], now.lat, now.lon)
            break
    btb = bearing_deg(now.lat, now.lon, blat, blon)
    offset = angle_diff(heading, btb) if heading is not None else None

    pos10 = sub.position_at(now.t - 10)
    speed_now = haversine_m(pos10[0], pos10[1], now.lat, now.lon) / 600 if pos10 else (seg_speed[-1] if seg_speed else 0)
    moving_now = speed_now * 600 > th.stop_radius_m

    eta = None
    if moving_now and closing > 0.5 and (offset is None or offset <= th.heading_toward_deg):
        eta = dists[-1] / closing / 60

    stops = _stop_events(sub, ds, th)
    stops_last60 = sum(1 for s in stops if _hhmm(s.end) >= now.t - th.approach_window_min)

    # geometri
    xy = [to_local_xy(p.lat, p.lon, blat, blon) for p in pts]
    xs, ys = [a for a, _ in xy], [b for _, b in xy]
    extent = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
    mean_d = sum(dists) / len(dists)
    cv = (sum((d - mean_d) ** 2 for d in dists) / len(dists)) ** 0.5 / max(mean_d, 1)
    angs = [math.degrees(math.atan2(x, y)) for x, y in xy]
    sweep = sum(abs(((b - a + 180) % 360) - 180) for a, b in zip(angs, angs[1:]))

    # mesafe trendi
    i_min = min(range(len(dists)), key=dists.__getitem__)
    span = max(dists) - min(dists)
    if span < 100:
        trend = "sabit"
    elif 0 < i_min < len(dists) - 1 and dists[0] - dists[i_min] > 200 and dists[-1] - dists[i_min] > 200:
        trend = "once_azalip_sonra_artiyor"
    elif dists[-1] < dists[0]:
        trend = "azaliyor"
    else:
        trend = "artiyor"

    initial_wait = stops[0].minutes if stops and stops[0].start == min_to_hhmm(pts[0].t) else 0

    # en yakın nokta çevresinde geçen süre: iki ucu da bantta olan ardışık örnek aralıklarının toplamı
    band = dists[i_min] + th.dwell_band_m
    dwell = sum(b.t - a.t for a, b, da, db in zip(pts, pts[1:], dists, dists[1:]) if da <= band and db <= band)

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
                for p in getattr(tr, "outliers", []) if t_ref is None or p.t <= t_ref]

    return TrackFeatures(
        track_id=tr.track_id, t_start=min_to_hhmm(pts[0].t), t_end=min_to_hhmm(now.t),
        dist_now_m=dists[-1], dist_start_m=dists[0], dist_min_m=min(dists), dist_max_m=max(dists),
        approach_total_m=dists[0] - dists[-1],
        approach_last60_m=(d60 - dists[-1]) if d60 is not None else None,
        closing_speed_mps=closing, speed_now_mps=speed_now, max_speed_mps=max(seg_speed or [0]),
        heading_deg=heading, bearing_to_base_deg=btb, heading_offset_deg=offset, eta_min=eta,
        stops=stops, stops_last60=stops_last60, stopped_minutes_total=sum(s.minutes for s in stops),
        moving_now=moving_now, path_length_m=sum(seg),
        net_displacement_m=haversine_m(pts[0].lat, pts[0].lon, now.lat, now.lon),
        extent_m=extent, radius_cv=cv, angular_sweep_deg=sweep, dist_trend=trend,
        initial_wait_min=initial_wait,
        window_min=now.t - pts[0].t, dist_min_time=min_to_hhmm(pts[i_min].t),
        approach_to_min_m=dists[0] - dists[i_min], retreat_from_min_m=dists[-1] - dists[i_min],
        dwell_near_min_min=dwell,
        route_passes=passes, route_overlap_pct=overlap_pct, on_route_now=on_route,
        final_leg_start=min_to_hhmm(leg_t0), final_leg_min=leg_min, final_leg_gain_m=leg_gain,
        final_leg_speed_mps=leg_speed, final_leg_eta_min=leg_eta, gps_outliers=outliers,
    )


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


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)
