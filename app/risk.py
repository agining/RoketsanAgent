"""Kural tabanlı risk sınıflandırması. Motorun seviyesi BURADAN gelir; LLM ajanı bu seviyeyle birlikte
ortak karar verir (karar tablosu: agent.decide_vehicle).

Senaryolar (README):
  DIRECT_FAST_APPROACH  → KRITIK  uzun bekleme, sonra ara durak olmadan hızla doğrudan üsse
  APPROACH_WITH_STOPS   → YUKSEK  son 60 dk'da ≥1.5 km yaklaşma + birden fazla ≥15 dk duraklama
  LOITER_NEAR_BASE      → YUKSEK  üsse 0.4–3 km'de küçük döngüde tur + duraklama
  FRIENDLY_PATROL       → ORTA    (resmi dost teyidi varsa DUSUK)
  UNTRACKED             → ORTA    ağır araç <2.5 km ya da herhangi araç <1.2 km; aksi halde DUSUK
  APPROACHING           → ORTA    yukarıdakilere uymayan ama üsse yönelmiş yaklaşma
  TRANSIT/MOVING_AWAY/PARKED → DUSUK

Motor güveni (margin): her kural, koşul listesi olarak tek yerde tanımlıdır (_tracked_rules). Aynı liste hem
sınıflandırmada hem de "motor ne kadar emin" sorusunda kullanılır:
  * net      → değerler eşiklerden uzak
  * sınırda  → eşleşen kuralın bir koşulu eşiği ancak geçti (can_drop) ya da daha yüksek riskli bir kural
               bir koşul yüzünden kıl payı kaçtı (can_rise). Yakınlık: eşiğin %margin_tol'u.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .config import HEAVY_LABELS, RISK_ORDER, Thresholds
from .tracking import TrackFeatures


def max_risk(levels: list[str]) -> str:
    return max(levels, key=RISK_ORDER.index) if levels else "DUSUK"


def _rank(level: str) -> int:
    return RISK_ORDER.index(level)


def _fmt(v: float | None, unit: str = "", nd: int = 0) -> str:
    return "—" if v is None else f"{v:.{nd}f}{unit}"


# ------------------------------------------------------------------ koşul / kural
_OP_SYMBOL = {">=": "≥", "<=": "≤", "<": "<", "==": "=", "true": ""}


@dataclass(frozen=True)
class Cond:
    """Tek bir kural koşulu. value None ise koşul sağlanmaz.
    soft=True → sayısal eşik; eşiğe yakınlık (sınırda) anlamlıdır. Sayım / evet-hayır koşulları soft değildir."""
    name: str
    value: float | int | bool | None
    op: str                      # ">=" | "<=" | "<" | "==" | "true"
    thr: float | int | None = None
    unit: str = ""
    nd: int = 1                  # gösterimdeki ondalık hane
    soft: bool = True

    def ok(self) -> bool:
        v, t = self.value, self.thr
        if v is None:
            return False
        if self.op == "true":
            return bool(v)
        if self.op == ">=":
            return v >= t
        if self.op == "<=":
            return v <= t
        if self.op == "<":
            return v < t
        if self.op == "==":
            return v == t
        raise ValueError(self.op)

    def near_miss(self, tol: float) -> bool:
        """Koşul sağlanmıyor ama eşiğe tol oranında yakın."""
        if not self.soft or self.value is None or self.ok():
            return False
        v, t = self.value, self.thr
        if self.op == ">=":
            return v >= t * (1 - tol)
        if self.op in ("<=", "<"):
            return v <= t * (1 + tol)
        return False

    def barely(self, tol: float) -> bool:
        """Koşul sağlanıyor ama eşiği ancak geçti."""
        if not self.soft or not self.ok():
            return False
        v, t = self.value, self.thr
        if self.op == ">=":
            return v < t * (1 + tol)
        if self.op in ("<=", "<"):
            return v > t * (1 - tol)
        return False

    def describe(self) -> str:
        return f"{self.name} {self.value:.{self.nd}f}{self.unit} (eşik {_OP_SYMBOL[self.op]} {self.thr:g}{self.unit})"


@dataclass
class Rule:
    scenario: str
    risk: str
    conds: list[Cond]
    reasons: Callable[[], list[str]]

    def matches(self) -> bool:
        return all(c.ok() for c in self.conds)


def _tracked_rules(f: TrackFeatures, th: Thresholds) -> list[Rule]:
    """Öncelik sırasıyla kurallar. İlk eşleşen kural senaryoyu belirler."""
    intermediate_stops = len(f.stops) - (1 if f.initial_wait_min else 0)
    ratio = f.path_length_m / max(f.extent_m, 1.0)
    heading = Cond("yönelim sapması", f.heading_offset_deg, "<=", th.heading_toward_deg, "°", nd=0)
    moving = Cond("hareket halinde", f.moving_now, "true", soft=False)

    def approach_with_stops_reasons() -> list[str]:
        reasons = [
            f"Son 60 dk'da üsse {_fmt(f.approach_last60_m, ' m')} yaklaştı, {len(f.stops)} adet ≥{th.stop_min_minutes} dk duraklama.",
            f"Yönelim sapması {_fmt(f.heading_offset_deg, '°')}, üsse mesafe {_fmt(f.dist_now_m, ' m')}.",
        ]
        if f.eta_min is not None:
            reasons.append(f"Mevcut hızla ETA ≈ {f.eta_min:.1f} dk — yakın takip gerekir.")
        return reasons

    return [
        # 1) sabit yarıçaplı devriye (üs etrafında tur)
        Rule("FRIENDLY_PATROL", "ORTA", [
            Cond("mesafe değişim katsayısı", f.radius_cv, "<=", 0.03, nd=3),
            Cond("taranan açı", f.angular_sweep_deg, ">=", 180, "°", nd=0),
            Cond("toplam duraklama", f.stopped_minutes_total, "<=", 15, " dk", nd=0),
            Cond("üsse mesafe", f.dist_now_m, ">=", th.loiter_min_dist_m, " m", nd=0),
        ], lambda: [
            f"Üs etrafında sabit yarıçaplı tur (ort. mesafe ~{_fmt(f.dist_now_m, ' m')}, "
            f"değişim katsayısı {f.radius_cv:.3f}, taranan açı {f.angular_sweep_deg:.0f}°).",
            "Resmi dost teyidi yoksa ORTA; teyit gelirse DUSUK'e iner.",
        ]),
        # 2) doğrudan hızlı yaklaşma
        Rule("DIRECT_FAST_APPROACH", "KRITIK", [
            heading, moving,
            Cond("hız", f.speed_now_mps, ">=", th.fast_speed_mps, " m/s"),
            Cond("ara duraklama sayısı", intermediate_stops, "==", 0, soft=False),
            Cond("ETA", f.eta_min, "<=", th.critical_eta_min, " dk"),
        ], lambda: [
            f"{f.initial_wait_min} dk bekledikten sonra ara durak olmadan üsse doğru {f.speed_now_mps:.1f} m/s ile ilerliyor.",
            f"Yönelim sapması {_fmt(f.heading_offset_deg, '°')}, üsse mesafe {_fmt(f.dist_now_m, ' m')}, ETA ≈ {_fmt(f.eta_min, ' dk', 1)}.",
        ]),
        # 3) duraklamalı yaklaşma
        Rule("APPROACH_WITH_STOPS", "YUKSEK", [
            Cond("son 60 dk yaklaşma", f.approach_last60_m or 0, ">=", th.approach_min_m, " m", nd=0),
            Cond("duraklama sayısı", len(f.stops), ">=", 2, soft=False),
            heading,
        ], approach_with_stops_reasons),
        # 4) üs yakınında tur atma
        Rule("LOITER_NEAR_BASE", "YUKSEK", [
            Cond("üsse mesafe", f.dist_now_m, ">=", th.loiter_min_dist_m, " m", nd=0),
            Cond("üsse mesafe", f.dist_now_m, "<=", th.loiter_max_dist_m, " m", nd=0),
            Cond("kapladığı alan", f.extent_m, "<=", 1500, " m", nd=0),
            Cond("yol/yer değiştirme oranı", ratio, ">=", 3),
            Cond("duraklama sayısı", len(f.stops), ">=", 2, soft=False),
        ], lambda: [
            f"Üsse {_fmt(f.dist_now_m, ' m')} mesafede ~{_fmt(f.extent_m, ' m')}'lik alanda döngü "
            f"(yol/yer değiştirme oranı {ratio:.1f}).",
            f"{len(f.stops)} duraklama, toplam {f.stopped_minutes_total} dk hareketsiz.",
        ]),
        # 5) diğer yönelmiş yaklaşmalar
        Rule("APPROACHING", "ORTA", [
            heading, moving,
            Cond("son 60 dk yaklaşma", f.approach_last60_m or 0, ">=", 500, " m", nd=0),
        ], lambda: [
            f"Üsse yönelmiş hareket (sapma {_fmt(f.heading_offset_deg, '°')}), son 60 dk yaklaşma {_fmt(f.approach_last60_m, ' m')}.",
            "Bilinen bir tehdit örüntüsüne uymuyor; izlenmeli.",
        ]),
    ]


def _classify_low(f: TrackFeatures) -> tuple[str, str, list[str]]:
    """6) düşük risk sınıfları"""
    if f.path_length_m < 150:
        return "PARKED", "DUSUK", ["İz boyunca hareketsiz (park halinde)."]
    if f.dist_trend == "once_azalip_sonra_artiyor" or (f.heading_offset_deg is not None and f.heading_offset_deg > 90):
        return "TRANSIT", "DUSUK", [
            f"Mesafe trendi: {f.dist_trend}; yönelim sapması {_fmt(f.heading_offset_deg, '°')} (üsse yönelmemiş).",
            "Mesafenin bir süre azalması tek başına tehdit sayılmadı.",
        ]
    if f.dist_trend == "artiyor":
        return "MOVING_AWAY", "DUSUK", ["Üsten uzaklaşıyor."]
    return "PARKED", "DUSUK", ["Hareket ettikten sonra durmuş; üsse yönelim yok."]


def classify_tracked(f: TrackFeatures, th: Thresholds) -> tuple[str, str, list[str]]:
    """(senaryo, risk, gerekçeler)"""
    for rule in _tracked_rules(f, th):
        if rule.matches():
            return rule.scenario, rule.risk, rule.reasons()
    return _classify_low(f)


def _untracked_conds(label: str, dist_m: float, th: Thresholds) -> list[Cond]:
    conds = [Cond("izsiz araç mesafesi", dist_m, "<", th.untracked_any_m, " m", nd=0)]
    if label in HEAVY_LABELS:
        conds.insert(0, Cond("izsiz ağır araç mesafesi", dist_m, "<", th.untracked_heavy_m, " m", nd=0))
    return conds


def classify_untracked(label: str, dist_m: float, th: Thresholds) -> tuple[str, str, list[str]]:
    heavy = label in HEAVY_LABELS
    if any(c.ok() for c in _untracked_conds(label, dist_m, th)):
        why = (f"İzi olmayan ağır araç, üsse {dist_m:.0f} m (<{th.untracked_heavy_m:.0f} m)."
               if heavy and dist_m < th.untracked_heavy_m
               else f"İzi olmayan araç, üsse {dist_m:.0f} m (<{th.untracked_any_m:.0f} m).")
        return "UNTRACKED", "ORTA", [why, "Davranış bilinmiyor; ek gözlem önerilir."]
    return "UNTRACKED", "DUSUK", [f"İzi olmayan {label}, üsse {dist_m:.0f} m; eşiklerin dışında."]


# ------------------------------------------------------------------ motor güveni (net / sınırda)
def _margin(drop_notes: list[str], rise_notes: list[str], rise_to: str | None = None) -> dict:
    """confidence: net | sinirda · can_drop: seviye kıl payı tuttu · can_rise: üst kural kıl payı kaçtı
    rise_to: kıl payı kaçan en yüksek kuralın seviyesi (yoksa None)"""
    return {"confidence": "sinirda" if drop_notes or rise_notes else "net",
            "can_drop": bool(drop_notes), "can_rise": bool(rise_notes), "rise_to": rise_to,
            "notes": drop_notes + rise_notes}


def firm_margin(note: str) -> dict:
    """Eşikten bağımsız kesin durumlar (resmi dost teyidi, düşük güvenle elenmiş tespit)."""
    return _margin([], []) | {"notes": [note]}


def tracked_margin(f: TrackFeatures, th: Thresholds, scenario: str, risk: str) -> dict:
    tol = th.margin_tol
    rules = _tracked_rules(f, th)
    drop, rise, rise_levels = [], [], []
    matched = next((r for r in rules if r.scenario == scenario), None)
    if matched and risk != "DUSUK":
        drop = [f"{risk}'e kıl payı girdi: {c.describe()}" for c in matched.conds if c.barely(tol)]
    for r in rules:
        if _rank(r.risk) <= _rank(risk):
            continue
        misses = [c for c in r.conds if c.near_miss(tol)]
        if misses and all(c.ok() or c.near_miss(tol) for c in r.conds):
            rise.append(f"Neredeyse {r.risk} ({r.scenario}): " + "; ".join(c.describe() for c in misses))
            rise_levels.append(r.risk)
    return _margin(drop, rise, max_risk(rise_levels) if rise_levels else None)


def untracked_margin(label: str, dist_m: float, th: Thresholds, risk: str) -> dict:
    tol, conds = th.margin_tol, _untracked_conds(label, dist_m, th)
    passed = [c for c in conds if c.ok()]
    if risk != "DUSUK" and passed and all(c.barely(tol) for c in passed):
        return _margin([f"ORTA'ya kıl payı girdi: {c.describe()}" for c in passed], [])
    if risk == "DUSUK":
        rise = [f"Neredeyse ORTA (UNTRACKED): {c.describe()}" for c in conds if c.near_miss(tol)]
        return _margin([], rise, "ORTA" if rise else None)
    return _margin([], [])


# ------------------------------------------------------------------ açıklama (PDF raporu / arayüz)
def _cond_view(c: Cond, tol: float) -> dict:
    """Tek koşulun okunabilir hâli: değer, eşik, sağlandı mı, eşiğe ne kadar yakın."""
    if c.op == "true":
        value, thr = ("evet" if c.value else "hayır"), "evet"
    else:
        if c.value is None:
            value = "—"
        elif isinstance(c.value, int) and not isinstance(c.value, bool):
            value = f"{c.value}{c.unit}"          # sayım koşulları (duraklama sayısı vb.) tam sayı
        else:
            value = f"{c.value:.{c.nd}f}{c.unit}"
        thr = f"{_OP_SYMBOL[c.op]} {c.thr:g}{c.unit}"
    return {"name": c.name, "value": value, "threshold": thr, "ok": c.ok(),
            "near_miss": c.near_miss(tol), "barely": c.barely(tol)}


def explain_tracked(f: TrackFeatures, th: Thresholds) -> list[dict]:
    """Her kuralın koşulları, değerleri ve sonucu — öncelik sırasıyla. Sınıflandırmayla aynı kural listesini
    (_tracked_rules) kullanır; rapordaki tablo motorun gerçekte uyguladığı kuralla birebir aynıdır.
    matched: senaryoyu belirleyen (ilk eşleşen) kural. Sonraki kurallar değerlendirilmez ama gösterilir."""
    out, winner_seen = [], False
    for r in _tracked_rules(f, th):
        ok = r.matches()
        out.append({"scenario": r.scenario, "risk": r.risk, "all_ok": ok, "matched": ok and not winner_seen,
                    "conds": [_cond_view(c, th.margin_tol) for c in r.conds]})
        winner_seen = winner_seen or ok
    return out


def explain_untracked(label: str, dist_m: float, th: Thresholds) -> list[dict]:
    conds = _untracked_conds(label, dist_m, th)
    ok = any(c.ok() for c in conds)
    return [{"scenario": "UNTRACKED", "risk": "ORTA", "all_ok": ok, "matched": ok, "any_of": True,
             "conds": [_cond_view(c, th.margin_tol) for c in conds]}]
