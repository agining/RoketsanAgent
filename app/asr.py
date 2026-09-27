"""Türkçe konuşma → metin (openai/whisper-small) REST uçları (api.py'ye `app.include_router(router)` ile bağlanır).

  POST /api/asr/start        → modeli yükler (ilk seferde Hugging Face'ten indirir); yüklüyse hemen döner
  GET  /api/asr/status       → {"loaded": bool, "loading": bool, "model": ..., "device": ...}
  POST /api/asr/transcribe   ← ham ses gövdesi (Content-Type: audio/wav önerilir)  → {"text": "...", ...}

Transcribe gövdesi dosyanın kendisidir (multipart değil):
  fetch('/api/asr/transcribe', {method: 'POST', headers: {'Content-Type': 'audio/wav'}, body: wavBlob})
WAV (PCM 8/16/32 bit, herhangi bir örnekleme hızı) doğrudan çözülür; diğer biçimler (webm, ogg, mp3 …)
transformers üzerinden ffmpeg ile çözülür, bu yüzden sistemde ffmpeg kurulu olmalıdır.
Model yüklenmeden transcribe çağrılırsa 409 döner.
"""
from __future__ import annotations

import io
import logging
import os
import threading
import time
import wave

import numpy as np
from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

log = logging.getLogger(__name__)

MODEL_ID = os.getenv("ASR_MODEL", "openai/whisper-small")
LANGUAGE = os.getenv("ASR_LANGUAGE", "turkish")
SAMPLE_RATE = 16_000                      # Whisper'ın beklediği örnekleme hızı
MAX_AUDIO_BYTES = 25 * 1024 * 1024

router = APIRouter(prefix="/api/asr", tags=["Konuşma → metin (Whisper)"])


class _Whisper:
    """Tek bir paylaşılan pipeline. Yükleme ve çıkarım kilitle sıralanır (model iş parçacığı güvenli değil)."""

    def __init__(self) -> None:
        self.pipe = None
        self.device = None
        self.loading = False
        self._load_lock = threading.Lock()
        self._run_lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self.pipe is not None

    def status(self) -> dict:
        return {"loaded": self.loaded, "loading": self.loading, "model": MODEL_ID,
                "language": LANGUAGE, "device": self.device}

    def load(self) -> dict:
        with self._load_lock:
            if self.pipe is None:
                self.loading = True
                try:
                    import torch
                    from transformers import pipeline

                    cuda = torch.cuda.is_available()
                    t0 = time.perf_counter()
                    self.pipe = pipeline(
                        "automatic-speech-recognition", model=MODEL_ID,
                        device=0 if cuda else -1, torch_dtype=torch.float16 if cuda else torch.float32,
                    )
                    self.device = "cuda" if cuda else "cpu"
                    log.info("ASR modeli yüklendi: %s (%s, %.1f s)", MODEL_ID, self.device, time.perf_counter() - t0)
                finally:
                    self.loading = False
        return self.status()

    def transcribe(self, audio: np.ndarray | bytes) -> str:
        with self._run_lock:
            inputs = {"raw": audio, "sampling_rate": SAMPLE_RATE} if isinstance(audio, np.ndarray) else audio
            out = self.pipe(inputs, chunk_length_s=30, batch_size=4,
                            generate_kwargs={"language": LANGUAGE, "task": "transcribe"})
        return out["text"].strip()


whisper = _Whisper()


def _decode_wav(data: bytes) -> np.ndarray:
    """PCM WAV → 16 kHz mono float32 [-1, 1]."""
    with wave.open(io.BytesIO(data)) as w:
        width, channels, rate = w.getsampwidth(), w.getnchannels(), w.getframerate()
        frames = w.readframes(w.getnframes())
    if width == 1:
        pcm = (np.frombuffer(frames, np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        pcm = np.frombuffer(frames, "<i2").astype(np.float32) / 32768
    elif width == 4:
        pcm = np.frombuffer(frames, "<i4").astype(np.float32) / 2147483648
    else:
        raise ValueError(f"desteklenmeyen WAV örnek genişliği: {width * 8} bit")
    pcm = pcm.reshape(-1, channels).mean(axis=1)
    if rate != SAMPLE_RATE and len(pcm):
        n = int(round(len(pcm) * SAMPLE_RATE / rate))
        pcm = np.interp(np.linspace(0, len(pcm) - 1, n), np.arange(len(pcm)), pcm).astype(np.float32)
    return pcm


@router.get("/status")
def asr_status():
    return whisper.status()


@router.post("/start")
def asr_start():
    """Modeli belleğe alır. İlk çağrı indirme + yükleme nedeniyle uzun sürebilir; sonrakiler anında döner."""
    try:
        return whisper.load()
    except Exception as e:  # indirme / bellek hataları arayüze okunur bir mesajla gitsin
        log.exception("ASR modeli yüklenemedi")
        raise HTTPException(500, f"ASR modeli yüklenemedi: {e}") from e


@router.post("/transcribe")
async def asr_transcribe(request: Request):
    """Ham ses gövdesini Türkçe metne çevirir. Önce POST /api/asr/start ile model yüklenmiş olmalı."""
    if not whisper.loaded:
        raise HTTPException(409, "ASR modeli yüklü değil; önce POST /api/asr/start çağırın.")
    data = await request.body()
    if not data:
        raise HTTPException(400, "Ses verisi boş.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, f"Ses dosyası çok büyük (en fazla {MAX_AUDIO_BYTES // (1024 * 1024)} MB).")

    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        try:
            audio: np.ndarray | bytes = _decode_wav(data)
        except (wave.Error, ValueError) as e:
            raise HTTPException(400, f"WAV çözülemedi: {e}") from e
        duration = len(audio) / SAMPLE_RATE
        if duration < 0.1:
            return {"text": "", "duration_s": round(duration, 2), "elapsed_s": 0.0}
    else:
        audio, duration = data, None      # ffmpeg ile çözülür (transformers)

    t0 = time.perf_counter()
    try:
        text = await run_in_threadpool(whisper.transcribe, audio)
    except Exception as e:
        log.exception("ASR çözümlemesi başarısız")
        raise HTTPException(500, f"Ses metne çevrilemedi: {e}") from e
    return {"text": text, "duration_s": round(duration, 2) if duration is not None else None,
            "elapsed_s": round(time.perf_counter() - t0, 2)}
