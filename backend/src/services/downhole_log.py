"""Absolute-depth helpers for drillhole traces and downhole logs.

Every 3D position in this application is derived from an **absolute downhole
distance measured from the collar (0.0 m) along the full desurveyed
trajectory** -- never from a relative offset or a cumulative index over the
intervals that happen to exist. That distinction matters when a hole has an
unsampled zone at the top: AADD004's first assay is 37.0 m - 38.0 m, and it
must render 37 m down the trace, not at the collar.

Two things are needed to make that hold:

* The trace must span the whole hole. Survey stations often stop short of the
  deepest logged interval (or the hole's stated total length), and
  ``interpolate_trace_position`` clamps to the trace's last point -- so every
  interval past the last station would pile up at the same coordinate.
  ``extend_trace_to_depth`` continues the trace along the final station's
  orientation so the full 0 .. Total_Length range is addressable.

* The log must be continuous. ``find_unsampled_gaps`` returns the depth ranges
  with no interval covering them, so the inspector can show an unbroken
  0.0 m -> Total_Length record with explicit "No Sample" rows.
"""
import math
from typing import Dict, List, Optional, Sequence, Tuple

# Depth comparisons are in metres; anything under this is the same depth.
DEPTH_TOLERANCE = 1e-6


def interpolate_trace_position(trace: List[Dict[str, float]], depth: float) -> List[float]:
    """3D position at an absolute downhole ``depth`` along a desurveyed trace.

    ``depth`` is measured from the collar (0.0), NOT from the first sampled
    interval. Clamps to the trace endpoints outside its range -- callers that
    need the full hole addressable should pass a trace already run through
    ``extend_trace_to_depth``.
    """
    if not trace:
        return [0.0, 0.0, 0.0]

    if depth <= trace[0]['depth']:
        return [trace[0]['x'], trace[0]['y'], trace[0]['z']]

    if depth >= trace[-1]['depth']:
        return [trace[-1]['x'], trace[-1]['y'], trace[-1]['z']]

    for i in range(1, len(trace)):
        p1 = trace[i - 1]
        p2 = trace[i]
        if p1['depth'] <= depth <= p2['depth']:
            d1, d2 = p1['depth'], p2['depth']
            if abs(d2 - d1) < 1e-9:
                return [p1['x'], p1['y'], p1['z']]
            t = (depth - d1) / (d2 - d1)
            return [
                p1['x'] + t * (p2['x'] - p1['x']),
                p1['y'] + t * (p2['y'] - p1['y']),
                p1['z'] + t * (p2['z'] - p1['z']),
            ]

    return [trace[-1]['x'], trace[-1]['y'], trace[-1]['z']]


def extend_trace_to_depth(
    trace: List[Dict[str, float]],
    total_depth: float,
) -> List[Dict[str, float]]:
    """Continue ``trace`` to ``total_depth`` along its final orientation.

    Returns the trace unchanged when it already reaches ``total_depth``. The
    appended station keeps the last station's dip/azimuth -- the standard
    assumption for the un-surveyed tail of a hole.
    """
    if not trace:
        return trace
    last = trace[-1]
    if total_depth - last['depth'] <= DEPTH_TOLERANCE:
        return trace

    delta = total_depth - last['depth']
    incl = math.radians(last.get('dip', -90.0))
    azi = math.radians(last.get('azimuth', 0.0))

    # Same convention as compute_minimum_curvature_trace: dip is measured from
    # horizontal (negative = downward), azimuth is clockwise from North.
    dx = math.cos(incl) * math.sin(azi)
    dy = math.cos(incl) * math.cos(azi)
    dz = math.sin(incl)

    return trace + [{
        'depth': total_depth,
        'x': last['x'] + delta * dx,
        'y': last['y'] + delta * dy,
        'z': last['z'] + delta * dz,
        'dip': last.get('dip', -90.0),
        'azimuth': last.get('azimuth', 0.0),
    }]


def compute_total_depth(
    trace: Sequence[Dict[str, float]],
    interval_depths: Sequence[float] = (),
    declared_total: Optional[float] = None,
) -> float:
    """End-of-hole depth: the deepest of surveys, logged intervals, and any
    declared Total_Length.

    Using the max means a hole whose assays run past its last survey station
    still gets a trace long enough to place them.
    """
    candidates = [0.0]
    if trace:
        candidates.append(float(trace[-1]['depth']))
    candidates.extend(float(d) for d in interval_depths if d is not None)
    if declared_total is not None:
        candidates.append(float(declared_total))
    return max(candidates)


def find_unsampled_gaps(
    intervals: Sequence[Tuple[float, float]],
    total_depth: float,
) -> List[Tuple[float, float]]:
    """Depth ranges in ``0 .. total_depth`` not covered by any interval.

    Overlapping and out-of-order intervals are handled by sweeping a coverage
    cursor, so the result is always a disjoint, ascending list. An empty
    interval list yields the single gap ``(0.0, total_depth)``.
    """
    spans = sorted(
        (float(f), float(t)) for f, t in intervals
        if f is not None and t is not None and float(t) > float(f)
    )

    gaps: List[Tuple[float, float]] = []
    cursor = 0.0
    for start, end in spans:
        if start - cursor > DEPTH_TOLERANCE:
            gaps.append((cursor, start))
        cursor = max(cursor, end)

    if total_depth - cursor > DEPTH_TOLERANCE:
        gaps.append((cursor, total_depth))

    return gaps
