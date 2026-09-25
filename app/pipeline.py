"""Deterministik analiz hattı: tespit → iz eşleştirme → öznitelik → risk → rapor doğrulama.
Çıktı (WorldState) hem LLM ajanının araçlarına hem de React'in okuyacağı API'ye kaynak olur."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import RISK_ORDER, Thresholds, settings
from .data import Dataset, load_dataset
from .detector import BaseDetector, build_detector
from .geo import bbox_center_latlon, frame_center, hhmm_to_min, min_to_hhmm, point_in_frame
from .reports import ReportVerifier
from .risk import (classify_tracked, classify_untracked, firm_margin, max_risk, tracked_margin,
                   untracked_margin)
from .tracking import compute_features
from .geo import haversine_m


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


class Analyzer:
    def __init__(self, ds: Dataset | None = None, detector: BaseDetector | None = None,
                 th: Thresholds | None = None):
        self.ds = ds or load_dataset(settings.data_dir)
        self.th = th or settings.thresholds
        self.detector = detector or build_detector(self.ds.raw_detections_path, settings.data_dir)

    # ---------------------------------------------------------------------------
    def run(self) -> WorldState:
        st = WorldState(generated_at=time.time(), detector=self.detector.name)
        assigned: set[str] = set()

        for fid, meta in sorted(self.ds.image_meta.items(), key=lambda kv: kv[1]["capture_time"]):
            t_cap = hhmm_to_min(meta["capture_time"])
            clat, clon = frame_center(meta)
            fr = {"frame_id": fid, "capture_time": meta["capture_time"], "capture_min": t_cap, "meta": meta,
                  "center": [clat, clon], "zone": self.ds.zone_of(clat, clon),
                  "dist_to_base_m": round(self.ds.dist_to_base(clat, clon), 1), "vehicle_ids": []}
            dets = self.detector.detect(fid)

            # 1) iz eşleştirme — global açgözlü, bire bir
            pairs = []
            centers = []
            for i, d in enumerate(dets):
                lat, lon = bbox_center_latlon(d["bbox"], meta)
                centers.append((lat, lon))
                if d["confidence"] < self.th.min_confidence:
                    continue
                for tid, tr in self.ds.tracks.items():
                    pos = tr.position_at(t_cap)
                    if pos:
                        dist = haversine_m(lat, lon, *pos)
                        if dist <= self.th.match_radius_m:
                            pairs.append((dist, i, tid))
            det_to_track: dict[int, tuple[str, float]] = {}
            used = set()
            for dist, i, tid in sorted(pairs):
                if i in det_to_track or tid in used or tid in assigned:
                    continue
                det_to_track[i] = (tid, dist)
                used.add(tid)

            # 2) tespit edilen araçlar
            for i, d in enumerate(dets):
                lat, lon = centers[i]
                vid = f"{fid}_v{i}"
                tid, mdist = det_to_track.get(i, (None, None))
                rec = self._vehicle_record(vid, fid, meta, t_cap, d["label"], d["confidence"], d["bbox"],
                                           lat, lon, tid, mdist, source="detection")
                if d["confidence"] < self.th.min_confidence:
                    rec.update(filtered=True, risk_level="DUSUK", scenario="FILTERED_LOW_CONF",
                               risk_reasons=[f"Güven {d['confidence']:.2f} < {self.th.min_confidence:.2f}: "
                                             "olası yanlış pozitif, risk hesabına katılmadı."],
                               margin=firm_margin("Düşük güvenli tespit; risk hesabına katılmadı."))
                st.vehicles[vid] = rec
                fr["vehicle_ids"].append(vid)
            assigned |= used

            # 3) karede olduğu halde tespit edilmemiş izler (kaçırılan tespit)
            for tid, tr in self.ds.tracks.items():
                if tid in assigned:
                    continue
                pos = tr.position_at(t_cap)
                if pos and point_in_frame(pos[0], pos[1], meta):
                    vid = f"{fid}_trk_{tid}"
                    rec = self._vehicle_record(vid, fid, meta, t_cap, None, None, None, pos[0], pos[1], tid, 0.0,
                                               source="track_only")
                    rec["risk_reasons"].insert(0, "Karede izi var ama tespit yok — model bu aracı kaçırmış olabilir.")
                    st.vehicles[vid] = rec
                    fr["vehicle_ids"].append(vid)
                    assigned.add(tid)
            st.frames[fid] = fr

        # 4) hiçbir kareye bağlanmayan izler (kare dışı; aralarında tehdit olabilir)
        for tid, tr in self.ds.tracks.items():
            if tid in assigned:
                continue
            st.offframe_track_ids.append(tid)
            f = compute_features(tr, self.ds, self.th, tr.t_end)
            scen, risk, reasons = classify_tracked(f, self.th)
            last = tr.points[-1]
            st.offframe_risk[tid] = {"track_id": tid, "scenario": scen, "risk_level": risk, "risk_reasons": reasons,
                                     "margin": tracked_margin(f, self.th, scen, risk),
                                     "last_time": min_to_hhmm(last.t), "lat": last.lat, "lon": last.lon,
                                     "zone": self.ds.zone_of(last.lat, last.lon), "features": f.to_dict()}

        # 5) rapor doğrulama
        verifier = ReportVerifier(self.ds, st, self.th)
        verdicts = [verifier.verify(r) for r in self.ds.reports]
        for v in verdicts:
            if v.report_type == "DOST_TEYITLI" and v.verdict == "destekler" and v.matched_vehicle_id:
                veh = st.vehicles[v.matched_vehicle_id]
                veh["risk_level"] = "DUSUK"
                veh["friendly_confirmed_by"].append(v.report_id)
                veh["risk_reasons"].append(f"Resmi dost teyidi ({v.report_id}, {v.time}) — risk DUSUK'e indirildi.")
                veh["margin"] = firm_margin(f"Resmi dost teyidi ({v.report_id}).")
            elif v.report_type == "DOST_TEYITLI" and v.matched_track_id in st.offframe_risk:
                st.offframe_risk[v.matched_track_id]["risk_level"] = "DUSUK"
                st.offframe_risk[v.matched_track_id]["margin"] = firm_margin(f"Resmi dost teyidi ({v.report_id}).")
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
    def _vehicle_record(self, vid, fid, meta, t_cap, label, conf, bbox, lat, lon, tid, mdist, source) -> dict:
        dist = self.ds.dist_to_base(lat, lon)
        rec = {"vehicle_id": vid, "frame_id": fid, "capture_time": meta["capture_time"], "capture_min": t_cap,
               "source": source, "label": label, "confidence": conf, "bbox": bbox,
               "lat": round(lat, 6), "lon": round(lon, 6), "zone": self.ds.zone_of(lat, lon),
               "dist_to_base_m": round(dist, 1), "bearing_from_base_deg": round(self.ds.bearing_from_base(lat, lon), 1),
               "track_id": tid, "track_match_m": round(mdist, 2) if mdist is not None else None,
               "features": None, "filtered": False, "friendly_confirmed_by": [], "report_ids": []}
        if tid:
            f = compute_features(self.ds.tracks[tid], self.ds, self.th, t_cap)
            scen, risk, reasons = classify_tracked(f, self.th)
            rec["features"] = f.to_dict()
            margin = tracked_margin(f, self.th, scen, risk)
        else:
            scen, risk, reasons = classify_untracked(label or "unknown", dist, self.th)
            margin = untracked_margin(label or "unknown", dist, self.th, risk)
        # margin: motor bu seviyeden ne kadar emin (net / sınırda) — ortak karar tablosu kullanır
        rec.update(scenario=scen, risk_level=risk, risk_reasons=reasons, margin=margin)
        return rec


def build_state() -> tuple[Analyzer, WorldState]:
    an = Analyzer()
    return an, an.run()