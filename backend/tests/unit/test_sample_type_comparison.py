"""Tests for DDH vs TR/FC population comparison.

Every expected value here is hand-computed from arithmetic written into the
test, not copied from the implementation's output. Where a number is not
self-evident the working is in a comment. If the implementation disagrees with
one of these numbers, the implementation is wrong.
"""
import math

import pytest

from backend.src.services.sample_type_comparison import (
    TypedComposite,
    compare_sample_types,
)


def _population(grade, count, sample_type, length=1.0):
    return [TypedComposite(grade, length, sample_type) for _ in range(count)]


# --- F1: identical populations -----------------------------------------------

def test_identical_populations_are_comparable():
    composites = _population(1.0, 100, "DDH") + _population(1.0, 100, "TR")

    result = compare_sample_types(composites)

    assert math.isclose(result.grade_ratio, 1.0)
    assert math.isclose(result.mean_ratio, 1.0)
    assert result.comparable is True
    assert result.reasons == []
    assert len(result.qq_points) == 50
    assert all(
        math.isclose(a, 1.0) and math.isclose(b, 1.0) for a, b in result.qq_points
    )


# --- F2: enriched trench population ------------------------------------------

def test_trench_enriched_twofold_is_flagged():
    composites = _population(1.0, 50, "DDH") + _population(2.0, 50, "TR")

    result = compare_sample_types(composites)

    assert math.isclose(result.grade_ratio, 2.0)
    assert result.comparable is False
    assert any("ratio" in reason for reason in result.reasons)
    # The ratio is reported, not acted on: no weighting appears anywhere.
    assert not hasattr(result, "recommended_weight")


def test_reasons_name_the_actual_numbers():
    composites = _population(1.0, 50, "DDH") + _population(2.0, 50, "TR")

    reasons = " ".join(compare_sample_types(composites).reasons)

    assert "2.000" in reasons


# --- F3: length weighting vs plain mean --------------------------------------

def test_plain_and_length_weighted_means_both_reported():
    # 10.0 g/t over 0.5 m and 1.0 g/t over 9.5 m.
    # plain mean          = (10.0 + 1.0) / 2 = 5.5
    # length-weighted     = (10.0 * 0.5 + 1.0 * 9.5) / 10.0 = 14.5 / 10.0 = 1.45
    # The gap between them is the sample-support effect this module exists for.
    composites = [
        TypedComposite(10.0, 0.5, "DDH"),
        TypedComposite(1.0, 9.5, "DDH"),
    ]

    stats = compare_sample_types(composites).by_type["DDH"]

    assert math.isclose(stats.mean, 5.5)
    assert math.isclose(stats.length_weighted_mean, 1.45)
    assert math.isclose(stats.total_length, 10.0)


def test_grade_ratio_uses_length_weighted_means():
    # DDH length-weighted mean: (10.0 * 0.5 + 1.0 * 9.5) / 10.0 = 1.45
    # TR  length-weighted mean: 2.9 over any length            = 2.9
    # ratio = 2.9 / 1.45 = 2.0  -- a plain-mean ratio would give 2.9 / 5.5.
    composites = [
        TypedComposite(10.0, 0.5, "DDH"),
        TypedComposite(1.0, 9.5, "DDH"),
        TypedComposite(2.9, 1.0, "TR"),
    ]

    result = compare_sample_types(composites)

    assert math.isclose(result.grade_ratio, 2.0)
    assert math.isclose(result.mean_ratio, 2.9 / 5.5)


# --- F4: small populations ---------------------------------------------------

def test_small_populations_are_not_declared_comparable():
    # Grades match perfectly, but five samples cannot establish that.
    composites = _population(1.0, 5, "DDH") + _population(1.0, 5, "TR")

    result = compare_sample_types(composites)

    assert result.comparable is False
    assert any("insufficient samples" in reason for reason in result.reasons)
    assert math.isclose(result.grade_ratio, 1.0)


# --- F5 / F6: degenerate populations -----------------------------------------

def test_empty_trench_population_does_not_raise():
    result = compare_sample_types(_population(1.0, 40, "DDH"))

    assert result.grade_ratio is None
    assert result.mean_ratio is None
    assert result.comparable is False
    assert result.qq_points == []
    assert result.by_type["DDH"].n == 40


def test_single_sample_leaves_spread_undefined():
    result = compare_sample_types([TypedComposite(3.0, 1.0, "DDH")])

    stats = result.by_type["DDH"]
    assert stats.n == 1
    assert math.isclose(stats.mean, 3.0)
    assert stats.std is None
    assert stats.cv is None
    assert math.isclose(stats.median, 3.0)


