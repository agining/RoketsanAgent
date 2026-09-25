import csv
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "mock_data"


def load_json(filename: str):
    path = DATA_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_detections():
    data = load_json("detections.json")

    if not isinstance(data, list):
        raise ValueError("detections.json liste olmalı")

    for item in data:
        if "image_id" not in item:
            raise ValueError("Detection içinde image_id eksik")

        if "detections" not in item:
            raise ValueError(
                f"{item.get('image_id')} için detections eksik"
            )

    return data


def load_image_meta():
    data = load_json("image_meta.json")

    if not isinstance(data, dict):
        raise ValueError("image_meta.json obje/dict olmalı")

    for image_id, meta in data.items():
        required = [
            "width_px",
            "height_px",
            "capture_time",
            "corner_coordinates",
        ]

        for field in required:
            if field not in meta:
                raise ValueError(
                    f"{image_id} metadata içinde {field} eksik"
                )

        corners = meta["corner_coordinates"]

        required_corners = [
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
        ]

        for corner in required_corners:
            if corner not in corners:
                raise ValueError(
                    f"{image_id} içinde {corner} eksik"
                )

    return data


def load_zones():
    data = load_json("zones.json")

    if "base" not in data:
        raise ValueError("zones.json içinde base eksik")

    if "zones" not in data:
        raise ValueError("zones.json içinde zones eksik")

    base = data["base"]

    for field in ["name", "lat", "lon"]:
        if field not in base:
            raise ValueError(
                f"zones.json base içinde {field} eksik"
            )

    for zone in data["zones"]:
        if "name" not in zone:
            raise ValueError("Zone içinde name eksik")

        if "center" not in zone:
            raise ValueError(
                f"{zone.get('name')} için center eksik"
            )

    return data


def load_reports():
    data = load_json("field_reports.json")

    if not isinstance(data, list):
        raise ValueError("field_reports.json liste olmalı")

    for report in data:
        for field in ["time", "source", "text"]:
            if field not in report:
                raise ValueError(
                    f"Field report içinde {field} eksik"
                )

    return data


def load_tracks():
    path = DATA_DIR / "tracks.csv"

    if not path.exists():
        raise FileNotFoundError(f"Dosya bulunamadı: {path}")

    rows = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required = {"track_id", "time", "lat", "lon"}

        if not required.issubset(reader.fieldnames or []):
            raise ValueError(
                "tracks.csv kolonları "
                "track_id,time,lat,lon olmalı"
            )

        for row in reader:
            rows.append({
                "track_id": row["track_id"],
                "time": row["time"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
            })

    return rows