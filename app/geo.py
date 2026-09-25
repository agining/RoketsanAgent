"""Coğrafi yardımcılar: mesafe, kerteriz, açı farkı, piksel→koordinat, saat dönüşümü."""
from __future__ import annotations

import math

EARTH_R = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """1. noktadan 2. noktaya kerteriz (0=Kuzey, 90=Doğu)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def angle_diff(a: float, b: float) -> float:
    """İki kerteriz arasındaki en küçük fark (0–180)."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def to_local_xy(lat: float, lon: float, lat0: float, lon0: float) -> tuple[float, float]:
    """Referans noktaya göre metre cinsinden (doğu, kuzey)."""
    x = math.radians(lon - lon0) * EARTH_R * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_R
    return x, y


def hhmm_to_min(t: str) -> int:
    h, m = t.strip().split(":")
    return int(h) * 60 + int(m)


def min_to_hhmm(m: int | float) -> str:
    m = int(round(m))
    return f"{m // 60:02d}:{m % 60:02d}"


def pixel_to_latlon(px: float, py: float, meta: dict) -> tuple[float, float]:
    """Eksen hizalı kare için doğrusal dönüşüm (README: köşe koordinatları eksen hizalı)."""
    c = meta["corner_coordinates"]
    top, bottom = c["top_left"][0], c["bottom_left"][0]
    left, right = c["top_left"][1], c["top_right"][1]
    lat = top - (py / meta["height_px"]) * (top - bottom)
    lon = left + (px / meta["width_px"]) * (right - left)
    return lat, lon


def bbox_center_latlon(bbox: list[float], meta: dict) -> tuple[float, float]:
    x, y, w, h = bbox  # [x_sol_ust, y_sol_ust, genişlik, yükseklik]
    return pixel_to_latlon(x + w / 2, y + h / 2, meta)


def frame_bounds(meta: dict) -> tuple[float, float, float, float]:
    """(lat_min, lat_max, lon_min, lon_max)"""
    c = meta["corner_coordinates"]
    lats = [c[k][0] for k in c]
    lons = [c[k][1] for k in c]
    return min(lats), max(lats), min(lons), max(lons)


def point_in_frame(lat: float, lon: float, meta: dict, margin_m: float = 0.0) -> bool:
    lat_min, lat_max, lon_min, lon_max = frame_bounds(meta)
    dlat = margin_m / 111_320.0
    dlon = margin_m / (111_320.0 * math.cos(math.radians(lat)))
    return (lat_min - dlat) <= lat <= (lat_max + dlat) and (lon_min - dlon) <= lon <= (lon_max + dlon)


def frame_center(meta: dict) -> tuple[float, float]:
    lat_min, lat_max, lon_min, lon_max = frame_bounds(meta)
    return (lat_min + lat_max) / 2, (lon_min + lon_max) / 2
