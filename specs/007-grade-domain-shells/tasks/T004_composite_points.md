# T004 — Composite → 3D Point Extraction

> Read `specs/007-grade-domain-shells/tasks.md` first. The domain conventions
> section is load-bearing for this task in particular.

| Field | Value |
|---|---|
| **Task ID** | T004 |
| **Priority** | P0 |
| **Dependencies** | T001 |
| **Complexity** | Large |
| **Status** | TODO |

---

## Context

T001 produces composites in **depth** space. Interpolation needs them in
**3D space**. For a drillhole that means desurveying the composite's midpoint
along the minimum-curvature trace. For a trench it means locating the sample
along the polyline by chainage.

This is the only task in T001–T007 that touches the database, and it is where
the project's real data conventions bite: dip sign, no axis swap, superseded
records, trench polylines that are not trajectories.

---

## Objective

Load a project's assay and trench sample data, composite it, and return a
single flat list of `TypedComposite` records carrying 3D coordinates, ready for
T005.

---

## Detailed Requirements

### Functional — drillholes

1. Query `Collar` rows for the project. For each collar, query its
   `AssayInterval` rows with **`superseded_by IS NULL`**, ordered by
   `from_depth`.
2. Convert to `RawInterval` and composite via T001's `composite_intervals`.
3. Build the hole's trace by calling
   `backend.src.services.desurvey.compute_minimum_curvature_trace()` with the
   collar coordinates and the hole's `Survey` rows. **Do not implement your own
   desurvey.** If the hole has no survey rows, synthesise a single station at
   depth 0 from the collar's own dip/azimuth if present; if neither exists,
   skip the hole and record it in `skipped`.
4. For each composite, take the **midpoint depth**
   `(from_depth + to_depth) / 2` and find its `(x, y, z)` by **linear
   interpolation between the two bracketing trace points** by depth. Depths
   beyond the last trace point are clamped to the last point and the composite
   is flagged in `warnings`.
5. `sample_type = "DDH"`.
6. Skip collars whose `status` is `planned` — a planned hole has no assays, and
   any `grade` on it is a *target*, not a result. Including targets in a grade
   shell would fabricate mineralisation. Record the count in `skipped`.

### Functional — trenches

7. Query `Trench` rows for the project with **`superseded_by IS NULL`**,
   grouped by `trench_id`, ordered by `point_order`.
8. The ordered points form a **polyline**. Compute cumulative chainage along it
   from `point_order = 0`.
9. Trench sample rows carry `from_depth` / `to_depth`, which are **chainage
   along the trench**, not vertical depth. Composite them with T001 exactly as
   for a hole, then place each composite's midpoint chainage on the polyline by
   linear interpolation between the bracketing polyline vertices.
10. Elevation comes from the interpolated polyline vertices' `elevation`. **Do
    not apply `dip` to move the sample below surface** — per the combined-CSV
    rules, trench points stay at collar elevation. If a vertex has
    `elevation is None`, skip that trench and record it.
11. `sample_type` is taken from `hole_type` where it is `TR`, `CH`, or `FC`;
    anything else defaults to `"TR"`.
12. A trench with fewer than 2 points cannot form a polyline. If it has exactly
    one point with a grade, emit a single composite at that point with
    `length = 1.0`, and note it in `warnings`.

### Functional — result

13. Return a result object containing the composites plus a **provenance
    report**: counts by sample type, skipped holes/trenches with reasons, and
    warnings. The API layer surfaces this to the user; it is not optional.
14. Raise `ValueError` if the project's assay rows carry more than one distinct
    non-null `grade_unit`.

### File Location

- `backend/src/services/composite_points.py`
- `backend/tests/unit/test_composite_points.py`
- `backend/tests/integration/test_composite_points_flow.py`

---

## Interface Contract

