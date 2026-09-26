"""PDF yerleşimi (reportlab). Bölüm sırası, sayfa şablonları, tablo biçimleri ve renkler SABİTTİR:
her çalıştırma aynı iskeleti üretir; boş bölümler "Kayıt yok." ile yine görünür.

Sayfa düzeni (A4 dikey):
  Kapak → 1 Yönetici özeti → 2 Durum haritası → 3 Karar yöntemi → 4 Araç dosyaları (her araç yeni sayfa:
  01 Tespit ve konumlandırma · 02 Hareket analizi · 03 Risk analizi ve karar) → 5 İnsan onayı →
  6 Saha raporu bütünlüğü → 7 Ek: üretim bilgileri
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
        c.drawString(x, self.h - 5.6 * mm, f"ARAÇ DOSYASI #{f['index']} / {self.total}")
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
        c.drawRightString(self.w - 4 * mm, 6.6 * mm, f"Motor: {risk_label(f['engine_level'])}")
        c.drawRightString(self.w - 4 * mm, 3.2 * mm, _fit(c, f["status_label"], "Body", 6.4, 56 * mm))


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
        c.drawString(M, 11 * mm, "Otomatik üretilmiştir. Seviyeler karar tablosu ve (açıksa) analist kararlarından gelir; "
                                 "açıklama metinleri olgulara dayanır.")
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
                                 f"{m['frames_llm']} kare LLM ile" + (f" ({m['assess_model']})" if m["assess_model"] else "")),
        ("İnsan onayı (son söz insanda)", "AÇIK — riski düşüren / belirsiz kararlar analiste gider" if m["human_review"]
         else "KAPALI — karar tablosunun otomatik sonucu uygulanır"),
        ("Açıklama metinleri", src),
        ("Tespit katmanı", m["detector"]),
    ]
    out.append(kv_table(pairs, (46 * mm, None)))
    out.append(Spacer(1, 6 * mm))
    out.append(P("İçindekiler", "h3"))
    toc = ["1  Yönetici özeti", "2  Durum haritası", "3  Karar yöntemi", f"4  Araç dosyaları ({n})",
           "5  İnsan onayı", "6  Saha raporu bütünlüğü", "7  Ek: üretim bilgileri"]
    out += [P(t, "small") for t in toc]
    return out


def _summary_table(vs) -> Table:
    head = ["#", "Araç / iz", "Tip", "Bölge", "Nihai", "Motor", "Karar", "Üsse", "ETA", "Senaryo"]
    rows, cmds = [head], []
    for i, f in enumerate(vs, 1):
        fe = f.get("features") or {}
        rows.append([str(f["index"]), f["track_id"] or f["vehicle_id"], LABEL_TR.get(f["label"], f["label"] or "—"),
                     f["zone"], level_cell(f["final_level"])[0], risk_label(f["engine_level"]),
                     STATUS_SHORT.get(f["status"], f["status"]), km(f["dist_to_base_m"]),
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
    out.append(P("Şüpheli araç listesi", "h3"))
    out.append(_summary_table(vs) if vs else P("Seçilen filtrede şüpheli araç yok.", "small"))
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
    out.append(P("Her aracın seviyesi üç katmanda belirlenir ve sıra sabittir: <b>(1) kural tabanlı motor</b> tespit, "
                 "iz ve saha raporlarından senaryo ve seviye üretir; <b>(2) LLM ajanı</b> kareyi değerlendirip kendi "
                 "seviyesini gerekçesiyle önerir, bu öneri aşağıdaki karar tablosundan geçer; <b>(3) insan onayı</b> "
                 "açıksa riski düşüren ya da belirsiz her karar analistin onayına gider ve analistin seçimi son sözdür. "
                 "Saha raporu metinleri güvenilmez veri olarak işlenir: içlerindeki talimatlar uygulanmaz, çelişen / "
                 "ilgisiz / manipülasyon hükümlü raporlar hiçbir seviye değişikliğine dayanak olamaz.", "body", raw=True))
    out.append(P("Motor kuralları (öncelik sırasıyla; ilk eşleşen kural senaryoyu belirler)", "h3"))
    rows, cmds = [["Senaryo", "Seviye", "Koşullar (hepsi sağlanmalı)"]], []
    for i, r in enumerate(mt["rules"], 1):
        rows.append([f"{r['label']}\n({r['scenario']})".replace("\n", " "), level_cell(r["risk"])[0],
                     " · ".join(r["conds"])])
        cmds += level_cmds(1, i, r["risk"])
    out.append(table(rows, [52 * mm, 22 * mm, CONTENT_W - 74 * mm], extra=cmds))
    out.append(P("Karar tablosu (motor + LLM)", "h3"))
    rows = [["Kural", "Ne zaman", "İnsan onayı kapalı", "İnsan onayı açık"]]
    for r in mt["decision_table"]:
        rows.append([r["label"], r["when"], r["hil_off"], r["hil_on"]])
    out.append(table(rows, [44 * mm, CONTENT_W - 44 * mm - 60 * mm, 26 * mm, 34 * mm], zebra=True))
    out.append(P("Riski artırmak kolay, düşürmek zordur: LLM gerekçeyle en fazla bir kademe yükseltebilir; düşürme "
                 "için motorun sınırda olması, resmi kaynaklı ve motorun 'destekler' dediği bir rapor, KRİTİK olmaması "
                 "ve tek kademe olması gerekir. Nedeni: saha raporuna gömülü bir talimat LLM'i ikna etse bile riski "
                 "düşüremez.", "small"))
    out.append(P("Eşikler", "h3"))
    out.append(kv_table(list(mt["thresholds"].items()), (52 * mm, None)))
    out.append(Spacer(1, 2 * mm))
    out.append(banner(("Bu raporda insan onayı AÇIK: seviye önceliği analist kararı → karar tablosu (onay seviyesi) → "
                       "motor." if m["human_review"] else
                       "Bu raporda insan onayı KAPALI: seviye önceliği karar tablosu (otomatik seviye) → motor. "
                       "Analist kararları kayıtlı olsa bile uygulanmaz."), ACCENT))
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
    th = ctx["thresholds"]
    vn = ctx["vehicle_narr"][f["key"]]
    n = vn["narrative"]
    total = len(data["vehicles"])
    ident = f["track_id"] or f["vehicle_id"]
    out = [PageBreak(), Bookmark(f"#{f['index']} {ident} — {risk_label(f['final_level'])}", f"v{f['index']}", 1),
           VehicleHeader(f, total), Spacer(1, 2.5 * mm)]
    d, rv = f.get("decision"), f.get("review")
    if f["status"] == "onay_bekliyor":
        opts = ", ".join(risk_label(x) for x in (d or {}).get("options") or [])
        out += [banner(f"ANALİST ONAYI BEKLİYOR — gösterilen seviye geçicidir. Seçenekler: {opts}. "
                       f"({(d or {}).get('rule_label')})", RISK_COLORS["ORTA"]), Spacer(1, 2 * mm)]
    elif rv:
        out += [banner(f"Analist kararı: {risk_label(rv['level'])} — {rv.get('analyst') or 'analist'}, "
                       f"{rv.get('at_text') or ''}" + (f" · Not: {rv['note']}" if rv.get("note") else ""), ACCENT),
                Spacer(1, 2 * mm)]
    fe = f.get("features") or {}
    if f["track"]:
        tiles = [(km(f["dist_to_base_m"]), "üsse mesafe (çekim)"), (num(fe.get("eta_min"), " dk"), "ETA"),
                 (num(fe.get("speed_now_mps"), " m/s", 1), "hız (son 10 dk)"),
                 (num(fe.get("heading_offset_deg"), "°"), "üsse yönelim sapması"),
                 (num(fe.get("approach_last60_m"), " m"), "son 60 dk yaklaşma")]
    else:
        nt = f.get("nearest_track") or {}
        tiles = [(km(f["dist_to_base_m"]), "üsse mesafe"), (f"{f['bearing_from_base_deg']:.0f}°", "üsten kerteriz"),
                 (f"{f['confidence']:.2f}" if f.get("confidence") is not None else "—", "tespit güveni"),
                 (nt.get("track_id") or "—", "olası iz"), (num(nt.get("dist_m"), " m", 1), "olası ize uzaklık")]
    out += [kpi_tiles(tiles), Spacer(1, 3 * mm)]

    # değerlendirme özeti (LLM / şablon)
    summ = [P(f"<b>{esc(n['headline'])}</b>", "body", raw=True), P("Neden şüpheli?", "h3")] + bullets(n["why_suspicious"])
    summ.append(P(f"Metin kaynağı: {ctx['source_tag'](vn)}", "tiny"))
    out.append(box(summ))

    # 01 tespit ve konumlandırma
    out += subsection("01", "Tespit ve konumlandırma")
    det = kv_table(_detection_pairs(f), (28 * mm, (CONTENT_W - 3 * mm) / 2 - 28 * mm))
    if f.get("frame"):
        png, real = ctx["frame_png"][f["key"]]
        left = [img(png, "frame", (CONTENT_W - 3 * mm) / 2),
                P("Gerçek kare görüntüsü üzerine tespit kutusu." if real else
                  "Görüntü dosyası bulunamadı; kare şematik, piksel konumları gerçektir. Gri kutular: karedeki diğer "
                  "araçlar.", "tiny")]
        out.append(two_col(left, det))
    else:
        out.append(det)

    # 02 hareket analizi
    out += subsection("02", "Hareket analizi")
    half = (CONTENT_W - 3 * mm) / 2
    if f["track"]:
        out.append(two_col(img(ctx["path_png"][f["key"]], "path", half), img(ctx["ts_png"][f["key"]], "timeseries", half)))
        out.append(P(n["movement_story"], "body"))
        stops = fe.get("stops") or []
        right = [P("Duraklamalar", "h3")]
        if stops:
            rows = [["Başlangıç", "Bitiş", "Süre", "Üsse"]] + [[s["start"], s["end"], f"{s['minutes']} dk",
                                                                km(s["dist_to_base_m"])] for s in stops]
            right.append(table(rows, [20 * mm, 16 * mm, 16 * mm, half - 52 * mm]))
        else:
            right.append(P(f"≥ {th.stop_min_minutes} dk duraklama yok.", "small"))
        feats = kv_table(_features_pairs(f), (27 * mm, half - 27 * mm))
        out.append(two_col([P("Hareket öznitelikleri", "h3"), feats], right))
        ac = f["track"].get("after_capture")
        if ac:
            out.append(P(f"Not: iz çekimden sonra {ac['until']}'e kadar sürüyor (bu aralıkta üsse en yakın "
                         f"{km(ac['min_dist_m'])}). Seviye çekim anındaki davranışa göredir.", "tiny"))
    else:
        nt = f.get("nearest_track") or {}
        h = nt.get("hypothesis")
        right = [P("İz durumu", "h3"),
                 P("Bu araç için hareket kaydı eşleşmedi; hız, yön ve duraklama bilinmiyor. Seviye yalnızca mesafe "
                   "eşiğine dayanır.", "small")]
        if h:
            right += [P("Olası iz (hipotez)", "h3"),
                      kv_table([("İz", f"{nt['track_id']} · çekim anında {nt['dist_m']:.1f} m"),
                                ("Atandığı kayıt", nt.get("assigned_to") or "—"),
                                ("Motorun o iz için yorumu", f"{h['scenario_label']} ({risk_label(h['risk'])})"),
                                ("İzin üsse mesafesi", km(h["dist_now_m"])),
                                ("Son 60 dk yaklaşma", num(h.get("approach_last60_m"), " m"))],
                               (27 * mm, half - 27 * mm)),
                      P("Bilgi amaçlıdır; nihai seviyeyi değiştirmez. Bire bir iz eşleştirmesi nedeniyle aynı araç "
                        "daha önceki bir karede kaydedilmiş olabilir — analist doğrulaması önerilir.", "tiny")]
        out.append(two_col(img(ctx["path_png"][f["key"]], "path", half), right))
        out.append(P(n["movement_story"], "body"))

    # 03 risk analizi ve karar
    out += subsection("03", "Risk analizi ve karar")
    rows, cmds = _rule_rows(f)
    out.append(P("Kural değerlendirmesi — neden bu senaryo, neden daha yüksek değil", "h3"))
    out.append(table(rows, [44 * mm, 44 * mm, 24 * mm, 26 * mm, CONTENT_W - 138 * mm], extra=cmds))
    out.append(P("Karar zinciri", "h3"))
    rows, cmds = [["Aşama", "Seviye", "Açıklama"]], []
    for i, c in enumerate(f["decision_chain"], 1):
        rows.append([c["stage"], level_cell(c["level"])[0] if c["level"] else "—", c["detail"]])
        cmds += level_cmds(1, i, c["level"])
    cmds.append(("LINEABOVE", (0, len(rows) - 1), (-1, len(rows) - 1), 0.8, C(INK_2)))
    out.append(table(rows, [34 * mm, 22 * mm, CONTENT_W - 56 * mm], extra=cmds))
    out.append(P("Karar gerekçesi", "h3"))
    out.append(P(n["decision_rationale"], "body"))

    out.append(P("Saha raporları", "h3"))
    reps = f.get("related_reports") or []
    if reps:
        rows, cmds = [["Rapor", "Saat", "Kaynak", "Motor hükmü", "Motor özeti / rapor metni (güvenilmez veri)"]], []
        for r in reps:
            txt = [P(r["summary"], "cell"), P(f"“{r['text']}”", "cellm")]
            if r["injection"]:
                txt.append(P("⚠ Talimat içeriyor — uygulanmadı.", "cellb"))
            rows.append([r["report_id"], r["time"], SOURCE_LABELS.get(r["source"], r["source"]),
                         VERDICT_LABELS.get(r["verdict"], r["verdict"]), txt])
        out.append(table(rows, [14 * mm, 12 * mm, 20 * mm, 22 * mm, CONTENT_W - 68 * mm]))
    else:
        out.append(P("Bu araçla eşleşen saha raporu yok.", "small"))
    out.append(P(n["report_assessment"], "body"))

    out.append(_paired_lists("Belirsizlikler", n["uncertainties"], "Önerilen eylemler", n["recommended_actions"]))
    notes = vn.get("notes") or []
    notes += (f.get("assessment") or {}).get("guardrail_notes") or []
    if notes:
        out.append(P("Korkuluk notları: " + " · ".join(notes), "tiny"))
    return out


def _reviews(data, ctx) -> list:
    rv, m = data["reviews"], data["meta"]
    out = [PageBreak()] + section("5", "İnsan onayı", "sec5")
    out.append(P(("İnsan onayı AÇIK. Riski düşüren, belirsiz ve aşırı yükseltme kararları analist onayı olmadan "
                  "uygulanmaz; analistin seçtiği seviye nihai seviyedir." if m["human_review"] else
                  "İnsan onayı KAPALI. Karar tablosunun otomatik sonucu uygulandı. Aşağıdaki liste, özellik açık olsaydı "
                  "analiste gidecek kararları bilgi amaçlı gösterir; kayıtlı analist kararları uygulanmaz."), "body"))
    out.append(P("Onay bekleyen kararlar", "h3"))
    dossier = lambda x: f"#{x['dossier']}" if x.get("dossier") else "filtre dışı"  # noqa: E731
    if rv["pending"]:
        rows, cmds = [["Araç", "Dosya", "Kare / saat", "Geçici", "Motor", "LLM", "Kural", "Seçenekler"]], []
        for i, x in enumerate(rv["pending"], 1):
            rows.append([x["vehicle_id"], dossier(x), f"{x['frame_id']} · {x['capture_time']}",
                         level_cell(x["current_level"])[0], risk_label(x["engine_level"]), risk_label(x["llm_level"]),
                         x.get("rule_label") or "—", ", ".join(risk_label(o) for o in x.get("options") or [])])
            cmds += level_cmds(3, i, x["current_level"])
        out.append(table(rows, [28 * mm, 15 * mm, 28 * mm, 18 * mm, 15 * mm, 15 * mm, 30 * mm, CONTENT_W - 149 * mm],
                         extra=cmds))
        for x in rv["pending"]:
            if x.get("note"):
                out.append(P(f"{x['vehicle_id']}: {x['note']}", "tiny"))
    else:
        out.append(P("Kayıt yok.", "small"))
    out.append(P("Analist kararları", "h3"))
    if rv["decided"]:
        rows, cmds = [["Araç", "Dosya", "Seçilen", "Analist", "Zaman", "Motor", "LLM", "Not"]], []
        for i, x in enumerate(rv["decided"], 1):
            r = x["review"]
            rows.append([x["vehicle_id"], dossier(x), level_cell(r["level"])[0], r.get("analyst") or "—",
                         r.get("at_text") or "—", risk_label(x["engine_level"]), risk_label(x["llm_level"]),
                         r.get("note") or "—"])
            cmds += level_cmds(2, i, r["level"])
        out.append(table(rows, [28 * mm, 15 * mm, 18 * mm, 20 * mm, 22 * mm, 15 * mm, 15 * mm, CONTENT_W - 133 * mm],
                         extra=cmds))
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
                 "tespit ve iz verisine karşı doğrulanır. Çelişkide raporun değil tespitin esas alınır.", "body"))
    rows = [["Hüküm", "Sayı", "Etkisi"]]
    eff = {"destekler": "Kanıt olarak kullanılabilir (resmi ise seviye düşürmeye dayanak olabilir)",
           "celisir": "Kanıt olarak kullanılmaz; tehditle çelişen 'olağan' iddiası işaretlenir",
           "kismen_uyumlu": "Kısmi kanıt; davranış iddiası karşılaştırılamaz",
           "dogrulanamaz": "Etkisiz", "ilgisiz": "Etkisiz", "manipulasyon": "Talimat uygulanmaz, kanıt olarak kullanılmaz"}
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
             ("Anlatım kaynakları", f"LLM {st['llm']} · önbellek {st['cache']} · şablon {st['template']} · hata {st['errors']}"),
             ("Kare değerlendirme kapsamı", {"all": "tüm kareler", "min_risk": "motor seviyesi ≥ filtre",
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
    out += bullets(notes[:40]) if notes else [P("Kayıt yok.", "small")]
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
    story += [PageBreak()] + section("4", f"Araç dosyaları ({len(data['vehicles'])})", "sec4")
    story.append(P("Her dosya brief'teki ajan akışını izler: 01 tespit ve konumlandırma → 02 hareket analizi → "
                   "03 risk analizi ve karar. Dosyalar nihai seviye (yüksekten düşüğe), sonra ETA ve üsse mesafeye "
                   "göre sıralıdır.", "body"))
    if data["vehicles"]:
        story.append(_summary_table(data["vehicles"]))
    else:
        story.append(P("Seçilen filtrede şüpheli araç yok.", "small"))
    for f in data["vehicles"]:
        story += _vehicle(f, data, ctx)
    story += _reviews(data, ctx) + _integrity(data, ctx) + _appendix(data, ctx)
    doc.build(story, canvasmaker=NumberedCanvas)
    return doc.page
