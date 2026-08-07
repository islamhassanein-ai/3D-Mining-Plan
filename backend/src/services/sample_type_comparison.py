"""Comparison of drillhole and trench/channel sample populations.

Trench and channel samples are a different sample support from diamond core.
They are larger, cut by hand along a surface that has been weathered and often
supergene-enriched, spaced far more densely than drilling, and collected under
conditions where a hammer follows the quartz. Pooling them with core assays
without first asking whether the two populations are comparable inflates
near-surface grade exactly where a pit is shallowest and the economics are most
sensitive to it -- which is why it is among the first things an auditor tests.

This module produces the evidence for that question. It does not answer it.
Nothing here selects a weighting, and no function returns a recommendation: the
choice of whether trench data informs grade, or only geometry, is a
project-specific geological decision made by the person who knows the deposit.

What comes out:

* per-type statistics, including **both** the plain mean and the
  length-weighted mean. Reporting only the plain mean hides sample support,
  which is the entire subject of this module.
* a **grade ratio** of non-reference to reference on length-weighted means --
  the single number that most directly bears on the question.
* a **Q-Q dataset** pairing the two populations quantile for quantile. A
  constant offset, a divergence confined to the upper tail, and a wholesale
  scale difference are three different geological stories, and only a Q-Q plot
  distinguishes them from a ratio alone.
* a ``comparable`` screening flag with written reasons.

``comparable`` is a screening heuristic and **not a statistical test**. No
hypothesis test is performed anywhere in this module. A ``True`` result does
not authorise pooling; it means nothing obvious showed up in three coarse
checks.

One limitation is worth stating plainly, because it bears directly on how the
output should be read: the comparison is **global, not spatially paired**.
Trenches sit at surface and drillholes mostly do not, so a grade difference
between the two populations may be real vertical zonation -- oxide enrichment,
a supergene blanket -- rather than a sampling artefact. Distinguishing those
requires comparing the two only where they overlap in space, which this module
does not do. Read a large grade ratio as "these populations differ, find out
why", never as "trench sampling is biased".

Grades reaching this module are assayed results. A composite never carries a
``None`` grade -- ``compositing.composite_intervals`` does not emit windows
with no assayed ground -- and a ``None`` arriving here means unassayed ground
has leaked in somewhere upstream, so it is rejected rather than skipped. A
genuine ``0.0`` g/t is a real result and is included in every statistic.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

# Screening thresholds for the advisory `comparable` flag. These are coarse
# defaults for a first look, not deposit-specific criteria.
_MIN_N_FOR_COMPARISON = 30
_RATIO_LOWER = 0.8
_RATIO_UPPER = 1.25
_MAX_RELATIVE_CV_DIFFERENCE = 0.35

_EPS = 1e-12

DEFAULT_REFERENCE_TYPE = "DDH"
DEFAULT_N_QUANTILES = 50

# Q-Q sampling stays inside the tails: the extreme order statistics of two
# unequal-sized populations are not comparable, and plotting them implies a
# precision the data does not have.
_QQ_MIN_QUANTILE = 0.01
_QQ_MAX_QUANTILE = 0.99

POOLED_LABEL = "ALL"


@dataclass(frozen=True)
class TypedComposite:
    """One composite, tagged with the sample type it came from.

    Coordinates are optional here -- this module needs none of them -- and are
    populated by ``composite_points`` for the tasks that do.
    """

    grade: float
    length: float
    sample_type: str
    x: Optional[float] = None
    y: Optional[float] = None
    z: Optional[float] = None


@dataclass(frozen=True)
class PopulationStats:
    """Summary statistics for one sample population.

    Statistics that are undefined for the sample count are ``None`` rather than
    zero: ``std`` and ``cv`` need at least two values, and ``cv`` additionally
    needs a non-zero mean. ``None`` here means "not defined", never "zero".
    """

    sample_type: str
    n: int
    mean: Optional[float]
    median: Optional[float]
    std: Optional[float]
    cv: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]
    p10: Optional[float]
    p25: Optional[float]
    p75: Optional[float]
    p90: Optional[float]
    total_length: float
    length_weighted_mean: Optional[float]


@dataclass(frozen=True)
class ComparisonResult:
    """Everything this module produces. No recommendation is included."""

    by_type: Dict[str, PopulationStats]
    pooled: PopulationStats
    qq_points: List[Tuple[float, float]]
    grade_ratio: Optional[float]
    mean_ratio: Optional[float]
    comparable: bool
    reasons: List[str]


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    """Quantile by linear interpolation between order statistics.

    Position is ``q * (n - 1)``, the convention numpy calls "linear" and the
    one the percentile and Q-Q outputs of this module both use, so a p50 and a
    Q-Q point at 0.5 always agree.
    """
    n = len(sorted_values)
    if n == 1:
        return sorted_values[0]

    position = q * (n - 1)
    lower = int(position)
    if lower >= n - 1:
        return sorted_values[-1]

    fraction = position - lower
    return sorted_values[lower] + fraction * (
        sorted_values[lower + 1] - sorted_values[lower]
    )


def _summarize(composites: Sequence[TypedComposite], label: str) -> PopulationStats:
    """Summary statistics for one population, tolerant of empty input."""
    n = len(composites)
    total_length = sum(c.length for c in composites)

    if n == 0:
        return PopulationStats(
            sample_type=label,
            n=0,
            mean=None,
            median=None,
            std=None,
            cv=None,
            minimum=None,
            maximum=None,
            p10=None,
            p25=None,
            p75=None,
            p90=None,
            total_length=0.0,
            length_weighted_mean=None,
        )

    grades = sorted(c.grade for c in composites)
    mean = sum(grades) / n

    if n >= 2:
        variance = sum((g - mean) ** 2 for g in grades) / (n - 1)
        std = variance ** 0.5
    else:
        std = None

    # A zero mean makes the coefficient of variation undefined rather than
    # infinite. It happens in practice: a barren domain of genuine 0.0 g/t
    # results is a real population, not an error.
    cv = std / mean if (std is not None and abs(mean) > _EPS) else None

    weighted = sum(c.grade * c.length for c in composites)
    length_weighted_mean = weighted / total_length if total_length > _EPS else None

    return PopulationStats(
        sample_type=label,
        n=n,
        mean=mean,
        median=_quantile(grades, 0.5),
        std=std,
        cv=cv,
        minimum=grades[0],
        maximum=grades[-1],
        p10=_quantile(grades, 0.10),
        p25=_quantile(grades, 0.25),
        p75=_quantile(grades, 0.75),
        p90=_quantile(grades, 0.90),
        total_length=total_length,
        length_weighted_mean=length_weighted_mean,
    )


def _qq_points(
    reference: Sequence[TypedComposite],
    other: Sequence[TypedComposite],
    n_quantiles: int,
) -> List[Tuple[float, float]]:
    """Pair the two populations quantile for quantile.

    Both populations are sampled at the same quantiles, so the two grades in a
    pair describe the same position in their respective distributions. An empty
    population yields no points -- there is nothing to pair against.
    """
    if not reference or not other:
        return []

    reference_grades = sorted(c.grade for c in reference)
    other_grades = sorted(c.grade for c in other)

    if n_quantiles == 1:
        quantiles = [(_QQ_MIN_QUANTILE + _QQ_MAX_QUANTILE) / 2.0]
    else:
        step = (_QQ_MAX_QUANTILE - _QQ_MIN_QUANTILE) / (n_quantiles - 1)
        quantiles = [_QQ_MIN_QUANTILE + i * step for i in range(n_quantiles)]

    return [
        (_quantile(reference_grades, q), _quantile(other_grades, q))
        for q in quantiles
    ]


def _screen(
    reference_stats: PopulationStats,
    other_stats: PopulationStats,
    grade_ratio: Optional[float],
    reference_type: str,
) -> Tuple[bool, List[str]]:
    """Run the three coarse screening checks and explain every failure.

    Advisory only. See the module docstring: this is not a statistical test,
    and passing it does not authorise pooling the two populations.
    """
    reasons: List[str] = []

    if (
        reference_stats.n < _MIN_N_FOR_COMPARISON
        or other_stats.n < _MIN_N_FOR_COMPARISON
    ):
        reasons.append(
            f"insufficient samples for comparison "
            f"({reference_type} n={reference_stats.n}, "
            f"{other_stats.sample_type} n={other_stats.n}; "
            f"{_MIN_N_FOR_COMPARISON} needed in each)"
        )

    if grade_ratio is None:
        reasons.append(
            "grade ratio undefined -- one population is empty or carries no length"
        )
    elif not (_RATIO_LOWER <= grade_ratio <= _RATIO_UPPER):
        reasons.append(
            f"length-weighted grade ratio {grade_ratio:.3f} is outside "
            f"{_RATIO_LOWER}-{_RATIO_UPPER} "
            f"({other_stats.sample_type} vs {reference_type})"
        )

    reference_cv = reference_stats.cv
    other_cv = other_stats.cv
    if reference_cv is None or other_cv is None:
        reasons.append(
            "coefficient of variation undefined for at least one population"
        )
    else:
        largest = max(reference_cv, other_cv)
        # Two constant populations both have cv 0 and are not "divergent"; the
        # relative difference is 0/0 there, and 0.0 is the right reading.
        relative = (
            abs(reference_cv - other_cv) / largest if largest > _EPS else 0.0
        )
        if relative > _MAX_RELATIVE_CV_DIFFERENCE:
            reasons.append(
                f"variability differs: cv {reference_cv:.3f} ({reference_type}) "
                f"vs {other_cv:.3f} ({other_stats.sample_type}), "
                f"relative difference {relative:.3f} exceeds "
                f"{_MAX_RELATIVE_CV_DIFFERENCE}"
            )

    return (not reasons), reasons


def compare_sample_types(
    composites: List[TypedComposite],
    reference_type: str = DEFAULT_REFERENCE_TYPE,
    n_quantiles: int = DEFAULT_N_QUANTILES,
) -> ComparisonResult:
    """Compare a reference sample type against every other type present.

    ``by_type`` keeps each sample type separate. The ratios and the Q-Q dataset
    compare ``reference_type`` against all non-reference types pooled together,
    since the question they serve is whether surface sampling as a whole reads
    the same as core.

    Raises ``ValueError`` if any composite carries a ``None`` grade, which would
    mean unassayed ground reached this module.
    """
    if n_quantiles < 1:
        raise ValueError(f"n_quantiles must be at least 1, got {n_quantiles}")

    for c in composites:
        if c.grade is None:
            raise ValueError(
                f"Composite of type {c.sample_type!r} has grade None; "
                "unassayed ground must be excluded during compositing, not here"
            )

    reference = [c for c in composites if c.sample_type == reference_type]
    other = [c for c in composites if c.sample_type != reference_type]

    by_type = {
        sample_type: _summarize(
            [c for c in composites if c.sample_type == sample_type], sample_type
        )
        for sample_type in sorted({c.sample_type for c in composites})
    }

    reference_stats = _summarize(reference, reference_type)
    other_stats = _summarize(other, "NON-" + reference_type)

    grade_ratio = _ratio(
        other_stats.length_weighted_mean, reference_stats.length_weighted_mean
    )
    mean_ratio = _ratio(other_stats.mean, reference_stats.mean)

    comparable, reasons = _screen(
        reference_stats, other_stats, grade_ratio, reference_type
    )

    return ComparisonResult(
        by_type=by_type,
        pooled=_summarize(composites, POOLED_LABEL),
        qq_points=_qq_points(reference, other, n_quantiles),
        grade_ratio=grade_ratio,
        mean_ratio=mean_ratio,
        comparable=comparable,
        reasons=reasons,
    )


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Ratio that is ``None`` rather than an exception when it is undefined."""
    if numerator is None or denominator is None or abs(denominator) <= _EPS:
        return None
    return numerator / denominator