def test_empty_input_does_not_raise():
    result = compare_sample_types([])

    assert result.by_type == {}
    assert result.pooled.n == 0
    assert result.grade_ratio is None
    assert result.comparable is False


def test_reference_type_absent_entirely():
    # Trenches only, no core. The comparison cannot be made, and saying so is
    # the correct outcome.
    result = compare_sample_types(_population(1.0, 40, "TR"))

    assert result.grade_ratio is None
    assert result.qq_points == []
    assert result.comparable is False
    assert "TR" in result.by_type


def test_zero_total_length_leaves_weighted_mean_undefined():
    composites = [
        TypedComposite(1.0, 0.0, "DDH"),
        TypedComposite(3.0, 0.0, "DDH"),
    ]

    stats = compare_sample_types(composites).by_type["DDH"]

    assert stats.length_weighted_mean is None
    assert math.isclose(stats.mean, 2.0)


# --- F7: Q-Q dataset ---------------------------------------------------------

def test_qq_points_are_monotonic_in_both_coordinates():
    composites = (
        [TypedComposite(float(i), 1.0, "DDH") for i in range(1, 41)]
        + [TypedComposite(float(i) * 0.5, 1.0, "TR") for i in range(1, 41)]
    )

    points = compare_sample_types(composites).qq_points

    reference = [p[0] for p in points]
    other = [p[1] for p in points]
    assert reference == sorted(reference)
    assert other == sorted(other)


def test_qq_point_count_follows_n_quantiles():
    composites = _population(1.0, 40, "DDH") + _population(1.0, 40, "TR")

    assert len(compare_sample_types(composites, n_quantiles=10).qq_points) == 10


def test_qq_separates_a_tail_difference_from_a_scale_difference():
    # DDH 1..40. TR is identical except its top five values are doubled.
    # The ratio alone cannot tell this from a uniform uplift; the Q-Q can,
    # because the low quantiles pair 1:1 and only the top ones diverge.
    ddh = [TypedComposite(float(i), 1.0, "DDH") for i in range(1, 41)]
    trench = [
        TypedComposite(float(i) * (2.0 if i > 35 else 1.0), 1.0, "TR")
        for i in range(1, 41)
    ]

    points = compare_sample_types(ddh + trench, n_quantiles=50).qq_points

    lowest = points[0]
    highest = points[-1]
    assert math.isclose(lowest[0], lowest[1])
    assert highest[1] > highest[0] * 1.5


# --- percentiles and spread --------------------------------------------------

def test_percentiles_use_linear_interpolation_between_order_statistics():
    # Grades 1..10, position = q * (n - 1) = q * 9.
    #   p10 -> 0.9  -> 1 + 0.9 * (2 - 1)  = 1.9
    #   p25 -> 2.25 -> 3 + 0.25 * (4 - 3) = 3.25
    #   p50 -> 4.5  -> 5 + 0.5 * (6 - 5)  = 5.5
    #   p75 -> 6.75 -> 7 + 0.75 * (8 - 7) = 7.75
    #   p90 -> 8.1  -> 9 + 0.1 * (10 - 9) = 9.1
    composites = [TypedComposite(float(i), 1.0, "DDH") for i in range(1, 11)]

    stats = compare_sample_types(composites).by_type["DDH"]

    assert math.isclose(stats.p10, 1.9)
    assert math.isclose(stats.p25, 3.25)
    assert math.isclose(stats.median, 5.5)
    assert math.isclose(stats.p75, 7.75)
    assert math.isclose(stats.p90, 9.1)
    assert math.isclose(stats.minimum, 1.0)
    assert math.isclose(stats.maximum, 10.0)


def test_standard_deviation_and_cv():
    # Grades 1..10: mean 5.5, sum of squared deviations
    #   2 * (4.5^2 + 3.5^2 + 2.5^2 + 1.5^2 + 0.5^2) = 2 * 41.25 = 82.5
    # sample variance (ddof=1) = 82.5 / 9, so std = sqrt(82.5 / 9)
    composites = [TypedComposite(float(i), 1.0, "DDH") for i in range(1, 11)]
    expected_std = math.sqrt(82.5 / 9)

    stats = compare_sample_types(composites).by_type["DDH"]

    assert math.isclose(stats.mean, 5.5)
    assert math.isclose(stats.std, expected_std)
    assert math.isclose(stats.cv, expected_std / 5.5)


