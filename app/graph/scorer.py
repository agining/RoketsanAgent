"""Deterministic scores for game regions; independent movement and report evidence."""
from __future__ import annotations

from .config import GraphAnalysisConfig, default_graph_config
from .models import SpatialNode
from .recommendations import describe_node
from .smoothing import compute_threat_lift


def _unit(value: float) -> float:
    return max(0.0, min(1.0, value))


class ExplainableScorer:
    def __init__(self, config: GraphAnalysisConfig | None = None):
        self.cfg = config or default_graph_config

    def score_all(self, nodes: list[SpatialNode]) -> None:
        for node in nodes:
            w, scales = self.cfg.weights, self.cfg.metrics
            smoothed_lift = compute_threat_lift(node.smoothed_threat_rate, node.global_threat_rate)
            lift = _unit((smoothed_lift - 1) / (scales.lift_saturation - 1))
            gap = _unit(node.threat_normal_centrality_gap / scales.centrality_gap_saturation)
            components = {
                "lift": (smoothed_lift, lift, w.lift_weight),
                "ratio": (node.smoothed_threat_rate, node.smoothed_threat_rate, w.smoothed_ratio_weight),
                "centrality_gap": (node.threat_normal_centrality_gap, gap, w.centrality_gap_weight),
                "trajectory_importance": (node.threat_trajectory_importance, node.threat_trajectory_importance, w.trajectory_importance_weight),
                "graph_centrality": (node.threat_graph_centrality, node.threat_graph_centrality, w.graph_centrality_weight),
                "intelligence": (node.related_intelligence_count, node.intelligence_confidence, w.intelligence_weight),
            }
            # Uniform class proportions / zero positive structural gap are not an anomaly.
            comparable_classes = 0 < node.global_threat_rate < 1
            anomaly_evidence = max(lift, gap) if node.threat_vehicle_count and comparable_classes else 0.0
            multiplier = anomaly_evidence
            breakdown = {
                name: {"raw": raw, "normalized": _unit(normalized), "weight": weight,
                       "contribution": _unit(normalized) * weight * multiplier}
                for name, (raw, normalized, weight) in components.items()
            }
            node.intelligence_contribution = breakdown["intelligence"]["contribution"]
            node.graph_interest_score = sum(item["contribution"] for name, item in breakdown.items() if name != "intelligence")
            node.interest_score = _unit(node.graph_interest_score + node.intelligence_contribution)
            node.score_breakdown = {"components": breakdown, "observation_confidence": node.sample_confidence,
                                    "anomaly_evidence": anomaly_evidence, "multiplier": multiplier,
                                    "smoothed_lift": smoothed_lift,
                                    "effective_pseudo_count": node.effective_pseudo_count}
            describe_node(node, self.cfg.region)

    def score_node(self, node: SpatialNode) -> None:
        self.score_all([node])
