"""Raporun SABİT teması: renkler, fontlar, ölçüler ve Türkçe etiketler.

Tema kodun içinde sabittir (ortam değişkeni / kullanıcı matplotlibrc'si / sistem fontu okunmaz). Böylece
farklı çalıştırmalarda ve farklı makinelerde PDF aynı görünür. Tema değiştiğinde THEME_VERSION artırılır;
sürüm rapor ekinde yazılıdır.

Renkler: grafik zemini, mürekkep ve risk (durum) renkleri dataviz referans paletinden. Risk rengi hiçbir
zaman tek başına anlam taşımaz — her rozet/işaretin yanında seviye etiketi yazılır.
"""
from __future__ import annotations

import os
from pathlib import Path

THEME_VERSION = "1.3"
ORG_NAME = os.getenv("REPORT_ORG_NAME", "HİSAR")
REPORT_TITLE = "Tehdit Değerlendirme Raporu"
REPORT_SUBTITLE = "Merkez Üs Çevresi · Araç Risk Değerlendirmesi"
REPORT_TZ = os.getenv("REPORT_TZ", "Europe/Istanbul")

# ------------------------------------------------------------------ renkler
INK = "#0b0b0b"            # birincil metin
INK_2 = "#52514e"          # ikincil metin
MUTED = "#898781"          # eksen / etiket
HAIRLINE = "#e1e0d9"       # ızgara, tablo çizgisi
BASELINE = "#c3c2b7"       # eksen çizgisi
SURFACE = "#fcfcfb"        # grafik ve kutu zemini
PAGE = "#ffffff"
PANEL = "#f4f3ef"          # tablo başlığı, bilgi kutusu
HEADER_BG = "#1d2433"      # sayfa üst bandı / kapak
HEADER_INK = "#ffffff"
ACCENT = "#2a78d6"         # bölüm numarası, bağlantı
TRACK_CONTEXT = "#b9b8b1"  # çekim sonrası iz (bağlam)

RISK_COLORS = {            # dataviz durum paleti: good / warning / serious / critical
    "DUSUK": "#0ca30c",
    "ORTA": "#fab219",
    "YUKSEK": "#ec835a",
    "KRITIK": "#d03b3b",
}
RISK_TEXT_ON = {           # rozet içindeki yazı rengi (okunabilirlik)
    "DUSUK": "#ffffff", "ORTA": "#0b0b0b", "YUKSEK": "#0b0b0b", "KRITIK": "#ffffff",
}
RISK_LABELS = {"DUSUK": "DÜŞÜK", "ORTA": "ORTA", "YUKSEK": "YÜKSEK", "KRITIK": "KRİTİK"}
RISK_ICONS = {"DUSUK": "●", "ORTA": "▲", "YUKSEK": "◆", "KRITIK": "■"}   # renk + şekil + etiket

