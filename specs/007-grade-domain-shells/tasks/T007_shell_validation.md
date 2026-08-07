# T007 — Shell Geometric and Statistical Validation

> Read `specs/007-grade-domain-shells/tasks.md` first.

| Field | Value |
|---|---|
| **Task ID** | T007 |
| **Priority** | P0 |
| **Dependencies** | T006 |
| **Complexity** | Medium |
| **Status** | TODO |

---

## Context

An unvalidated shell is a picture, not a domain. Three numbers decide whether a
shell is defensible:

- **Watertightness** — an open solid has no inside, so nothing downstream can
  flag blocks by it.
- **Metal capture** — the fraction of contained metal above the threshold that
  actually falls inside the shell. Below ~90% the shell is missing
  mineralisation, usually because the search anisotropy is wrong.
- **Internal dilution** — the fraction of enclosed sample length that is
  *below* threshold. 10–25% is normal; much more means the shell is too
  generous and has smeared waste into the domain.

This task computes them. It does not pass or fail the shell — the geologist
does, with these numbers in front of them.

---

## Objective

A pure function that reports geometric integrity and grade statistics for a
generated shell against the composites it was built from.

---

## Detailed Requirements

### Geometric checks

1. **Watertight** — every edge shared by exactly two faces. Report
   `n_boundary_edges` (shared by one) and `n_nonmanifold_edges` (shared by
   three or more).
2. **Degenerate faces** — count triangles with a repeated vertex index or zero
   area (below `1e-9`).
3. **Duplicate faces** — count faces with identical vertex sets.
4. **Volume** — absolute signed-tetrahedron sum, per component and total.
5. **Bounding box** — min/max easting, northing, elevation.

### Point-in-solid test

6. Implement a ray-casting containment test: cast a ray from the point along
   `+x` and count triangle crossings; odd means inside. Use a fixed, slightly
   irrational direction (e.g. `(1.0, 0.0013, 0.0007)` normalised) to avoid
   degenerate hits through vertices and edges — a pure `+x` ray hits shared
   edges often enough to produce wrong answers on real meshes.
7. Points must be tested against **all** components; inside any component
   counts as inside.

### Statistical checks

8. `metal_capture` = (metal of composites inside the shell) / (metal of **all**
   composites at or above threshold, whether inside or not), where metal is
   `grade × length`. `None` when the denominator is zero.
9. `internal_dilution` = (length of inside composites **below** threshold) /
   (total length of inside composites). `None` when nothing is inside.
10. Report inside/outside counts, mean grades, and total lengths — **broken out
    by sample type**. A shell that captures core well but trenches poorly is a
    specific, diagnosable problem, and pooling the two hides it.
11. Report `n_composites_inside`, `n_composites_above_threshold`,
    and `mean_grade_inside`.

### File Location

- `backend/src/services/shell_validation.py`
- `backend/tests/unit/test_shell_validation.py`

### Dependencies allowed

`numpy` (already present from T005). Nothing new.

---

## Interface Contract

```python
from dataclasses import dataclass, field
from backend.src.services.isosurface import IsosurfaceResult
from backend.src.services.sample_type_comparison import TypedComposite

@dataclass(frozen=True)
class GeometryReport:
    is_watertight: bool
    n_boundary_edges: int
    n_nonmanifold_edges: int
    n_degenerate_faces: int
    n_duplicate_faces: int
    n_components: int
    total_volume: float
    bounding_box: tuple[tuple[float, float, float], tuple[float, float, float]]

@dataclass(frozen=True)
class TypeStats:
    sample_type: str
    n_inside: int
    n_outside: int
    length_inside: float
    mean_grade_inside: float | None

@dataclass(frozen=True)
class StatisticsReport:
    threshold: float
    n_composites_inside: int
    n_composites_above_threshold: int
    metal_capture: float | None
    internal_dilution: float | None
    mean_grade_inside: float | None
    by_sample_type: list[TypeStats]

@dataclass(frozen=True)
class ValidationReport:
    geometry: GeometryReport
    statistics: StatisticsReport
    notes: list[str] = field(default_factory=list)

def validate_shell(
    result: IsosurfaceResult,
    composites: list[TypedComposite],
    threshold: float,
) -> ValidationReport: ...

def point_in_mesh(
    point: tuple[float, float, float],
    component,          # MeshComponent
) -> bool: ...
```

`notes` carries plain-language observations, e.g.
`"metal capture 0.72 is below the 0.90 guideline — consider revising the search anisotropy"`.
These are observations, not verdicts. Never phrase them as pass/fail.

---

## Test Fixtures (hand-computed)

**F1 — unit cube containment.** Build an axis-aligned cube from `(0,0,0)` to
`(10,10,10)` as 12 triangles. Assert:
- `point_in_mesh((5,5,5))` → `True`
- `point_in_mesh((15,5,5))` → `False`
- `point_in_mesh((-1,5,5))` → `False`
- `volume == 1000.0` to `1e-6`
- `is_watertight is True`

**F2 — face-centre and edge robustness.** `point_in_mesh((5,5,0.001))` →
`True`; `(5,5,-0.001)` → `False`. Also test a point on the axis through a cube
vertex, e.g. `(5, 10, 10)` offset inward by `1e-4` → `True`. A naive `+x` ray
gets these wrong.

**F3 — open mesh.** Remove one triangle from F1's cube.
`is_watertight is False`, `n_boundary_edges == 3`.

**F4 — metal capture.** Cube from F1. Composites, all length `1.0`:
inside `(5,5,5) @ 4.0` and `(6,6,6) @ 2.0`; outside `(50,50,50) @ 10.0`.
Threshold `1.0`. All three are above threshold.
`metal_capture = (4+2) / (4+2+10) = 6/16 = 0.375`. Assert exactly.

**F5 — internal dilution.** Add an inside composite `(4,4,4) @ 0.2`, length
`1.0`, threshold `1.0`. Inside length `3.0`, below-threshold inside length
`1.0` → `internal_dilution == 1/3`. Assert to `1e-9`.

**F6 — by sample type.** Mark one inside composite `TR` and the rest `DDH`.
Assert `by_sample_type` has two entries with the right counts.

**F7 — empty shell.** `IsosurfaceResult` with no components →
`n_composites_inside == 0`, `internal_dilution is None`, `metal_capture == 0.0`
(zero captured of a non-zero total — not `None`). No exception.

**F8 — no composites above threshold.** `metal_capture is None`.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | F1–F8 pass, with `0.375` and `1/3` exact |
| AC-2 | P0 | Ray casting is robust to face-, edge-, and vertex-aligned points (F2) |
| AC-3 | P0 | Watertight detection correct for both closed and opened meshes |
| AC-4 | P0 | Statistics are broken out by sample type |
| AC-5 | P0 | `metal_capture` denominator is **all** above-threshold composites, not just the inside ones |
| AC-6 | P0 | Empty and degenerate inputs return a report rather than raising |
| AC-7 | P1 | `notes` are observations; the module emits no pass/fail verdict |

---

## Anti-Patterns to Avoid

- Making `metal_capture` the ratio of inside metal to inside metal. It is
  trivially 1.0 and tells you nothing. The denominator is everything above
  threshold anywhere in the dataset.
- A pure `+x` ray. Real meshes have axis-aligned faces and it will produce
  wrong containment on exactly the vertices a test would check.
- Using a bounding-box test as a stand-in for containment.
- Emitting `is_valid: bool`. The geologist decides. This module reports.
- Pooling sample types in the statistics.
