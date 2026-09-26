"""Insert observed segment crossings using Shapely's STRtree spatial index."""
from __future__ import annotations

from collections import defaultdict

from shapely.geometry import LineString
from shapely.strtree import STRtree

from ..data import Track
from .geometry import LocalProjection


def _crossing_points(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Point":
        return [geometry]
    if geometry.geom_type == "LineString":
        from shapely.geometry import Point
        return [Point(geometry.coords[0]), Point(geometry.coords[-1])]
    return [point for part in geometry.geoms for point in _crossing_points(part)]


def observed_paths(tracks: dict[str, Track], projection: LocalProjection) -> dict[str, list[tuple[float, float]]]:
    paths = {tid: [projection.project(p.lat, p.lon) for p in tr.points]
             for tid, tr in sorted(tracks.items())}
    segments = []
    owners = []
    cuts = defaultdict(list)
    for tid, points in paths.items():
        for index, (a, b) in enumerate(zip(points, points[1:])):
            if a != b:
                segments.append(LineString([a, b]))
                owners.append((tid, index))
    if segments:
        tree = STRtree(segments)
        for index, segment in enumerate(segments):
            for other_index in tree.query(segment, predicate="intersects"):
                other_index = int(other_index)
                if other_index <= index or owners[index][0] == owners[other_index][0]:
                    continue
                for point in _crossing_points(segment.intersection(segments[other_index])):
                    coord = (point.x, point.y)
                    cuts[owners[index]].append((segment.project(point), coord))
                    cuts[owners[other_index]].append((segments[other_index].project(point), coord))
    augmented = {}
    for tid, points in paths.items():
        sequence = []
        for index, point in enumerate(points):
            sequence.append(point)
            sequence.extend(coord for _, coord in sorted(cuts.get((tid, index), ())))
        augmented[tid] = [(round(x, 8), round(y, 8)) for x, y in sequence]
    return augmented
