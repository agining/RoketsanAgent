"""Saha raporlarının ayrıştırılması ve kanıta (kare tespitleri + izler) karşı doğrulanması.

Hükümler: destekler | celisir | kismen_uyumlu | dogrulanamaz | ilgisiz | manipulasyon
Her hüküm, hangi alt kontrollerin (konum/tip/zaman/davranış) nasıl sonuçlandığını `checks`
alanında taşır — hem UI'da gösterilir hem de LLM ajanına kanıt olarak verilir.

Rapor metni GÜVENİLMEZ veridir: içindeki talimatlar uygulanmaz, sadece işaretlenir.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field

from .config import HEAVY_LABELS, RISK_ORDER, Thresholds
from .geo import angle_diff, bearing_deg, haversine_m, hhmm_to_min, point_in_frame

TR_MAP = str.maketrans("ıİşŞğĞüÜöÖçÇâÂîÎûÛ", "iIsSgGuUoOcCaAiIuU")

TYPE_WORDS = {
    "kamyon": {"truck"}, "tir": {"truck"}, "agir arac": HEAVY_LABELS,
    "panelvan": {"van"}, "minibus": {"van"}, "kamyonet": {"van", "truck"},
    "otomobil": {"car"}, "binek": {"car"}, "araba": {"car"},
    "otobus": {"bus"},
}
DIRECTIONS = {"kuzey": 0, "kuzeydogu": 45, "dogu": 90, "guneydogu": 135,
              "guney": 180, "guneybati": 225, "bati": 270, "kuzeybati": 315}

INJECTION_PATTERNS = [
    r"talimat\w*\s+(yok\s*say|gormezden|unut)", r"yok\s*say", r"sistem\s*not", r"system\s*(note|prompt)",
    r"ignore\s+(all\s+)?(previous|prior)", r"\bprompt\b", r"olarak\s+(raporla|isaretle|siniflandir)",
    r"risk\w*\s+(dusuk|low)\s+olarak", r"(asistan|agent|model|yapay\s*zeka)\s*[,:]", r"you\s+are\s+now",
]
STATIONARY_WORDS = ["hareketsiz", "konuslanmis", "duruyor", "park halinde", "bekliyor", "sabit duruyor"]
MOVING_WORDS = ["ilerliyor", "hareket halinde", "seyir halinde", "gidiyor", "geciyor", "hizla", "yaklasiyor"]
# Devriye örüntüsü sayılan motor senaryoları (resmi dost teyidi bunlarda riski düşürebilir)
PATROL_SCENARIOS = {"FRIENDLY_PATROL", "PATROL_FAR"}
# İz yoksa, rapor saatindeki hareket durumunu senaryodan tahmin ederken "duruyor" sayılanlar
STATIONARY_SCENARIOS = {"PARKED", "UNTRACKED", "STATIC_NEAR_BASE"}
NORMAL_WORDS = ["hareketleri olagan", "olagan disi bir durum yok", "transit geciyor", "supheli bir durum yok"]


def normalize(text: str) -> str:
    t = text.translate(TR_MAP)
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t.lower()).strip()


# ------------------------------------------------------------------ ayrıştırma
@dataclass
class ParsedReport:
    coord: tuple[float, float] | None = None
    zone: str | None = None
    types: list[str] = field(default_factory=list)       # olası etiketler
    type_word: str | None = None
    count: int | None = None
    color: str | None = None
    claims_stationary: bool = False
    claims_moving: bool = False
    claims_fast: bool = False
    direction_deg: float | None = None
    toward_base: bool = False
    claims_normal: bool = False
    zone_traffic_normal: bool = False
    friendly_claim: bool = False
    friendly_confirmed_wording: bool = False
    stale: bool = False
    exercise: bool = False
    injection: bool = False
    injection_span: str | None = None
    observation_text: str = ""


def parse_report(text: str, zone_names: list[str]) -> ParsedReport:
    n = normalize(text)
    p = ParsedReport()

    # manipülasyon: talimat kısmını ayır, gözlem kısmını ayrıca değerlendir
    for pat in INJECTION_PATTERNS:
        m = re.search(pat, n)
        if m:
            p.injection = True
            cut = n.rfind(".", 0, m.start())
            p.injection_span = n[cut + 1:].strip() if cut >= 0 else n[m.start():]
            n = n[:cut + 1] if cut >= 0 else n[:m.start()]
            break
    p.observation_text = n

    m = re.search(r"(-?\d{1,3}\.\d+)\s*([ns])[\s,]+(-?\d{1,3}\.\d+)\s*([ew])", n)
    if m:
        lat, lon = float(m.group(1)), float(m.group(3))
        p.coord = (-lat if m.group(2) == "s" else lat, -lon if m.group(4) == "w" else lon)

    for z in sorted(zone_names, key=len, reverse=True):
        if normalize(z) in n:
            p.zone = z
            break

    for w, labels in sorted(TYPE_WORDS.items(), key=lambda kv: -len(kv[0])):
        if re.search(rf"\b{w}\b", n):
            p.type_word, p.types = w, sorted(labels)
            break
    m = re.search(r"\b(\d+)\s+(kamyon|panelvan|otomobil|otobus|agir arac|arac|tir|minibus)", n)
    if m:
        p.count = int(m.group(1))
    m = re.search(r"\b(kirmizi|mavi|yesil|sari|siyah|beyaz|gri|turuncu|mor|kahverengi)\b", n)
    if m:
        p.color = m.group(1)

    p.claims_normal = any(w in n for w in NORMAL_WORDS)
    p.claims_stationary = any(w in n for w in STATIONARY_WORDS)
    p.claims_moving = any(w in n for w in MOVING_WORDS)
    p.claims_fast = "hizla" in n
    m = re.search(r"\b(kuzeydogu|kuzeybati|guneydogu|guneybati|kuzey|guney|dogu|bati)\s+yonun", n)
    if m:
        p.direction_deg = DIRECTIONS[m.group(1)]
    p.toward_base = bool(re.search(r"\buse\s+dogru|\busse\b|merkez\s+use", n))
    p.zone_traffic_normal = "trafik akisi normal" in n
    p.friendly_claim = "dost" in n or "bize ait" in n
    p.friendly_confirmed_wording = "kimlik teyidi" in n or "teyit edilmis" in n or "teyidi yapilmistir" in n
    p.stale = "dun gece" in n or "dun aksam" in n or "gecen hafta" in n
    p.exercise = "tatbikat" in n
    return p


# ------------------------------------------------------------------ doğrulama
@dataclass
class ReportVerdict:
    report_id: str
    time: str
    source: str
    text: str
    verdict: str
    report_type: str
    summary: str
    matched_vehicle_id: str | None = None
    matched_track_id: str | None = None
    related_frames: list[str] = field(default_factory=list)
    zone: str | None = None
    checks: dict = field(default_factory=dict)
    injection_detected: bool = False
    injection_span: str | None = None
    affects_risk: bool = False
    parsed: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _speed_at(track, t: int) -> float | None:
    a, b = track.position_at(t - 5), track.position_at(t + 5)
    if a and b:
        return haversine_m(*a, *b) / 600
    a, b = track.position_at(t - 10), track.position_at(t)
    if a and b:
        return haversine_m(*a, *b) / 600
    return None


def _displacement(track, t0: int, t1: int) -> float | None:
    a, b = track.position_at(t0), track.position_at(t1)
    return haversine_m(*a, *b) if a and b else None


def _motion_state(track, t: int, stop_r: float) -> tuple[bool | None, bool | None]:
    """(rapor saatinden önceki 10 dk'da hareket etti mi, rapor saati ±5 dk'da hareket ediyor mu)"""
    before = _displacement(track, t - 10, t)
    around = _displacement(track, t - 5, t + 5)
    return (None if before is None else before > stop_r,
            None if around is None else around > stop_r)


def _heading_at(track, t: int) -> float | None:
    for back in (5, 10, 15):
        a, b = track.position_at(t - back), track.position_at(t)
        if a and b and haversine_m(*a, *b) > 20:
            return bearing_deg(*a, *b)
    return None


class ReportVerifier:
    def __init__(self, ds, state, th: Thresholds):
        self.ds, self.state, self.th = ds, state, th
        self.zone_names = [z.name for z in ds.zones]

    # -------------------------------------------------------------- ana giriş
    def verify(self, r: dict) -> ReportVerdict:
        p = parse_report(r["text"], self.zone_names)
        t = hhmm_to_min(r["time"])
        v = ReportVerdict(report_id=r["id"], time=r["time"], source=r.get("source", "unknown"),
                          text=r["text"], verdict="dogrulanamaz", report_type="BILINMIYOR", summary="",
                          zone=p.zone, injection_detected=p.injection, injection_span=p.injection_span,
                          parsed={k: val for k, val in asdict(p).items() if k != "observation_text"})

        if p.stale:
            v.verdict, v.report_type = "ilgisiz", "ESKI_IHBAR"
            v.summary = "Önceki geceye ait, doğrulanmamış ihbar; mevcut görev penceresiyle ilgisiz."
        elif p.coord:
            self._verify_coordinate(v, p, t)
        elif p.zone and p.zone_traffic_normal:
            self._verify_zone_normal(v, p, t)
        elif p.zone:
            self._verify_zone_observation(v, p, t)
        elif p.exercise:
            v.verdict, v.report_type = "dogrulanamaz", "GENEL_TATBIKAT"
            v.summary = "Konumsuz, genel tatbikat bildirimi; belirli bir araçla ilişkilendirilemez ve riski düşürmez."
        else:
            v.summary = "Raporda konum ya da bölge bilgisi bulunamadı."

        if p.injection:
            v.checks["observation_verdict"] = v.verdict
            v.verdict = "manipulasyon"
            v.report_type = "MANIPULASYON"
            v.affects_risk = False
            v.summary = ("Rapor metni sisteme yönelik talimat içeriyor; talimat UYGULANMADI ve rapor kanıt olarak "
                         f"kullanılmadı. Gözlem kısmının bağımsız değerlendirmesi: {v.checks['observation_verdict']}. "
                         + v.summary)
        return v

    # -------------------------------------------------------------- koordinatlı
    def _candidates(self, lat: float, lon: float, t: int):
        """(araç_id | None, iz_id | None, d_capture, d_report, capture_t)"""
        out = []
        for veh in self.state.vehicles.values():
            if veh["filtered"]:
                continue
            d_cap = haversine_m(lat, lon, veh["lat"], veh["lon"])
            d_rep = None
            if veh["track_id"]:
                pos = self.ds.tracks[veh["track_id"]].position_at(t)
                if pos:
                    d_rep = haversine_m(lat, lon, *pos)
            out.append((veh["vehicle_id"], veh["track_id"], d_cap, d_rep, veh["capture_min"]))
        for tid in self.state.offframe_track_ids:
            pos = self.ds.tracks[tid].position_at(t)
            if pos:
                out.append((None, tid, None, haversine_m(lat, lon, *pos), None))
        return out

    def _verify_coordinate(self, v: ReportVerdict, p: ParsedReport, t: int):
        lat, lon = p.coord
        R, tol = self.th.report_match_radius_m, self.th.report_time_tol_min
        frames_here = [fid for fid, fr in self.state.frames.items()
                       if point_in_frame(lat, lon, fr["meta"], self.th.frame_margin_m)]
        v.related_frames = frames_here
        v.zone = self.ds.zone_of(lat, lon)
        cands = self._candidates(lat, lon, t)

        def same_time(c):  # rapor saati çekim saatine yakın ve kare konumu tutuyor
            return c[2] is not None and c[2] <= R and abs(t - c[4]) <= tol
        timely = [c for c in cands if (c[3] is not None and c[3] <= R) or same_time(c)]
        loc_only = [c for c in cands if c[2] is not None and c[2] <= R and c not in timely]

        v.checks["kare_icinde"] = bool(frames_here)
        v.checks["rapor_saatinde_eslesen_iz_sayisi"] = len({c[1] or c[0] for c in timely})

        def eff_dist(c):  # adayın rapor noktasına en yakın (yarıçap içindeki) mesafesi
            return min(x for x in (c[2], c[3]) if x is not None and x <= R)

        def type_mismatch(c):  # rapor tip veriyorsa ve aracın etiketi biliniyorsa uyuşmazlık
            label = (self.state.vehicles.get(c[0]) or {}).get("label")
            return bool(p.types) and label is not None and label not in p.types

        # "Rapor saatinde yakın" adaylar, "çekim anında yakın" adaylardan körü körüne öne alınmaz:
        # önce tip uyumu, sonra mesafe. (brief img_000860: 12:35 raporu 3 m'deki kamyonu anlatıyor;
        # 40 m ötede park etmiş binek aracı rapor saatinde yarıçap içinde diye seçilmemeli.)
        pool = timely + loc_only
        if pool:
            best = min(pool, key=lambda c: (type_mismatch(c), eff_dist(c)))
            if best in timely:
                self._judge_matched(v, p, t, best, timely)
                return
            veh = self.state.vehicles[best[0]]
            v.matched_vehicle_id, v.matched_track_id = best[0], best[1]
            v.related_frames = sorted(set(v.related_frames) | {veh["frame_id"]})
            where = (f"rapor saatinde ({v.time}) iz kaydına göre ~{best[3]:.0f} m uzakta"
                     if best[3] is not None else f"rapor saatinde ({v.time}) iz kaydı yok")
            v.checks.update({"konum_cekim_aninda": "uyumlu", "konum_rapor_saatinde": "uyumsuz",
                             "zaman": f"rapor {v.time}, çekim {veh['capture_time']}"})
            type_ok = self._type_check(p, veh["label"])
            v.checks["tip"] = type_ok
            v.verdict, v.report_type = "kismen_uyumlu", "ZAMAN_KAYMASI"
            v.summary = (f"Konum ve tip {veh['frame_id']} karesindeki {veh['label']} ({best[1] or 'izsiz'}) ile "
                         f"çekim anında ({veh['capture_time']}) örtüşüyor, ancak araç {where}. "
                         "Rapor büyük olasılıkla farklı bir zamana ait gözlemi aktarıyor; davranış iddiası bu nedenle "
                         "tespitle karşılaştırılamadı.")
            if p.claims_normal:
                risk, scen = self._track_final(best[1]) if best[1] else (veh["risk_level"], veh["scenario"])
                threat = risk in ("YUKSEK", "KRITIK")
                v.checks["olagan_iddiasi"] = "aracın güncel durumuyla çelişiyor" if threat else "uyumlu"
                if threat:
                    v.summary += (f" Ayrıca 'olağan' nitelendirmesi aracın güncel durumuyla ({risk}, {scen}) "
                                  "çelişiyor; rapor güven verici kanıt olarak kullanılmamalı.")
            return

        if frames_here:
            fr = self.state.frames[frames_here[0]]
            v.verdict, v.report_type = "celisir", "HAYALET_KARE_ICI"
            v.checks.update({"konum": "kare içinde ama eşleşen araç yok"})
            v.summary = (f"Koordinat {frames_here[0]} karesinin içinde (çekim {fr['capture_time']}), fakat karede "
                         f"bu noktada araç yok ve rapor saatinde yakından geçen bir iz de bulunmuyor.")
            return

        v.verdict, v.report_type = "dogrulanamaz", "HAYALET_KARE_DISI"
        v.checks.update({"konum": "hiçbir karenin kapsamında değil, yakın iz yok"})
        v.summary = "Koordinat hiçbir karenin kapsamında değil ve rapor saatinde yakında iz yok; doğrulanamaz."

    def _track_final(self, tid: str) -> tuple[str | None, str | None]:
        """İzin son konumundaki değerlendirmesi: kare dışıysa oradan, değilse en geç çekimli kayıttan."""
        off = self.state.offframe_risk.get(tid)
        if off:
            return off["risk_level"], off["scenario"]
        recs = [v for v in self.state.vehicles.values() if v["track_id"] == tid and not v["filtered"]]
        if not recs:
            return None, None
        last = max(recs, key=lambda v: v["capture_min"])
        return last["risk_level"], last["scenario"]

    def _type_check(self, p: ParsedReport, label: str | None) -> str:
        if not p.types:
            return "belirtilmemis"
        if label is None:
            return "dogrulanamaz"
        return "uyumlu" if label in p.types else "uyumsuz"

    def _judge_matched(self, v: ReportVerdict, p: ParsedReport, t: int, best, timely):
        vid, tid, d_cap, d_rep, _ = best
        veh = self.state.vehicles.get(vid) if vid else None
        track = self.ds.tracks.get(tid) if tid else None
        v.matched_vehicle_id, v.matched_track_id = vid, tid
        if veh:
            v.related_frames = sorted(set(v.related_frames) | {veh["frame_id"]})
        label = veh["label"] if veh else None
        # Bir iz birden fazla karede kayıtlı olabilir (erken karedeki anlık görüntü + bittiği kare).
        # Tehdit / devriye yargısı izin SON durumuna göre yapılır; eşleşen anlık görüntüye göre değil.
        risk, scenario = self._track_final(tid) if tid else (None, None)
        if risk is None and veh:
            risk, scenario = veh["risk_level"], veh["scenario"]

        # davranış (rapor saatindeki iz hareketinden; iz yoksa karedeki senaryodan)
        spd = _speed_at(track, t) if track else None
        mv_before, mv_around = _motion_state(track, t, self.th.stop_radius_m) if track else (None, None)
        if mv_before is None and mv_around is None and veh:
            mv_before = mv_around = scenario not in STATIONARY_SCENARIOS
        v.checks["konum"] = "uyumlu"
        v.checks["mesafe_m"] = round(min(x for x in (d_cap, d_rep) if x is not None), 1)
        v.checks["tip"] = self._type_check(p, label)
        v.checks["hiz_rapor_saatinde_mps"] = round(spd, 1) if spd is not None else None

        # sayı iddiası
        if p.count and p.count > 1:
            # aynı iz birden fazla karede kayıtlı olabilir → iz (yoksa araç) kimliğine göre tekilleştir
            same = {c[1] or c[0] for c in timely
                    if (self.state.vehicles.get(c[0]) or {}).get("label") in (p.types or [label])}
            v.checks["sayi"] = "uyumlu" if len(same) >= p.count else f"uyumsuz (bulunan {len(same)})"

        behav = "belirtilmemis"
        if p.claims_stationary and (mv_before is not None or mv_around is not None):
            # "uzun süredir hareketsiz / konuşlanmış": rapor saatine kadar olan 10 dk'ya bakılır
            moving = mv_before if mv_before is not None else mv_around
            behav = "uyumlu" if not moving else "uyumsuz (araç rapor saatinde hareketli)"
        elif p.claims_moving and (mv_before is not None or mv_around is not None):
            moving = bool(mv_before) or bool(mv_around)
            behav = "uyumlu" if moving else "uyumsuz (araç rapor saatinde duruyor)"
            if moving and p.direction_deg is not None and track:
                hd = _heading_at(track, t)
                if hd is not None and angle_diff(hd, p.direction_deg) > 60:
                    behav = f"uyumsuz (yön {hd:.0f}°)"
        v.checks["davranis"] = behav

        # "olağan / transit" iddiası tehdit aracı için
        threat = risk in ("YUKSEK", "KRITIK")
        if p.claims_normal:
            v.checks["olagan_iddiasi"] = "tehdit aracıyla çelişiyor" if threat else "uyumlu"

        # dost iddiası
        if p.friendly_claim:
            confirmed = v.source == "official" and p.friendly_confirmed_wording
            v.checks["dost_iddiasi"] = "resmi teyitli" if confirmed else "teyitsiz (üçüncü taraf / teyit ifadesi yok)"
            if confirmed and scenario in PATROL_SCENARIOS:
                v.verdict, v.report_type, v.affects_risk = "destekler", "DOST_TEYITLI", True
                v.summary = (f"Resmi kaynak, kimlik teyitli dost devriye bildirimi; rapor saatinde {tid} izi ile "
                             f"~{v.checks['mesafe_m']} m içinde eşleşti ve iz sabit yarıçaplı devriye örüntüsünde. "
                             "İlgili aracın riski DUSUK'e indirildi.")
            elif confirmed:
                v.verdict, v.report_type = "kismen_uyumlu", "DOST_TEYITLI"
                v.summary = ("Resmi dost teyidi var ancak eşleşen araç devriye örüntüsünde değil; risk otomatik "
                             "düşürülmedi, analist onayı gerekir.")
            else:
                v.verdict, v.report_type = ("celisir" if threat else "dogrulanamaz"), "DOST_ALDATICI"
                v.summary = ("Üçüncü taraftan gelen teyitsiz 'dost unsur' iddiası; risk düşürülmedi."
                             + (f" Eşleşen araç {risk} riskli ({scenario}), iddia tehdit tablosuyla çelişiyor." if threat else ""))
            return

        # hüküm
        bad = [k for k in ("tip", "davranis", "sayi") if str(v.checks.get(k, "")).startswith("uyumsuz")]
        if p.claims_normal and threat:
            v.verdict, v.report_type = "celisir", "YANILTICI_OLAGAN"
            v.summary = (f"Konum/tip doğru ({label or 'iz'} {tid or ''}), fakat araç {risk} riskli ({scenario}); "
                         "'olağan' nitelendirmesi davranış analiziyle çelişiyor.")
        elif "davranis" in bad:
            v.verdict, v.report_type = "celisir", "YANLIS_DAVRANIS"
            v.summary = (f"Konum tutarlı ({tid or label}) ancak davranış iddiası izle çelişiyor: {v.checks['davranis']}."
                         + (f" Tip de uyuşmuyor (tespit '{label}')." if "tip" in bad else ""))
        elif "tip" in bad:
            v.verdict, v.report_type = "celisir", "YANLIS_TIP"
            v.summary = f"Konumda araç var ama tespit sınıfı '{label}', rapor '{p.type_word}' diyor."
            if {label} | set(p.types) <= {"van", "truck"}:
                v.summary += " (van↔truck sınıf karışıklığı ihtimali düşük de olsa var; güven skoru kontrol edilmeli.)"
        elif "sayi" in bad:
            v.verdict, v.report_type = "kismen_uyumlu", "SAYI_UYUMSUZ"
            v.summary = f"Konum/tip tutarlı ancak araç sayısı tutmuyor: {v.checks['sayi']}."
        elif v.checks["tip"] == "dogrulanamaz":
            v.verdict, v.report_type = "kismen_uyumlu", "IZ_ESLESMESI"
            why = ("araç karede tespit edilmediği (yalnızca iz) için" if veh else "iz hiçbir karede görünmediği için")
            v.summary = (f"Rapor saatinde {tid} izi bu noktada; davranış {v.checks['davranis']}, ancak {why} "
                         "araç tipi doğrulanamadı.")
        else:
            v.verdict, v.report_type = "destekler", "DOGRU_GOZLEM"
            v.summary = (f"Konum, tip ({label}) ve davranış tespit/iz verisiyle tutarlı"
                         + (f"; araç {risk} riskli ({scenario})." if risk else "."))
        if p.color:
            v.checks["renk"] = "dogrulanamaz (tespit modeli renk üretmiyor)"

    # -------------------------------------------------------------- bölge bazlı
    def _threats_in_zone(self, zone: str, t: int, window: int = 60) -> list[dict]:
        out, seen = [], set()
        for veh in self.state.vehicles.values():
            if veh["filtered"] or veh["risk_level"] not in ("YUKSEK", "KRITIK"):
                continue
            key = veh["track_id"] or veh["vehicle_id"]   # aynı iz birden fazla karede olabilir
            if key in seen:
                continue
            in_zone_now = False
            if veh["track_id"]:
                pos = self.ds.tracks[veh["track_id"]].position_at(t)
                in_zone_now = bool(pos) and self.ds.zone_of(*pos) == zone
            if in_zone_now or (veh["zone"] == zone and abs(veh["capture_min"] - t) <= window):
                out.append(veh)
                seen.add(key)
        return out

    def _verify_zone_normal(self, v: ReportVerdict, p: ParsedReport, t: int):
        threats = self._threats_in_zone(p.zone, t)
        v.related_frames = sorted({x["frame_id"] for x in threats} |
                                  {fid for fid, fr in self.state.frames.items() if fr["zone"] == p.zone})
        if threats:
            v.verdict, v.report_type = "celisir", "BOLGE_NORMAL"
            ids = ", ".join(f"{x['track_id'] or x['vehicle_id']} ({x['risk_level']})" for x in threats)
            v.summary = f"'{p.zone}' için 'trafik normal' deniyor, ancak rapor saatine yakın bölgede tehdit var: {ids}."
            v.checks["bolgedeki_tehditler"] = [x["vehicle_id"] for x in threats]
        else:
            v.verdict, v.report_type = "ilgisiz", "BOLGE_NORMAL"
            v.summary = f"'{p.zone}' bölgesinde rapor saatine yakın tehdit bulunmuyor; genel durum bildirimi, karar etkisi yok."

    def _verify_zone_observation(self, v: ReportVerdict, p: ParsedReport, t: int):
        v.report_type = "BOLGE_GOZLEM"
        cands = []
        for veh in self.state.vehicles.values():
            if veh["filtered"] or not veh["track_id"]:
                continue
            tr = self.ds.tracks[veh["track_id"]]
            pos = tr.position_at(t)
            if not pos or self.ds.zone_of(*pos) != p.zone:
                continue
            spd, hd = _speed_at(tr, t), _heading_at(tr, t)
            toward = hd is not None and angle_diff(hd, bearing_deg(*pos, self.ds.base["lat"], self.ds.base["lon"])) <= 45
            if (p.claims_moving and (spd or 0) > 1.0 and (toward or not p.toward_base)) or (p.claims_stationary and (spd or 0) <= 1.0):
                cands.append((veh, spd, toward))
        # ilk bulunan değil, en riskli aday (dict sırasına bağımlı olmasın)
        cands.sort(key=lambda c: RISK_ORDER.index(c[0]["risk_level"]), reverse=True)
        type_match = [c for c in cands if not p.types or c[0]["label"] in p.types]
        v.checks["bolgede_uyan_arac_sayisi"] = len(cands)
        v.checks["tip_uyan"] = len(type_match)
        if type_match:
            veh = type_match[0][0]
            v.matched_vehicle_id, v.matched_track_id = veh["vehicle_id"], veh["track_id"]
            v.related_frames = [veh["frame_id"]]
            v.verdict = "destekler"
            v.summary = (f"Rapor saatinde '{p.zone}' koridorunda iddiaya uyan araç var: {veh['track_id']} "
                         f"({veh['label']}, {veh['risk_level']}, {veh['scenario']}); {veh['frame_id']} karesinde görüldü.")
        elif cands:
            veh = cands[0][0]
            v.matched_vehicle_id, v.matched_track_id = veh["vehicle_id"], veh["track_id"]
            v.related_frames = [veh["frame_id"]]
            v.verdict = "kismen_uyumlu"
            v.summary = (f"Bölgede davranışı uyan araç var ({veh['track_id']}), ancak tip farklı: tespit '{veh['label']}', "
                         f"rapor '{p.type_word}'. Sınıf karışıklığı olasılığı da göz önünde bulundurulmalı.")
        else:
            v.verdict = "dogrulanamaz"
            v.summary = f"Rapor saatinde '{p.zone}' koridorunda iddiaya uyan izli araç bulunamadı."
