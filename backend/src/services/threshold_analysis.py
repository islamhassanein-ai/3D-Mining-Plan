"""Evidence for choosing a grade-domain threshold.

A threshold that defines an orebody has to be justified from the data. "0.3 g/t
because that is what we always use" does not survive review when the
log-probability plot shows the population break at 0.15.

Three lines of evidence, which is the point -- one of them alone is easy to read
into whatever answer you were expecting:

* **Log-probability.** Grades plotted against their cumulative probability on a
  probability scale. A single log-normal population plots as a straight line;
  an inflection marks where one population gives way to another, which is what a
  domain boundary is. This is the only one of the three that can suggest a
  threshold nobody thought to test.

* **Metal capture.** For each candidate threshold, what fraction of the contained
  metal survives and how much length it takes to hold it. A threshold that keeps
  90% of the metal in 40% of the ground is doing its job; one that keeps 60% is
  discarding the deposit.

* **Contact analysis.** Mean grade against signed distance from the boundary the
  threshold implies. A real domain steps at zero. A gradational one ramps, and a
  hard-boundary domain drawn through a ramp will over-smooth on one side and
  under-smooth on the other.

Nothing here selects a threshold or ranks the candidates. These functions return
numbers; the geologist reads them.

All three take composites from ``composite_points``, so the grades are already
length-weighted, repeat samples on one metre are already averaged, and the
sample types are already distinguished. Callers that want a threshold for one
population pass only that population.
"""
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence

from backend.src.services.sample_type_comparison import TypedComposite

_EPS = 1e-12

# Hazen plotting position. Other conventions exist -- i/n and (i-1)/n among
# them -- and the choice shifts the tails visibly on a probability axis. Hazen
# is the one these plots are conventionally read against, so it is what the
# curve means unless someone says otherwise.
_HAZEN_OFFSET = 0.5

DEFAULT_BIN_WIDTH = 5.0
DEFAULT_MAX_DISTANCE = 50.0


@dataclass(frozen=True)
class LogProbPoint:
    cumulative_probability: float
    grade: float


@dataclass(frozen=True)
class LogProbResult:
    """Points for a log-probability plot.

    ``n_excluded_non_positive`` counts grades at or below zero. They cannot be
    placed on a log axis and are reported rather than dropped quietly -- a
    barren tail is a fact about the deposit, and a plot that silently omits it
    overstates how mineralised the population is.
    """

    points: List[LogProbPoint]
    n_excluded_non_positive: int


@dataclass(frozen=True)
class CaptureRow:
    threshold: float
    n_above: int
    length_above: float
    metal_above: float
    length_fraction: Optional[float]
    metal_fraction: Optional[float]
    mean_grade_above: Optional[float]


@dataclass(frozen=True)
class ContactBin:
    distance_bin_center: float
    n: int
    mean_grade: Optional[float]
    length_weighted_mean_grade: Optional[float]


def log_probability_points(
    composites: Sequence[TypedComposite],
) -> LogProbResult:
    """Cumulative probability against grade, ascending, Hazen positions.

    Grades are returned on their natural scale; the log axis belongs to whatever
    draws the plot.
    """
    grades = sorted(c.grade for c in composites if c.grade > 0.0)
    n_excluded = len(composites) - len(grades)

    n = len(grades)
    points = [
        LogProbPoint(
            cumulative_probability=(i + 1 - _HAZEN_OFFSET) / n,
            grade=grade,
        )
        for i, grade in enumerate(grades)
    ]

    return LogProbResult(points=points, n_excluded_non_positive=n_excluded)


