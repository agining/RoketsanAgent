"""Build shared spatial regions and directed graphs from game entity trajectories."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

import networkx as nx

from ..data import Track
from .config import SpatialGraphConfig, default_graph_config
from .geometry import LocalProjection, RadiusIndex
from .models import SpatialEdge, SpatialNode
from .paths import observed_paths


@dataclass
class TrajectoryGraphBundle:
    g_all: nx.DiGraph
    g_normal: nx.DiGraph
    g_threat: nx.DiGraph
    nodes: dict[str, SpatialNode]
    edges: list[SpatialEdge]
    point_to_node: dict[tuple[float, float], str]
    track_node_sequences: dict[str, list[str]]
    track_classification: dict[str, bool]
    node_tracks: dict[str, set[str]]
    node_threat_tracks: dict[str, set[str]]
    node_normal_tracks: dict[str, set[str]]


class SpatialGraphBuilder:
    def __init__(self, config: SpatialGraphConfig | None = None):
        self.cfg = config or default_graph_config.spatial

    def build(self, tracks: dict[str, Track], track_classification: dict[str, bool]) -> TrajectoryGraphBundle:
        tracks = {tid: tr for tid, tr in sorted(tracks.items()) if tr.points and tid in track_classification}
        classification = {tid: track_classification[tid] for tid in tracks}
        projection = LocalProjection.from_coordinates((p.lat, p.lon) for tr in tracks.values() for p in tr.points)
        paths = observed_paths(tracks, projection)
        index = RadiusIndex(self.cfg.cluster_radius_m)
        assignments = {}
        cluster_points = defaultdict(list)
        # Sorting unique coordinates makes snapping independent of the input track order.
        for x, y in sorted({point for path in paths.values() for point in path}):
            nearby = index.nearby(x, y)
            nid = nearby[0][1] if nearby else f"N_{len(index.points) + 1:05d}"
            if not nearby:
                index.add(nid, x, y)
            assignments[(x, y)] = nid
            cluster_points[nid].append((x, y))
        members = defaultdict(set)
        endpoint_nodes = set()
        for tid, path in paths.items():
            for point in path:
                members[assignments[point]].add(tid)
            endpoint_nodes.update(assignments[p] for p in (path[0], path[-1]))
        # Interior samples used by only one entity are geometry, not meaningful junctions.
        retained = endpoint_nodes | {nid for nid, tids in members.items() if len(tids) > 1}
        all_assignments = assignments
        assignments = {point: nid for point, nid in assignments.items() if nid in retained}
        nodes = {}
        for nid, points in cluster_points.items():
            if nid not in retained:
                continue
            lat, lon = projection.unproject(sum(p[0] for p in points) / len(points),
                                            sum(p[1] for p in points) / len(points))
            nodes[nid] = SpatialNode(nid, lat, lon)
        g_all, g_normal, g_threat = nx.DiGraph(), nx.DiGraph(), nx.DiGraph()
        g_all.add_nodes_from((nid, {"lat": node.lat, "lon": node.lon}) for nid, node in nodes.items())
        node_tracks, threat_tracks, normal_tracks = defaultdict(set), defaultdict(set), defaultdict(set)
        edge_tracks = defaultdict(set)
        sequences = {}
        for tid, path in paths.items():
            is_threat = classification[tid]
            subgraph = g_threat if is_threat else g_normal
            sequence = []
            previous_cluster = None
            for coord in path:
                nid = all_assignments[coord]
                if nid not in nodes:
                    previous_cluster = nid
                    continue
                nodes[nid].point_count += 1
                if nid != previous_cluster or not self.cfg.filter_self_loops:
                    sequence.append(nid)
                previous_cluster = nid
            sequences[tid] = sequence
            for nid, passages in Counter(sequence).items():
                nodes[nid].passage_count += passages
                node_tracks[nid].add(tid)
                (threat_tracks if is_threat else normal_tracks)[nid].add(tid)
                subgraph.add_node(nid, lat=nodes[nid].lat, lon=nodes[nid].lon)
            for source, target in zip(sequence, sequence[1:]):
                if source == target and self.cfg.filter_self_loops:
                    continue
                edge_tracks[(source, target)].add(tid)
                for graph in (g_all, subgraph):
                    weight = graph.get_edge_data(source, target, {}).get("weight", 0) + 1
                    graph.add_edge(source, target, weight=weight)
        for nid, node in nodes.items():
            node.total_vehicle_count = node.unique_vehicle_count = len(node_tracks[nid])
            node.threat_vehicle_count = node.unique_threat_trajectories = len(threat_tracks[nid])
            node.normal_vehicle_count = node.unique_normal_trajectories = len(normal_tracks[nid])
            node.incoming_edge_count = g_all.in_degree(nid)
            node.outgoing_edge_count = g_all.out_degree(nid)
        edges = [SpatialEdge(source, target, data["weight"],
                             g_threat.get_edge_data(source, target, {}).get("weight", 0),
                             g_normal.get_edge_data(source, target, {}).get("weight", 0),
                             sorted(edge_tracks[(source, target)]))
                 for source, target, data in sorted(g_all.edges(data=True))]
        return TrajectoryGraphBundle(g_all, g_normal, g_threat, nodes, edges,
                                     {projection.unproject(*p): nid for p, nid in assignments.items()},
                                     sequences, classification, dict(node_tracks), dict(threat_tracks), dict(normal_tracks))
