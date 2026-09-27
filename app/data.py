"""Veri yükleme. Formatlar case brief (slayt 13–14) ile aynı; gerçek veri gelince DATA_DIR değişir."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from .geo import angle_diff, bearing_deg, haversine_m, hhmm_to_min
from .config import settings


@dataclass
class TrackPoint:
    t: int      # gün içindeki dakika
    lat: float
    lon: float


@dataclass
class Track:
    track_id: str
    points: list[TrackPoint]
    outliers: list[TrackPoint] = field(default_factory=list)   # yüklemede ayıklanan GPS sıçramaları

    @property
    def t_start(self) -> int:
        return self.points[0].t

    @property
    def t_end(self) -> int:
        return self.points[-1].t

    def position_at(self, t: float) -> tuple[float, float] | None:
        """Doğrusal interpolasyon; iz penceresi dışındaysa None (README: ızgara dışı saatler için)."""
        pts = self.points
        if t < pts[0].t or t > pts[-1].t:
            return None
        for a, b in zip(pts, pts[1:]):
            if a.t <= t <= b.t:
                if b.t == a.t:
                    return a.lat, a.lon
                r = (t - a.t) / (b.t - a.t)
                return a.lat + r * (b.lat - a.lat), a.lon + r * (b.lon - a.lon)
        return pts[-1].lat, pts[-1].lon


@dataclass
class Zone:
    name: str
    lat: float
    lon: float
    bearing: float = 0.0
    dist_m: float = 0.0


@dataclass
class Dataset:
    base: dict
    zones: list[Zone]
    image_meta: dict
    tracks: dict[str, Track]
    reports: list[dict]
    raw_detections_path: Path

    # --- bölge atama: üsten kerterize göre sektör (README: bölgeler nokta değil koridor) ---
    def zone_of(self, lat: float, lon: float) -> str:
        b = bearing_deg(self.base["lat"], self.base["lon"], lat, lon)
        return min(self.zones, key=lambda z: angle_diff(z.bearing, b)).name

    def dist_to_base(self, lat: float, lon: float) -> float:
        return haversine_m(self.base["lat"], self.base["lon"], lat, lon)

    def bearing_from_base(self, lat: float, lon: float) -> float:
        return bearing_deg(self.base["lat"], self.base["lon"], lat, lon)


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


def load_dataset(data_dir: Path, th=None) -> Dataset:
    data_dir = Path(data_dir)
    th = th or settings.thresholds
    # utf-8-sig: dosya BOM'lu gelirse de okur, BOM'suz UTF-8'i de aynen okur
    zones_raw = json.loads((data_dir / "zones.json").read_text(encoding="utf-8-sig"))
    base = zones_raw["base"]
    zones = []
    for z in zones_raw["zones"]:
        lat, lon = z["center"]
        zones.append(Zone(
            name=z["name"], lat=lat, lon=lon,
            bearing=bearing_deg(base["lat"], base["lon"], lat, lon),
            dist_m=haversine_m(base["lat"], base["lon"], lat, lon),
        ))

    image_meta = json.loads((data_dir / "image_meta.json").read_text(encoding="utf-8-sig"))
    if isinstance(image_meta, list):  # [{"image_id": ..., ...}] biçimine de dayanıklı ol
        image_meta = {m.get("image_id") or m.get("id"): m for m in image_meta}

    tracks: dict[str, list[TrackPoint]] = {}
    with open(data_dir / "tracks.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            tracks.setdefault(row["track_id"], []).append(
                TrackPoint(hhmm_to_min(row["time"]), float(row["lat"]), float(row["lon"]))
            )
    track_objs = {}
    for tid, p in tracks.items():
        pts, spikes = drop_gps_spikes(sorted(p, key=lambda x: x.t), th)   # veri kalitesi: GPS sıçramaları
        track_objs[tid] = Track(tid, pts, spikes)

    reports = json.loads((data_dir / "field_reports.json").read_text(encoding="utf-8-sig"))
    if isinstance(reports, dict):  # {"reports": [...]} biçimine de dayanıklı ol
        reports = reports.get("reports") or next((v for v in reports.values() if isinstance(v, list)), [])
    for i, r in enumerate(reports):
        r.setdefault("id", f"R{i:03d}")

    return Dataset(
        base=base, zones=zones, image_meta=image_meta, tracks=track_objs,
        reports=reports, raw_detections_path=data_dir / "detections_sim.json",
    )
