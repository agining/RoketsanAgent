"""PDF yerleşimi (reportlab). Bölüm sırası, sayfa şablonları, tablo biçimleri ve renkler SABİTTİR:
her çalıştırma aynı iskeleti üretir; boş bölümler "Kayıt yok." ile yine görünür.

Sayfa düzeni (A4 dikey):
  Kapak → 1 Yönetici özeti → 2 Durum haritası → 3 Karar yöntemi →
  4 Kompakt araç değerlendirme kayıtları → 5 İnsan onayı → 6 Saha raporu bütünlüğü →
  7 Ek: üretim bilgileri. Araç kayıtları yeni sayfa zorlamaz; karar için gerekli bilgiler özetlenir.
"""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, Image,
                                NextPageTemplate, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle)

from ..config import RISK_ORDER
from . import charts
from .theme import (ACCENT, BASELINE, FONT_FILES, FOOTER_H_MM, FS_BODY, FS_H1, FS_H2, FS_H3, FS_SMALL, FS_TINY,
                    HAIRLINE, HEADER_BG, HEADER_H_MM, HEADER_INK, INK, INK_2, LABEL_TR, MUTED, ORG_NAME,
                    PAGE_MARGIN_MM, PANEL, REPORT_SUBTITLE, REPORT_TITLE, RISK_COLORS, RISK_ICONS, RISK_TEXT_ON,
                    SCENARIO_SHORT, SOURCE_LABELS, STATUS_LABELS, STATUS_SHORT, SURFACE, THEME_VERSION, TREND_LABELS,
                    VERDICT_LABELS, font_dir, risk_label)

PAGE_W, PAGE_H = A4
M = PAGE_MARGIN_MM * mm
CONTENT_W = PAGE_W - 2 * M
C = colors.HexColor


# ------------------------------------------------------------------ fontlar ve stiller
_FONTS_DONE = False


def _register_fonts():
    global _FONTS_DONE
    if _FONTS_DONE:
        return
    d = font_dir()
    for name, fn in FONT_FILES.items():
        pdfmetrics.registerFont(TTFont(name, str(d / fn)))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic",
                                  boldItalic="Body-BoldItalic")
    pdfmetrics.registerFontFamily("Mono", normal="Mono", bold="Mono-Bold", italic="Mono", boldItalic="Mono-Bold")
    _FONTS_DONE = True


def _styles() -> dict:
    base = dict(fontName="Body", textColor=C(INK), alignment=TA_LEFT)
    return {
        "body": ParagraphStyle("body", fontSize=FS_BODY, leading=FS_BODY * 1.42, spaceAfter=3, **base),
        "lead": ParagraphStyle("lead", fontSize=FS_BODY + 0.6, leading=(FS_BODY + 0.6) * 1.42, spaceAfter=4, **base),
        "small": ParagraphStyle("small", fontSize=FS_SMALL, leading=FS_SMALL * 1.38, **{**base, "textColor": C(INK_2)}),
        "tiny": ParagraphStyle("tiny", fontSize=FS_TINY, leading=FS_TINY * 1.35, **{**base, "textColor": C(MUTED)}),
        "h1": ParagraphStyle("h1", fontSize=FS_H1, leading=FS_H1 * 1.2, spaceAfter=4,
                             **{**base, "fontName": "Body-Bold"}),
        "h2": ParagraphStyle("h2", fontSize=FS_H2, leading=FS_H2 * 1.25, spaceBefore=7, spaceAfter=3,
                             **{**base, "fontName": "Body-Bold"}),
        "h3": ParagraphStyle("h3", fontSize=FS_H3, leading=FS_H3 * 1.3, spaceBefore=5, spaceAfter=2,
                             **{**base, "fontName": "Body-Bold"}),
        "bullet": ParagraphStyle("bullet", fontSize=FS_BODY, leading=FS_BODY * 1.4, leftIndent=10, bulletIndent=2,
                                 spaceAfter=1.5, **base),
        "cell": ParagraphStyle("cell", fontSize=FS_SMALL, leading=FS_SMALL * 1.3, **base),
        "cellb": ParagraphStyle("cellb", fontSize=FS_SMALL, leading=FS_SMALL * 1.3, **{**base, "fontName": "Body-Bold"}),
        "cellm": ParagraphStyle("cellm", fontSize=FS_SMALL, leading=FS_SMALL * 1.3, **{**base, "textColor": C(INK_2)}),
        "cellr": ParagraphStyle("cellr", fontSize=FS_SMALL, leading=FS_SMALL * 1.3, **{**base, "alignment": TA_RIGHT}),
        "kpi_v": ParagraphStyle("kpi_v", fontSize=13, leading=15, **{**base, "fontName": "Body-Bold"}),
        "kpi_l": ParagraphStyle("kpi_l", fontSize=FS_TINY, leading=FS_TINY * 1.3, **{**base, "textColor": C(INK_2)}),
    }


S: dict = {}


def esc(s) -> str:
    return escape("" if s is None else str(s))


def P(text: str, style: str = "body", raw: bool = False) -> Paragraph:
    return Paragraph(text if raw else esc(text), S[style])


def tint(hex_color: str, a: float) -> colors.Color:
    c = C(hex_color)
    return colors.Color(1 - a * (1 - c.red), 1 - a * (1 - c.green), 1 - a * (1 - c.blue))


def km(m) -> str:
    return "—" if m is None else (f"{m / 1000:.2f} km" if m >= 1000 else f"{m:.0f} m")


def num(v, unit="", nd=0) -> str:
    return "—" if v is None else f"{v:.{nd}f}{unit}"


# ------------------------------------------------------------------ özel akış öğeleri
class Bookmark(Flowable):
    """PDF kenar çubuğu (outline) girişi."""

    def __init__(self, title: str, key: str, level: int = 0):
        super().__init__()
        self.title, self.key, self.level = title, key, level

    def wrap(self, aw, ah):
        return 0, 0

    def draw(self):
        self.canv.bookmarkPage(self.key)
        self.canv.addOutlineEntry(self.title, self.key, level=self.level, closed=self.level > 0)


