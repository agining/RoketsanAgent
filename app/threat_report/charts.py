"""Rapor grafikleri (matplotlib, Agg). Her grafik SABİT boyut ve SABİT rcParams ile çizilir; kullanıcının
matplotlibrc'si ya da sistem fontu sonucu değiştirmez. Çıktı PNG bayt dizisidir.

Kurallar (dataviz): tek y ekseni (mesafe ve hız ayrı panellerde), ince çizgiler, çekik ızgara, risk rengi her
zaman şekil + etiketle birlikte, metin mürekkep renginde (seri renginde değil).
"""
from __future__ import annotations

import io
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402

from .theme import (BASELINE, CHART_DPI, HAIRLINE, INK, INK_2, MUTED, PANEL, RISK_COLORS, SURFACE,  # noqa: E402
                    TRACK_CONTEXT, font_dir, risk_label)

MARKERS = {"DUSUK": "o", "ORTA": "^", "YUKSEK": "D", "KRITIK": "s"}   # şekil de seviyeyi taşır
for _f in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
    font_manager.fontManager.addfont(str(font_dir() / _f))

RC = {
    "font.family": "DejaVu Sans", "font.size": 7.0, "axes.titlesize": 7.6, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.titlecolor": INK, "axes.labelsize": 6.6, "axes.labelcolor": INK_2,
    "xtick.labelsize": 6.2, "ytick.labelsize": 6.2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": BASELINE, "axes.linewidth": 0.6, "axes.facecolor": SURFACE, "figure.facecolor": "white",
    "axes.grid": True, "grid.color": HAIRLINE, "grid.linewidth": 0.5, "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False, "legend.fontsize": 6.0, "legend.frameon": False,
    "text.color": INK, "lines.solid_capstyle": "round", "lines.dash_capstyle": "round",
    "savefig.dpi": CHART_DPI, "path.simplify": False, "axes.unicode_minus": True,
}
SIZES = {"overview": (7.0, 6.3), "path": (3.45, 3.25), "timeseries": (3.45, 3.25), "frame": (3.45, 2.15)}


def _png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=CHART_DPI, facecolor="white", metadata={"Software": None})
    plt.close(fig)
    return buf.getvalue()


def _fig(kind: str, **kw):
    return plt.figure(figsize=SIZES[kind], layout="constrained", **kw)


def _base(ax, label=True, size=7):
    ax.plot([0], [0], marker="D", ms=size, mfc="white", mec=INK, mew=1.2, zorder=6, ls="none")
    if label:
        ax.annotate("ÜS", (0, 0), xytext=(5, -9), textcoords="offset points", fontsize=6.4, fontweight="bold",
                    color=INK, zorder=7)


def _rings(ax, radii, label=True):
    for r in radii:
        ax.add_patch(Circle((0, 0), r, fill=False, ec=BASELINE, lw=0.5, ls=(0, (3, 3)), zorder=1))
        if label:
            a = math.radians(205)
            ax.annotate(f"{r:g} km", (r * math.cos(a), r * math.sin(a)), xytext=(2, -1), textcoords="offset points",
                        fontsize=5.2, color=MUTED, zorder=1)


def _zones(ax, zones) -> list:
    return [ax.annotate(z["name"].replace(" ", "\n", 1), tuple(z["xy_km"]), ha="center", va="center", fontsize=5.2,
                        color=MUTED, zorder=2, alpha=0.95) for z in zones]


def _drop_overlapping(fig, background: list, foreground: list) -> None:
    """Arka plan etiketlerinden (bölge adları) ön plandaki bir etiketle gerçekten çakışanları kaldırır.
    Ölçüm çizilmiş metnin kutusuyla yapılır (tahmin değil)."""
    fig.canvas.draw()
    r = fig.canvas.get_renderer()
    boxes = [a.get_window_extent(r) for a in foreground]
    for a in background:
        bb = a.get_window_extent(r)
        if any(bb.overlaps(b) for b in boxes):
            a.remove()


def _equal_limits(ax, xs, ys, pad=0.25, min_half=0.6):
    """Eşit ölçek (1 km yatay = 1 km dikey); eksen kutusu sabit kalır, sınırlar genişler."""
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = max((x1 - x0) / 2 + pad, (y1 - y0) / 2 + pad, min_half)
    ax.set_xlim(cx - half, cx + half)
    ax.set_ylim(cy - half, cy + half)
    ax.set_aspect("equal", adjustable="box")


