"""Kural tabanlı risk sınıflandırması. Motorun seviyesi BURADAN gelir; LLM ajanı bu seviyeyle birlikte
ortak karar verir (karar tablosu: agent.decide_vehicle), ardından fusion.py bağımsız hakem olarak tartar.

Tasarım ilkesi: bir koşul ancak araçları birbirinden AYIRIYORSA risk belirleyebilir. Bu veride karelere dışarıdan
gelen hemen her araç radyal yollarda üsse doğru ilerliyor ve yolda birkaç kez ≥15 dk duruyor; yani "üsse yönelim"
ve "duraklama" tek başına tehdit işareti değildir (eski APPROACH_WITH_STOPS kuralı bu yüzden kaldırıldı).
Ayırt edici olanlar: üsse ne kadar sokulduğu (en yakın mesafe), bunun dışarıdan gelinerek mi yapıldığı, en yakın
noktada ne kadar beklendiği, çekim anındaki mesafe, araç sınıfı (ağır araç) ve devriye/durağan örüntüleri.

Senaryolar (ilk eşleşen kural kazanır; öncelik sırasıyla):
  FRIENDLY_PATROL      → ORTA    üs etrafında sabit yarıçaplı tur, üsse ≤2 km (resmi dost teyidi varsa DUSUK)
  DIRECT_FAST_APPROACH → KRITIK  ara durak olmadan hızla (≥7 m/s) doğrudan üsse, ETA ≤10 dk
  CLOSE_APPROACH       → YUKSEK  dışarıdan (≥1.5 km yaklaşarak) gelip üsse ≤1 km'ye sokuldu; sonra geri çekilmiş
                                 olsa da (gidiş-dönüş / keşif örüntüsü)
  HEAVY_NEAR_APPROACH  → YUKSEK  ağır araç (truck/bus) dışarıdan gelip çekim anında üsse ≤2 km
  LOITER_NEAR_BASE     → YUKSEK  üsse 0.4–3 km'de küçük alanda döngü + duraklama (gerçekten hareket etmiş: yol ≥500 m)
  NEAR_BASE_ARRIVAL    → ORTA    dışarıdan gelip çekim anında üsse ≤2 km (sınıf fark etmez)
  NEAR_PASS            → ORTA    dışarıdan gelip üssün 1.5 km'si içinden geçti
  HEAVY_APPROACH       → ORTA    ağır araç dışarıdan gelip çekim anında üsse ≤3 km
  STATIC_NEAR_BASE     → ORTA    tüm pencere boyunca (≥90 dk) kıpırdamadan üsse ≤3 km'de duruyor
  APPROACHING          → ORTA    üsse yönelmiş, hareket halinde, son 60 dk ≥0.5 km yaklaşma ve üsse ≤2 km
  UNTRACKED            → ORTA    izsiz ağır araç <2.5 km ya da herhangi araç <1.2 km; aksi halde DUSUK
  OUTBOUND             → DUSUK   üs çevresinde (≤1.2 km) başlayıp uzaklaşan çıkış trafiği
  PATROL_FAR           → DUSUK   üsten ≥2 km'de sabit yarıçaplı tur
  TRANSIT / MOVING_AWAY / PARKED → DUSUK

"Dışarıdan geldi": iz başlangıcındaki mesafe ile en yakın (ya da çekim anındaki) mesafe arasındaki fark ≥1.5 km.
Üs çevresinde başlayıp uzaklaşan araçlar bu yüzden CLOSE_APPROACH sayılmaz (OUTBOUND).

Araç sınıfı: tespitin etiketi; aynı nesneye düşen kopya kutulardan birinde güvenilir (≥0.50) ağır etiket varsa da
ağır sayılır ("ağır" riski artırmak için yeterli, "hafif" ağır olmadığını kanıtlamaz). Yalnızca izden bilinen
(sınıfı bilinmeyen) araç ağır sayılmaz; rapor ağır araç diyorsa LLM gerekçeyle yükseltebilir.

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


def _km(v: float | None) -> str:
    return "—" if v is None else f"{v / 1000:.2f} km"


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
        if self.op == "true":
            return f"{self.name}: {'evet' if self.value else 'hayır'}"
        return f"{self.name} {self.value:.{self.nd}f}{self.unit} (eşik {_OP_SYMBOL[self.op]} {self.thr:g}{self.unit})"


@dataclass
class Rule:
    scenario: str
    risk: str
    conds: list[Cond]
    reasons: Callable[[], list[str]]

    def matches(self) -> bool:
        return all(c.ok() for c in self.conds)


def is_heavy(label: str | None, alt_labels: list[dict] | None = None, min_alt_conf: float = 0.5) -> bool:
    """Etiket ağırsa ya da aynı nesneye düşen kopya kutulardan birinde yeterince güvenli ağır etiket varsa."""
    if label in HEAVY_LABELS:
        return True
    return any(a.get("label") in HEAVY_LABELS and (a.get("confidence") or 0) >= min_alt_conf
               for a in (alt_labels or []))


def _tracked_rules(f: TrackFeatures, th: Thresholds, heavy: bool = False) -> list[Rule]:
    """Öncelik sırasıyla kurallar. İlk eşleşen kural senaryoyu belirler."""
    intermediate_stops = len(f.stops) - (1 if f.initial_wait_min else 0)
    ratio = f.path_length_m / max(f.extent_m, 1.0)
    heading = Cond("yönelim sapması", f.heading_offset_deg, "<=", th.heading_toward_deg, "°", nd=0)
    moving = Cond("hareket halinde", f.moving_now, "true", soft=False)
    heavy_c = Cond("ağır araç (truck/bus)", heavy, "true", soft=False)
    came_to_min = Cond("dışarıdan sokulma (başlangıç − en yakın)", f.approach_to_min_m, ">=", th.approach_gain_m,
                       " m", nd=0)
    came_to_now = Cond("dışarıdan gelme (başlangıç − şimdi)", f.approach_total_m, ">=", th.approach_gain_m,
                       " m", nd=0)
    near_now = Cond("üsse mesafe", f.dist_now_m, "<=", th.near_arrival_m, " m", nd=0)

    def journey() -> str:
        return (f"Başlangıç {_km(f.dist_start_m)} → en yakın {_km(f.dist_min_m)} ({f.dist_min_time}) → "
                f"çekim anında {_km(f.dist_now_m)}.")

    def close_approach_reasons() -> list[str]:
        out = [f"Dışarıdan {f.approach_to_min_m / 1000:.1f} km yaklaşıp üsse {f.dist_min_m:.0f} m'ye kadar sokuldu. "
               + journey()]
        if f.dwell_near_min_min:
            out.append(f"En yakın noktanın {th.dwell_band_m:.0f} m bandında ~{f.dwell_near_min_min} dk kaldı.")
        if f.retreat_from_min_m >= 500:
            out.append(f"Ardından {f.retreat_from_min_m / 1000:.1f} km geri çekildi — gidiş-dönüş (keşif) örüntüsü; "
                       "geri çekilme riski düşürmez.")
        return out

    return [
        # 1) sabit yarıçaplı devriye / tur (yakın halka)
        Rule("FRIENDLY_PATROL", "ORTA", [
            Cond("mesafe değişim katsayısı", f.radius_cv, "<=", th.patrol_radius_cv, nd=3),
            Cond("taranan açı", f.angular_sweep_deg, ">=", th.patrol_min_sweep_deg, "°", nd=0),
            Cond("üsse mesafe", f.dist_now_m, ">=", th.loiter_min_dist_m, " m", nd=0),
            Cond("üsse mesafe", f.dist_now_m, "<=", th.patrol_near_m, " m", nd=0),
        ], lambda: [
            f"Üs etrafında sabit yarıçaplı tur (mesafe ~{_fmt(f.dist_now_m, ' m')}, "
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
        # 3) dışarıdan gelip üssün 1 km'si içine sokulma (gidiş-dönüş dahil)
        Rule("CLOSE_APPROACH", "YUKSEK", [
            came_to_min,
            Cond("en yakın mesafe", f.dist_min_m, "<=", th.close_approach_m, " m", nd=0),
        ], close_approach_reasons),
        # 4) ağır araç yakın halkada
        Rule("HEAVY_NEAR_APPROACH", "YUKSEK", [heavy_c, came_to_now, near_now], lambda: [
            f"Ağır araç dışarıdan {f.approach_total_m / 1000:.1f} km yaklaşarak üsse {f.dist_now_m:.0f} m mesafede. "
            + journey(),
        ]),
        # 5) üs yakınında tur atma
        Rule("LOITER_NEAR_BASE", "YUKSEK", [
            Cond("üsse mesafe", f.dist_now_m, ">=", th.loiter_min_dist_m, " m", nd=0),
            Cond("üsse mesafe", f.dist_now_m, "<=", th.loiter_max_dist_m, " m", nd=0),
            Cond("kapladığı alan", f.extent_m, "<=", th.loiter_max_extent_m, " m", nd=0),
            Cond("toplam yol", f.path_length_m, ">=", th.loiter_min_path_m, " m", nd=0),
            Cond("yol/yer değiştirme oranı", ratio, ">=", 3),
            Cond("duraklama sayısı", len(f.stops), ">=", 2, soft=False),
        ], lambda: [
            f"Üsse {_fmt(f.dist_now_m, ' m')} mesafede ~{_fmt(f.extent_m, ' m')}'lik alanda döngü "
            f"(yol/yer değiştirme oranı {ratio:.1f}).",
            f"{len(f.stops)} duraklama, toplam {f.stopped_minutes_total} dk hareketsiz.",
        ]),
        # 6) dışarıdan gelip yakın halkada (sınıf fark etmez)
        Rule("NEAR_BASE_ARRIVAL", "ORTA", [came_to_now, near_now], lambda: [
            f"Dışarıdan {f.approach_total_m / 1000:.1f} km yaklaşarak çekim anında üsse {f.dist_now_m:.0f} m mesafede. "
            + journey(),
            "Niyet/kimlik kanıtı yok; yakın takip ve kimlik teyidi önerilir.",
        ]),
        # 7) 1.5 km içinden geçiş
        Rule("NEAR_PASS", "ORTA", [
            came_to_min,
            Cond("en yakın mesafe", f.dist_min_m, "<=", th.near_pass_m, " m", nd=0),
        ], lambda: [
            f"Dışarıdan gelip üssün {f.dist_min_m:.0f} m yakınından geçti ({f.dist_min_time}). " + journey(),
        ]),
        # 8) ağır araç orta halkada
        Rule("HEAVY_APPROACH", "ORTA", [
            heavy_c, came_to_now,
            Cond("üsse mesafe", f.dist_now_m, "<=", th.heavy_watch_m, " m", nd=0),
        ], lambda: [
            f"Ağır araç dışarıdan {f.approach_total_m / 1000:.1f} km yaklaşarak üsse {f.dist_now_m:.0f} m mesafede. "
            + journey(),
        ]),
        # 9) yakın halkada uzun süre kıpırdamadan duran araç
        Rule("STATIC_NEAR_BASE", "ORTA", [
            Cond("toplam yol", f.path_length_m, "<=", th.static_max_path_m, " m", nd=0),
            Cond("gözlem süresi", f.window_min, ">=", th.static_min_window_min, " dk", nd=0, soft=False),
            Cond("üsse mesafe", f.dist_now_m, "<=", th.static_near_m, " m", nd=0),
        ], lambda: [
            f"{f.window_min} dk boyunca yerinden kıpırdamadan üsse {f.dist_now_m:.0f} m mesafede duruyor "
            f"(toplam yol {f.path_length_m:.0f} m).",
            "Gözetleme/konuşlanma olasılığı; kimlik teyidi önerilir.",
        ]),
        # 10) yakın halkada üsse yönelmiş hareket
        Rule("APPROACHING", "ORTA", [
            heading, moving,
            Cond("son 60 dk yaklaşma", f.approach_last60_m or 0, ">=", 500, " m", nd=0),
            Cond("üsse mesafe", f.dist_now_m, "<=", th.approaching_max_dist_m, " m", nd=0),
        ], lambda: [
            f"Üsse yönelmiş hareket (sapma {_fmt(f.heading_offset_deg, '°')}), son 60 dk yaklaşma "
            f"{_fmt(f.approach_last60_m, ' m')}, üsse {f.dist_now_m:.0f} m, ETA ≈ {_fmt(f.eta_min, ' dk', 1)}.",
            "Bilinen bir tehdit örüntüsüne uymuyor; izlenmeli.",
        ]),
    ]


def _classify_low(f: TrackFeatures, th: Thresholds) -> tuple[str, str, list[str]]:
    """Düşük risk sınıfları. Sıra önemli: çıkış trafiği ve uzak devriye TRANSIT'ten önce ayrıştırılır."""
    if f.path_length_m < th.static_max_path_m:
        return "PARKED", "DUSUK", [f"İz boyunca hareketsiz (park halinde), üsse {f.dist_now_m:.0f} m."]
    if f.dist_start_m <= th.outbound_start_m and f.dist_now_m - f.dist_start_m >= th.outbound_min_gain_m:
        return "OUTBOUND", "DUSUK", [
            f"Üs çevresinde ({f.dist_start_m:.0f} m) başlayıp {f.dist_now_m:.0f} m'ye uzaklaştı — üsten çıkış trafiği.",
        ]
    if f.radius_cv <= th.patrol_radius_cv and f.angular_sweep_deg >= th.patrol_min_sweep_deg:
        return "PATROL_FAR", "DUSUK", [
            f"Üs etrafında sabit yarıçaplı tur ama üsse {f.dist_now_m:.0f} m (> {th.patrol_near_m:.0f} m) uzakta.",
        ]
    if f.dist_trend == "once_azalip_sonra_artiyor" or (f.heading_offset_deg is not None and f.heading_offset_deg > 90):
        return "TRANSIT", "DUSUK", [
            f"Mesafe trendi: {f.dist_trend}; yönelim sapması {_fmt(f.heading_offset_deg, '°')}; "
            f"en yakın {f.dist_min_m:.0f} m (üssün {th.near_pass_m:.0f} m'si içine girmedi).",
        ]
    if f.dist_trend == "artiyor":
        return "MOVING_AWAY", "DUSUK", ["Üsten uzaklaşıyor."]
    if f.dist_trend == "azaliyor":
        return "TRANSIT", "DUSUK", [
            f"Üsse doğru olağan radyal trafik: üsse {f.dist_now_m:.0f} m, yakın halkaların dışında "
            f"(ETA ≈ {_fmt(f.eta_min, ' dk', 1)}).",
        ]
    return "PARKED", "DUSUK", ["Hareket ettikten sonra durmuş; üsse yönelim yok."]


