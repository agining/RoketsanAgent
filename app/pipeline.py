"""Deterministik analiz hattı: tespit → iz eşleştirme → öznitelik → risk → rapor doğrulama.
Çıktı (WorldState) hem LLM ajanının araçlarına hem de React'in okuyacağı API'ye kaynak olur.

Tespit katmanındaki düzeltmeler:
  * Kopya kutular: aynı karede IoU ≥ duplicate_iou olan kutular (sınıftan bağımsız) tek nesne sayılır. En güvenli
    kutu tutulur; diğerlerinin etiketi alt_labels'a yazılır (ör. car 0.75 / truck 0.61 → ağır olabilir). Kopya
    kutu kaydı silinmez, DUPLICATE_BOX olarak elenmiş gösterilir.
  * Düşük güvenli kutular (min_confidence altı) çekim anında aynı noktada biten bir izle doğrulanırsa kabul edilir
    ve etiketi korunur. Böylece aynı araç hem "elenmiş kutu" hem de "izden kurtarılmış araç" olarak iki kez sayılmaz.
  * İz eşleştirme her karede bire birdir; bir iz farklı saatlerdeki farklı karelerde de eşleşebilir.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import RISK_ORDER, Thresholds, settings
from .data import Dataset, load_dataset
from .detector import BaseDetector, build_detector
from .geo import bbox_center_latlon, frame_center, haversine_m, hhmm_to_min, min_to_hhmm, point_in_frame
from .reports import ReportVerifier
from .risk import (classify_tracked, classify_untracked, firm_margin, is_bus, is_heavy, max_risk, tracked_margin,
                   untracked_margin)
from .tracking import compute_features


@dataclass
class WorldState:
    frames: dict = field(default_factory=dict)          # frame_id → kare özeti
    vehicles: dict = field(default_factory=dict)        # vehicle_id → araç kaydı
    reports: list = field(default_factory=list)         # doğrulanmış rapor kayıtları
    offframe_track_ids: list = field(default_factory=list)
    offframe_risk: dict = field(default_factory=dict)   # track_id → {risk_level, scenario, ...}
    generated_at: float = 0.0
    detector: str = ""

    # ----------------------------------------------------------- React/ajan görünümleri
    def frame_view(self, frame_id: str, include_tracks: bool = False, ds: Dataset | None = None) -> dict:
        fr = self.frames[frame_id]
        vehicles = [self.vehicle_view(vid, include_track=include_tracks, ds=ds) for vid in fr["vehicle_ids"]]
        reports = [r for r in self.reports if frame_id in r["related_frames"]]
        return {**{k: v for k, v in fr.items() if k != "meta"}, "corner_coordinates": fr["meta"]["corner_coordinates"],
                "width_px": fr["meta"]["width_px"], "height_px": fr["meta"]["height_px"],
                "vehicles": vehicles, "reports": reports}

    def vehicle_view(self, vid: str, include_track: bool = False, ds: Dataset | None = None) -> dict:
        v = dict(self.vehicles[vid])
        if include_track and ds and v["track_id"]:
            tr = ds.tracks[v["track_id"]]
            v["track_points"] = [{"time": min_to_hhmm(p.t), "lat": p.lat, "lon": p.lon}
                                 for p in tr.points if p.t <= v["capture_min"]]
        return v


def _iou(a: list[float], b: list[float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0.0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


def group_duplicates(dets: list[dict], iou_thr: float) -> dict[int, tuple[int, float]]:
    """Sınıftan bağımsız NMS. Dönen: kopya kutu indeksi → (tutulan kutu indeksi, IoU)."""
    order = sorted(range(len(dets)), key=lambda i: -dets[i]["confidence"])
    kept: list[int] = []
    dup: dict[int, tuple[int, float]] = {}
    for i in order:
        best = max(((k, _iou(dets[i]["bbox"], dets[k]["bbox"])) for k in kept), key=lambda x: x[1], default=None)
        if best and best[1] >= iou_thr:
            dup[i] = best
        else:
            kept.append(i)
    return dup


class Analyzer:
    def __init__(self, ds: Dataset | None = None, detector: BaseDetector | None = None,
                 th: Thresholds | None = None):
        self.ds = ds or load_dataset(settings.data_dir)
        self.th = th or settings.thresholds
        self.detector = detector or build_detector(self.ds.raw_detections_path, settings.data_dir)

    # ---------------------------------------------------------------------------
    def run(self) -> WorldState:
        st = WorldState(generated_at=time.time(), detector=self.detector.name)
        seen_tracks: set[str] = set()     # en az bir karede görülen izler (kare dışı izleri ayırmak için)

        for fid, meta in sorted(self.ds.image_meta.items(), key=lambda kv: kv[1]["capture_time"]):
            t_cap = hhmm_to_min(meta["capture_time"])
            clat, clon = frame_center(meta)
            fr = {"frame_id": fid, "capture_time": meta["capture_time"], "capture_min": t_cap, "meta": meta,
                  "center": [clat, clon], "zone": self.ds.zone_of(clat, clon),
                  "dist_to_base_m": round(self.ds.dist_to_base(clat, clon), 1), "vehicle_ids": []}
            dets = self.detector.detect(fid)

            # 0) kopya kutular — aynı nesneye düşen kutular tek araç
            dup = group_duplicates(dets, self.th.duplicate_iou)
            alt_labels: dict[int, list[dict]] = {}
            for i, (k, ov) in dup.items():
                alt_labels.setdefault(k, []).append({"label": dets[i]["label"],
                                                     "confidence": round(dets[i]["confidence"], 3),
                                                     "iou": round(ov, 2)})

            # 1) iz eşleştirme — kare içinde global açgözlü, bire bir. Güvenli kutular önce; düşük güvenli kutu
            #    yalnız çekim anında aynı noktada bir iz varsa kabul edilir.
            pairs = []
            centers = []
            for i, d in enumerate(dets):
                lat, lon = bbox_center_latlon(d["bbox"], meta)
                centers.append((lat, lon))
                if i in dup or d["confidence"] < self.th.low_conf_floor:
                    continue
                low = d["confidence"] < self.th.min_confidence
                for tid, tr in self.ds.tracks.items():
                    pos = tr.position_at(t_cap)
                    if pos:
                        dist = haversine_m(lat, lon, *pos)
                        if dist <= self.th.match_radius_m:
                            pairs.append((low, dist, i, tid))
            det_to_track: dict[int, tuple[str, float]] = {}
            used: set[str] = set()
            for low, dist, i, tid in sorted(pairs):
                if i in det_to_track or tid in used:
                    continue
                det_to_track[i] = (tid, dist)
                used.add(tid)

            # 2) tespit edilen araçlar
            for i, d in enumerate(dets):
                lat, lon = centers[i]
                vid = f"{fid}_v{i}"
                tid, mdist = det_to_track.get(i, (None, None))
                rec = self._vehicle_record(vid, fid, meta, t_cap, d["label"], d["confidence"], d["bbox"],
                                           lat, lon, tid, mdist, source="detection",
                                           alt_labels=alt_labels.get(i, []))
                if i in dup:
                    k, ov = dup[i]
                    rec.update(filtered=True, duplicate_of=f"{fid}_v{k}", risk_level="DUSUK", scenario="DUPLICATE_BOX",
                               risk_reasons=[f"{fid}_v{k} kutusuyla IoU {ov:.2f}: aynı nesnenin kopya kutusu "
                                             f"({d['label']} {d['confidence']:.2f}); tek araç sayıldı."],
                               margin=firm_margin("Kopya kutu; risk hesabına katılmadı."))
                elif d["confidence"] < self.th.min_confidence and tid:
                    rec["low_conf_corroborated"] = True
                    rec["risk_reasons"].insert(0, f"Güven {d['confidence']:.2f} < {self.th.min_confidence:.2f}, ancak "
                                                  f"çekim anında {tid} izi aynı noktada ({mdist:.1f} m): tespit izle "
                                                  "doğrulandı, etiket korundu.")
                elif d["confidence"] < self.th.min_confidence:
                    rec.update(filtered=True, risk_level="DUSUK", scenario="FILTERED_LOW_CONF",
                               risk_reasons=[f"Güven {d['confidence']:.2f} < {self.th.min_confidence:.2f} ve aynı "
                                             "noktada iz yok: olası yanlış pozitif, risk hesabına katılmadı."],
                               margin=firm_margin("Düşük güvenli tespit; risk hesabına katılmadı."))
                st.vehicles[vid] = rec
                fr["vehicle_ids"].append(vid)

            # 3) karede olduğu halde tespit edilmemiş izler (kaçırılan tespit)
            for tid, tr in self.ds.tracks.items():
                if tid in used:
                    continue
                pos = tr.position_at(t_cap)
                if pos and point_in_frame(pos[0], pos[1], meta):
                    vid = f"{fid}_trk_{tid}"
                    rec = self._vehicle_record(vid, fid, meta, t_cap, None, None, None, pos[0], pos[1], tid, 0.0,
                                               source="track_only")
                    rec["risk_reasons"].insert(0, "Karede izi var ama tespit yok — model bu aracı kaçırmış olabilir.")
                    st.vehicles[vid] = rec
                    fr["vehicle_ids"].append(vid)
                    used.add(tid)
            seen_tracks |= used
            st.frames[fid] = fr

        # 4) hiçbir kareye bağlanmayan izler (kare dışı; aralarında tehdit olabilir)
        for tid, tr in self.ds.tracks.items():
            if tid in seen_tracks:
                continue
            st.offframe_track_ids.append(tid)
            f = compute_features(tr, self.ds, self.th, tr.t_end)
            scen, risk, reasons = classify_tracked(f, self.th, heavy=False)
            last = tr.points[-1]
            st.offframe_risk[tid] = {"track_id": tid, "scenario": scen, "risk_level": risk, "risk_reasons": reasons,
                                     "margin": tracked_margin(f, self.th, scen, risk, heavy=False),
                                     "last_time": min_to_hhmm(last.t), "lat": last.lat, "lon": last.lon,
                                     "zone": self.ds.zone_of(last.lat, last.lon), "features": f.to_dict()}

        # 5) rapor doğrulama
        verifier = ReportVerifier(self.ds, st, self.th)
        verdicts = [verifier.verify(r) for r in self.ds.reports]
        for v in verdicts:
            if v.report_type == "DOST_TEYITLI" and v.verdict == "destekler" and (v.matched_vehicle_id or v.matched_track_id):
                # Teyit izin kendisine aittir: aynı izin bütün kare kayıtları ve kare dışı kaydı düşer.
                recs = [x for x in st.vehicles.values()
                        if not x["filtered"] and ((v.matched_track_id and x["track_id"] == v.matched_track_id)
                                                  or x["vehicle_id"] == v.matched_vehicle_id)]
                for veh in recs:
                    if veh["risk_level"] == "KRITIK":
                        veh["risk_reasons"].append(f"Resmi dost teyidi ({v.report_id}) var ama KRITIK otomatik "
                                                   "düşürülmez; analist onayı gerekir.")
                        continue
                    veh["risk_level"] = "DUSUK"
                    veh["friendly_confirmed_by"].append(v.report_id)
                    veh["risk_reasons"].append(f"Resmi dost teyidi ({v.report_id}, {v.time}) — risk DUSUK'e indirildi.")
                    veh["margin"] = firm_margin(f"Resmi dost teyidi ({v.report_id}).")
                off = st.offframe_risk.get(v.matched_track_id)
                if off and off["risk_level"] != "KRITIK":
                    off["risk_level"] = "DUSUK"
                    off["margin"] = firm_margin(f"Resmi dost teyidi ({v.report_id}).")
            elif v.report_type == "DOST_TEYITLI" and v.matched_track_id in st.offframe_risk:
                off = st.offframe_risk[v.matched_track_id]
                if v.verdict == "destekler" and off["risk_level"] != "KRITIK":
                    off["risk_level"] = "DUSUK"
                    off["margin"] = firm_margin(f"Resmi dost teyidi ({v.report_id}).")
            if v.matched_vehicle_id:
                st.vehicles[v.matched_vehicle_id]["report_ids"].append(v.report_id)
        st.reports = [v.to_dict() for v in verdicts]

        # 6) kare risk seviyesi = araçların en yükseği
        for fid, fr in st.frames.items():
            vs = [st.vehicles[v] for v in fr["vehicle_ids"] if not st.vehicles[v]["filtered"]]
            fr["risk_level"] = max_risk([v["risk_level"] for v in vs])
            fr["counts"] = {lvl: sum(1 for v in vs if v["risk_level"] == lvl) for lvl in RISK_ORDER}
            top = sorted(vs, key=lambda v: RISK_ORDER.index(v["risk_level"]), reverse=True)
            fr["top_vehicle_id"] = top[0]["vehicle_id"] if top else None
            fr["report_ids"] = [r["report_id"] for r in st.reports if fid in r["related_frames"]]
        return st

    # ---------------------------------------------------------------------------
    def _vehicle_record(self, vid, fid, meta, t_cap, label, conf, bbox, lat, lon, tid, mdist, source,
                        alt_labels: list[dict] | None = None) -> dict:
        dist = self.ds.dist_to_base(lat, lon)
        alt_labels = alt_labels or []
        heavy = is_heavy(label, alt_labels, self.th.heavy_alt_min_conf)
        bus = is_bus(label, alt_labels, self.th.heavy_alt_min_conf)   # ROUTINE_SHUTTLE için
        rec = {"vehicle_id": vid, "frame_id": fid, "capture_time": meta["capture_time"], "capture_min": t_cap,
               "source": source, "label": label, "confidence": conf, "bbox": bbox, "alt_labels": alt_labels,
               "heavy": heavy, "lat": round(lat, 6), "lon": round(lon, 6), "zone": self.ds.zone_of(lat, lon),
               "dist_to_base_m": round(dist, 1), "bearing_from_base_deg": round(self.ds.bearing_from_base(lat, lon), 1),
               "track_id": tid, "track_match_m": round(mdist, 2) if mdist is not None else None,
               "features": None, "filtered": False, "duplicate_of": None, "low_conf_corroborated": False,
               "friendly_confirmed_by": [], "report_ids": []}
        if tid:
            f = compute_features(self.ds.tracks[tid], self.ds, self.th, t_cap)
            scen, risk, reasons = classify_tracked(f, self.th, heavy=heavy, bus=bus)
            rec["features"] = f.to_dict()
            margin = tracked_margin(f, self.th, scen, risk, heavy=heavy, bus=bus)
        else:
            scen, risk, reasons = classify_untracked(label or "unknown", dist, self.th, heavy=heavy)
            margin = untracked_margin(label or "unknown", dist, self.th, risk, heavy=heavy)
        if alt_labels and label not in {a["label"] for a in alt_labels}:
            alts = ", ".join(f"{a['label']} {a['confidence']:.2f}" for a in alt_labels)
            reasons = reasons + [f"Aynı nesneye düşen kopya kutu(lar): {alts} — sınıf belirsiz"
                                 + (", ağır araç sayıldı." if heavy and label not in ("truck", "bus") else ".")]
        # margin: motor bu seviyeden ne kadar emin (net / sınırda) — ortak karar tablosu kullanır
        rec.update(scenario=scen, risk_level=risk, risk_reasons=reasons, margin=margin)
        return rec


def build_state() -> tuple[Analyzer, WorldState]:
    an = Analyzer()
    return an, an.run()