class Badge(Flowable):
    """Risk rozeti: renk + şekil + etiket (renk tek başına anlam taşımaz)."""

    def __init__(self, level: str, w: float = 27 * mm, h: float = 7 * mm, fs: float = 8.2, prefix: str = ""):
        super().__init__()
        self.level, self.w, self.h, self.fs, self.prefix = level, w, h, fs, prefix

    def wrap(self, aw, ah):
        return self.w, self.h

    def draw(self):
        c = self.canv
        c.setFillColor(C(RISK_COLORS[self.level]))
        c.roundRect(0, 0, self.w, self.h, 1.6 * mm, fill=1, stroke=0)
        c.setFillColor(C(RISK_TEXT_ON[self.level]))
        c.setFont("Body-Bold", self.fs)
        c.drawCentredString(self.w / 2, (self.h - self.fs * 0.72) / 2,
                            f"{self.prefix}{RISK_ICONS[self.level]} {risk_label(self.level)}")


class VehicleHeader(Flowable):
    """Araç dosyası başlık bandı."""

    def __init__(self, f: dict, total: int):
        super().__init__()
        self.f, self.total, self.h = f, total, 21 * mm

    def wrap(self, aw, ah):
        self.w = aw
        return aw, self.h

    def draw(self):
        c, f = self.canv, self.f
        lvl = f["final_level"]
        c.setFillColor(C(PANEL))
        c.roundRect(0, 0, self.w, self.h, 2 * mm, fill=1, stroke=0)
        c.setFillColor(C(RISK_COLORS[lvl]))
        c.rect(0, 0, 3.2 * mm, self.h, fill=1, stroke=0)
        x = 7 * mm
        c.setFillColor(C(INK_2)); c.setFont("Body-Bold", 6.8)
        c.drawString(x, self.h - 5.6 * mm, f"ARAÇ DEĞERLENDİRME #{f['index']} / {self.total}")
        ident = f["track_id"] or f["vehicle_id"]
        title = f"{ident} · {LABEL_TR.get(f['label'], f['label'] or 'tip bilinmiyor')}"
        if f["vehicle_id"] and f["track_id"]:
            title += f" · {f['vehicle_id']}"
        c.setFillColor(C(INK)); c.setFont("Body-Bold", 13)
        c.drawString(x, self.h - 11.6 * mm, _fit(c, title, "Body-Bold", 13, self.w - 60 * mm))
        sub = " · ".join(s for s in [f["frame_id"] or "kare dışı iz", f["capture_time"], f["zone"],
                                      f["scenario_label"]] if s)
        c.setFillColor(C(INK_2)); c.setFont("Body", 7.6)
        c.drawString(x, self.h - 16.4 * mm, _fit(c, sub, "Body", 7.6, self.w - 60 * mm))
        # rozet + motor/karar satırı
        bw, bh = 34 * mm, 8 * mm
        bx, by = self.w - bw - 4 * mm, self.h - bh - 4 * mm
        c.setFillColor(C(RISK_COLORS[lvl])); c.roundRect(bx, by, bw, bh, 1.6 * mm, fill=1, stroke=0)
        c.setFillColor(C(RISK_TEXT_ON[lvl])); c.setFont("Body-Bold", 9.5)
        c.drawCentredString(bx + bw / 2, by + 2.6 * mm, f"{RISK_ICONS[lvl]} {risk_label(lvl)}")
        c.setFillColor(C(INK_2)); c.setFont("Body", 6.4)
        d = f.get("decision") or {}
        if d.get("fusion_action"):
            line1 = f"Motor {risk_label(f['engine_level'])} · İlk LLM {risk_label(d.get('llm_level'))} · Fusion {risk_label(d.get('fusion_level'))}"
            line2 = f"{d.get('fusion_action')} → {risk_label(d.get('auto_level'))}"
        else:
            line1 = f"Motor: {risk_label(f['engine_level'])}"
            line2 = f["status_label"]
        c.drawRightString(self.w - 4 * mm, 6.6 * mm, _fit(c, line1, "Body", 6.4, 66 * mm))
        c.drawRightString(self.w - 4 * mm, 3.2 * mm, _fit(c, line2, "Body", 6.4, 66 * mm))


def _fit(c, text: str, font: str, size: float, width: float) -> str:
    if c.stringWidth(text, font, size) <= width:
        return text
    while text and c.stringWidth(text + "…", font, size) > width:
        text = text[:-1]
    return text + "…"


# ------------------------------------------------------------------ yardımcı tablolar
def table(rows, widths, header=True, zebra=False, style="cell", extra=None, repeat=1) -> Table:
    data = []
    for i, r in enumerate(rows):
        cells = []
        for v in r:
            if isinstance(v, Flowable):
                cells.append(v)
            else:
                cells.append(P(v, "cellb" if header and i == 0 else style))
        data.append(cells)
    t = Table(data, colWidths=widths, repeatRows=repeat if header else 0, hAlign="LEFT")
    cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3.2), ("RIGHTPADDING", (0, 0), (-1, -1), 3.2),
            ("TOPPADDING", (0, 0), (-1, -1), 2.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, C(HAIRLINE))]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), C(PANEL)), ("LINEBELOW", (0, 0), (-1, 0), 0.7, C(BASELINE))]
    if zebra:
        for i in range(1 if header else 0, len(data)):
            if (i % 2 == 0) == header:
                cmds.append(("BACKGROUND", (0, i), (-1, i), C(SURFACE)))
    t.setStyle(TableStyle(cmds + (extra or [])))
    return t


def kv_table(pairs, widths=(38 * mm, None)) -> Table:
    w2 = widths[1] or (CONTENT_W - widths[0])
    rows = [[P(k, "cellm"), v if isinstance(v, Flowable) else P(v, "cell")] for k, v in pairs]
    return table(rows, [widths[0], w2], header=False)


def level_cell(level: str | None) -> list:
    """Tablo hücresi için: rozet komutları (arka plan) + metin."""
    return [P(f"{RISK_ICONS.get(level, '')} {risk_label(level)}" if level else "—", "cellb")]


def level_cmds(col: int, row: int, level: str | None) -> list:
    if not level:
        return []
    return [("BACKGROUND", (col, row), (col, row), tint(RISK_COLORS[level], 0.28))]