def _place_labels(ax, items, span, avoid=()):
    """Etiket çakışması önleme (veri koordinatında): her etiket için noktanın çevresindeki 8 aday konumdan
    başka etiket ve işaretlerle çakışmayan ilki seçilir; uzaksa noktaya ince bir çizgiyle bağlanır."""
    w, h = span * 0.052, span * 0.034           # "#12" etiket kutusu tahmini
    d = span * 0.03
    cands = [(d, d * 0.4), (d, -d * 1.4), (-d - w, d * 0.4), (-d - w, -d * 1.4),
             (-w / 2, d * 1.1), (-w / 2, -d * 1.9), (d * 2.2, -h / 2), (-d * 2.2 - w, -h / 2),
             (d * 2.4, d * 1.6), (-d * 2.4 - w, d * 1.6), (d * 2.4, -d * 2.6), (-d * 2.4 - w, -d * 2.6)]
    boxes = [(ax_ - span * 0.012, ay_ - span * 0.012, span * 0.024, span * 0.024) for ax_, ay_ in avoid]

    def hit(b):
        x, y, bw, bh = b
        return sum(1 for (X, Y, W, H) in boxes if x < X + W and X < x + bw and y < Y + H and Y < y + bh)

    anns = []
    for x, y, text, color in items:
        best = min(((hit((x + ox, y + oy, w, h)), k, (x + ox, y + oy)) for k, (ox, oy) in enumerate(cands)))
        lx, ly = best[2]
        boxes.append((lx, ly, w, h))
        far = math.hypot(lx + w / 2 - x, ly + h / 2 - y) > span * 0.05
        anns.append(ax.annotate(text, (x, y), xytext=(lx + w * 0.08, ly + h * 0.22), textcoords="data", fontsize=6.0,
                                fontweight="bold", color=INK, zorder=9, annotation_clip=False,
                                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.4, shrinkA=0, shrinkB=2) if far else None,
                                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec=color, lw=0.6, alpha=0.95)))
    return anns


def _split_track(points, t_cap):
    pre = [p for p in points if p["t"] <= t_cap]
    post = [p for p in points if p["t"] >= t_cap]
    return pre, post


def _inside(p, half):
    return abs(p["x_km"]) <= half and abs(p["y_km"]) <= half


def _entry_point(pts, half, inset=0.96):
    """İzin kare harita sınırına (±half·inset) ilk girdiği nokta: dışarıdaki a → içerideki b doğru parçası."""
    h = half * inset
    for a, b in zip(pts, pts[1:]):
        if _inside(a, h) or not _inside(b, h):
            continue
        ax_, ay_, bx, by = a["x_km"], a["y_km"], b["x_km"], b["y_km"]
        ts = []
        for s0, s1, lim in ((ax_, bx, h), (ax_, bx, -h), (ay_, by, h), (ay_, by, -h)):
            if s1 != s0:
                t = (lim - s0) / (s1 - s0)
                if 0 <= t <= 1:
                    x, y = ax_ + t * (bx - ax_), ay_ + t * (by - ay_)
                    if abs(x) <= h + 1e-9 and abs(y) <= h + 1e-9:
                        ts.append((t, x, y))
        if ts:
            _, x, y = max(ts)            # dışarıdan gelirken sınırı son kestiği yer = giriş
            return x, y
    return None


