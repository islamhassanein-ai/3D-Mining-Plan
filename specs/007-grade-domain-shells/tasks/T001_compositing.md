# T001 — Length-Weighted Compositing Service

> Read `specs/007-grade-domain-shells/tasks.md` first. Its conventions are
> binding and are not repeated here.

| Field | Value |
|---|---|
| **Task ID** | T001 |
| **Phase** | 007 — Grade Domain Shells |
| **Priority** | P0 |
| **Dependencies** | None |
| **Complexity** | Medium |
| **Status** | **DONE — reference implementation** |

> **This task is implemented.** `backend/src/services/compositing.py` and
> `backend/tests/unit/test_compositing.py` are the canonical reference for
> coding style, docstring depth, test structure, fixture philosophy, and
> validation approach across feature 007. Read both before implementing any
> other task in this feature.

---

## Context

Assay intervals arrive at irregular lengths — a 0.3 m vein sample sits next to
a 2.0 m bulk sample. Any grade comparison or interpolation made on raw
intervals is biased toward short, high-grade samples, because each sample gets
equal weight regardless of how much rock it represents. Compositing converts
irregular samples into equal-length, length-weighted units so that every
composite represents the same volume of rock.

Every downstream task in this feature consumes composites. Nothing consumes raw
intervals.

---

## Objective

A pure function that turns a list of depth-ordered assay intervals for one hole
or one trench line into a list of fixed-length composites, weighting each
contributing interval by its length, and never compositing across a gap.

---

## Detailed Requirements

### Functional

1. Composite along depth into runs of length `composite_length` (default `1.0`).
2. Each composite's grade is the **length-weighted mean** of the intervals
   overlapping it:
   `grade = sum(gradeᵢ × overlapᵢ) / sum(overlapᵢ)`
3. Intervals with `grade is None` are **excluded**: they contribute neither
   grade nor length. If a composite window has zero assayed length, that
   composite is not emitted at all.
4. **Never composite across a gap.** If the depth gap between consecutive
   intervals exceeds `gap_tolerance` (default `0.01` m), close the current
   composite run and start a new one at the next interval's `from_depth`.
   Compositing restarts from the new `from_depth`, not from a global grid.
5. **Residual handling.** A trailing partial composite shorter than
   `0.5 × composite_length` is merged into the preceding composite in the same
   run (extending it). A trailing partial of `≥ 0.5 × composite_length` is
   emitted as its own composite, with its true `length` recorded. If a run
   produces only one composite and it is shorter than half, emit it anyway —
   never discard sampled ground.
6. Overlapping input intervals are an error: raise `ValueError` naming the two
   overlapping intervals. Do not silently pick one.
7. Inputs are not assumed sorted. Sort by `from_depth` first.
8. `from_depth >= to_depth` on any input is a `ValueError`.

### File Location

- `backend/src/services/compositing.py`
- `backend/tests/unit/test_compositing.py`

### Dependencies allowed

Python standard library only. No numpy in this task.

---

## Interface Contract

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class RawInterval:
    from_depth: float
    to_depth: float
    grade: float | None      # None == logged, never assayed
    sample_id: str | None = None

@dataclass(frozen=True)
class Composite:
    from_depth: float
    to_depth: float
    grade: float             # never None -- unassayed windows are not emitted
    length: float            # to_depth - from_depth
    assayed_length: float    # length actually backed by assayed intervals
    n_source_intervals: int

def composite_intervals(
    intervals: list[RawInterval],
    composite_length: float = 1.0,
    gap_tolerance: float = 0.01,
) -> list[Composite]:
    ...
```

`assayed_length < length` means the composite contains unassayed ground.
Downstream tasks use this to decide whether a composite is trustworthy; it must
be recorded honestly, not clamped to `length`.

---

## Deliverables

| # | File | Description |
|---|---|---|
| 1 | `backend/src/services/compositing.py` | `RawInterval`, `Composite`, `composite_intervals` |
| 2 | `backend/tests/unit/test_compositing.py` | Tests covering every case below |

---

## Test Fixtures (hand-computed — assert exactly these)

**F1 — clean 1 m composite.**
Input: `[(0,1,2.0), (1,2,4.0), (2,3,6.0)]`, length 1.0
Expect: three composites, grades `2.0, 4.0, 6.0`, each `length=1.0`.

**F2 — length weighting.**
Input: `[(0, 0.5, 10.0), (0.5, 2.0, 2.0)]`, length 1.0
Composite 0–1: `(10.0×0.5 + 2.0×0.5) / 1.0` = **6.0**
Composite 1–2: `2.0`
Expect grades `[6.0, 2.0]`. A naive unweighted mean gives `6.0, 2.0` for the
first too only by coincidence — assert the first composite's
`n_source_intervals == 2`.

**F3 — NULL exclusion.**
Input: `[(0, 0.5, 8.0), (0.5, 1.0, None)]`, length 1.0
Expect: one composite, grade **8.0** (not 4.0), `length=1.0`,
`assayed_length=0.5`.
*If your implementation returns 4.0 you have treated NULL as zero. Fix it.*

**F4 — fully unassayed window.**
Input: `[(0, 1.0, None), (1.0, 2.0, 5.0)]`, length 1.0
Expect: exactly one composite, `from_depth=1.0`, grade `5.0`.

**F5 — gap breaks the run.**
Input: `[(0, 1.0, 3.0), (10.0, 11.0, 7.0)]`, length 1.0
Expect: two composites at `0–1` and `10–11`. No composite spans the gap, and
nothing is emitted between 1 and 10.

**F6 — short residual merges.**
Input: `[(0, 1.4, 5.0)]`, length 1.0
Residual 0.4 < 0.5 → merged. Expect **one** composite `0–1.4`, grade `5.0`,
`length=1.4`.

**F7 — long residual stands alone.**
Input: `[(0, 1.8, 5.0)]`, length 1.0
Residual 0.8 ≥ 0.5 → own composite. Expect **two**: `0–1.0` and `1.0–1.8`
(`length=0.8`), both grade `5.0`.

**F8 — overlap raises.**
Input: `[(0, 2.0, 1.0), (1.0, 3.0, 2.0)]` → `ValueError`.

**F9 — unsorted input.**
F1's intervals shuffled must give F1's result.

**F10 — mass balance.** For any input with no NULLs and no gaps:
`sum(grade × length)` over composites equals `sum(grade × length)` over inputs
to within `1e-9`. Assert this on F2 and F7.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | All ten fixtures F1–F10 pass exactly as stated |
| AC-2 | P0 | `grade is None` never contributes to a grade or a length |
| AC-3 | P0 | No composite spans a gap larger than `gap_tolerance` |
| AC-4 | P0 | `composite_intervals` is pure: no I/O, no DB, no globals, no logging |
| AC-5 | P0 | Metal is conserved (AC per F10) |
| AC-6 | P1 | Overlapping and inverted intervals raise `ValueError` with the offending depths in the message |
| AC-7 | P1 | Type hints on every public function; module docstring states the NULL rule |

---

## Anti-Patterns to Avoid

- Using `grade or 0.0` — this converts `None` **and a genuine 0.0 g/t** to zero.
  Test `is None` explicitly.
- Compositing onto a global depth grid starting at 0 regardless of gaps. Runs
  restart at the gap.
- Dropping the residual because "it's only 0.4 m". That 0.4 m may be the vein.
- Rounding grades. Keep full float precision; presentation rounds, not this.