def classify_tracked(f: TrackFeatures, th: Thresholds, heavy: bool = False) -> tuple[str, str, list[str]]:
    """(senaryo, risk, gerekçeler)"""
    for rule in _tracked_rules(f, th, heavy):
        if rule.matches():
            return rule.scenario, rule.risk, rule.reasons()
    return _classify_low(f, th)


def _untracked_conds(label: str, dist_m: float, th: Thresholds, heavy: bool | None = None) -> list[Cond]:
    heavy = (label in HEAVY_LABELS) if heavy is None else heavy
    conds = [Cond("izsiz araç mesafesi", dist_m, "<", th.untracked_any_m, " m", nd=0)]
    if heavy:
        conds.insert(0, Cond("izsiz ağır araç mesafesi", dist_m, "<", th.untracked_heavy_m, " m", nd=0))
    return conds


def classify_untracked(label: str, dist_m: float, th: Thresholds,
                       heavy: bool | None = None) -> tuple[str, str, list[str]]:
    heavy = (label in HEAVY_LABELS) if heavy is None else heavy
    if any(c.ok() for c in _untracked_conds(label, dist_m, th, heavy)):
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


def tracked_margin(f: TrackFeatures, th: Thresholds, scenario: str, risk: str, heavy: bool = False) -> dict:
    tol = th.margin_tol
    rules = _tracked_rules(f, th, heavy)
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