# ------------------------------------------------------------------ genel durum haritası
def overview_map(data: dict) -> bytes:
    """Harita araç konumlarına göre kırpılır (üs merkezde); dışarıdan gelen izlerin girişinde başlangıç mesafesi
    yazılır. Böylece uzaktan gelen tek bir iz, üs çevresindeki araçları sıkıştırmaz."""
    meta, vs = data["meta"], data["vehicles"]
    with plt.rc_context(RC):
        fig = _fig("overview")
        ax = fig.add_subplot()
        rmax = max([math.hypot(*f["xy_km"]) for f in vs] + [1.0])
        half = math.ceil((rmax + 0.7) * 2) / 2
        span = 2 * half
        _rings(ax, [r for r in range(1, int(half) + 1)])
        labels, avoid, entry_anns = [], [(0.0, 0.0)], []
        for f in reversed(vs):              # önemli olanlar en üstte çizilsin
            col, lvl = RISK_COLORS[f["final_level"]], f["final_level"]
            if f["track"]:
                pre, post = _split_track(f["track"]["points"], f["capture_min"])
                if len(post) > 1:
                    ax.plot([p["x_km"] for p in post], [p["y_km"] for p in post], color=TRACK_CONTEXT, lw=0.9,
                            ls=(0, (2, 2)), zorder=3)
                ax.plot([p["x_km"] for p in pre], [p["y_km"] for p in pre], color=col, lw=1.5, zorder=4)
                p0 = pre[0]
                if _inside(p0, half):
                    ax.plot([p0["x_km"]], [p0["y_km"]], marker="o", ms=3.2, mfc="white", mec=col, mew=0.9, zorder=5)
                else:                        # iz haritanın dışından geliyor: sınırı kestiği yere not düş
                    ex = _entry_point(pre, half)
                    if ex:
                        ex_x, ex_y = ex
                        entry_anns.append(ax.annotate(f"#{f['index']} iz başlangıcı: üsse {p0['dist_m'] / 1000:.1f} km ({p0['time']})",
                                    (ex_x, ex_y), xytext=(-4 if ex_x > 0 else 4, -9 if ex_y > 0 else 6),
                                    textcoords="offset points", ha="right" if ex_x > 0 else "left", va="center",
                                    fontsize=5.4, color=INK_2, zorder=6,
                                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85)))
                        avoid.append((ex_x, ex_y))
            x, y = f["xy_km"]
            ax.plot([x], [y], marker=MARKERS[lvl], ms=6.5, mfc=col, mec="white", mew=0.8, zorder=8, ls="none")
            labels.append((x, y, f"#{f['index']}", col))
            avoid.append((x, y))
        zone_anns = _zones(ax, meta["zones"])
        _base(ax, size=8)
        ax.set_xlim(-half, half); ax.set_ylim(-half, half)
        ax.set_aspect("equal", adjustable="box")
        num_anns = _place_labels(ax, list(reversed(labels)), span, avoid)
        ax.set_xlabel("Doğu (km)")
        ax.set_ylabel("Kuzey (km)")
        present = [lv for lv in ("KRITIK", "YUKSEK", "ORTA", "DUSUK") if any(f["final_level"] == lv for f in vs)]
        handles = [Line2D([], [], marker=MARKERS[lv], ls="-", color=RISK_COLORS[lv], mfc=RISK_COLORS[lv], mec="white",
                          ms=6, lw=1.4, label=risk_label(lv)) for lv in present]
        handles += [Line2D([], [], marker="D", ls="none", mfc="white", mec=INK, ms=6, label="Merkez Üs"),
                    Line2D([], [], color=TRACK_CONTEXT, lw=0.9, ls=(0, (2, 2)), label="Çekim sonrası iz"),
                    Line2D([], [], marker="o", ls="none", mfc="white", mec=INK_2, ms=4, label="İz başlangıcı")]
        ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=len(handles),
                  handlelength=2.2, columnspacing=1.4)
        ax.set_title("Şüpheli araçlar — üsse göre çekim konumu ve rota (#: dosya no)")
        _drop_overlapping(fig, zone_anns, entry_anns + num_anns)
        return _png(fig)


# ------------------------------------------------------------------ araç rotası
def _side_label(ax, x, y, text, cx, above=True, gap=4, **kw):
    """Etiketi noktanın eksen merkezine bakan tarafına, üstüne ya da altına yazar (kenardan taşmasın).
    Çok satırlı metin de doğru hizalanır: üstteyse alt kenarı, alttaysa üst kenarı noktaya yakın durur."""
    right = x <= cx
    y0, y1 = ax.get_ylim()
    lines = text.count("\n") + 1
    if above and y > y1 - (y1 - y0) * (0.08 + 0.05 * lines):   # üst kenara yakınsa başlığa değmesin
        above = False
    elif not above and y < y0 + (y1 - y0) * (0.06 + 0.05 * lines):
        above = True
    ax.annotate(text, (x, y), xytext=(6 if right else -6, gap if above else -gap), textcoords="offset points",
                ha="left" if right else "right", va="bottom" if above else "top",
                fontsize=kw.pop("fontsize", 5.6), zorder=kw.pop("zorder", 8), linespacing=1.15, **kw)


