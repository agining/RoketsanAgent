"""Merge nearby game regions while counting each entity only once per region."""
from __future__ import annotations
import copy

from ..geo import haversine_m
from .builder import TrajectoryGraphBundle
from .config import RegionClusteringConfig, default_graph_config
from .geometry import LocalProjection, RadiusIndex
from .models import HighInterestRegion, SpatialNode


class RegionMerger:
    def __init__(self, config: RegionClusteringConfig | None = None):
        self.cfg = config or default_graph_config.region

    def merge_high_interest_nodes(self, nodes: list[SpatialNode], global_threat_rate: float,
                                  bundle: TrajectoryGraphBundle) -> list[HighInterestRegion]:
        if not nodes:
            return []
        projection = LocalProjection.from_coordinates((n.lat, n.lon) for n in nodes)
        index = RadiusIndex(self.cfg.merge_radius_m)
        by_id = {node.node_id: node for node in nodes}
        for node in nodes:
            index.add(node.node_id, *projection.project(node.lat, node.lon))
        # Partition spatial regions before applying group rules to unique regional tracks.
        ordered = sorted(nodes, key=lambda n: (-n.interest_score, n.node_id))
        visited = set()
        regions = []
        for seed in ordered:
            if seed.node_id in visited:
                continue
            member_ids = [nid for _, nid in index.nearby(*projection.project(seed.lat, seed.lon)) if nid not in visited]
            visited.update(member_ids)
            members = [by_id[nid] for nid in member_ids]
            all_tracks = set().union(*(bundle.node_tracks.get(nid, set()) for nid in member_ids))
            threat_tracks = set().union(*(bundle.node_threat_tracks.get(nid, set()) for nid in member_ids))
            normal_tracks = set().union(*(bundle.node_normal_tracks.get(nid, set()) for nid in member_ids))
            related_ids = sorted({rid for node in members for rid in node.related_intelligence_ids})
            # Keep representative-node score and breakdown together; region counts use unions.
            radius = max(self.cfg.merge_radius_m,
                         max(haversine_m(seed.lat, seed.lon, node.lat, node.lon) for node in members))
            local_rate = len(threat_tracks) / len(all_tracks) if all_tracks else 0.0
            region = HighInterestRegion(
                region_id=f"REG_{seed.node_id}", lat=seed.lat, lon=seed.lon, radius_m=radius,
                interest_score=seed.interest_score, severity=seed.severity,
                total_vehicle_count=len(all_tracks), threat_vehicle_count=len(threat_tracks),
                normal_vehicle_count=len(normal_tracks), global_threat_rate=global_threat_rate,
                local_threat_rate=local_rate, threat_lift=local_rate / global_threat_rate if global_threat_rate else 0.0,
                threat_normal_centrality_gap=seed.threat_normal_centrality_gap,
                unique_threat_trajectories=len(threat_tracks), related_intelligence_count=len(related_ids),
                confidence=seed.sample_confidence, recommendation=seed.recommendation,
                explanation=list(seed.explanations), related_intelligence_ids=related_ids,
                member_node_ids=sorted(member_ids), score_breakdown=copy.deepcopy(seed.score_breakdown),
                graph_interest_score=seed.graph_interest_score, intelligence_contribution=seed.intelligence_contribution,
                representative_node_id=seed.node_id,
            )
            self._apply_group_score(region)
            regions.append(region)
        return sorted(regions, key=lambda r: (-r.interest_score, r.region_id))

    def _apply_group_score(self, region: HighInterestRegion) -> None:
        """Game priority rule: several distinct threat tracks, not repeat observations."""
        count = region.threat_vehicle_count
        ratio = region.local_threat_rate
        grouped = count >= self.cfg.group_min_threat_tracks and ratio >= self.cfg.group_min_threat_ratio
        target = 0.0
        if grouped:
            target = (self.cfg.high_interest_threshold if count >= self.cfg.group_high_threat_tracks
                      else self.cfg.medium_interest_threshold)
        old_score = region.interest_score
        score = max(old_score, target)
        # A single threat entity must not become a high-priority group, even with large raw lift.
        if count < self.cfg.group_min_threat_tracks:
            score = min(score, max(0.0, self.cfg.medium_interest_threshold - 0.001))
        if score < old_score:
            factor = score / old_score if old_score else 0.0
            for component in region.score_breakdown.get("components", {}).values():
                component["contribution"] *= factor
            region.graph_interest_score *= factor
            region.intelligence_contribution *= factor
        boost = max(0.0, score - old_score)
        region.score_breakdown.setdefault("components", {})["group_concentration"] = {
            "raw": count, "normalized": target, "weight": 1.0, "contribution": boost,
        }
        region.score_breakdown["group_rule"] = {
            "matched": grouped, "distinct_threat_tracks": count, "local_threat_ratio": ratio,
            "minimum_tracks": self.cfg.group_min_threat_tracks,
            "high_tracks": self.cfg.group_high_threat_tracks,
            "minimum_ratio": self.cfg.group_min_threat_ratio,
            "base_score": old_score, "score_cap_applied": score < old_score,
        }
        region.graph_interest_score += boost
        region.interest_score = score
        if score >= self.cfg.critical_interest_threshold:
            region.severity = "KRITIK"
        elif score >= self.cfg.high_interest_threshold:
            region.severity = "YUKSEK"
        elif score >= self.cfg.medium_interest_threshold:
            region.severity = "ORTA"
        else:
            region.severity = "DUSUK"
        if grouped:
            reason = (f"Bu bölgede {count} farklı tehdit etiketli araç gözlendi; "
                      f"bölgedeki araçların %{ratio * 100:.0f}'ini oluşturuyor. Grup yoğunluğu kuralı uygulandı.")
            region.explanation.extend([reason, "Aynı bölgede bulunmak birlikte veya eşzamanlı hareket edildiğini tek başına göstermez."])
            region.recommendation = "Grup yoğunluğu: araç gerekçelerini ve geçiş zamanlarını birlikte incele."
        elif count < self.cfg.group_min_threat_tracks:
            region.explanation.append("Tekil araçlar grup yoğunluğu için yeterli sayılmadı.")
            region.recommendation = "Rutin gözlem; belirgin bir araç grubu saptanmadı."
