# T004 — Composite → 3D Point Extraction

> Read `specs/007-grade-domain-shells/tasks.md` first. The domain conventions
> section is load-bearing for this task in particular.

| Field | Value |
|---|---|
| **Task ID** | T004 |
| **Priority** | P0 |
| **Dependencies** | T001 |
| **Complexity** | Large |
| **Status** | **DONE — with a specification deviation** |

> Implemented in `backend/src/services/composite_points.py`, with 23 unit tests
> and 15 integration tests. `backend/analyze_sample_types.py` runs the T002
> comparison against a real project.
>
> **Requirements 8–10 below were not implemented as written.** They call for
> compositing trench samples along `from_depth`/`to_depth` as chainage and
> interpolating position along the polyline. The real database does not support
> it: chainage is not unique (paired face samples share a chainage but differ by
> ~1 m in elevation and by up to 18 g/t), no polyline exists in the schema
> independent of the sample coordinates, and 173 assayed legacy rows carry no
> chainage. Each assayed trench row instead becomes one composite at the
> coordinates it states.
>
> Investigated in full in
> [`../analysis/Q5_trench_geometry_findings.md`](../analysis/Q5_trench_geometry_findings.md);
> the decision is [`T010`](T010_trench_geometry_decision.md), which will rewrite
> requirements 8–10 to match whatever is chosen.
>
> Two smaller corrections to this spec: the collar status column is
> `hole_status`, not `status`; and `Collar` has no dip/azimuth, so a hole with
> no survey rows is skipped rather than given a synthesised station.

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
   desurvey.** A hole with no survey rows is **skipped and recorded in
   `skipped`** — `Collar` carries no dip or azimuth of its own, so there is
   nothing to synthesise a station from, and assuming a vertical hole (as
   `scene.py` does so that something is drawn) would place real assays at
   invented coordinates that go on to shape a shell.
   Extend the trace to the deepest composite with
   `downhole_log.compute_total_depth` and `extend_trace_to_depth` before
   sampling it; survey stations routinely stop short of the deepest assay, and
   without extending, every composite past the last station clamps onto one
   coordinate.
4. For each composite, take the **midpoint depth**
   `(from_depth + to_depth) / 2` and find its `(x, y, z)` with
   `downhole_log.interpolate_trace_position`, which interpolates between the
   bracketing trace points at an **absolute depth measured from the collar**.
   Warn when the assays run deeper than the surveys.
5. `sample_type = "DDH"` for every collar-borne composite, including `RC`.
   See Q6 — RC is currently pooled with diamond core. Adel contains no RC, so
   nothing turns on it today; report the split via
   `collars_by_hole_type` so the pooling stays visible.
6. Skip collars whose **`hole_status`** is `planned` (the column is
   `hole_status`, not `status`; `NULL` reads as drilled) — a planned hole has no
   assays, and any `grade` on it is a *target*, not a result. Including targets
   in a grade shell would fabricate mineralisation. Record each in `skipped`.
   Also skip, defensively, any collar whose `hole_type` is a trench type.

### Functional — trenches

> Requirements 8–10 were **rewritten on 2026-08-08** after the original chainage
> rule proved unimplementable against the real database. The investigation is
> [`../analysis/Q5_trench_geometry_findings.md`](../analysis/Q5_trench_geometry_findings.md);
> the resolution is [`T010`](T010_trench_geometry_decision.md).

7. Query `Trench` rows for the project with **`superseded_by IS NULL`**,
   **explicitly ordered** by `trench_id`, `point_order`, `id`, then grouped by
   `trench_id`. The `id` tiebreak matters: legacy rows carry no `point_order`,
   and without a total order their sequence is whatever the planner returns.
8. **Each assayed trench row is one composite.** Trench samples are **not**
   composited along chainage and no position is interpolated. The row's stored
   `easting`/`northing`/`elevation` are accurate and authoritative and mark the
   **midpoint of the sample interval** — confirmed from Adel field data — which
   makes trench placement consistent with the drillhole path, where composites
   are also placed at their midpoint.
9. **Chainage gives length, not position.** `length = to_depth - from_depth`
   where both are present. Chainage cannot position a sample because it is not
   unique: Adel's face lines carry paired samples sharing a chainage about a
   metre apart in elevation, reading 0.06 against 7.86 g/t in one case. Nor is
   there a stored polyline to interpolate along — the table holds points, and
   the line is only those points joined.