def _cluster(items: list[tuple[float, float, str]], tol: float) -> list[list]:
    """Aynı noktaya düşen etiketleri birleştirir (ör. aynı yerde başlangıç + iki duraklama)."""
    out: list[list] = []
    for x, y, txt in items:
        for c in out:
            if math.hypot(x - c[0], y - c[1]) <= tol:
                c[2].append(txt)
                break
        else:
            out.append([x, y, [txt]])
    return out


def vehicle_path(f: dict, meta: dict) -> bytes:
    col, lvl = RISK_COLORS[f["final_level"]], f["final_level"]
    tr, nt = f.get("track"), f.get("nearest_track") or {}
    cx, cy = f["xy_km"]
    fe = f.get("features") or {}
    # sınırlar önce: etiket yönü eksen merkezine göre seçilecek
    xs, ys = [0.0, cx], [0.0, cy]
    if f.get("frame"):
        xs += [p[0] for p in f["frame"]["footprint_km"]]; ys += [p[1] for p in f["frame"]["footprint_km"]]
    pts = tr["points"] if tr else (nt.get("points") or [])
    xs += [p["x_km"] for p in pts]; ys += [p["y_km"] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    mid_x = (x0 + x1) / 2
    with plt.rc_context(RC):
        fig = _fig("path")
        ax = fig.add_subplot()
        _equal_limits(ax, xs, ys, pad=0.22, min_half=0.35)
        if f.get("frame"):
            ax.add_patch(Polygon(f["frame"]["footprint_km"], closed=True, fc=PANEL, ec=BASELINE, lw=0.6, zorder=2))
        if tr:
            pre, post = _split_track(pts, f["capture_min"])
            if len(post) > 1:
                ax.plot([p["x_km"] for p in post], [p["y_km"] for p in post], color=TRACK_CONTEXT, lw=1.0,
                        ls=(0, (2, 2)), zorder=3)
            ax.plot([p["x_km"] for p in pre], [p["y_km"] for p in pre], color=col, lw=1.6, zorder=4)
            ax.plot([p["x_km"] for p in pre], [p["y_km"] for p in pre], ls="none", marker="o", ms=1.8,
                    color=col, zorder=4)
            p0 = pre[0]
            stops = fe.get("stops") or []
            first_wait = stops[0] if stops and stops[0]["start"] == p0["time"] else None
            ax.plot([p0["x_km"]], [p0["y_km"]], marker="o", ms=5, mfc="white", mec=col, mew=1.1, zorder=6)
            notes = [(p0["x_km"], p0["y_km"], f"başlangıç {p0['time']}"
                      + (f" · {first_wait['minutes']} dk bekleme" if first_wait else ""))]
            for s in stops:
                sp = p0 if s is first_wait else next((p for p in pts if p["time"] == s["start"]), None)
                if not sp:
                    continue
                ax.plot([sp["x_km"]], [sp["y_km"]], marker="o", ms=4 + min(s["minutes"], 120) / 12,
                        mfc="none", mec=INK_2, mew=0.9, zorder=5)
                if s is not first_wait:
                    notes.append((sp["x_km"], sp["y_km"], f"{s['start']}–{s['end']} · {s['minutes']} dk"))
            xl = ax.get_xlim()
            clusters = _cluster(notes, tol=(xl[1] - xl[0]) * 0.05)
            for k, (x, y, lines) in enumerate(clusters):
                _side_label(ax, x, y, "\n".join(lines), mid_x, above=(k == 0), color=INK_2)
            cap_below = any(0 < y - cy < (xl[1] - xl[0]) * 0.14 and abs(x - cx) < (xl[1] - xl[0]) * 0.3
                            for x, y, _ in clusters)
            hd = fe.get("heading_deg")
            if hd is not None:
                L = max(x1 - x0, y1 - y0, 0.5) * 0.09
                ax.annotate("", (cx + L * math.sin(math.radians(hd)), cy + L * math.cos(math.radians(hd))), (cx, cy),
                            arrowprops=dict(arrowstyle="-|>", color=INK, lw=0.9, mutation_scale=7), zorder=8)
        elif pts:
            ax.plot([p["x_km"] for p in pts], [p["y_km"] for p in pts], color=TRACK_CONTEXT, lw=1.0,
                    ls=(0, (2, 2)), zorder=3)
            q = pts[0]
            ax.plot([q["x_km"]], [q["y_km"]], marker="o", ms=3.5, mfc="white", mec=MUTED, zorder=4)
            _side_label(ax, q["x_km"], q["y_km"], f"olası iz {nt['track_id']} ({q['time']}'dan)", mid_x, above=False,
                        color=INK_2)
        # çekim noktası ve üsse doğrultu
        ax.plot([cx, 0], [cy, 0], color=MUTED, lw=0.7, ls=(0, (4, 3)), zorder=3)
        ang = math.degrees(math.atan2(cy, cx))
        ax.annotate(f"{f['dist_to_base_m'] / 1000:.2f} km", (cx * 0.45, cy * 0.45), ha="center", va="center",
                    fontsize=5.8, color=INK, rotation=ang if -90 < ang < 90 else ang - 180, rotation_mode="anchor",
                    xytext=(0, 5), textcoords="offset points", zorder=7)
        ax.plot([cx], [cy], marker=MARKERS[lvl], ms=7.5, mfc=col, mec="white", mew=0.9, zorder=9, ls="none")
        _side_label(ax, cx, cy, f"çekim {f['capture_time']}", mid_x, above=not (tr and cap_below), gap=5,
                    fontweight="bold", color=INK, fontsize=5.8, zorder=9)
        _base(ax)
        ax.set_xlabel("Doğu (km)"); ax.set_ylabel("Kuzey (km)")
        ax.set_title("Rota — üsse göre (km)" if tr else "Konum — üsse göre (km)")
        return _png(fig)


# ------------------------------------------------------------------ mesafe + hız (iki panel, tek eksen)
def _time_ticks(ax, t0, t1):
    step = 15 if t1 - t0 <= 150 else 30
    first = int(math.ceil(t0 / step) * step)
    ticks = list(range(first, int(t1) + 1, step))
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t // 60:02d}:{t % 60:02d}" for t in ticks])


def vehicle_timeseries(f: dict, th) -> bytes:
    col = RISK_COLORS[f["final_level"]]
    pts = f["track"]["points"]
    t_cap = f["capture_min"]
    with plt.rc_context(RC):
        fig = _fig("timeseries")
        ax1, ax2 = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [3, 2]})
        t = [p["t"] for p in pts]
        for ax in (ax1, ax2):
            for s in (f.get("features") or {}).get("stops") or []:
                a, b = _hm(s["start"]), _hm(s["end"])
                ax.axvspan(a, b, color=PANEL, zorder=0, lw=0)
            ax.axvline(t_cap, color=INK_2, lw=0.8, ls=(0, (3, 2)), zorder=2)
        pre = [p for p in pts if p["t"] <= t_cap]
        post = [p for p in pts if p["t"] >= t_cap]
        ax1.plot([p["t"] for p in pre], [p["dist_m"] / 1000 for p in pre], color=col, lw=1.6, zorder=3)
        if len(post) > 1:
            ax1.plot([p["t"] for p in post], [p["dist_m"] / 1000 for p in post], color=TRACK_CONTEXT, lw=1.0,
                     ls=(0, (2, 2)), zorder=3)
        ax1.plot([t_cap], [f["dist_to_base_m"] / 1000], marker=MARKERS[f["final_level"]], ms=6, mfc=col, mec="white",
                 zorder=5, ls="none")
        ax1.set_ylabel("Üsse mesafe (km)")
        ax1.set_ylim(bottom=0)
        # çekim etiketi: nokta üst kenara yakınsa başlığa değmesin diye noktanın altına yazılır
        yd = f["dist_to_base_m"] / 1000
        top = ax1.get_ylim()[1]
        low = yd > top * 0.72
        ax1.annotate(f"çekim {f['capture_time']}\n{yd:.2f} km", (t_cap, yd), xytext=(-4, -5 if low else 5),
                     textcoords="offset points", ha="right", va="top" if low else "bottom", fontsize=5.6,
                     color=INK, linespacing=1.15, zorder=6,
                     bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))
        ax1.set_title("Üsse mesafe ve hız (gri bant: duraklama)")
        sp = [(p["t"], p["speed_mps"]) for p in pts if p["speed_mps"] is not None]
        ax2.step([a for a, _ in sp], [b for _, b in sp], where="pre", color=INK_2, lw=1.0, zorder=3)
        ax2.axhline(th.fast_speed_mps, color=RISK_COLORS["KRITIK"], lw=0.7, ls=(0, (4, 2)), zorder=2)
        ax2.annotate(f"hızlı yaklaşma eşiği {th.fast_speed_mps:g} m/s", (t[0], th.fast_speed_mps), xytext=(2, 2),
                     textcoords="offset points", fontsize=5.3, color=INK_2)
        ax2.set_ylabel("Hız (m/s)")
        ax2.set_ylim(0, max(th.fast_speed_mps * 1.35, max((b for _, b in sp), default=0) * 1.15))
        _time_ticks(ax2, t[0], t[-1])
        ax2.set_xlim(t[0], t[-1])
        return _png(fig)


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


