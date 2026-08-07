"""Length-weighted compositing of assay intervals.

Assay samples arrive at whatever length the geologist cut them: a 0.3 m vein
sample sits next to a 2.0 m bulk sample. Any statistic taken over raw intervals
gives those two samples equal weight, which silently over-weights the short
ones -- and short samples are cut short precisely because someone saw
mineralisation, so the bias runs high, every time. Compositing rebuilds the
samples into equal-length units so each one represents the same volume of rock.

Everything downstream in the grade-shell feature consumes composites. Nothing
consumes raw intervals.

Three rules here are geological decisions rather than implementation details,
and each one is load-bearing:

* **A NULL grade is not a zero.** ``AssayInterval.grade_value`` is nullable and
  means "logged, never assayed". Ground that was never assayed contributes
  neither grade nor length: it is unknown, not barren. Averaging it in as 0.0
  dilutes every composite that touches unassayed ground, and the resulting
  shells shrink in exactly the places where sampling was thinnest. A genuine
  0.0 g/t result is a different thing entirely and is composited normally,
  which is why the test below is ``is None`` and never a falsiness check.

* **Compositing never crosses a gap.** Two intervals 9 m apart are two runs of
  sampled ground with unsampled rock between them, not one continuous sample.
  A composite spanning the gap would invent a grade for rock nobody looked at.
  Each run restarts its own composite grid at its own start depth, so composite
  boundaries are not aligned to a global grid across a hole.

* **Residual ground is never discarded.** The last partial composite in a run
  is merged into its predecessor when it is shorter than half a composite, and
  emitted on its own when it is longer. It is never dropped. That trailing
  0.4 m may be the vein.

``assayed_length`` is reported separately from ``length`` so callers can see
when a composite spans ground that was only partly assayed. It is recorded
honestly and never clamped up to ``length``; downstream code decides what to do
about it.

Depths are metres along the hole for drillholes, and metres of chainage along
the trench floor for trenches (see the trench rules in
``specs/006-combined-csv-import/tasks.md``). This module does not care which --
it works in one-dimensional depth space and knows nothing about 3D geometry.
"""
from dataclasses import dataclass
from typing import List, Optional

# Depth arithmetic tolerance. Depths come from CSV text and carry the usual
# float representation error, so exact comparisons on boundaries are unsafe.
_EPS = 1e-9

# Default maximum depth discontinuity that still counts as continuous ground.
# Anything larger opens a new compositing run.
DEFAULT_GAP_TOLERANCE = 0.01

DEFAULT_COMPOSITE_LENGTH = 1.0

# A trailing partial composite at or above this fraction of the composite
# length stands on its own; below it, it is merged into its predecessor.
_RESIDUAL_MERGE_FRACTION = 0.5


@dataclass(frozen=True)
class RawInterval:
    """One assay interval as stored, before compositing.

    ``grade`` of ``None`` means logged but never assayed -- distinct from a
    genuine 0.0 g/t result.
    """

    from_depth: float
    to_depth: float
    grade: Optional[float]
    sample_id: Optional[str] = None


@dataclass(frozen=True)
class Composite:
    """One fixed-length composite.

    ``grade`` is never ``None``: a window with no assayed ground is not emitted
    at all. ``assayed_length`` is the part of ``length`` actually backed by
    assayed intervals, and may be less than ``length`` when the composite spans
    unassayed ground.
    """

    from_depth: float
    to_depth: float
    grade: float
    length: float
    assayed_length: float
    n_source_intervals: int


def _validate(intervals: List[RawInterval]) -> List[RawInterval]:
    """Sort by depth and reject inverted or overlapping intervals.

    Overlaps are an error rather than something to resolve here. Picking a
    winner would be a data-quality decision made silently, in the wrong layer,
    on the geologist's behalf.
    """
    for iv in intervals:
        if iv.from_depth >= iv.to_depth:
            raise ValueError(
                f"Interval has from_depth >= to_depth: "
                f"{iv.from_depth} -> {iv.to_depth}"
                + (f" (sample {iv.sample_id})" if iv.sample_id else "")
            )

    ordered = sorted(intervals, key=lambda iv: (iv.from_depth, iv.to_depth))

    for previous, current in zip(ordered, ordered[1:]):
        if current.from_depth < previous.to_depth - _EPS:
            raise ValueError(
                f"Overlapping intervals: "
                f"{previous.from_depth}-{previous.to_depth} overlaps "
                f"{current.from_depth}-{current.to_depth}"
            )

    return ordered


