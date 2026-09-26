"""Empirical Bayes shrinkage and volume-based reliability, described in the graph documentation."""
from __future__ import annotations

from .config import SmoothingConfig, default_graph_config


def compute_smoothed_threat_rate(threat_count: int, total_count: int, global_threat_rate: float,
                                cfg: SmoothingConfig | None = None) -> float:
    config = cfg or default_graph_config.smoothing
    if total_count <= 0:
        return global_threat_rate
    c = config.bayesian_pseudo_count
    return (threat_count + c * global_threat_rate) / (total_count + c)


def compute_sample_confidence(unique_vehicle_count: int, cfg: SmoothingConfig | None = None) -> float:
    config = cfg or default_graph_config.smoothing
    if unique_vehicle_count <= 0:
        return 0.0
    ratio = min(1.0, unique_vehicle_count / config.min_observation_threshold)
    return config.min_confidence_floor + (1 - config.min_confidence_floor) * ratio


def compute_threat_lift(local_rate: float, global_rate: float) -> float:
    return local_rate / global_rate if global_rate > 0 else 0.0