```python
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from backend.src.services.sample_type_comparison import TypedComposite

@dataclass
class ExtractionReport:
    n_ddh_composites: int = 0
    n_trench_composites: int = 0
    skipped: list[str] = field(default_factory=list)   # "DDH-001: no survey rows"
    warnings: list[str] = field(default_factory=list)
    grade_unit: str | None = None

@dataclass
class ExtractionResult:
    composites: list[TypedComposite]
    report: ExtractionReport

def extract_composite_points(
    db: Session,
    project_id,                       # uuid.UUID
    composite_length: float = 1.0,
) -> ExtractionResult:
    ...
```

`TypedComposite.x/y/z` are populated for every returned composite. A composite
without coordinates must never be emitted — drop it and record why.

---

## Test Fixtures

Unit tests should exercise the geometry helpers directly; use the repo's
existing session fixtures in `backend/tests/conftest.py` for the integration
test, and the CSVs in `backend/fixtures/reference_project/`.

**F1 — vertical hole.** Collar at `(1000, 2000, 500)`, single survey
`depth=0, dip=-90, azimuth=0`, one assay `0–2 m @ 3.0`, composite length 1.0.
Expect two composites at `(1000, 2000, 499.5)` and `(1000, 2000, 498.5)`.
*Elevation decreases with depth.* If your z increases, your dip sign is wrong.

**F2 — inclined hole.** Collar `(0,0,0)`, survey `depth=0, dip=0, azimuth=90`
(horizontal, due East), assay `0–2 @ 1.0`. Expect composites at
`(0.5, 0, 0)` and `(1.5, 0, 0)` — easting increases, northing and elevation
unchanged, to `1e-6`.

**F3 — no axis swap.** In F1, assert `z == 499.5`, i.e. elevation lives in `z`
and northing in `y`. A swapped implementation puts `2000` in `z`.

**F4 — superseded excluded.** Two assay rows over the same interval, one with
`superseded_by` set. Only the live one contributes.

**F5 — planned hole skipped.** A collar with `status='planned'` and target
intervals produces zero composites and one entry in `report.skipped`.

**F6 — trench polyline.** Trench with points at chainage-defining vertices
`(0,0,100)` and `(100,0,100)`, one sample `from=0, to=10, grade=2.0`.
Expect ten 1 m composites at `x = 0.5, 1.5, … 9.5`, all `y=0`, all `z=100`.

**F7 — trench stays at surface.** Give the trench in F6 a `dip = -45`. The
composites' `z` must still be `100`. Dip is ground slope metadata, not a
trajectory.

**F8 — mixed units raise.** Two assays, `g/t` and `ppm` → `ValueError`.

**F9 — report populated.** For a project with one hole and one trench,
`report.n_ddh_composites` and `n_trench_composites` are both non-zero and
`report.grade_unit` is set.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | F1–F9 pass |
| AC-2 | P0 | Desurvey is delegated to `desurvey.compute_minimum_curvature_trace` — no reimplementation |
| AC-3 | P0 | Every query filters `superseded_by IS NULL` |
| AC-4 | P0 | Planned holes contribute nothing |
| AC-5 | P0 | No axis swap; `(x,y,z) == (easting, northing, elevation)` |
| AC-6 | P0 | Trench composites keep polyline elevation; dip is never applied as a trajectory |
| AC-7 | P0 | Every skipped hole/trench appears in `report.skipped` with a reason |
| AC-8 | P1 | Integration test runs against the reference-project fixtures and passes |

---

## Anti-Patterns to Avoid

- Re-deriving the trace with `sin`/`cos` "because it's just a straight hole".
  Call the service. It handles the sign convention and the dogleg correctly.
- Placing a composite at its `from_depth` rather than its midpoint.
- Treating `Trench.from_depth` as vertical depth. It is chainage along the
  trench floor.
- Including planned-hole target grades. They are a drilling proposal, and
  turning them into an orebody shell manufactures a deposit that does not exist.
- Returning composites with `None` coordinates and letting T005 deal with it.
