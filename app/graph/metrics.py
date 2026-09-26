"""Graph metrics on observed game paths; formulas and assumptions: docs/graph-analysis.md."""
from __future__ import annotations

import networkx as nx
from dataclasses import replace

from .builder import TrajectoryGraphBundle
from .config import GraphAnalysisConfig, default_graph_config
from .smoothing import compute_sample_confidence, compute_smoothed_threat_rate, compute_threat_lift


def _centralities(graph: nx.DiGraph, cfg):
    if len(graph) < 2:
        zeros = {node: 0.0 for node in graph}
        return zeros, zeros
    # Directed degree has at most 2*(n-1) neighbours; NetworkX total degree can exceed 1.
    degree = {node: (graph.in_degree(node) + graph.out_degree(node) - 2 * graph.has_edge(node, node)) / (2 * (len(graph) - 1))
              for node in graph}
    sample = min(len(graph), cfg.betweenness_sample_size)
    between = nx.betweenness_centrality(graph, k=sample if sample < len(graph) else None,
                                       normalized=True, seed=cfg.random_seed)
    return degree, between


def compute_all_metrics(bundle: TrajectoryGraphBundle, config: GraphAnalysisConfig | None = None) -> float:
    cfg = config or default_graph_config
    degree, between = _centralities(bundle.g_all, cfg.metrics)
    threat_degree, threat_between = _centralities(bundle.g_threat, cfg.metrics)
    normal_degree, normal_between = _centralities(bundle.g_normal, cfg.metrics)
    total = len(bundle.track_classification)
    threats = sum(bundle.track_classification.values())
    baseline = threats / total if total else 0.0
    bw = cfg.metrics.betweenness_weight
    mean_volume = sum(n.unique_vehicle_count for n in bundle.nodes.values()) / len(bundle.nodes) if bundle.nodes else 0.0
    smoothing = replace(cfg.smoothing, bayesian_pseudo_count=max(mean_volume, 1e-9)) if cfg.smoothing.adaptive else cfg.smoothing
    for nid, node in bundle.nodes.items():
        node.degree_centrality = degree.get(nid, 0.0)
        node.betweenness_centrality = between.get(nid, 0.0)
        denominator = max(1, len(bundle.g_all) - 1)
        self_loop = bundle.g_all.has_edge(nid, nid)
        node.in_degree_centrality = (node.incoming_edge_count - self_loop) / denominator
        node.out_degree_centrality = (node.outgoing_edge_count - self_loop) / denominator
        node.weighted_degree = float(bundle.g_all.degree(nid, weight="weight"))
        node.threat_graph_centrality = bw * threat_between.get(nid, 0.0) + (1 - bw) * threat_degree.get(nid, 0.0)
        node.normal_graph_centrality = bw * normal_between.get(nid, 0.0) + (1 - bw) * normal_degree.get(nid, 0.0)
        node.threat_normal_centrality_gap = node.threat_graph_centrality - node.normal_graph_centrality
        node.global_threat_rate = baseline
        node.raw_threat_ratio = node.threat_vehicle_count / node.total_vehicle_count if node.total_vehicle_count else 0.0
        node.smoothed_threat_rate = compute_smoothed_threat_rate(node.threat_vehicle_count, node.total_vehicle_count,
                                                               baseline, smoothing)
        # Raw lift is the observed P(class | region) / P(class), not the smoothed alternative.
        node.threat_lift = compute_threat_lift(node.raw_threat_ratio, baseline)
        node.threat_trajectory_importance = node.unique_threat_trajectories / threats if threats else 0.0
        node.sample_confidence = (node.unique_vehicle_count / (node.unique_vehicle_count + mean_volume)
                                  if cfg.smoothing.adaptive and node.unique_vehicle_count else
                                  compute_sample_confidence(node.unique_vehicle_count, cfg.smoothing))
        node.effective_pseudo_count = smoothing.bayesian_pseudo_count
    return baseline
