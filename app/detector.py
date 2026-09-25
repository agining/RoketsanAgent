"""Tespit katmanı. 1. aşama modeli hazır olana kadar SimulatedDetector, detections_sim.json'u
gerçek model çıktısıymış gibi döndürür. Model geldiğinde DETECTOR_BACKEND=yolo yapmak yeterli;
pipeline'ın geri kalanı değişmez."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from .config import settings

# Kaggle / YOLO sınıf adlarını pipeline'ın kullandığı 4 sınıfa indirger
LABEL_MAP = {
    "car": "car", "automobile": "car", "otomobil": "car",
    "van": "van", "panelvan": "van",
    "truck": "truck", "kamyon": "truck",
    "bus": "bus", "otobus": "bus",
}


class BaseDetector(ABC):
    name: str = "base"

    @abstractmethod
    def detect(self, image_id: str, image_path: Path | None = None) -> list[dict]:
        """[{label, confidence, bbox:[x,y,w,h]}] döndürür (brief'teki format)."""


class SimulatedDetector(BaseDetector):
    name = "simulated"

    def __init__(self, path: Path):
        self._cache = json.loads(Path(path).read_text(encoding="utf-8"))

    def detect(self, image_id: str, image_path: Path | None = None) -> list[dict]:
        return [
            {**d, "label": LABEL_MAP.get(d["label"].lower(), d["label"].lower())}
            for d in self._cache.get(image_id, [])
        ]


class YoloDetector(BaseDetector):
    """Ultralytics YOLO sarmalayıcısı. Ağırlık dosyası YOLO_WEIGHTS ile verilir."""
    name = "yolo"

    def __init__(self, weights: str, images_dir: Path):
        from ultralytics import YOLO  # opsiyonel bağımlılık
        self.model = YOLO(weights)
        self.images_dir = Path(images_dir)

    def detect(self, image_id: str, image_path: Path | None = None) -> list[dict]:
        path = image_path or next(self.images_dir.glob(f"{image_id}.*"))
        res = self.model(str(path), verbose=False)[0]
        out = []
        for box, conf, cls in zip(res.boxes.xywh.tolist(), res.boxes.conf.tolist(), res.boxes.cls.tolist()):
            cx, cy, w, h = box
            label = res.names[int(cls)].lower()
            out.append({
                "label": LABEL_MAP.get(label, label),
                "confidence": round(float(conf), 3),
                "bbox": [cx - w / 2, cy - h / 2, w, h],
            })
        return out


def build_detector(raw_detections_path: Path, data_dir: Path) -> BaseDetector:
    if settings.detector_backend == "yolo":
        if not settings.yolo_weights:
            raise RuntimeError("DETECTOR_BACKEND=yolo için YOLO_WEIGHTS tanımlanmalı")
        return YoloDetector(settings.yolo_weights, Path(data_dir) / "images")
    return SimulatedDetector(raw_detections_path)
