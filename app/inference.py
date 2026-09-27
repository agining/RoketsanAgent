"""On-demand image inference, isolated from the dataset analysis pipeline."""
from __future__ import annotations

import io
import logging
import os
import time
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from PIL import Image, UnidentifiedImageError

from .config import ROOT, settings
from .detector import LABEL_MAP

log = logging.getLogger(__name__)
MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 16_000_000


class Detection(BaseModel):
    label: str
    confidence: float
    bbox: list[float]


class InferenceResult(BaseModel):
    model: str
    image_width: int
    image_height: int
    processing_ms: float
    detections: list[Detection]


class InferenceService:
    def __init__(self, weights: Path | None = None):
        self.weights = weights or Path(os.getenv('INFERENCE_WEIGHTS', str(ROOT / 'model' / 'yolo26x_custom.pt')))
        self.device = os.getenv('INFERENCE_DEVICE', 'cpu')
        self._model = None
        self._lock = Lock()

    def status(self):
        return {'model': self.weights.name, 'weights_available': self.weights.is_file(),
                'loaded': self._model is not None, 'busy': self._lock.locked(),
                'device': self.device, 'max_upload_bytes': MAX_BYTES,
                'supported_formats': ['JPEG', 'PNG'], 'bbox_format': 'xywh',
                'coordinate_unit': 'pixel'}

    def predict(self, payload: bytes, confidence: float, iou: float) -> InferenceResult:
        if not self._lock.acquire(blocking=False):
            raise HTTPException(429, 'Inference service is busy. Retry after the current request.', headers={'Retry-After': '5'})
        try:
            try:
                image = Image.open(io.BytesIO(payload))
                if image.format not in {'JPEG', 'PNG'}:
                    raise HTTPException(415, 'Only JPEG and PNG images are supported.')
                if image.width * image.height > MAX_PIXELS:
                    raise HTTPException(413, 'Image exceeds the 16 megapixel limit.')
                image.load()
                image = image.convert('RGB')
            except (UnidentifiedImageError, OSError, ValueError):
                raise HTTPException(422, 'Invalid or corrupted image.') from None
            except Image.DecompressionBombError:
                raise HTTPException(413, 'Image exceeds the pixel limit.') from None
            if self._model is None:
                if not self.weights.is_file():
                    raise HTTPException(503, 'Model weights are unavailable.')
                try:
                    config_dir = Path(os.environ.setdefault('YOLO_CONFIG_DIR', str(settings.output_dir / 'inference-runtime')))
                    (config_dir / 'Ultralytics').mkdir(parents=True, exist_ok=True)
                    from ultralytics import YOLO
                    self._model = YOLO(str(self.weights))
                except Exception:
                    log.exception('Unable to initialize inference model')
                    raise HTTPException(503, 'Inference model could not be initialized.') from None
            started = time.perf_counter()
            try:
                result = self._model.predict(source=image, conf=confidence, iou=iou,
                                             classes=[0, 1, 2, 3], device=self.device, verbose=False,
                                             save=False, stream=False)[0]
                detections = []
                if result.boxes is not None:
                    for box, conf, cls in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()):
                        x1, y1, x2, y2 = box
                        label = result.names[int(cls)].lower()
                        detections.append(Detection(label=LABEL_MAP.get(label, label), confidence=float(conf),
                                                    bbox=[x1, y1, x2 - x1, y2 - y1]))
                return InferenceResult(model=self.weights.name, image_width=image.width, image_height=image.height,
                                       processing_ms=round((time.perf_counter() - started) * 1000, 2), detections=detections)
            except Exception:
                log.exception('Image inference failed')
                raise HTTPException(500, 'Image inference failed.') from None
        finally:
            self._lock.release()


inference_service = InferenceService()
router = APIRouter(prefix='/api/inference', tags=['Vehicle Detection'])


@router.get('/status')
def inference_status():
    """Model availability and runtime state. Does not initialize the model."""
    return inference_service.status()


@router.post('/detect', response_model=InferenceResult, openapi_extra={
    'requestBody': {'required': True, 'content': {
        media: {'schema': {'type': 'string', 'format': 'binary'}} for media in ('image/jpeg', 'image/png')
    }}
})
async def detect_image(request: Request, confidence: float = Query(0.3, gt=0, le=1),
                       iou: float = Query(0.7, gt=0, le=1)):
    """Detect vehicles in an uploaded image. Send image bytes as the request body.

    Returns pixel bounding boxes in [x, y, width, height] format. Does not persist
    uploaded images or modify dataset records.
    """
    if request.headers.get('content-type', '').split(';')[0].strip().lower() not in {'image/jpeg', 'image/png'}:
        raise HTTPException(415, 'Content-Type must be image/jpeg or image/png.')
    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, 'Upload exceeds the 15 MB limit.')
        payload.extend(chunk)
    if not payload:
        raise HTTPException(422, 'Image body is empty.')
    return await run_in_threadpool(inference_service.predict, bytes(payload), confidence, iou)