def _split_runs(
    intervals: List[RawInterval],
    gap_tolerance: float,
) -> List[List[RawInterval]]:
    """Group depth-ordered intervals into runs of continuous ground.

    Unassayed (NULL-grade) intervals still count as continuous ground: they
    were logged, so the rock was there and was looked at. They break no run.
    What breaks a run is a depth discontinuity -- ground that is absent from the
    interval table altogether.
    """
    if not intervals:
        return []

    runs: List[List[RawInterval]] = [[intervals[0]]]
    for previous, current in zip(intervals, intervals[1:]):
        if current.from_depth - previous.to_depth > gap_tolerance:
            runs.append([current])
        else:
            runs[-1].append(current)

    return runs


def _window_bounds(
    run_start: float,
    run_end: float,
    composite_length: float,
) -> List[tuple]:
    """Lay composite windows over one run, applying the residual rule.

    Returns ``[(from_depth, to_depth), ...]`` covering the run exactly, with no
    gaps and no overlap, so that no sampled ground is lost.
    """
    total = run_end - run_start
    n_full = int(total / composite_length + _EPS)
    residual = total - n_full * composite_length

    if n_full == 0:
        # A run shorter than a single composite still gets one composite. It is
        # real sampled ground and discarding it would lose a narrow high-grade
        # intersection -- the most valuable thing in the dataset.
        return [(run_start, run_end)]

    bounds = [
        (
            run_start + i * composite_length,
            run_start + (i + 1) * composite_length,
        )
        for i in range(n_full)
    ]

    if residual > _EPS:
        if residual >= _RESIDUAL_MERGE_FRACTION * composite_length:
            bounds.append((bounds[-1][1], run_end))
        else:
            # Absorb the short tail into the last full composite, which becomes
            # slightly longer than composite_length.
            bounds[-1] = (bounds[-1][0], run_end)
    else:
        # Clean division: snap the final boundary to the run end so float drift
        # does not leave a sliver of ground uncovered.
        bounds[-1] = (bounds[-1][0], run_end)

    return bounds


def _composite_window(
    window_from: float,
    window_to: float,
    intervals: List[RawInterval],
) -> Optional[Composite]:
    """Length-weight the assayed intervals overlapping one window.

    Returns ``None`` when the window contains no assayed ground at all, which
    is how unassayed windows are dropped rather than emitted as zeros.
    """
    weighted_sum = 0.0
    assayed_length = 0.0
    n_sources = 0

    for iv in intervals:
        overlap = min(window_to, iv.to_depth) - max(window_from, iv.from_depth)
        if overlap <= _EPS:
            continue

        # An unassayed interval contributes neither grade nor length. Its
        # overlap is deliberately not added to assayed_length -- that shortfall
        # is the signal that this composite spans unassayed ground.
        if iv.grade is None:
            continue

        weighted_sum += float(iv.grade) * overlap
        assayed_length += overlap
        n_sources += 1

    if assayed_length <= _EPS:
        return None

    return Composite(
        from_depth=window_from,
        to_depth=window_to,
        grade=weighted_sum / assayed_length,
        length=window_to - window_from,
        assayed_length=assayed_length,
        n_source_intervals=n_sources,
    )


def composite_intervals(
    intervals: List[RawInterval],
    composite_length: float = DEFAULT_COMPOSITE_LENGTH,
    gap_tolerance: float = DEFAULT_GAP_TOLERANCE,
) -> List[Composite]:
    """Composite one hole's or one trench line's intervals to a fixed length.

    Each composite's grade is the length-weighted mean of the assayed intervals
    overlapping it. Intervals with ``grade is None`` are excluded entirely, runs
    are broken at depth gaps larger than ``gap_tolerance``, and trailing
    residual ground is merged or emitted per the module docstring.

    Raises ``ValueError`` for inverted or overlapping input intervals.
    """
    if composite_length <= 0:
        raise ValueError(f"composite_length must be positive, got {composite_length}")
    if gap_tolerance < 0:
        raise ValueError(f"gap_tolerance must not be negative, got {gap_tolerance}")

    ordered = _validate(list(intervals))
    if not ordered:
        return []

    composites: List[Composite] = []
    for run in _split_runs(ordered, gap_tolerance):
        run_start = run[0].from_depth
        run_end = run[-1].to_depth

        for window_from, window_to in _window_bounds(
            run_start, run_end, composite_length
        ):
            composite = _composite_window(window_from, window_to, run)
            if composite is not None:
                composites.append(composite)

    return composites