10. Where no length is stated, `length_when_unspecified` decides: `None` (the
    default) **excludes the row and warns**, rather than inventing a sample
    support; a stated number includes it under that assumption. All 424 Adel
    trench rows carry chainage, so this path is generic handling and needs no
    geological default.
11. **Never apply `dip` to move a trench sample below surface** — per the
    combined-CSV rules it is ground slope at the start point, not a trajectory.
    A row with an incomplete position is excluded and warned about.
12. `sample_type` is taken from `hole_type` where it is `TR`, `CH`, or `FC`,
    upper-cased; anything else defaults to `"TR"`. The classification belongs in
    the data — **no `trench_id` string matching in any service** (see T011).

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
    project_id,                       # uuid.UUID or str
    composite_length: float = 1.0,
    trench_length_when_unspecified: float | None = None,
) -> ExtractionResult:
    ...
```

The implemented `ExtractionReport` carries more than the sketch above — every
record that does not become a composite is accounted for:
`composites_by_type`, `collars_by_hole_type`, `n_collars_considered`,
`n_trench_lines_considered`, `n_assay_intervals_read`, `n_trench_rows_read`,
`n_unassayed_assay_intervals`, `n_unassayed_trench_rows`, alongside `skipped`,
`warnings` and `grade_unit`.

The transformation is kept separate from the querying so it can be tested
without a database:

```python
def build_drillhole_composites(collar, surveys, intervals, composite_length=1.0)
    -> tuple[list[TypedComposite], list[str]]

def build_trench_composites(points, length_when_unspecified=None)
    -> tuple[list[TypedComposite], list[str], int]
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

**F5 — planned hole skipped.** A collar with `hole_status='planned'` and target
intervals produces zero composites and one entry in `report.skipped`.

**F6 — trench sample sits where its row says.** Two rows at `(100,200,300)` and
`(110,200,300)`, samples `0–1 @ 2.0` and `1–2 @ 4.0`. Expect two composites at
exactly those coordinates, each `length = 1.0`. Nothing is interpolated.

**F7 — trench stays at surface.** Give a trench row `dip = -45`. Its composite's
`z` must still be the row's stated elevation. Dip is ground slope metadata, not
a trajectory.

**F7b — paired chainage does not collide.** Four rows, two at chainage `0–1`
and two at `1–2`, at distinct coordinates (Adel's AAF002 pattern). Expect
**four** composites, all four grades preserved. Compositing along chainage would
raise on the overlap; placing each row at its own coordinates keeps them.

**F7c — no stated length.** A row with `from_depth`/`to_depth` NULL is excluded
and warned about by default, and included with the given length when
`length_when_unspecified` is passed.

**F7d — deterministic order.** Two extractions of the same project, including
rows with `point_order IS NULL`, return identical composites in identical
order.

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
| AC-6 | P0 | Trench composites keep the elevation their row states; dip is never applied as a trajectory |
| AC-7 | P0 | Every skipped hole/trench appears in `report.skipped` or `report.warnings` with a reason |
| AC-8 | P0 | The trench query has a total `ORDER BY`, and extraction is deterministic |
| AC-9 | P0 | No `trench_id` (or any hole-name) string matching anywhere in `backend/src/services/` |
| AC-10 | P1 | The pure builders are unit-tested without a database |

---

## Anti-Patterns to Avoid

- Re-deriving the trace with `sin`/`cos` "because it's just a straight hole".
  Call the service. It handles the sign convention and the dogleg correctly.
- Placing a composite at its `from_depth` rather than its midpoint.
- Treating `Trench.from_depth` as vertical depth. It is chainage along the
  trench, and it gives the sample's **length**, not its position.
- Deriving a sample type from a hole or trench name. The classification belongs
  in the data; a prefix match in a service reclassifies future datasets by
  accident and leaves every other consumer of the table reading the old value.
- Reading trenches without a total `ORDER BY` because "it seems to come back in
  order anyway".
- Including planned-hole target grades. They are a drilling proposal, and
  turning them into an orebody shell manufactures a deposit that does not exist.
- Returning composites with `None` coordinates and letting T005 deal with it.
