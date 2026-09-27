"""Merkezi ayarlar. Gerçek veri geldiğinde sadece DATA_DIR (veya .env'deki DATA_DIR) değişmeli."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(value, minimum) if minimum is not None else value


def _env_float(name: str, default: float, minimum: float | None = None) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(value, minimum) if minimum is not None else value


@dataclass(frozen=True)
class Thresholds:
    # --- tespit ---
    min_confidence: float = 0.40          # altı düşük güvenli yanlış pozitif sayılır ...
    low_conf_floor: float = 0.25          # ... ama bu değerin üstündeyse ve çekim anında bir iz aynı noktadaysa kabul edilir
    duplicate_iou: float = 0.50           # aynı karede bu IoU'nun üstündeki kutular (sınıftan bağımsız) tek nesnedir
    heavy_alt_min_conf: float = 0.50      # birleştirilen kopya kutudaki ağır etiket bu güvenin üstündeyse araç ağır sayılır
    # --- iz eşleştirme ---
    match_radius_m: float = 5.0           # iz son noktası ↔ kutu merkezi (sapma <1 m + ±2 px jitter)
    # --- duraklama ---
    stop_radius_m: float = 20.0           # README: 15–25 m arası
    stop_min_minutes: int = 15
    # --- yaklaşma ---
    approach_window_min: int = 60
    heading_toward_deg: float = 45.0      # üsse yönelim sayılacak açı
    fast_speed_mps: float = 7.0           # DIRECT_FAST_APPROACH
    critical_eta_min: float = 10.0
    approach_gain_m: float = 1500.0       # "dışarıdan geldi" sayılacak asgari yaklaşma (başlangıç − en yakın / şimdi)
    close_approach_m: float = 1000.0      # CLOSE_APPROACH: üsse bu mesafenin içine sokuldu
    near_pass_m: float = 1500.0           # NEAR_PASS: bu mesafenin içinden geçti
    near_arrival_m: float = 2000.0        # NEAR_BASE_ARRIVAL / HEAVY_NEAR_APPROACH: çekim anında üsse bu kadar yakın
    heavy_watch_m: float = 3000.0         # HEAVY_APPROACH: ağır araç bu halkanın içinde
    approaching_max_dist_m: float = 2000.0  # APPROACHING (ORTA) yalnız yakın halkada; dışı olağan radyal trafik
    dwell_band_m: float = 250.0           # en yakın nokta çevresinde bekleme süresi ölçülürken kullanılan bant
    # --- tur / devriye ---
    loiter_min_dist_m: float = 400.0
    loiter_max_dist_m: float = 3000.0
    loiter_max_extent_m: float = 1500.0   # döngünün kapladığı alan (bbox köşegeni) üst sınırı
    loiter_min_path_m: float = 500.0      # park halindeki GPS titreşimi döngü sayılmasın
    patrol_radius_cv: float = 0.03        # üsse mesafe std/ort (sabit yarıçap)
    patrol_min_sweep_deg: float = 90.0    # üs etrafında taranan açı
    patrol_near_m: float = 2000.0         # bu mesafenin içindeki devriye/tur ORTA, dışı DUSUK
    # --- durağan / çıkış ---
    static_max_path_m: float = 150.0      # tüm pencere boyunca toplam yol bundan kısaysa araç durağan
    static_min_window_min: int = 90       # durağanlık en az bu kadar süre gözlenmiş olmalı
    static_near_m: float = 3000.0         # STATIC_NEAR_BASE halkası
    outbound_start_m: float = 1200.0      # iz üsse bu mesafe içinde başladıysa ...
    outbound_min_gain_m: float = 500.0    # ... ve en az bu kadar uzaklaştıysa: üsten çıkış trafiği
    # --- izsiz araç ---
    untracked_heavy_m: float = 2500.0
    untracked_any_m: float = 1200.0
    # --- rapor doğrulama ---
    report_match_radius_m: float = 60.0   # rapor koordinatı ↔ araç
    report_time_tol_min: int = 10         # rapor saati ↔ çekim saati "aynı an" toleransı
    frame_margin_m: float = 15.0          # koordinat kare içinde mi kontrolünde pay
    # --- motor güveni (ortak karar) ---
    margin_tol: float = 0.10              # değer eşiğin bu oranda yakınındaysa motor "sınırda" sayılır
    # --- rutin hat aracı / servis otobüsü (ROUTINE_SHUTTLE) ---
    shuttle_pass_near_m: float = 1500.0   # bu halkaya her giriş bir "üs yakınından geçiş" sayılır
    shuttle_pass_reset_m: float = 1000.0  # yeni geçiş için halkanın en az bu kadar dışına çıkılmış olmalı
    shuttle_min_passes: int = 3           # aynı hattan en az bu kadar geçiş
    shuttle_corridor_m: float = 120.0     # "aynı hat" koridoru (şerit + GPS sapması)
    shuttle_min_overlap_pct: float = 80.0  # iz noktalarının bu yüzdesi hattın başka bir seferiyle aynı koridorda
    shuttle_route_gap_min: int = 30       # örtüşme sayılması için iki sefer arasında en az bu kadar dakika
    shuttle_stop_clear_m: float = 2500.0  # bu mesafe içinde hiç duraklama olmamalı (üs yakınında beklemez)
    # --- duraklama / hat sapması sonrası ani hızlı son etap (FAST_FINAL_APPROACH) ---
    dash_speed_mps: float = 10.0          # son etap ort. hızı; bu veride olağan trafik ≤ ~9.4 m/s
    dash_heading_deg: float = 30.0        # son etapta üsse yönelim (DIRECT_FAST_APPROACH'tan sıkı)
    # --- veri kalitesi: tek örneklik GPS sıçraması ---
    gps_spike_min_speed_mps: float = 12.0  # gidiş ve dönüş bacaklarının ikisi de bu hızın üstünde ...
    gps_spike_return_m: float = 20.0       # ... ve araç bir sonraki örnekte eski noktasına bu kadar yakın dönmüşse


@dataclass(frozen=True)
class FusionPolicy:
    """Fusion/adjudicator için doğrulanabilir olgu eşikleri ve uygulama guardrail'leri.

    Bu eşikler risk.py motorunun kararını taklit etmek için değil, LLM'in kullandığı olguların gerçekten
    context içinde bulunup bulunmadığını doğrulamak için kullanılır. Nihai seviye fusion LLM tarafından
    bağımsız önerilir.
    """

    # geçmiş davranış olguları
    close_approach_m: float = field(
        default_factory=lambda: _env_float("FUSION_CLOSE_APPROACH_M", 1000.0, 1.0))
    near_approach_m: float = field(
        default_factory=lambda: _env_float("FUSION_NEAR_APPROACH_M", 2000.0, 1.0))
    end_near_m: float = field(
        default_factory=lambda: _env_float("FUSION_END_NEAR_M", 2000.0, 1.0))
    far_now_m: float = field(
        default_factory=lambda: _env_float("FUSION_FAR_NOW_M", 3000.0, 1.0))
    min_approach_gain_m: float = field(
        default_factory=lambda: _env_float("FUSION_MIN_APPROACH_GAIN_M", 1500.0, 1.0))
    retreat_after_close_m: float = field(
        default_factory=lambda: _env_float("FUSION_RETREAT_AFTER_CLOSE_M", 800.0, 1.0))
    near_stop_m: float = field(
        default_factory=lambda: _env_float("FUSION_NEAR_STOP_M", 2500.0, 1.0))
    long_stop_min: int = field(
        default_factory=lambda: _env_int("FUSION_LONG_STOP_MIN", 30, 1))
    repeated_stops: int = field(
        default_factory=lambda: _env_int("FUSION_REPEATED_STOPS", 2, 1))
    loiter_sweep_deg: float = field(
        default_factory=lambda: _env_float("FUSION_LOITER_SWEEP_DEG", 180.0, 1.0))
    loiter_radius_cv: float = field(
        default_factory=lambda: _env_float("FUSION_LOITER_RADIUS_CV", 0.08, 0.001))
    stable_path_m: float = field(
        default_factory=lambda: _env_float("FUSION_STABLE_PATH_M", 300.0, 1.0))
    # "yaklaştı" sayılması için başlangıçtan en yakın noktaya asgari mesafe kazancı. Üs çevresinden başlayan
    # (çıkış trafiği) izler H_*_APPROACH anahtarlarını tetiklemesin.
    real_approach_gain_m: float = field(
        default_factory=lambda: _env_float("FUSION_REAL_APPROACH_GAIN_M", 500.0, 0.0))
    outbound_start_m: float = field(
        default_factory=lambda: _env_float("FUSION_OUTBOUND_START_M", 1200.0, 1.0))
    outbound_min_gain_m: float = field(
        default_factory=lambda: _env_float("FUSION_OUTBOUND_MIN_GAIN_M", 500.0, 0.0))

    # güncel hareket olguları
    heading_toward_deg: float = field(
        default_factory=lambda: _env_float("FUSION_HEADING_TOWARD_DEG", 60.0, 0.0))
    heading_away_deg: float = field(
        default_factory=lambda: _env_float("FUSION_HEADING_AWAY_DEG", 100.0, 0.0))
    fast_speed_mps: float = field(
        default_factory=lambda: _env_float("FUSION_FAST_SPEED_MPS", 7.0, 0.0))
    parked_speed_mps: float = field(
        default_factory=lambda: _env_float("FUSION_PARKED_SPEED_MPS", 0.5, 0.0))
    short_eta_min: float = field(
        default_factory=lambda: _env_float("FUSION_SHORT_ETA_MIN", 10.0, 0.0))
    long_eta_min: float = field(
        default_factory=lambda: _env_float("FUSION_LONG_ETA_MIN", 30.0, 0.0))
    weak_recent_approach_m: float = field(
        default_factory=lambda: _env_float("FUSION_WEAK_RECENT_APPROACH_M", 500.0, 0.0))

    # karar doğrulama
    min_confidence: float = field(
        default_factory=lambda: min(1.0, _env_float("FUSION_MIN_CONFIDENCE", 0.72, 0.0)))
    high_confidence: float = field(
        default_factory=lambda: min(1.0, _env_float("FUSION_HIGH_CONFIDENCE", 0.86, 0.0)))
    critical_min_confidence: float = field(
        default_factory=lambda: min(1.0, _env_float("FUSION_CRITICAL_MIN_CONFIDENCE", 0.90, 0.0)))
    one_step_min_score: int = field(
        default_factory=lambda: _env_int("FUSION_ONE_STEP_MIN_SCORE", 2, 1))
    two_step_min_score: int = field(
        default_factory=lambda: _env_int("FUSION_TWO_STEP_MIN_SCORE", 4, 1))
    one_step_min_keys: int = field(
        default_factory=lambda: _env_int("FUSION_ONE_STEP_MIN_KEYS", 2, 1))
    two_step_min_keys: int = field(
        default_factory=lambda: _env_int("FUSION_TWO_STEP_MIN_KEYS", 2, 1))
    critical_current_min_score: int = field(
        default_factory=lambda: _env_int("FUSION_CRITICAL_CURRENT_MIN_SCORE", 5, 1))
    critical_downgrade_min_score: int = field(
        default_factory=lambda: _env_int("FUSION_CRITICAL_DOWNGRADE_MIN_SCORE", 4, 1))
    # DUSUK<->YUKSEK gibi iki kademelik değişim güçlü kanıtla otomatik uygulanabilir;
    # DUSUK<->KRITIK üç kademe ise varsayılan olarak otomatik tam uygulanmaz.
    max_auto_delta: int = field(
        default_factory=lambda: min(2, _env_int("FUSION_MAX_AUTO_DELTA", 2, 0)))


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", ROOT / "data")))
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", ROOT / "outputs")))
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    # OpenAI uyumlu başka sağlayıcı (ör. GLM) için uç nokta; boşsa OpenAI
    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL") or None
    # 1 → GLM düşünme modu açılır, modelin reasoning_content'i ajan izine "reasoning" olayı olarak düşer
    llm_thinking: bool = os.getenv("LLM_THINKING", "0") == "1"

    # --- ikinci aşama fusion/adjudication LLM ---
    fusion_enabled: bool = field(default_factory=lambda: _env_bool("FUSION_ENABLED", True))
    # Boşsa ilk ajanla aynı model kullanılır. Farklı bir model kullanmak istersen FUSION_LLM_MODEL ver.
    fusion_model: str | None = os.getenv("FUSION_LLM_MODEL") or None
    # GLM / OpenAI-compatible sağlayıcılar için function_calling en uyumlu seçenek.
    fusion_llm_method: str = os.getenv("FUSION_LLM_METHOD", "function_calling")
    fusion_timeout_s: float = field(default_factory=lambda: _env_float("FUSION_LLM_TIMEOUT", 120.0, 1.0))
    fusion_concurrency: int = field(default_factory=lambda: _env_int("FUSION_CONCURRENCY", 4, 1))
    fusion: FusionPolicy = field(default_factory=FusionPolicy)

    detector_backend: str = os.getenv("DETECTOR_BACKEND", "simulated")  # simulated | yolo
    yolo_weights: str | None = os.getenv("YOLO_WEIGHTS")
    # "Son söz insanda" özelliğinin ilk açılıştaki durumu; arayüzden (PUT /api/settings) değiştirilir
    human_review_default: bool = os.getenv("HUMAN_REVIEW", "0") == "1"
    thresholds: Thresholds = field(default_factory=Thresholds)

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


settings = Settings()

RISK_ORDER = ["DUSUK", "ORTA", "YUKSEK", "KRITIK"]
HEAVY_LABELS = {"truck", "bus"}