def kpi_tiles(items: list[tuple[str, str]], n: int | None = None) -> Table:
    n = n or len(items)
    w = CONTENT_W / n
    cells = [[[P(v, "kpi_v"), P(lbl, "kpi_l")] for v, lbl in items]]
    t = Table(cells, colWidths=[w] * n, hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C(SURFACE)),
                           ("BOX", (0, 0), (-1, -1), 0.5, C(HAIRLINE)),
                           ("LINEAFTER", (0, 0), (-2, -1), 0.5, C(HAIRLINE)),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def level_tiles(counts: dict, total_label: str, total: int) -> Table:
    items = [(str(total), total_label)] + [(str(counts[lv]), f"{RISK_ICONS[lv]} {risk_label(lv)}")
                                           for lv in reversed(RISK_ORDER)]
    t = kpi_tiles(items)
    cmds = []
    for i, lv in enumerate(reversed(RISK_ORDER), 1):
        cmds += [("LINEABOVE", (i, 0), (i, 0), 2.2, C(RISK_COLORS[lv]))]
    t.setStyle(TableStyle(cmds))
    return t


def banner(text: str, color: str, raw=False) -> Table:
    t = Table([[P(text, "cellb", raw=raw)]], colWidths=[CONTENT_W], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), tint(color, 0.22)),
                           ("LINEBEFORE", (0, 0), (0, -1), 2.4, C(color)),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                           ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    return t


def box(flowables: list, bg=SURFACE, edge=HAIRLINE) -> Table:
    t = Table([[flowables]], colWidths=[CONTENT_W], hAlign="LEFT")
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), C(bg)), ("BOX", (0, 0), (-1, -1), 0.5, C(edge)),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                           ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7)]))
    return t


def bullets(items: list[str], numbered=False) -> list:
    if not items:
        return [P("Kayıt yok.", "small")]
    return [Paragraph(esc(x), S["bullet"], bulletText=(f"{i}." if numbered else "•")) for i, x in enumerate(items, 1)]


def section(num: str, title: str, key: str) -> list:
    return [Bookmark(f"{num} {title}", key, 0),
            P(f'<font color="{ACCENT}">{esc(num)}</font>&nbsp;&nbsp;{esc(title)}', "h1", raw=True),
            _rule(), Spacer(1, 3 * mm)]


def subsection(num: str, title: str) -> list:
    return [CondPageBreak(30 * mm),
            P(f'<font color="{ACCENT}">{esc(num)}</font>&nbsp;&nbsp;{esc(title)}', "h2", raw=True)]


class _Rule(Flowable):
    def __init__(self, color=BASELINE, width=0.8):
        super().__init__()
        self.color, self.lw = color, width

    def wrap(self, aw, ah):
        self.w = aw
        return aw, 2

    def draw(self):
        self.canv.setStrokeColor(C(self.color)); self.canv.setLineWidth(self.lw)
        self.canv.line(0, 1, self.w, 1)


def _rule():
    return _Rule()


def img(png: bytes, kind: str, width: float) -> Image:
    fw, fh = charts.SIZES[kind]
    return Image(io.BytesIO(png), width=width, height=width * fh / fw)