def metal_capture_curve(
    composites: Sequence[TypedComposite],
    thresholds: Sequence[float],
) -> List[CaptureRow]:
    """Length and metal retained at each candidate threshold.

    ``thresholds`` is required and carries no default: this function reports the
    shape of the curve and makes no recommendation about where to cut it.

    The comparison is ``grade >= threshold`` throughout -- count, length and
    metal alike. Mixing ``>`` and ``>=`` between them is the classic way to make
    a capture table that is wrong at exactly the round numbers a reviewer checks
    first.

    Denominators are over **all** composites, including those below every
    candidate: ground that fails the cut-off still occupies the deposit.
    """
    total_length = sum(c.length for c in composites)
    total_metal = sum(c.grade * c.length for c in composites)

    rows: List[CaptureRow] = []
    for threshold in thresholds:
        above = [c for c in composites if c.grade >= threshold]
        length_above = sum(c.length for c in above)
        metal_above = sum(c.grade * c.length for c in above)

        rows.append(CaptureRow(
            threshold=threshold,
            n_above=len(above),
            length_above=length_above,
            metal_above=metal_above,
            length_fraction=(
                length_above / total_length if total_length > _EPS else None
            ),
            metal_fraction=(
                metal_above / total_metal if total_metal > _EPS else None
            ),
            mean_grade_above=(
                metal_above / length_above if length_above > _EPS else None
            ),
        ))

    return rows


def _signed_distance_to_other_side(
    composite: TypedComposite,
    above: Sequence[TypedComposite],
    below: Sequence[TypedComposite],
    is_above: bool,
) -> Optional[float]:
    """Distance to the nearest composite on the other side of the threshold.

    Positive when the composite is itself above threshold, negative when below,
    so that the sign axis reads as "distance into the domain" against "distance
    out of it".
    """
    others = below if is_above else above
    if not others:
        return None

    nearest = min(
        math.dist((composite.x, composite.y, composite.z), (o.x, o.y, o.z))
        for o in others
    )
    return nearest if is_above else -nearest


def contact_analysis(
    composites: Sequence[TypedComposite],
    threshold: float,
    bin_width: float = DEFAULT_BIN_WIDTH,
    max_distance: float = DEFAULT_MAX_DISTANCE,
) -> List[ContactBin]:
    """Mean grade against signed distance from the implied domain boundary.

    A **sharp** contact shows a step at distance zero; a **gradational** one
    shows a ramp. This function does not classify which -- it returns the bins
    and the reader decides, because the difference between a step and a steep
    ramp is a judgement about the deposit, not a threshold on a number.

    Composites without coordinates are excluded. The search is brute force over
    pairs, which is ample at the few-thousand-composite scale this works at and
    keeps the definition of "nearest" obvious.
    """
    if bin_width <= 0:
        raise ValueError(f"bin_width must be positive, got {bin_width}")
    if max_distance <= 0:
        raise ValueError(f"max_distance must be positive, got {max_distance}")

    located = [c for c in composites if c.x is not None
               and c.y is not None and c.z is not None]
    above = [c for c in located if c.grade >= threshold]
    below = [c for c in located if c.grade < threshold]

    n_bins = int(math.ceil(max_distance / bin_width))
    # Bins run from -max_distance to +max_distance, none straddling zero, so
    # the step at the boundary is not smeared across a bin that contains both
    # sides of it.
    edges = [(-(i + 1) * bin_width, -i * bin_width) for i in range(n_bins)][::-1]
    edges += [(i * bin_width, (i + 1) * bin_width) for i in range(n_bins)]

    buckets: List[List[TypedComposite]] = [[] for _ in edges]

    for composite in located:
        is_above = composite.grade >= threshold
        distance = _signed_distance_to_other_side(composite, above, below, is_above)
        if distance is None or abs(distance) > max_distance:
            continue

        for index, (low, high) in enumerate(edges):
            # Half-open away from zero, so a composite exactly on a bin edge
            # lands in one bucket and only one.
            if low <= distance < high or (high == max_distance and distance == high):
                buckets[index].append(composite)
                break

    bins: List[ContactBin] = []
    for (low, high), members in zip(edges, buckets):
        if members:
            total_length = sum(c.length for c in members)
            mean_grade = sum(c.grade for c in members) / len(members)
            weighted = (
                sum(c.grade * c.length for c in members) / total_length
                if total_length > _EPS else None
            )
        else:
            mean_grade = None
            weighted = None

        bins.append(ContactBin(
            distance_bin_center=(low + high) / 2.0,
            n=len(members),
            mean_grade=mean_grade,
            length_weighted_mean_grade=weighted,
        ))

    return bins
