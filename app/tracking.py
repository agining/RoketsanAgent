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
    )


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)
