"""Veri yükleme. Formatlar case brief (slayt 13–14) ile aynı; gerçek veri gelince DATA_DIR değişir."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from .geo import angle_diff, bearing_deg, haversine_m, hhmm_to_min


@dataclass
class TrackPoint:
    t: int      # gün içindeki dakika
    lat: float
    lon: float


@dataclass
class Track:
    track_id: str
    points: list[TrackPoint]

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


def load_dataset(data_dir: Path) -> Dataset:
    data_dir = Path(data_dir)
    zones_raw = json.loads((data_dir / "zones.json").read_text(encoding="utf-8"))
    base = zones_raw["base"]
    zones = []
    for z in zones_raw["zones"]:
        lat, lon = z["center"]
        zones.append(Zone(
            name=z["name"], lat=lat, lon=lon,
            bearing=bearing_deg(base["lat"], base["lon"], lat, lon),
            dist_m=haversine_m(base["lat"], base["lon"], lat, lon),
        ))

    image_meta = json.loads((data_dir / "image_meta.json").read_text(encoding="utf-8"))

    tracks: dict[str, list[TrackPoint]] = {}
    with open(data_dir / "tracks.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tracks.setdefault(row["track_id"], []).append(
                TrackPoint(hhmm_to_min(row["time"]), float(row["lat"]), float(row["lon"]))
            )
    track_objs = {tid: Track(tid, sorted(p, key=lambda x: x.t)) for tid, p in tracks.items()}

    reports = json.loads((data_dir / "field_reports.json").read_text(encoding="utf-8"))
    for i, r in enumerate(reports):
        r.setdefault("id", f"R{i:03d}")

    return Dataset(
        base=base, zones=zones, image_meta=image_meta, tracks=track_objs,
        reports=reports, raw_detections_path=data_dir / "detections_sim.json",
    )