def test_diverging_variability_is_flagged_even_when_means_match():
    # Both populations mean 1.0, so the grade ratio is exactly 1.0 and passes.
    # DDH alternates +/-0.1, TR alternates +/-0.8: same grade, very different
    # sample behaviour, which is what a support difference looks like.
    ddh = [
        TypedComposite(1.0 + (0.1 if i % 2 else -0.1), 1.0, "DDH")
        for i in range(40)
    ]
    trench = [
        TypedComposite(1.0 + (0.8 if i % 2 else -0.8), 1.0, "TR")
        for i in range(40)
    ]

    result = compare_sample_types(ddh + trench)

    assert math.isclose(result.grade_ratio, 1.0)
    assert result.comparable is False
    assert any("variability differs" in reason for reason in result.reasons)


def test_constant_populations_do_not_divide_by_zero_on_cv():
    # Both cv are exactly 0.0; the relative difference is 0/0 and must read 0.
    composites = _population(1.0, 40, "DDH") + _population(1.0, 40, "TR")

    result = compare_sample_types(composites)

    assert math.isclose(result.by_type["DDH"].cv, 0.0)
    assert result.comparable is True


# --- grade semantics ---------------------------------------------------------

def test_genuine_zero_grades_are_included():
    # 0.0 g/t is an assay result and belongs in the statistics. Twenty barren
    # composites and twenty at 2.0 g/t give a mean of 1.0, not 2.0.
    composites = _population(0.0, 20, "DDH") + _population(2.0, 20, "DDH")

    stats = compare_sample_types(composites).by_type["DDH"]

    assert stats.n == 40
    assert math.isclose(stats.mean, 1.0)
    assert math.isclose(stats.minimum, 0.0)


def test_barren_population_leaves_cv_undefined_without_raising():
    # Every grade 0.0: mean 0.0, so cv is undefined rather than infinite.
    result = compare_sample_types(_population(0.0, 40, "DDH"))

    stats = result.by_type["DDH"]
    assert math.isclose(stats.mean, 0.0)
    assert math.isclose(stats.std, 0.0)
    assert stats.cv is None


def test_none_grade_is_rejected():
    # A None grade means unassayed ground leaked past compositing. Silently
    # skipping it would hide the upstream fault.
    composites = [
        TypedComposite(1.0, 1.0, "DDH"),
        TypedComposite(None, 1.0, "TR"),
    ]

    with pytest.raises(ValueError, match="grade None"):
        compare_sample_types(composites)


# --- multiple sample types ---------------------------------------------------

def test_each_sample_type_is_reported_separately():
    composites = (
        _population(1.0, 30, "DDH")
        + _population(2.0, 20, "TR")
        + _population(4.0, 10, "FC")
    )

    result = compare_sample_types(composites)

    assert set(result.by_type) == {"DDH", "TR", "FC"}
    assert result.by_type["TR"].n == 20
    assert result.by_type["FC"].n == 10
    assert math.isclose(result.by_type["FC"].mean, 4.0)


def test_non_reference_types_pool_for_the_ratio():
    # TR at 2.0 over 20 m and FC at 4.0 over 10 m pool to
    # (2.0 * 20 + 4.0 * 10) / 30 = 80 / 30 = 2.6666...
    # against DDH at 1.0, so the ratio is 80 / 30.
    composites = (
        _population(1.0, 30, "DDH")
        + _population(2.0, 20, "TR")
        + _population(4.0, 10, "FC")
    )

    result = compare_sample_types(composites)

    assert math.isclose(result.grade_ratio, 80.0 / 30.0)


def test_pooled_statistics_cover_every_type():
    composites = _population(1.0, 30, "DDH") + _population(3.0, 10, "TR")

    pooled = compare_sample_types(composites).pooled

    assert pooled.n == 40
    assert math.isclose(pooled.mean, (30 * 1.0 + 10 * 3.0) / 40)


def test_reference_type_is_configurable():
    composites = _population(1.0, 30, "TR") + _population(2.0, 30, "DDH")

    result = compare_sample_types(composites, reference_type="TR")

    # DDH is now the non-reference population: 2.0 / 1.0
    assert math.isclose(result.grade_ratio, 2.0)


# --- purity ------------------------------------------------------------------

def test_input_is_not_mutated_and_order_does_not_matter():
    composites = _population(1.0, 30, "DDH") + _population(2.0, 30, "TR")
    before = list(composites)
    reversed_input = list(reversed(composites))

    result = compare_sample_types(composites)
    reversed_result = compare_sample_types(reversed_input)

    assert composites == before
    assert result == reversed_result


def test_invalid_n_quantiles_raises():
    with pytest.raises(ValueError, match="n_quantiles"):
        compare_sample_types(_population(1.0, 5, "DDH"), n_quantiles=0)