# ------------------------------------------------------------------ etiketler
SCENARIO_LABELS = {
    "DIRECT_FAST_APPROACH": "Doğrudan hızlı yaklaşma",
    "FAST_FINAL_APPROACH": "Bekleme/hat sapması sonrası ani hızlı yaklaşma",
    "ROUTINE_SHUTTLE": "Rutin hat aracı (servis otobüsü)",
    "CLOSE_APPROACH": "Yakın yaklaşma / geri çekilme",
    "HEAVY_NEAR_APPROACH": "Ağır araç yakın yaklaşması",
    "LOITER_NEAR_BASE": "Üs yakınında tur atma",
    "NEAR_BASE_ARRIVAL": "Üs yakınına varış",
    "NEAR_PASS": "Üs yakınından geçiş",
    "HEAVY_APPROACH": "Ağır araç yaklaşması",
    "STATIC_NEAR_BASE": "Üs yakınında uzun süre durağan",
    "FRIENDLY_PATROL": "Sabit yarıçaplı devriye",
    "APPROACHING": "Üsse yönelmiş hareket",
    "UNTRACKED": "İzsiz araç (davranış bilinmiyor)",
    "OUTBOUND": "Üsten çıkış trafiği",
    "PATROL_FAR": "Uzak devriye / tur",
    "TRANSIT": "Transit geçiş",
    "MOVING_AWAY": "Üsten uzaklaşma",
    "PARKED": "Park / hareketsiz",
    "DUPLICATE_BOX": "Kopya tespit kutusu",
    "FILTERED_LOW_CONF": "Düşük güvenli tespit (elendi)",
    # eski kayıtlarla geriye dönük uyumluluk
    "APPROACH_WITH_STOPS": "Duraklamalı yaklaşma (eski kural)",
}
STATUS_LABELS = {
    "motor": "Motor seviyesi (LLM kararı yok)",
    "uzlasi": "Motor + ilk LLM uzlaştı",
    "llm_yukseltti": "İlk LLM guardrail'i yükseltti",
    "fazla_yukseltme": "İlk LLM yükseltmesi sınırlandı",
    "motor_kesin": "İlk guardrail motor seviyesini korudu",
    "llm_dusurdu": "İlk LLM guardrail'i düşürdü",
    "belirsiz": "İlk guardrail belirsiz — motor seviyesi",
    "reddedildi": "İlk LLM önerisi reddedildi",
    "llm_belirtmedi": "İlk LLM belirtmedi — motor seviyesi",
    "fusion_yukseltti": "Fusion yükseltti",
    "fusion_dusurdu": "Fusion düşürdü",
    "fusion_sinirlandi": "Fusion değişikliği sınırlandı",
    "fusion_geri_aldi": "Fusion ilk LLM değişikliğini geri aldı",
    "onay_bekliyor": "ANALİST ONAYI BEKLİYOR",
    "analist_karari": "Analist kararı",
}
STATUS_SHORT = {           # özet tablosu için kısa hâller
    "motor": "motor", "uzlasi": "ilk LLM = motor", "llm_yukseltti": "ilk LLM ↑",
    "fazla_yukseltme": "ilk LLM ↑ (sınırlı)", "motor_kesin": "ilk guardrail: motor",
    "llm_dusurdu": "ilk LLM ↓", "belirsiz": "ilk guardrail: belirsiz", "reddedildi": "ilk LLM reddedildi",
    "llm_belirtmedi": "motor", "fusion_yukseltti": "Fusion ↑", "fusion_dusurdu": "Fusion ↓",
    "fusion_sinirlandi": "Fusion sınırlı", "fusion_geri_aldi": "Fusion geri aldı",
    "onay_bekliyor": "ONAY BEKLİYOR", "analist_karari": "analist",
}
SCENARIO_SHORT = {
    "DIRECT_FAST_APPROACH": "Hızlı yaklaşma", "CLOSE_APPROACH": "Yakın yaklaşma", 
    "HEAVY_NEAR_APPROACH": "Ağır yakın yaklaşma", "LOITER_NEAR_BASE": "Tur atma",
    "NEAR_BASE_ARRIVAL": "Yakına varış", "NEAR_PASS": "Yakın geçiş", "HEAVY_APPROACH": "Ağır yaklaşma",
    "STATIC_NEAR_BASE": "Yakında durağan", "FRIENDLY_PATROL": "Devriye", "APPROACHING": "Yönelmiş hareket",
    "UNTRACKED": "İzsiz araç", "OUTBOUND": "Çıkış", "PATROL_FAR": "Uzak devriye", "TRANSIT": "Transit",
    "MOVING_AWAY": "Uzaklaşma", "PARKED": "Park", "DUPLICATE_BOX": "Kopya kutu",
    "FILTERED_LOW_CONF": "Elendi", "APPROACH_WITH_STOPS": "Duraklamalı yaklaşma",
    "FAST_FINAL_APPROACH": "Ani son hamle", "ROUTINE_SHUTTLE": "Rutin hat",
}
VERDICT_LABELS = {
    "destekler": "Destekler", "celisir": "Çelişir", "kismen_uyumlu": "Kısmen uyumlu",
    "dogrulanamaz": "Doğrulanamaz", "ilgisiz": "İlgisiz", "manipulasyon": "Manipülasyon",
}
SOURCE_LABELS = {"official": "Resmi", "third_party": "Üçüncü taraf", "unknown": "Bilinmiyor"}
LABEL_TR = {"car": "otomobil", "van": "panelvan", "truck": "kamyon", "bus": "otobüs", None: "—"}
TREND_LABELS = {"azaliyor": "azalıyor", "artiyor": "artıyor", "sabit": "sabit",
                "once_azalip_sonra_artiyor": "önce azalıp sonra artıyor"}

# ------------------------------------------------------------------ ölçüler (mm) ve yazı boyutları (pt)
PAGE_MARGIN_MM = 16
HEADER_H_MM = 11
FOOTER_H_MM = 9
FS_BODY = 8.6
FS_SMALL = 7.2
FS_TINY = 6.4
FS_H1 = 15
FS_H2 = 11
FS_H3 = 9.4
CHART_DPI = 200


# ------------------------------------------------------------------ fontlar
def font_dir() -> Path:
    """Matplotlib ile gelen DejaVu fontları: her kurulumda aynı dosya → her makinede aynı görünüm.
    Türkçe karakterlerin (ş, ğ, ı, İ) tamamını içerir."""
    import matplotlib
    return Path(matplotlib.get_data_path()) / "fonts" / "ttf"


FONT_FILES = {
    # Rapor gövdesi için orantılı sans-serif: daha resmi görünür ve monospace'e göre
    # aynı bilgiyi daha az satırda taşır. Mono yalnızca teknik alanlar için korunur.
    "Body": "DejaVuSans.ttf",
    "Body-Bold": "DejaVuSans-Bold.ttf",
    "Body-Italic": "DejaVuSans-Oblique.ttf",
    "Body-BoldItalic": "DejaVuSans-BoldOblique.ttf",
    "Mono": "DejaVuSansMono.ttf",
    "Mono-Bold": "DejaVuSansMono-Bold.ttf",
}


def risk_label(level: str | None) -> str:
    return RISK_LABELS.get(level or "", level or "—")


def scenario_label(s: str | None) -> str:
    return SCENARIO_LABELS.get(s or "", s or "—")


def status_label(s: str | None) -> str:
    return STATUS_LABELS.get(s or "", s or "—")