# T003 — Cut-off Threshold Analysis

> Read `specs/007-grade-domain-shells/tasks.md` first.

| Field | Value |
|---|---|
| **Task ID** | T003 |
| **Priority** | P0 |
| **Dependencies** | T001 |
| **Complexity** | Medium |
| **Status** | **DONE** |

> **Unblocked by D8**: no cut-off is set in advance. This task builds the
> evidence — log-probability, metal capture, contact analysis — and the
> threshold is chosen from it afterwards. `metal_capture_curve` takes its
> candidate thresholds as a required argument and carries **no default and no
> recommendation**; the list describes the shape of the curve only.

---

## Context

The threshold that defines a grade domain must be justified from the data, not
picked by habit. "0.3 g/t because that's what we always use" does not survive
review when the log-probability plot shows a population break at 0.15.

The three standard lines of evidence are: a log-probability plot (inflections
mark boundaries between statistical populations), a metal-capture curve (what
fraction of contained metal a given threshold retains), and contact analysis
(does grade actually step across the proposed boundary, or drift smoothly?).
This task computes all three as data. Plotting happens in the frontend (T009).

---

## Objective

Pure functions producing the three datasets a geologist needs to choose and
defend a grade-shell threshold.

---

## Detailed Requirements

### 1. Log-probability dataset

For composites sorted ascending by grade, emit points
`(cumulative_probability, grade)` where cumulative probability uses the
**Hazen plotting position** `(i - 0.5) / n` for `i = 1..n`.

- Grades `<= 0` cannot be plotted on a log axis. Exclude them and report the
  excluded count in the result rather than dropping them silently.
- Return grades on the natural scale; the frontend applies the log axis.

### 2. Metal capture / grade–tonnage curve

For each threshold in `thresholds`:

- `n_above` — count of composites with `grade >= threshold`
- `length_above` — total length of those composites
- `metal_above` — `sum(grade × length)` over those composites
- `length_fraction` — `length_above / total_length`
- `metal_fraction` — `metal_above / total_metal`  ← **the metal capture**
- `mean_grade_above` — `metal_above / length_above`, `None` when zero length

`total_metal` and `total_length` are over **all** composites, including those
below every threshold. When `total_metal` is 0, all fractions are `None`.

### 3. Contact analysis

Given composites carrying 3D coordinates and a threshold, for each composite
compute the signed distance to the nearest composite on the *other* side of the
threshold — negative if the composite is itself below threshold, positive if
above — then bin those distances and report the mean grade per bin.

- Bin width default `5.0` m, range default `±50.0` m.
- Report `distance_bin_center`, `n`, `mean_grade`, `length_weighted_mean_grade`.
- Composites lacking coordinates (`x is None`) are excluded; report the count.
- A **sharp** contact shows a step at distance 0; a **gradational** contact
  shows a smooth ramp. Do not classify it — return the numbers.

### File Location

- `backend/src/services/threshold_analysis.py`
- `backend/tests/unit/test_threshold_analysis.py`

### Dependencies allowed

Python standard library, plus `numpy` **only if already added by another
task**. A brute-force O(n²) nearest-neighbour search is acceptable here —
composite counts are in the thousands, and clarity beats speed.

---

## Interface Contract

```python
from dataclasses import dataclass
from backend.src.services.sample_type_comparison import TypedComposite

@dataclass(frozen=True)
class LogProbPoint:
    cumulative_probability: float
    grade: float

@dataclass(frozen=True)
class LogProbResult:
    points: list[LogProbPoint]
    n_excluded_non_positive: int

@dataclass(frozen=True)
class CaptureRow:
    threshold: float
    n_above: int
    length_above: float
    metal_above: float
    length_fraction: float | None
    metal_fraction: float | None
    mean_grade_above: float | None

@dataclass(frozen=True)
class ContactBin:
    distance_bin_center: float
    n: int
    mean_grade: float | None
    length_weighted_mean_grade: float | None

def log_probability_points(
    composites: list[TypedComposite],
) -> LogProbResult: ...

def metal_capture_curve(
    composites: list[TypedComposite],
    thresholds: list[float],
) -> list[CaptureRow]: ...

def contact_analysis(
    composites: list[TypedComposite],
    threshold: float,
    bin_width: float = 5.0,
    max_distance: float = 50.0,
) -> list[ContactBin]: ...
```

---

## Test Fixtures (hand-computed)

**F1 — Hazen positions.** 4 composites, grades `1,2,3,4`.
Expect cumulative probabilities exactly `0.125, 0.375, 0.625, 0.875`.

**F2 — non-positive exclusion.** Grades `[0.0, -1.0, 2.0, 4.0]` →
`len(points) == 2`, `n_excluded_non_positive == 2`, and the two remaining
probabilities are `0.25` and `0.75`.

**F3 — metal capture arithmetic.** Four composites, all length `1.0`, grades
`0.1, 0.5, 2.0, 5.0`. `total_length = 4.0`, `total_metal = 7.6`.

| threshold | n_above | length_above | metal_above | length_fraction | metal_fraction |
|---|---|---|---|---|---|
| 0.0 | 4 | 4.0 | 7.6 | 1.0 | 1.0 |
| 0.5 | 3 | 3.0 | 7.5 | 0.75 | 0.98684… |
| 2.0 | 2 | 2.0 | 7.0 | 0.5 | 0.92105… |
| 6.0 | 0 | 0.0 | 0.0 | 0.0 | 0.0 |

Assert `metal_fraction` at 0.5 equals `7.5 / 7.6` to `1e-9`. Note the
threshold comparison is `>=`, so `0.5` is **included** at threshold `0.5`.

**F4 — mean grade above.** At threshold `2.0` in F3,
`mean_grade_above == 7.0 / 2.0 == 3.5`.

**F5 — zero metal.** All grades `0.0` → every `metal_fraction is None`, no
`ZeroDivisionError`.

**F6 — sharp contact.** Composites on a line at `x = -20,-15,…,20`, grade
`0.1` for `x < 0` and `5.0` for `x >= 0`, threshold `1.0`. Expect bins at
negative distance centres to have `mean_grade == 0.1` and positive centres
`5.0`, with the step at zero.

**F7 — missing coordinates** are excluded without raising.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | F1–F7 pass exactly, including the `7.5/7.6` value |
| AC-2 | P0 | Threshold comparison is `>=` everywhere, consistently |
| AC-3 | P0 | Zero-metal and zero-length cases return `None`, never raise |
| AC-4 | P0 | Non-positive grades are excluded from log-prob and **counted**, not dropped silently |
| AC-5 | P0 | All three functions are pure |
| AC-6 | P1 | `contact_analysis` uses length-weighted means alongside plain means |

---

## Anti-Patterns to Avoid

- Using `i / n` or `(i - 1) / n` for plotting position — Hazen `(i - 0.5)/n` is
  specified because it is the convention these plots are read against.
- Mixing `>` and `>=` between the count, length, and metal calculations. One
  inconsistency makes the whole table wrong at exactly the boundary values a
  geologist will check first.
- Auto-selecting a "best" threshold. This task presents evidence. The choice is
  the user's, made in T009.
- Silently dropping zero-grade composites from the capture curve — they carry
  length and belong in the denominator.
