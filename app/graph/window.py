"""Clip observed trajectories to a same-day interval without extrapolating."""
from __future__ import annotations

from ..data import Track, TrackPoint


def clip_tracks(tracks: dict[str, Track], start: int | None, end: int | None) -> dict[str, Track]:
    if start is not None and end is not None and start > end:
        raise ValueError("Başlangıç zamanı bitiş zamanından sonra olamaz.")
    clipped = {}
    for tid, track in sorted(tracks.items()):
        if not track.points:
            continue
        lo = max(start if start is not None else track.t_start, track.t_start)
        hi = min(end if end is not None else track.t_end, track.t_end)
        if lo > hi:
            continue
        times = sorted({lo, hi, *(p.t for p in track.points if lo <= p.t <= hi)})
        points = []
        for t in times:
            position = track.position_at(t)
            if position is not None:
                points.append(TrackPoint(t, *position))
        if points:
            clipped[tid] = Track(tid, points)
    return clipped