# ------------------------------------------------------------------ kare görünümü (tespit + konumlandırma)
def _find_image(images_dir: Path, frame_id: str) -> Path | None:
    for ext in ("png", "jpg", "jpeg"):
        p = images_dir / f"{frame_id}.{ext}"
        if p.exists():
            return p
    return None


def _latlon_to_px(lat, lon, fr):
    c = fr["corners"]
    top, bottom, left, right = c["top_left"][0], c["bottom_left"][0], c["top_left"][1], c["top_right"][1]
    return (lon - left) / (right - left) * fr["width_px"], (top - lat) / (top - bottom) * fr["height_px"]


def frame_view(f: dict, images_dir: Path) -> tuple[bytes, bool]:
    """(PNG, gerçek görüntü mü). Görüntü yoksa kare şematik çizilir (piksel koordinatları doğru)."""
    fr = f["frame"]
    W, H = fr["width_px"], fr["height_px"]
    col = RISK_COLORS[f["final_level"]]
    img_path = _find_image(images_dir, fr["frame_id"])
    with plt.rc_context(RC | {"axes.grid": False}):
        fig = _fig("frame")
        ax = fig.add_subplot()
        if img_path:
            import matplotlib.image as mpimg
            ax.imshow(mpimg.imread(str(img_path)), extent=(0, W, H, 0), zorder=0)
        else:
            ax.add_patch(Rectangle((0, 0), W, H, fc=SURFACE, ec=BASELINE, lw=0.8, zorder=0))
            for gx in range(120, W, 120):
                ax.plot([gx, gx], [0, H], color=HAIRLINE, lw=0.4, zorder=1)
            for gy in range(90, H, 90):
                ax.plot([0, W], [gy, gy], color=HAIRLINE, lw=0.4, zorder=1)
            ax.text(W / 2, H - 14, "görüntü dosyası yok — şematik (piksel koordinatları)", ha="center", va="bottom",
                    fontsize=5.4, color=MUTED, zorder=2)
        for o in fr["others"]:
            if o["bbox"]:
                x, y, w, h = o["bbox"]
                ax.add_patch(Rectangle((x, y), w, h, fill=False, ec=MUTED, lw=0.8, zorder=3))
                ax.text(x, y - 4, o["label"] or "iz", fontsize=5.0, color=INK_2, zorder=3)
            else:
                px, py = _latlon_to_px(o["lat"], o["lon"], fr)
                ax.plot([px], [py], marker="x", ms=4, color=MUTED, zorder=3)
        if f["bbox"]:
            x, y, w, h = f["bbox"]
            ax.add_patch(Rectangle((x, y), w, h, fill=False, ec=col, lw=1.8, zorder=5))
            ax.add_patch(Rectangle((x, y), w, h, fill=False, ec=INK, lw=0.4, zorder=5))
            txt = f"#{f['index']} {f['label']} {f['confidence']:.2f}"
            ax.text(x, y - 6, txt, fontsize=5.8, fontweight="bold", color=INK, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=col, lw=0.7))
            ax.plot([x + w / 2], [y + h / 2], marker="+", ms=5, color=INK, zorder=6)
        else:
            px, py = _latlon_to_px(f["lat"], f["lon"], fr)
            ax.add_patch(Circle((px, py), 14, fill=False, ec=col, lw=1.8, zorder=5))
            ax.text(px + 18, py, f"#{f['index']} iz konumu (tespit yok)", fontsize=5.8, fontweight="bold",
                    color=INK, va="center", zorder=6)
        ax.set_xlim(0, W); ax.set_ylim(H, 0)
        ax.set_aspect("equal")
        ax.set_xticks([0, W // 2, W]); ax.set_yticks([0, H // 2, H])
        ax.tick_params(length=2)
        ax.set_title(f"{fr['frame_id']} · {fr['capture_time']} · {W}×{H} px")
        return _png(fig), img_path is not None
