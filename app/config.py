"""Merkezi ayarlar. Gerçek veri geldiğinde sadece DATA_DIR (veya .env'deki DATA_DIR) değişmeli."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Thresholds:
    # --- tespit ---
    min_confidence: float = 0.40          # altı düşük güvenli yanlış pozitif sayılır
    # --- iz eşleştirme ---
    match_radius_m: float = 5.0           # iz son noktası ↔ kutu merkezi (sapma <1 m + ±2 px jitter)
    track_end_tol_min: int = 5            # iz bu karede "bitiyor" sayılması için |t_end - t_cap| toleransı
    # --- duraklama ---
    stop_radius_m: float = 20.0           # README: 15–25 m arası
    stop_min_minutes: int = 15
    # --- yaklaşma ---
    approach_window_min: int = 60
    approach_min_m: float = 1500.0        # APPROACH_WITH_STOPS
    heading_toward_deg: float = 45.0      # üsse yönelim sayılacak açı
    fast_speed_mps: float = 7.0           # DIRECT_FAST_APPROACH
    critical_eta_min: float = 10.0
    # --- tur / devriye ---
    loiter_min_dist_m: float = 400.0
    loiter_max_dist_m: float = 3000.0
    loiter_max_extent_m: float = 900.0    # döngünün kapladığı alan (bbox köşegeni) üst sınırı
    patrol_radius_cv: float = 0.08        # üsse mesafe std/ort (sabit yarıçap)
    patrol_min_sweep_deg: float = 60.0    # üs etrafında taranan açı
    # --- izsiz araç ---
    untracked_heavy_m: float = 2500.0
    untracked_any_m: float = 1200.0
    # --- rapor doğrulama ---
    report_match_radius_m: float = 60.0   # rapor koordinatı ↔ araç
    report_time_tol_min: int = 10         # rapor saati ↔ çekim saati "aynı an" toleransı
    frame_margin_m: float = 15.0          # koordinat kare içinde mi kontrolünde pay


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", ROOT / "data")))
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", ROOT / "outputs")))
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    detector_backend: str = os.getenv("DETECTOR_BACKEND", "simulated")  # simulated | yolo
    yolo_weights: str | None = os.getenv("YOLO_WEIGHTS")
    thresholds: Thresholds = field(default_factory=Thresholds)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()

RISK_ORDER = ["DUSUK", "ORTA", "YUKSEK", "KRITIK"]
HEAVY_LABELS = {"truck", "bus"}
