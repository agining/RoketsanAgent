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

THEME_VERSION = "1.1"
ORG_NAME = os.getenv("REPORT_ORG_NAME", "HİSAR")
REPORT_TITLE = "Tehdit Değerlendirme Raporu"
REPORT_SUBTITLE = "Merkez Üs çevresi · şüpheli araç dosyaları"
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
    "APPROACH_WITH_STOPS": "Duraklamalı yaklaşma",
    "LOITER_NEAR_BASE": "Üs yakınında tur atma",
    "FRIENDLY_PATROL": "Sabit yarıçaplı devriye",
    "APPROACHING": "Üsse yönelmiş hareket",
    "UNTRACKED": "İzsiz araç (davranış bilinmiyor)",
    "TRANSIT": "Transit geçiş",
    "MOVING_AWAY": "Üsten uzaklaşma",
    "PARKED": "Park / hareketsiz",
    "FILTERED_LOW_CONF": "Düşük güvenli tespit (elendi)",
}
STATUS_LABELS = {
    "motor": "Motor seviyesi (LLM kararı yok)",
    "uzlasi": "Motor + LLM uzlaştı",
    "llm_yukseltti": "LLM gerekçeyle yükseltti",
    "fazla_yukseltme": "Aşırı yükseltme — kısmen uygulandı",
    "motor_kesin": "Motor kesin — LLM itirazı not edildi",
    "llm_dusurdu": "LLM düşürdü",
    "belirsiz": "Belirsiz — motor sınırda",
    "reddedildi": "LLM önerisi reddedildi",
    "llm_belirtmedi": "LLM belirtmedi — motor seviyesi",
    "onay_bekliyor": "ANALİST ONAYI BEKLİYOR",
    "analist_karari": "Analist kararı",
}
STATUS_SHORT = {           # özet tablosu için kısa hâller
    "motor": "motor", "uzlasi": "uzlaşı", "llm_yukseltti": "LLM ↑", "fazla_yukseltme": "LLM ↑ (kısmi)",
    "motor_kesin": "motor kesin", "llm_dusurdu": "LLM ↓", "belirsiz": "belirsiz", "reddedildi": "LLM reddedildi",
    "llm_belirtmedi": "motor", "onay_bekliyor": "ONAY BEKLİYOR", "analist_karari": "analist",
}
SCENARIO_SHORT = {
    "DIRECT_FAST_APPROACH": "Hızlı yaklaşma", "APPROACH_WITH_STOPS": "Duraklamalı yaklaşma",
    "LOITER_NEAR_BASE": "Tur atma", "FRIENDLY_PATROL": "Devriye", "APPROACHING": "Yönelmiş hareket",
    "UNTRACKED": "İzsiz araç", "TRANSIT": "Transit", "MOVING_AWAY": "Uzaklaşma", "PARKED": "Park",
    "FILTERED_LOW_CONF": "Elendi",
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
    "Body": "DejaVuSansMono.ttf",
    "Body-Bold": "DejaVuSansMono-Bold.ttf",
    "Body-Italic": "DejaVuSansMono-Oblique.ttf",
    "Body-BoldItalic": "DejaVuSansMono-BoldOblique.ttf",
    "Mono": "DejaVuSansMono.ttf",
    "Mono-Bold": "DejaVuSansMono-Bold.ttf",
}


def risk_label(level: str | None) -> str:
    return RISK_LABELS.get(level or "", level or "—")


def scenario_label(s: str | None) -> str:
    return SCENARIO_LABELS.get(s or "", s or "—")


def status_label(s: str | None) -> str:
    return STATUS_LABELS.get(s or "", s or "—")