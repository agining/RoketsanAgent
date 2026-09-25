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
from .risk import classify_tracked, classify_untracked, max_risk
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
        frames = sorted(self.ds.image_meta.items(), key=lambda kv: (hhmm_to_min(kv[1]["capture_time"]), kv[0]))

        for fid, meta in frames:
            t_cap = hhmm_to_min(meta["capture_time"])
            clat, clon = frame_center(meta)
            fr = {"frame_id": fid, "capture_time": meta["capture_time"], "capture_min": t_cap, "meta": meta,
                  "center": [clat, clon], "zone": self.ds.zone_of(clat, clon),
                  "dist_to_base_m": round(self.ds.dist_to_base(clat, clon), 1), "vehicle_ids": [],
                  "passing_tracks": []}
            dets = self.detector.detect(fid)
            positions = {tid: pos for tid, tr in self.ds.tracks.items()
                         if (pos := self._position_for_match(tr, t_cap)) is not None}

            # 1) iz eşleştirme — bire bir kısıtı SADECE KARE İÇİNDE.
            #    Bir iz, bittiği kareden önce başka bir karenin alanından geçebilir. Global bir
            #    "atanmış izler" kümesi, izi o erken kareye bağlayıp asıl karesindeki tespitten
            #    koparıyordu (araç UNTRACKED kalıp davranış özniteliklerini kaybediyordu).
            #    Aynı mesafe aralığında, bu karede BİTEN iz geçen ize tercih edilir.
            pairs, centers, nearest = [], [], []
            for i, d in enumerate(dets):
                lat, lon = bbox_center_latlon(d["bbox"], meta)
                centers.append((lat, lon))
                ranked = sorted((haversine_m(lat, lon, *pos), tid) for tid, pos in positions.items())
                nearest.append(ranked[:2])
                if d["confidence"] < self.th.min_confidence:
                    continue
                for dist, tid in ranked:
                    if dist > self.th.match_radius_m:
                        break
                    pairs.append((0 if self._ends_at(tid, t_cap) else 1, dist, i, tid))
            det_to_track: dict[int, tuple[str, float]] = {}
            used: set[str] = set()
            for _, dist, i, tid in sorted(pairs):
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
                                           lat, lon, tid, mdist, source="detection")
                # brief'teki gibi: "T0122 · <1 m (ikinci en yakın: T0032 · 41 m)" — hem açıklama hem
                # gerçek veride match_radius_m ayarı için teşhis bilgisi
                rec["track_candidates"] = [{"track_id": t, "dist_m": round(dd, 1)} for dd, t in nearest[i]]
                if d["confidence"] < self.th.min_confidence:
                    rec.update(filtered=True, risk_level="DUSUK", scenario="FILTERED_LOW_CONF",
                               risk_reasons=[f"Güven {d['confidence']:.2f} < {self.th.min_confidence:.2f}: "
                                             "olası yanlış pozitif, risk hesabına katılmadı."])
                st.vehicles[vid] = rec
                fr["vehicle_ids"].append(vid)

            # 3) çekim anında karenin içinde olup bu karede tespitle eşleşmemiş izler
            for tid, pos in positions.items():
                if tid in used or not point_in_frame(pos[0], pos[1], meta):
                    continue
                if self._ends_at(tid, t_cap):
                    # iz bu karede bitiyor → aracın kendi karesi; tespit yok = kaçırılmış tespit
                    vid = f"{fid}_trk_{tid}"
                    rec = self._vehicle_record(vid, fid, meta, t_cap, None, None, None, pos[0], pos[1], tid, 0.0,
                                               source="track_only")
                    rec["risk_reasons"].insert(0, "Karede izi var ama tespit yok — model bu aracı kaçırmış olabilir.")
                    st.vehicles[vid] = rec
                    fr["vehicle_ids"].append(vid)
                else:
                    # iz bu karenin alanından çekim anında sadece GEÇİYOR; aracın son konumu başka yerde.
                    # Araç kaydı açılmaz: asıl değerlendirme izin bittiği yerde yapılır (kendi karesi
                    # ya da kare dışı). Burada bağlam olarak tutulur.
                    fr["passing_tracks"].append({"track_id": tid, "lat": round(pos[0], 6), "lon": round(pos[1], 6),
                                                 "track_end": min_to_hhmm(self.ds.tracks[tid].t_end)})
            st.frames[fid] = fr

        # 4) kare dışı izler: izin BİTTİĞİ andaki durumu hiçbir karede değerlendirilmemiş her iz.
        #    Değişmez: her iz, son konumunda tam bir kez değerlendirilir (kendi karesinde ya da burada).
        #    Erken bir karede görünmüş (geçen/eşleşen) iz de son durumuyla burada değerlendirilir.
        evaluated_at_end = {v["track_id"] for v in st.vehicles.values()
                            if v["track_id"] and self._ends_at(v["track_id"], v["capture_min"])}
        seen_in: dict[str, set[str]] = {}
        for v in st.vehicles.values():
            if v["track_id"]:
                seen_in.setdefault(v["track_id"], set()).add(v["frame_id"])
        for fr in st.frames.values():
            for p in fr["passing_tracks"]:
                seen_in.setdefault(p["track_id"], set()).add(fr["frame_id"])
        for tid, tr in self.ds.tracks.items():
            if tid in evaluated_at_end:
                continue
            st.offframe_track_ids.append(tid)
            f = compute_features(tr, self.ds, self.th, tr.t_end)
            scen, risk, reasons = classify_tracked(f, self.th)
            last = tr.points[-1]
            st.offframe_risk[tid] = {"track_id": tid, "scenario": scen, "risk_level": risk, "risk_reasons": reasons,
                                     "last_time": min_to_hhmm(last.t), "lat": last.lat, "lon": last.lon,
                                     "zone": self.ds.zone_of(last.lat, last.lon), "features": f.to_dict(),
                                     "seen_in_frames": sorted(seen_in.get(tid, ())),   # boş = hiçbir karede görünmedi
                                     "friendly_confirmed_by": []}

        # 5) rapor doğrulama
        verifier = ReportVerifier(self.ds, st, self.th)
        verdicts = [verifier.verify(r) for r in self.ds.reports]
        for v in verdicts:
            # sadece doğrulanmış (destekler) resmi dost teyidi riski düşürür; kismen_uyumlu düşürmez
            if v.report_type == "DOST_TEYITLI" and v.verdict == "destekler":
                self._apply_friendly(st, v)
            if v.matched_vehicle_id:
                st.vehicles[v.matched_vehicle_id]["report_ids"].append(v.report_id)
        st.reports = [v.to_dict() for v in verdicts]

        # 5b) erken karedeki anlık görüntüye izin son durumunu iliştir (ajan/UI bağlamı için)
        final_state = {tid: {"where": "kare_disi", "risk_level": r["risk_level"], "scenario": r["scenario"],
                             "time": r["last_time"]} for tid, r in st.offframe_risk.items()}
        for v in st.vehicles.values():
            if v["track_id"] and self._ends_at(v["track_id"], v["capture_min"]):
                final_state[v["track_id"]] = {"where": v["frame_id"], "risk_level": v["risk_level"],
                                              "scenario": v["scenario"], "time": v["capture_time"]}
        for v in st.vehicles.values():
            if v["track_id"] and not self._ends_at(v["track_id"], v["capture_min"]):
                v["track_final_state"] = final_state.get(v["track_id"])
        for fr in st.frames.values():
            for p in fr["passing_tracks"]:
                p["final_state"] = final_state.get(p["track_id"])

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
    def _ends_at(self, tid: str, t_cap: int) -> bool:
        """İz bu çekim anında mı bitiyor? (veri: kare araçlarının izi çekim anında biter)"""
        return abs(self.ds.tracks[tid].t_end - t_cap) <= self.th.track_end_tol_min

    def _position_for_match(self, tr, t_cap: int) -> tuple[float, float] | None:
        """İz penceresi içindeyse interpolasyon. Çekim anı izin son noktasından en fazla
        track_end_tol_min sonra ise (ızgara dışı çekim saati) son hızla kısa ekstrapolasyon."""
        pos = tr.position_at(t_cap)
        if pos is not None or not (0 < t_cap - tr.t_end <= self.th.track_end_tol_min):
            return pos
        if len(tr.points) < 2:
            return tr.points[-1].lat, tr.points[-1].lon
        a, b = tr.points[-2], tr.points[-1]
        r = (t_cap - b.t) / max(b.t - a.t, 1)
        return b.lat + r * (b.lat - a.lat), b.lon + r * (b.lon - a.lon)

    def _apply_friendly(self, st: WorldState, v) -> None:
        """Doğrulanmış resmi dost teyidi: aynı izin TÜM kayıtlarına ve kare dışı kaydına uygulanır."""
        reason = f"Resmi dost teyidi ({v.report_id}, {v.time}) — risk DUSUK'e indirildi."
        tid = v.matched_track_id
        for veh in st.vehicles.values():
            if veh["vehicle_id"] == v.matched_vehicle_id or (tid and veh["track_id"] == tid):
                veh["risk_level"] = "DUSUK"
                veh["friendly_confirmed_by"].append(v.report_id)
                veh["risk_reasons"].append(reason)
        if tid in st.offframe_risk:
            off = st.offframe_risk[tid]
            off["risk_level"] = "DUSUK"
            off["friendly_confirmed_by"].append(v.report_id)
            off["risk_reasons"].append(reason)

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
        else:
            scen, risk, reasons = classify_untracked(label or "unknown", dist, self.th)
        rec.update(scenario=scen, risk_level=risk, risk_reasons=reasons)
        return rec


def build_state() -> tuple[Analyzer, WorldState]:
    an = Analyzer()
    return an, an.run()
