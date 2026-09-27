"""Local metric projection and a radius-aware spatial hash for game map regions."""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from ..geo import EARTH_R


@dataclass(frozen=True)
class LocalProjection:
    lat0: float
    lon0: float

    @classmethod
    def from_coordinates(cls, coordinates: Iterable[tuple[float, float]]):
        values = list(coordinates)
        if not values:
            return cls(0.0, 0.0)
        return cls(sum(p[0] for p in values) / len(values),
                   sum(p[1] for p in values) / len(values))

    def project(self, lat: float, lon: float) -> tuple[float, float]:
        return (math.radians(lon - self.lon0) * EARTH_R * math.cos(math.radians(self.lat0)),
                math.radians(lat - self.lat0) * EARTH_R)

    def unproject(self, x: float, y: float) -> tuple[float, float]:
        return (self.lat0 + math.degrees(y / EARTH_R),
                self.lon0 + math.degrees(x / (EARTH_R * math.cos(math.radians(self.lat0)))))


class RadiusIndex:
    def __init__(self, radius_m: float):
        self.radius = radius_m
        self.cells: dict[tuple[int, int], list[str]] = defaultdict(list)
        self.points: dict[str, tuple[float, float]] = {}

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return math.floor(x / self.radius), math.floor(y / self.radius)

    def add(self, key: str, x: float, y: float) -> None:
        self.points[key] = (x, y)
        self.cells[self._key(x, y)].append(key)

    def nearby(self, x: float, y: float) -> list[tuple[float, str]]:
        cx, cy = self._key(x, y)
        found = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for key in self.cells.get((cx + dx, cy + dy), ()):
                    px, py = self.points[key]
                    distance = math.hypot(px - x, py - y)
                    if distance <= self.radius:
                        found.append((distance, key))
        return sorted(found)
