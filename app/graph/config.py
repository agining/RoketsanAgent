"""Validated configuration for retrospective game-trajectory analysis."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
import math


def _positive(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")


@dataclass(frozen=True)
class SpatialGraphConfig:
    cluster_radius_m: float = 65.0
    filter_self_loops: bool = True
    threat_risk_levels: tuple[str, ...] = ("YUKSEK", "KRITIK")

    def __post_init__(self):
        _positive(self.cluster_radius_m, "cluster_radius_m")


@dataclass(frozen=True)
class SmoothingConfig:
    adaptive: bool = True
    bayesian_pseudo_count: float = 20.0
    min_observation_threshold: int = 12
    min_confidence_floor: float = 0.0

    def __post_init__(self):
        _positive(self.bayesian_pseudo_count, "bayesian_pseudo_count")
        if self.min_observation_threshold < 1:
            raise ValueError("min_observation_threshold must be positive")
        if not 0 <= self.min_confidence_floor <= 1:
            raise ValueError("min_confidence_floor must be in [0, 1]")


@dataclass(frozen=True)
class ScoreWeightsConfig:
    lift_weight: float = 0.28
    smoothed_ratio_weight: float = 0.20
    centrality_gap_weight: float = 0.20
    trajectory_importance_weight: float = 0.14
    graph_centrality_weight: float = 0.10
    intelligence_weight: float = 0.08

    def __post_init__(self):
        values = [getattr(self, f.name) for f in fields(self)]
        if any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError("Score weights must be finite and nonnegative")
        if not math.isclose(sum(values), 1.0):
            raise ValueError("Score weights must sum to one")


@dataclass(frozen=True)
class MetricConfig:
    betweenness_sample_size: int = 256
    random_seed: int = 0
    betweenness_weight: float = 0.5
    lift_saturation: float = 6.0
    centrality_gap_saturation: float = 0.25

    def __post_init__(self):
        if self.betweenness_sample_size < 1:
            raise ValueError("betweenness_sample_size must be positive")
        if not 0 <= self.betweenness_weight <= 1:
            raise ValueError("betweenness_weight must be in [0, 1]")
        if not math.isfinite(self.lift_saturation) or self.lift_saturation <= 1:
            raise ValueError("lift_saturation must exceed one")
        _positive(self.centrality_gap_saturation, "centrality_gap_saturation")


@dataclass(frozen=True)
class RegionClusteringConfig:
    group_min_threat_tracks: int = 3
    group_high_threat_tracks: int = 4
    group_min_threat_ratio: float = 0.5
    merge_radius_m: float = 120.0
    min_interest_for_region: float = 0.35
    high_interest_threshold: float = 0.65
    medium_interest_threshold: float = 0.40
    critical_interest_threshold: float = 0.80

    def __post_init__(self):
        if not 2 <= self.group_min_threat_tracks <= self.group_high_threat_tracks:
            raise ValueError("Group thresholds require at least two distinct tracks and ordered counts")
        if not 0 < self.group_min_threat_ratio <= 1:
            raise ValueError("Group ratio must be in (0, 1]")
        _positive(self.merge_radius_m, "merge_radius_m")
        thresholds = (self.min_interest_for_region, self.medium_interest_threshold,
                      self.high_interest_threshold, self.critical_interest_threshold)
        if not 0 <= thresholds[0] <= thresholds[1] <= thresholds[2] <= thresholds[3] <= 1:
            raise ValueError("Region thresholds must be ordered in [0, 1]")


@dataclass(frozen=True)
class IntelligenceMatchingConfig:
    coord_match_radius_m: float = 150.0
    llm_timeout_seconds: int = 30

    def __post_init__(self):
        _positive(self.coord_match_radius_m, "coord_match_radius_m")
        _positive(self.llm_timeout_seconds, "llm_timeout_seconds")


@dataclass(frozen=True)
class GraphAnalysisConfig:
    spatial: SpatialGraphConfig = field(default_factory=SpatialGraphConfig)
    smoothing: SmoothingConfig = field(default_factory=SmoothingConfig)
    weights: ScoreWeightsConfig = field(default_factory=ScoreWeightsConfig)
    metrics: MetricConfig = field(default_factory=MetricConfig)
    region: RegionClusteringConfig = field(default_factory=RegionClusteringConfig)
    intelligence: IntelligenceMatchingConfig = field(default_factory=IntelligenceMatchingConfig)
    cache_entries: int = 8

    def __post_init__(self):
        if self.cache_entries < 1:
            raise ValueError("cache_entries must be positive")


default_graph_config = GraphAnalysisConfig()