def untracked_margin(label: str, dist_m: float, th: Thresholds, risk: str, heavy: bool | None = None) -> dict:
    tol, conds = th.margin_tol, _untracked_conds(label, dist_m, th, heavy)
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


def explain_tracked(f: TrackFeatures, th: Thresholds, heavy: bool = False) -> list[dict]:
    """Her kuralın koşulları, değerleri ve sonucu — öncelik sırasıyla. Sınıflandırmayla aynı kural listesini
    (_tracked_rules) kullanır; rapordaki tablo motorun gerçekte uyguladığı kuralla birebir aynıdır.
    matched: senaryoyu belirleyen (ilk eşleşen) kural. Sonraki kurallar değerlendirilmez ama gösterilir."""
    out, winner_seen = [], False
    for r in _tracked_rules(f, th, heavy):
        ok = r.matches()
        out.append({"scenario": r.scenario, "risk": r.risk, "all_ok": ok, "matched": ok and not winner_seen,
                    "conds": [_cond_view(c, th.margin_tol) for c in r.conds]})
        winner_seen = winner_seen or ok
    return out


def explain_untracked(label: str, dist_m: float, th: Thresholds, heavy: bool | None = None) -> list[dict]:
    conds = _untracked_conds(label, dist_m, th, heavy)
    ok = any(c.ok() for c in conds)
    return [{"scenario": "UNTRACKED", "risk": "ORTA", "all_ok": ok, "matched": ok, "any_of": True,
             "conds": [_cond_view(c, th.margin_tol) for c in conds]}]