def _paired_lists(lt: str, left: list[str], rt: str, right: list[str], gap=3 * mm) -> Table:
    """İki sütunlu madde listesi; her madde ayrı satır olduğu için sayfa sonunda bölünebilir (tek başına sayfa
    kaplamaz). Başlık satırı yeni sayfada tekrar edilir."""
    w = (CONTENT_W - gap) / 2
    L = [Paragraph(esc(x), S["bullet"], bulletText="•") for x in left] or [P("Kayıt yok.", "small")]
    R = [Paragraph(esc(x), S["bullet"], bulletText=f"{i}.") for i, x in enumerate(right, 1)] or [P("Kayıt yok.", "small")]
    rows = [[P(lt, "h3"), "", P(rt, "h3")]]
    for i in range(max(len(L), len(R))):
        rows.append([L[i] if i < len(L) else "", "", R[i] if i < len(R) else ""])
    t = Table(rows, colWidths=[w, gap, w], repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def two_col(left, right, gap=3 * mm) -> Table:
    w = (CONTENT_W - gap) / 2
    t = Table([[left, "", right]], colWidths=[w, gap, w], hAlign="LEFT")
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


# ------------------------------------------------------------------ sayfa şablonları
class NumberedCanvas(canvas.Canvas):
    """"Sayfa X / Y" için iki geçişli tuval."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved)
        for st in self._saved:
            self.__dict__.update(st)
            if self._pageNumber > 1:
                self.setFont("Body", FS_TINY); self.setFillColor(C(MUTED))
                self.drawRightString(PAGE_W - M, FOOTER_H_MM * mm * 0.55, f"Sayfa {self._pageNumber} / {n}")
            super().showPage()
        super().save()


def _on_cover(meta):
    def draw(c, doc):
        c.saveState()
        band = 92 * mm
        c.setFillColor(C(HEADER_BG)); c.rect(0, PAGE_H - band, PAGE_W, band, fill=1, stroke=0)
        c.setFillColor(C(ACCENT)); c.rect(M, PAGE_H - band + 14 * mm, 22 * mm, 1.4 * mm, fill=1, stroke=0)
        c.setFillColor(C(HEADER_INK))
        c.setFont("Body-Bold", 10); c.drawString(M, PAGE_H - 22 * mm, ORG_NAME)
        c.setFont("Body", 8); c.drawString(M, PAGE_H - 27 * mm, "Üs Koruma · ISR Analiz Sistemi")
        c.setFont("Body-Bold", 26); c.drawString(M, PAGE_H - 50 * mm, REPORT_TITLE)
        c.setFont("Body", 11); c.drawString(M, PAGE_H - 58 * mm, REPORT_SUBTITLE)
        c.setFont("Body", 8.4)
        c.drawString(M, PAGE_H - 70 * mm, f"Rapor No: {meta['report_id']}")
        c.drawString(M, PAGE_H - 75 * mm, f"Oluşturulma: {meta['generated_at']} · Filtre: {meta['filter_label']}")
        c.setFont("Body", FS_TINY); c.setFillColor(C(MUTED))
        c.drawString(M, 11 * mm, "Otomatik üretilmiştir. Seviyeler motor + ilk LLM + fusion kanıt kapısı ve (açıksa) "
                                 "analist kararlarından gelir.")
        c.drawString(M, 7.5 * mm, "Operasyonel karar öncesi analist doğrulaması gerekir.")
        c.restoreState()
    return draw


def _on_body(meta):
    def draw(c, doc):
        c.saveState()
        h = HEADER_H_MM * mm
        c.setFillColor(C(HEADER_BG)); c.rect(0, PAGE_H - h, PAGE_W, h, fill=1, stroke=0)
        c.setFillColor(C(HEADER_INK)); c.setFont("Body-Bold", 7.4)
        c.drawString(M, PAGE_H - h + 4 * mm, f"{ORG_NAME} · {REPORT_TITLE.upper()}")
        c.setFont("Body", 7)
        c.drawRightString(PAGE_W - M, PAGE_H - h + 4 * mm, f"{meta['report_id']} · {meta['filter_label']}")
        c.setStrokeColor(C(HAIRLINE)); c.setLineWidth(0.5)
        c.line(M, FOOTER_H_MM * mm, PAGE_W - M, FOOTER_H_MM * mm)
        c.setFont("Body", FS_TINY); c.setFillColor(C(MUTED))
        hil = "insan onayı AÇIK" if meta["human_review"] else "insan onayı KAPALI"
        c.drawString(M, FOOTER_H_MM * mm * 0.55, f"{meta['generated_at']} · {hil} · tema v{THEME_VERSION}")
        c.restoreState()
    return draw


# ------------------------------------------------------------------ bölümler
def _cover(data, ctx) -> list:
    m, c = data["meta"], data["counts"]
    n = len(data["vehicles"])
    out = [Spacer(1, 84 * mm)]
    out.append(level_tiles(c, "şüpheli araç (filtre)", n))
    out.append(Spacer(1, 5 * mm))
    if m["human_review"] and data["reviews"]["pending_count"]:
        out.append(banner(f"UYARI: {data['reviews']['pending_count']} karar analist onayı bekliyor — ilgili araçların "
                          "seviyeleri geçicidir (bkz. Bölüm 5).", RISK_COLORS["ORTA"]))
        out.append(Spacer(1, 3 * mm))
    src = ctx["narrative_source_text"]
    pairs = [
        ("Rapor No", m["report_id"]), ("Oluşturulma", m["generated_at"]),
        ("Hazırlayan", m.get("prepared_by") or "Otomatik (sistem)"),
        ("Veri penceresi", f"{m['data_window']} · {m['frames_total']} kare · {m['tracks_total']} iz · "
                           f"{m['reports_total']} saha raporu"),
        ("Seçim filtresi", f"{m['filter_label']}" + (" · kare dışı izler dahil" if m["include_offframe"] else "")),
        ("Kare değerlendirmesi", f"{m['frames_assessed']}/{m['frames_total']} kare değerlendirildi · "
                                 f"{m['frames_llm']} kare ilk LLM" + (f" ({m['assess_model']})" if m["assess_model"] else "")
                                 + f" · {m.get('frames_fusion', 0)} kare fusion"
                                 + (f" ({m.get('fusion_model')})" if m.get("fusion_model") else "")
                                 + (f" · {m.get('frames_fusion_error', 0)} fusion hatası" if m.get("frames_fusion_error") else "")),
        ("İnsan onayı (son söz insanda)", "AÇIK — onay gerektiren otomatik kararlar analiste gider; analist kararı üstündür"
         if m["human_review"] else "KAPALI — fusion/guardrail otomatik sonucu uygulanır"),
        ("Açıklama metinleri", src),
        ("Tespit katmanı", m["detector"]),
    ]
    out.append(kv_table(pairs, (46 * mm, None)))
    out.append(Spacer(1, 6 * mm))
    out.append(P("İçindekiler", "h3"))
    toc = ["1  Yönetici özeti", "2  Durum haritası", "3  Karar yöntemi", f"4  Araç değerlendirme kayıtları ({n})",
           "5  İnsan onayı", "6  Saha raporu bütünlüğü", "7  Ek: üretim bilgileri"]
    out += [P(t, "small") for t in toc]
    return out


def _summary_table(vs) -> Table:
    head = ["#", "Araç / iz", "Tip", "Bölge", "Nihai", "Motor", "Karar", "Üsse", "ETA", "Senaryo"]
    rows, cmds = [head], []
    fusion_short = {"ESCALATE": "Fusion ↑", "DEESCALATE": "Fusion ↓", "KEEP": "Fusion = motor",
                    "REJECTED": "Fusion reddedildi", "CAPPED_UP": "Fusion ↑ sınır", "CAPPED_DOWN": "Fusion ↓ sınır"}
    for i, f in enumerate(vs, 1):
        fe = f.get("features") or {}
        d = f.get("decision") or {}
        decision_text = fusion_short.get(d.get("fusion_action")) or STATUS_SHORT.get(f["status"], f["status"])
        rows.append([str(f["index"]), f["track_id"] or f["vehicle_id"], LABEL_TR.get(f["label"], f["label"] or "—"),
                     f["zone"], level_cell(f["final_level"])[0], risk_label(f["engine_level"]),
                     decision_text, km(f["dist_to_base_m"]),
                     num(fe.get("eta_min"), " dk"), SCENARIO_SHORT.get(f["scenario"], f["scenario_label"])])
        cmds += level_cmds(4, i, f["final_level"])
        if f["status"] == "onay_bekliyor":
            cmds.append(("BACKGROUND", (6, i), (6, i), tint(RISK_COLORS["ORTA"], 0.35)))
    w = [7 * mm, 24 * mm, 16 * mm, 33 * mm, 18 * mm, 15 * mm, 21 * mm, 15 * mm, 11 * mm, None]
    w[-1] = CONTENT_W - sum(x for x in w[:-1])
    return table(rows, w, zebra=True, extra=cmds)


def _executive(data, ctx) -> list:
    ex = ctx["executive"]["narrative"]
    vs = data["vehicles"]
    out = section("1", "Yönetici özeti", "sec1")
    out.append(P(ex["situation"], "lead"))
    out.append(P("Temel bulgular", "h3"))
    out += bullets(ex["key_findings"])
    out.append(P("Öncelikli eylemler", "h3"))
    out += bullets(ex["priorities"], numbered=True)
    out.append(P("Öncelikli araç görünümü", "h3"))
    if vs:
        preview = vs[:12]
        out.append(_summary_table(preview))
        if len(vs) > len(preview):
            out.append(P(f"Yönetici özetinde ilk {len(preview)} kayıt gösterilir; kalan {len(vs) - len(preview)} kayıt "
                         "Bölüm 4'te yer alır.", "tiny"))
    else:
        out.append(P("Seçilen filtrede şüpheli araç yok.", "small"))
    out.append(Spacer(1, 2 * mm))
    out.append(two_col([P("Karar süreci", "h3"), P(ex["decision_process"], "small")],
                       [P("Saha raporu bütünlüğü", "h3"), P(ex["report_integrity"], "small")]))
    out.append(P(f"Metin kaynağı: {ctx['source_tag'](ctx['executive'])}", "tiny"))
    return out


def _situation(data, ctx) -> list:
    out = [PageBreak()] + section("2", "Durum haritası", "sec2")
    out.append(img(ctx["overview_png"], "overview", CONTENT_W))
    out.append(P("Harita üsse göre yerel metrik düzlemdedir (üs = 0,0; yukarı kuzey). Renkli çizgi: çekim anına "
                 "kadarki iz; kesikli gri: çekimden sonra devam eden iz. İşaret şekli ve rengi nihai seviyeyi, "
                 "etiket (#) araç dosyası numarasını gösterir.", "tiny"))
    out.append(Spacer(1, 3 * mm))
    ac, sc = data["all_counts"], data["counts"]
    rows = [["Seviye", "Tüm araçlar", "Rapora giren", "Açıklama"]]
    desc = {"KRITIK": "Acil müdahale gerektiren tehdit", "YUKSEK": "Sürekli izleme ve hazırlık",
            "ORTA": "Ek gözlem / kimlik teyidi", "DUSUK": "Rutin izleme"}
    cmds = []
    for i, lv in enumerate(reversed(RISK_ORDER), 1):
        rows.append([level_cell(lv)[0], str(ac[lv]), str(sc[lv]), desc[lv]])
        cmds += level_cmds(0, i, lv)
    out.append(P("Seviye dağılımı (nihai seviyeye göre)", "h3"))
    out.append(table(rows, [28 * mm, 26 * mm, 26 * mm, CONTENT_W - 80 * mm], extra=cmds))
    return out


def _methodology(data, ctx) -> list:
    mt, m = data["methodology"], data["meta"]
    out = [PageBreak()] + section("3", "Karar yöntemi", "sec3")
    out.append(P("Her aracın otomatik seviyesi artık dört aşamalı bir zincirle üretilir: <b>(1) kural tabanlı motor</b> "
                 "tespit ve hareket verisinden ilk seviye/senaryoyu üretir; <b>(2) ilk LLM</b> aynı kareyi bağımsız "
                 "yorumlar ve eski guardrail yalnız fusion öncesi güvenli başlangıç/fallback seviyesini oluşturur; "
                 "<b>(3) fusion hakemi</b> motoru ve ilk LLM'i ground-truth kabul etmeden CURRENT + tüm geçmiş HISTORY + "
                 "saha raporlarını birlikte değerlendirir; <b>(4) kanıt kapısı</b> fusion değişikliğini yalnız doğrulanmış "
                 "ACTIVE olgularla uygular. İnsan onayı açıksa analist kararı bütün otomatik katmanların üstündedir. "
                 "Saha raporu metinleri güvenilmez veridir; talimatları uygulanmaz ve manipülasyon/çelişki karar dayanağı "
                 "yapılmaz.", "body", raw=True))

    out.append(P("Motor kuralları (öncelik sırasıyla; ilk eşleşen kural senaryoyu belirler)", "h3"))
    rows, cmds = [["Senaryo", "Seviye", "Koşullar (hepsi sağlanmalı)"]], []
    for i, r in enumerate(mt["rules"], 1):
        rows.append([f"{r['label']} ({r['scenario']})", level_cell(r["risk"])[0],
                     " · ".join(r["conds"])])
        cmds += level_cmds(1, i, r["risk"])
    out.append(table(rows, [52 * mm, 22 * mm, CONTENT_W - 74 * mm], extra=cmds))

    out.append(P("İlk LLM guardrail'i (fusion öncesi başlangıç / fallback)", "h3"))
    rows = [["Durum", "Ne zaman", "Fusion öncesi sonuç"]]
    for r in mt.get("primary_guardrail_table") or []:
        rows.append([r["label"], r["when"], r["result"]])
    out.append(table(rows, [48 * mm, CONTENT_W - 48 * mm - 34 * mm, 34 * mm], zebra=True))
    out.append(P("Bu tablo artık nihai otomatik otorite değildir. Fusion başarılıysa ilk LLM değişikliği dahil tüm seviye "
                 "değişiklikleri motor seviyesine göre aynı doğrulanmış kanıt kapısından yeniden sınanır; doğrulanmayan "
                 "ilk LLM değişikliği geri alınabilir.", "small"))

    out.append(P("Fusion hakemi ve kanıt kapısı", "h3"))
    rows = [["#", "İlke", "Uygulama"]]
    for r in mt.get("fusion_flow") or []:
        rows.append([r["step"], r["role"], r["detail"]])
    out.append(table(rows, [9 * mm, 39 * mm, CONTENT_W - 48 * mm], zebra=True))
    out.append(Spacer(1, 1.5 * mm))
    out.append(two_col([P("Fusion doğrulama eşikleri", "h3"),
                        kv_table(list((mt.get("fusion_thresholds") or {}).items()), (43 * mm, None))],
                       [P("Motor / veri eşikleri", "h3"),
                        kv_table(list(mt["thresholds"].items()), (43 * mm, None))]))
    out.append(Spacer(1, 2 * mm))

    if m["human_review"]:
        text = ("Bu raporda insan onayı AÇIK: seviye önceliği analist kararı → fusion sonrası doğrulanmış otomatik/onay "
                "seviyesi → fusion yoksa ilk motor+LLM guardrail sonucu → motor.")
    else:
        text = ("Bu raporda insan onayı KAPALI: seviye önceliği fusion sonrası doğrulanmış auto_level → fusion yoksa "
                "ilk motor+LLM guardrail sonucu → motor. Kayıtlı analist kararları uygulanmaz.")
    out.append(banner(text, ACCENT))
    return out


# ------------------------------------------------------------------ araç dosyası
def _rule_rows(f: dict) -> tuple[list, list]:
    """Eşleşen kural (tüm koşullar) + önce gelen/daha yüksek kurallarda sağlanmayan koşullar."""
    rules = f.get("rules") or []
    matched = next((r for r in rules if r["matched"]), None)
    m_rank = RISK_ORDER.index(matched["risk"]) if matched else -1
    rows, cmds = [["Kural", "Koşul", "Değer", "Eşik", "Sonuç"]], []

    def res(c):
        if c["ok"]:
            return "✓ sağlandı" + (" (kıl payı)" if c["barely"] else "")
        return "✗ kıl payı kaçtı" if c["near_miss"] else "✗ sağlanmadı"

    seen_matched = False
    for r in rules:
        is_m = r is matched
        before = not seen_matched
        seen_matched = seen_matched or is_m
        if not is_m and not (before or RISK_ORDER.index(r["risk"]) > m_rank):
            continue
        conds = r["conds"] if is_m or r.get("any_of") else [c for c in r["conds"] if not c["ok"]]
        if not conds:
            continue
        tag = ("EŞLEŞTİ · " if is_m else "") + f"{r['scenario']} ({risk_label(r['risk'])})"
        for j, c in enumerate(conds):
            rows.append([tag if j == 0 else "", c["name"], c["value"], c["threshold"], res(c)])
            i = len(rows) - 1
            if c["ok"]:
                cmds.append(("TEXTCOLOR", (4, i), (4, i), C(INK)))
            if is_m:
                cmds.append(("BACKGROUND", (0, i), (-1, i), tint(RISK_COLORS[r["risk"]], 0.14)))
    return rows, cmds


def _detection_pairs(f: dict) -> list:
    src = {"detection": "Tespit modeli (kutu)", "track_only": "Yalnızca iz (model kaçırmış)"}.get(f["source"], f["source"])
    if f["kind"] == "offframe_track":
        src = "Kare dışı iz (hiçbir karede görünmedi)"
    pairs = [("Kaynak", src)]
    if f["label"]:
        pairs.append(("Sınıf / güven", f"{f['label']} ({LABEL_TR.get(f['label'])}) · {f['confidence']:.2f}"))
    if f["bbox"]:
        x, y, w, h = f["bbox"]
        pairs.append(("Kutu (x, y, g, y)", f"{x:g}, {y:g}, {w:g}, {h:g} → merkez {x + w / 2:g}, {y + h / 2:g} px"))
    pairs += [("Koordinat", f"{f['lat']:.6f} N, {f['lon']:.6f} E"),
              ("Bölge", f["zone"]), ("Üsse mesafe", km(f["dist_to_base_m"])),
              ("Üsten kerteriz", f"{f['bearing_from_base_deg']:.0f}°")]
    if f["track_id"]:
        pairs.append(("İz eşleşmesi", f"{f['track_id']}" + (f" · {f['track_match_m']:.1f} m" if f.get("track_match_m")
                                                           is not None else "")))
    nt = f.get("nearest_track")
    if nt:
        pairs.append(("İz eşleşmesi", f"yok — en yakın iz {nt['track_id']} {nt['dist_m']:.1f} m (eşik "
                                      f"{nt['match_radius_m']:g} m); iz {nt['assigned_to'] or '—'} kaydına atanmış"))
    return pairs


def _features_pairs(f: dict) -> list:
    fe = f.get("features") or {}
    return [
        ("Üsse mesafe", f"başlangıç {km(fe.get('dist_start_m'))} → çekim {km(fe.get('dist_now_m'))} "
                        f"(en yakın {km(fe.get('dist_min_m'))})"),
        ("Son 60 dk yaklaşma", num(fe.get("approach_last60_m"), " m")),
        ("Hız", f"son 10 dk {num(fe.get('speed_now_mps'), ' m/s', 1)} · en yüksek {num(fe.get('max_speed_mps'), ' m/s', 1)}"),
        ("Yön / sapma", f"hareket {num(fe.get('heading_deg'), '°')} · üsse kerteriz {num(fe.get('bearing_to_base_deg'), '°')} "
                        f"· sapma {num(fe.get('heading_offset_deg'), '°')}"),
        ("ETA (mevcut hızla)", num(fe.get("eta_min"), " dk", 1)),
        ("Yol / yer değiştirme", f"{num(fe.get('path_length_m'), ' m')} / {num(fe.get('net_displacement_m'), ' m')}"),
        ("Mesafe trendi", TREND_LABELS.get(fe.get("dist_trend"), fe.get("dist_trend") or "—")),
        ("Duraklama", f"{len(fe.get('stops') or [])} olay · toplam {fe.get('stopped_minutes_total') or 0} dk · "
                      f"başlangıç bekleme {fe.get('initial_wait_min') or 0} dk"),
    ]


def _vehicle(f: dict, data: dict, ctx: dict) -> list:
    """Kompakt araç kaydı.

    Karar/veri yapısını değiştirmez; yalnızca PDF'teki tekrarlı denetim dökümlerini
    yönetici düzeyi bir özete indirger. Ayrıntılı kural ve karar zinciri verileri
    ``data`` içinde aynen kalır.
    """
    vn = ctx["vehicle_narr"][f["key"]]
    n = vn["narrative"]
    total = len(data["vehicles"])
    ident = f["track_id"] or f["vehicle_id"]
    fe = f.get("features") or {}

    # Yeni sayfa zorlaması yok: sayfada yeterli alan varsa sonraki kayıt aynı sayfada başlar.
    out = [CondPageBreak(78 * mm),
           Bookmark(f"#{f['index']} {ident} - {risk_label(f['final_level'])}", f"v{f['index']}", 1),
           VehicleHeader(f, total), Spacer(1, 2 * mm)]

    d, rv = f.get("decision"), f.get("review")
    if f["status"] == "onay_bekliyor":
        opts = ", ".join(risk_label(x) for x in (d or {}).get("options") or [])
        out += [banner(f"ANALİST ONAYI BEKLİYOR - geçici seviye. Seçenekler: {opts}.",
                       RISK_COLORS["ORTA"]), Spacer(1, 1.5 * mm)]
    elif rv:
        out += [banner(f"Analist kararı: {risk_label(rv['level'])}"
                       + (f" - {rv.get('analyst')}" if rv.get("analyst") else ""), ACCENT),
                Spacer(1, 1.5 * mm)]

    conf = f"{f['confidence']:.2f}" if f.get("confidence") is not None else "-"
    eta = num(fe.get("eta_min"), " dk", 1)
    speed = num(fe.get("speed_now_mps"), " m/s", 1)
    track = f["track_id"] or "eşleşmedi"
    compact_rows = [
        ["Araç", f"{LABEL_TR.get(f['label'], f['label'] or 'tip bilinmiyor')} / {conf}",
         "Bölge", f["zone"], "Üsse", km(f["dist_to_base_m"])],
        ["İz", track, "Senaryo", f["scenario_label"], "ETA / hız", f"{eta} / {speed}"],
    ]
    out.append(table(compact_rows, [16 * mm, 36 * mm, 16 * mm, 38 * mm, 18 * mm, CONTENT_W - 124 * mm],
                     header=False, style="cell"))
    out.append(Spacer(1, 1.5 * mm))

    if d and d.get("fusion_action"):
        pre = d.get("pre_fusion") or {}
        fusion_conf = d.get("fusion_confidence")
        fusion_pairs = [
            ("Motor", risk_label(f["engine_level"])),
            ("İlk LLM", risk_label(d.get("llm_level"))),
            ("Fusion öncesi", risk_label(pre.get("auto_level")) if pre else "—"),
            ("Fusion önerisi", risk_label(d.get("fusion_level"))),
            ("Fusion uygulaması", f"{d.get('fusion_action')} → {risk_label(d.get('auto_level'))}"),
            ("Fusion güveni", f"{fusion_conf:.2f}" if isinstance(fusion_conf, (int, float)) else "—"),
        ]
        out.append(P("Otomatik karar zinciri", "h3"))
        out.append(kv_table(fusion_pairs, (34 * mm, None)))
        ev = d.get("fusion_evidence_keys") or []
        if ev:
            out.append(P("Fusion kanıtları: " + ", ".join(ev), "tiny"))
        out.append(Spacer(1, 1.2 * mm))

    out.append(P(n["headline"], "lead"))
    out += bullets((n.get("why_suspicious") or [])[:3])

    movement = (n.get("movement_story") or "").strip()
    rationale = (n.get("decision_rationale") or "").strip()
    if movement or rationale:
        out.append(P("Hareket ve karar özeti", "h3"))
        out.append(P(" ".join(x for x in [movement, rationale] if x), "small"))

    report_text = (n.get("report_assessment") or "").strip()
    if report_text:
        out.append(P("Saha raporu değerlendirmesi", "h3"))
        out.append(P(report_text, "small"))

    uncertainties = (n.get("uncertainties") or [])[:2]
    actions = (n.get("recommended_actions") or [])[:3]
    if uncertainties or actions:
        out.append(_paired_lists("Kritik belirsizlikler", uncertainties, "Önerilen eylemler", actions))

    out.append(P(f"Metin kaynağı: {ctx['source_tag'](vn)}", "tiny"))
    out += [Spacer(1, 3 * mm), _rule(), Spacer(1, 3 * mm)]
    return out


def _reviews(data, ctx) -> list:
    rv, m = data["reviews"], data["meta"]
    out = [PageBreak()] + section("5", "İnsan onayı", "sec5")
    out.append(P(("İnsan onayı AÇIK. Fusion/guardrail tarafından needs_review işaretlenen kararlar analiste gider; "
                  "analistin seçtiği seviye bütün otomatik katmanların üstünde nihai seviyedir." if m["human_review"] else
                  "İnsan onayı KAPALI. Fusion varsa doğrulanmış otomatik sonuç, yoksa ilk motor+LLM fallback sonucu "
                  "uygulanır. Aşağıdaki kayıtlı analist kararları bu raporda uygulanmaz."), "body"))
    out.append(P("Onay bekleyen kararlar", "h3"))
    dossier = lambda x: f"#{x['dossier']}" if x.get("dossier") else "filtre dışı"  # noqa: E731
    if rv["pending"]:
        rows, cmds = [["Araç", "Dosya", "Kare / saat", "Geçici", "Motor", "İlk LLM", "Fusion", "Kural / aksiyon", "Seçenekler"]], []
        for i, x in enumerate(rv["pending"], 1):
            fusion_txt = risk_label(x.get("fusion_level")) if x.get("fusion_level") else "—"
            rule_txt = x.get("fusion_action") or x.get("rule_label") or "—"
            rows.append([x["vehicle_id"], dossier(x), f"{x['frame_id']} · {x['capture_time']}",
                         level_cell(x["current_level"])[0], risk_label(x["engine_level"]), risk_label(x["llm_level"]),
                         fusion_txt, rule_txt, ", ".join(risk_label(o) for o in x.get("options") or [])])
            cmds += level_cmds(3, i, x["current_level"])
        out.append(table(rows, [24 * mm, 13 * mm, 24 * mm, 17 * mm, 13 * mm, 14 * mm, 14 * mm, 28 * mm,
                                CONTENT_W - 147 * mm], extra=cmds))
        for x in rv["pending"]:
            if x.get("note"):
                out.append(P(f"{x['vehicle_id']}: {x['note']}", "tiny"))
    else:
        out.append(P("Kayıt yok.", "small"))
    out.append(P("Analist kararları", "h3"))
    if rv["decided"]:
        rows, cmds = [["Araç", "Dosya", "Seçilen", "Analist", "Zaman", "Motor", "İlk LLM", "Fusion", "Not"]], []
        for i, x in enumerate(rv["decided"], 1):
            r = x["review"]
            rows.append([x["vehicle_id"], dossier(x), level_cell(r["level"])[0], r.get("analyst") or "—",
                         r.get("at_text") or "—", risk_label(x["engine_level"]), risk_label(x["llm_level"]),
                         risk_label(x.get("fusion_level")) if x.get("fusion_level") else "—", r.get("note") or "—"])
            cmds += level_cmds(2, i, r["level"])
        out.append(table(rows, [24 * mm, 13 * mm, 17 * mm, 18 * mm, 21 * mm, 13 * mm, 14 * mm, 14 * mm,
                                CONTENT_W - 134 * mm], extra=cmds))
        out.append(P("'filtre dışı': analistin seçtiği seviye rapor filtresinin altında kaldığı için araç dosyası "
                     "oluşturulmadı; karar yine de burada kayıt altındadır.", "tiny"))
        if not m["human_review"]:
            out.append(P("İnsan onayı kapalı olduğu için bu kararlar bu raporda uygulanmadı.", "tiny"))
    else:
        out.append(P("Kayıt yok.", "small"))
    return out


def _integrity(data, ctx) -> list:
    it = data["integrity"]
    out = [PageBreak()] + section("6", "Saha raporu bütünlüğü", "sec6")
    out.append(P("Raporlar olduğu gibi kabul edilmez: her rapor konum, zaman, tip, davranış ve dost iddiası açısından "
                 "tespit ve iz verisine karşı doğrulanır. Çelişkide doğrulanmış sensör/track olguları esas alınır; "
                 "rapor veya motor hükmü tek başına ground-truth değildir.", "body"))
    rows = [["Hüküm", "Sayı", "Etkisi"]]
    eff = {"destekler": "Yardımcı kanıt; fusion değişikliği için tek başına yeterli değildir",
           "celisir": "Değişiklik dayanağı olamaz; karşı olgu olarak görünür",
           "kismen_uyumlu": "Yardımcı/kısmi kanıt; tek başına seviye değiştirmez",
           "dogrulanamaz": "Seviye değişikliği dayanağı değildir", "ilgisiz": "Etkisiz",
           "manipulasyon": "Talimat uygulanmaz, kanıt olarak kullanılmaz"}
    for k, v in it["verdict_counts"].items():
        rows.append([VERDICT_LABELS[k], str(v), eff[k]])
    out.append(table(rows, [32 * mm, 16 * mm, CONTENT_W - 48 * mm], zebra=True))
    out.append(P("Manipülasyon (talimat içeren) raporlar", "h3"))
    if it["manipulation"]:
        rows = [["Rapor", "Saat", "Kaynak", "Talimat kısmı", "Değerlendirme"]]
        for x in it["manipulation"]:
            rows.append([x["report_id"], x["time"], SOURCE_LABELS.get(x["source"], x["source"]), x["span"] or "—",
                         x["summary"]])
        out.append(table(rows, [14 * mm, 12 * mm, 20 * mm, 50 * mm, CONTENT_W - 96 * mm]))
    else:
        out.append(P("Kayıt yok.", "small"))
    out.append(P("Rapor tipleri", "h3"))
    rows = [["Tip", "Sayı"]] + [[k, str(v)] for k, v in it["type_counts"].items()]
    out.append(table(rows, [60 * mm, 20 * mm]))
    out.append(P(f"Şüpheli araçlarla eşleşen raporlar: {', '.join(it['related_report_ids']) or 'yok'}.", "small"))
    return out


def _appendix(data, ctx) -> list:
    m = data["meta"]
    out = [PageBreak()] + section("7", "Ek: üretim bilgileri", "sec7")
    st = ctx["narrative_stats"]
    pairs = [("Rapor No", m["report_id"]), ("Olgu özeti (digest)", m["facts_digest"]),
             ("Tema sürümü", THEME_VERSION), ("İstem sürümü", ctx["prompt_version"]),
             ("Anlatım modeli", ctx["narrative_model"] or "yok (deterministik şablon)"),
             ("İlk LLM modeli", m.get("assess_model") or "yok"),
             ("Fusion modeli", m.get("fusion_model") or "yok / devre dışı"),
             ("Fusion sonucu", f"{m.get('frames_fusion', 0)} başarılı · {m.get('frames_fusion_error', 0)} hata"),
             ("Anlatım kaynakları", f"LLM {st['llm']} · önbellek {st['cache']} · şablon {st['template']} · hata {st['errors']}"),
             ("Kare değerlendirme kapsamı", {"all": "tüm kareler (ilk LLM + fusion)", "min_risk": "motor seviyesi ≥ filtre",
                                            "none": "yalnızca mevcut önbellek"}.get(m["assess_scope"], m["assess_scope"])),
             ("Üretim süresi", f"{ctx['elapsed_s']:.1f} sn")]
    out.append(kv_table(pairs, (46 * mm, None)))
    out.append(P("Aynı olgu özeti (digest) aynı girdi anlamına gelir: aynı veri, aynı kararlar ve aynı filtreyle "
                 "üretilen raporlar aynı içeriği ve biçimi taşır (anlatım önbelleği sayesinde metin de değişmez).", "tiny"))
    out.append(P("Karar durumları sözlüğü", "h3"))
    out.append(table([["Durum", "Anlamı"]] + [[k, v] for k, v in STATUS_LABELS.items()], [34 * mm, CONTENT_W - 34 * mm],
                     zebra=True))
    notes = ctx["all_notes"]
    out.append(P("Korkuluk notları", "h3"))
    if notes:
        shown = notes[:12]
        out += bullets(shown)
        if len(notes) > len(shown):
            out.append(P(f"{len(notes) - len(shown)} ek teknik not rapor görünümünde tekrar edilmedi.", "tiny"))
    else:
        out.append(P("Kayıt yok.", "small"))
    return out


# ------------------------------------------------------------------ ana giriş
def render_pdf(path, data: dict, ctx: dict) -> int:
    _register_fonts()
    S.clear(); S.update(_styles())
    meta = data["meta"]
    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=M, rightMargin=M, topMargin=M, bottomMargin=M,
                          title=f"{REPORT_TITLE} — {meta['report_id']}", author=ORG_NAME,
                          subject=f"Şüpheli araç raporu · {meta['filter_label']}", creator=f"{ORG_NAME} threat_report",
                          invariant=1)
    cover = Frame(M, M, CONTENT_W, PAGE_H - 2 * M, id="cover", leftPadding=0, rightPadding=0, topPadding=0,
                  bottomPadding=0)
    body = Frame(M, FOOTER_H_MM * mm + 4 * mm, CONTENT_W, PAGE_H - HEADER_H_MM * mm - FOOTER_H_MM * mm - 10 * mm,
                 id="body", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate("cover", [cover], onPage=_on_cover(meta)),
                          PageTemplate("body", [body], onPage=_on_body(meta))])
    story = [Bookmark("Kapak", "cover", 0)] + _cover(data, ctx) + [NextPageTemplate("body"), PageBreak()]
    story += _executive(data, ctx) + _situation(data, ctx) + _methodology(data, ctx)
    story += [PageBreak()] + section("4", f"Araç değerlendirme kayıtları ({len(data['vehicles'])})", "sec4")
    story.append(P("Kayıtlar nihai risk seviyesi, ETA ve üsse mesafeye göre sıralıdır. Her kayıt yalnızca karar için "
                   "gerekli tespit, hareket, saha raporu ve eylem özetini içerir; tekrar eden teknik denetim dökümleri "
                   "rapor görünümüne alınmaz.", "body"))
    if not data["vehicles"]:
        story.append(P("Seçilen filtrede şüpheli araç yok.", "small"))
    for f in data["vehicles"]:
        story += _vehicle(f, data, ctx)
    story += _reviews(data, ctx) + _integrity(data, ctx) + _appendix(data, ctx)
    doc.build(story, canvasmaker=NumberedCanvas)
    return doc.page
