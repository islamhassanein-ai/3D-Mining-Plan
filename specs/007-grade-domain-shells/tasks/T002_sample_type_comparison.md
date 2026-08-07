# T002 — DDH vs TR/FC Population Comparison

> Read `specs/007-grade-domain-shells/tasks.md` first.

| Field | Value |
|---|---|
| **Task ID** | T002 |
| **Priority** | P0 |
| **Dependencies** | T001 |
| **Complexity** | Medium |
| **Status** | TODO |

---

## Context

Trench and channel samples are a different sample support from diamond core:
larger, cut by hand, taken at surface where oxidation and supergene enrichment
have altered grades, and usually spaced far more densely. Pooling them with
core assays without first testing whether the two populations are comparable is
the most commonly audited error in a gold resource, because it inflates
near-surface grade exactly where the pit is shallowest and the economics are
most sensitive.

This task produces the evidence a geologist uses to decide whether trench data
may be used for grade interpolation, or only for shell geometry. **It does not
make that decision** — it reports, the user chooses in T008/T009.

---

## Objective

A pure function that takes composites tagged by sample type and returns
comparative statistics plus a Q–Q dataset, so the two populations can be
inspected side by side.

---

## Detailed Requirements

### Functional

1. Compute, **per sample type** and for the pooled set:
   `n`, `mean`, `median`, `std` (sample std, ddof=1), `cv` (`std/mean`),
   `min`, `max`, `p10`, `p25`, `p75`, `p90`, `total_length`,
   `length_weighted_mean`.
2. `length_weighted_mean = sum(grade × length) / sum(length)`. Report **both**
   this and the plain mean — a large divergence is itself a finding.
3. Build a **Q–Q dataset**: sort each population, sample both at a shared set
   of quantiles (default 50 evenly spaced from 0.01 to 0.99), and return paired
   `(ddh_quantile_grade, other_quantile_grade)` points. Use linear
   interpolation between order statistics.
4. Compute a **grade ratio** `trench_length_weighted_mean /
   ddh_length_weighted_mean`, and a `mean_ratio` likewise. Return `None` for a
   ratio when the denominator is zero or the population is empty.
5. Return a `comparable` boolean flag, `True` only when **all** hold:
   - both populations have `n >= 30`
   - `0.8 <= grade_ratio <= 1.25`
   - `abs(ddh_cv - other_cv) / max(ddh_cv, other_cv) <= 0.35`
   Along with it return `reasons: list[str]` naming every failed condition in
   plain language. When `n < 30` in either population, `comparable` is `False`
   with the reason `"insufficient samples for comparison (DDH n=…, TR n=…)"`.
6. `comparable` is advisory. The docstring must say so explicitly: it is a
   screening heuristic, not a statistical test, and a `True` result does not
   authorise pooling.
7. Empty or single-element populations must not raise. Return the struct with
   `None` for statistics that are undefined (`std` and `cv` need `n >= 2`).

### File Location

- `backend/src/services/sample_type_comparison.py`
- `backend/tests/unit/test_sample_type_comparison.py`

### Dependencies allowed

Python standard library (`statistics` is fine). No numpy.

---

## Interface Contract

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TypedComposite:
    grade: float
    length: float
    sample_type: str          # "DDH" | "TR" | "FC"
    x: float | None = None
    y: float | None = None
    z: float | None = None

@dataclass(frozen=True)
class PopulationStats:
    sample_type: str
    n: int
    mean: float | None
    median: float | None
    std: float | None
    cv: float | None
    minimum: float | None
    maximum: float | None
    p10: float | None
    p25: float | None
    p75: float | None
    p90: float | None
    total_length: float
    length_weighted_mean: float | None

@dataclass(frozen=True)
class ComparisonResult:
    by_type: dict[str, PopulationStats]   # keyed by sample_type
    pooled: PopulationStats
    qq_points: list[tuple[float, float]]  # (ddh_grade, other_grade)
    grade_ratio: float | None             # length-weighted, other / ddh
    mean_ratio: float | None
    comparable: bool
    reasons: list[str]

def compare_sample_types(
    composites: list[TypedComposite],
    reference_type: str = "DDH",
    n_quantiles: int = 50,
) -> ComparisonResult:
    ...
```

Sample types other than `reference_type` are pooled into the "other"
population for the Q–Q and ratio calculations, but `by_type` keeps each type
separate.

---

## Test Fixtures (hand-computed)

**F1 — identical populations.** 100 DDH and 100 TR composites, all grade
`1.0`, all length `1.0`. Expect `grade_ratio == 1.0`, `comparable is True`,
`reasons == []`, and every Q–Q point equal to `(1.0, 1.0)`.

**F2 — trench enriched 2×.** 50 DDH at `1.0`, 50 TR at `2.0`, all length 1.0.
Expect `grade_ratio == 2.0`, `comparable is False`, and `reasons` containing a
string mentioning the ratio.

**F3 — length weighting matters.** DDH: one composite grade `10.0` length
`0.5`, one grade `1.0` length `9.5`.
Plain mean = `5.5`. Length-weighted = `(10×0.5 + 1×9.5)/10 = 1.45`.
Assert both values exactly.

**F4 — small n.** 5 DDH, 5 TR, identical grades. `comparable is False` with an
insufficient-samples reason, even though the grades match perfectly.

**F5 — empty trench population.** 40 DDH, 0 TR. No exception.
`grade_ratio is None`, `comparable is False`.

**F6 — single sample.** `n == 1` → `std is None`, `cv is None`, `mean` set.

**F7 — Q–Q monotonicity.** For any two populations, `qq_points` must be
non-decreasing in both coordinates.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | F1–F7 pass exactly |
| AC-2 | P0 | Empty and single-element populations never raise |
| AC-3 | P0 | Length-weighted and plain means are both reported and are distinct values in F3 |
| AC-4 | P0 | Function is pure — no I/O, no DB |
| AC-5 | P0 | `comparable`'s docstring states it is advisory and not a statistical test |
| AC-6 | P1 | `reasons` is human-readable and names actual numbers |

---

## Anti-Patterns to Avoid

- Reporting only the plain mean. Sample support is the entire point of this
  task; an unweighted mean hides it.
- Making `comparable` a hard gate that blocks downstream work. It is a report.
- Dividing by zero when a population is empty or has zero total length.
- Claiming a statistical test (K–S, t-test) was performed. This task performs
  none, and the output must not imply otherwise.
