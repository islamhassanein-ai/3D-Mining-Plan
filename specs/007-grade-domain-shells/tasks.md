# 007 — Gold Grade Domain Shells (Orebody Wireframes)

Generate 3D Au grade-domain shells from the integrated DDH + trench/channel
database already in this project, and render them through the existing
wireframe layer.

**Read this file before opening any individual task file.** Every task file in
`tasks/` assumes the conventions below and does not repeat them.

**Then read [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md).** It records four settled
decisions that are binding on every task, and four open geological questions
that block specific tasks. A task marked blocked there must not be implemented
until its question is answered in that file.

---

## What this feature is, and is not

**Is:** compositing, DDH-vs-trench population comparison, cut-off threshold
support, a distance-weighted grade interpolant, an iso-surface shell at a
chosen threshold, and validation of that shell (watertight, metal capture,
internal dilution).

**Is not:** variography, kriging, block modelling, grade estimation, resource
classification, or reserve reporting. Do not add any of these. The shell this
feature produces is a *domain boundary* — a geometric envelope — not an
estimate. Anything presented as a resource number is out of scope and must not
be produced.

This is decision **D3** in `OPEN_QUESTIONS.md`, and it is binding on output
wording as well as on code: the words "resource", "reserve", "Measured",
"Indicated", "Inferred", "JORC", and "NI 43-101" must not be used to describe
the output anywhere in the API, UI, exports, or docs, and no tonnage or
contained-metal figure may be presented as an estimate. Shell volume and metal
*capture fraction* are permitted — they describe the shell, not the deposit.

## Implementer boundary (D4)

Implement the specified behaviour only. Do not independently change geological
assumptions, coordinate conventions, dip conventions, cut-off values, trench
weighting, or extrapolation rules.

**If a specification is ambiguous, stop and report the ambiguity. Do not invent
a rule.** A plausible invented rule is worse than a blocked task, because it
produces output that looks correct and is not.

---

## Task order and dependencies

| Task | Title | Depends on | DB? | Complexity | Status |
|---|---|---|---|---|---|
| [T001](tasks/T001_compositing.md) | Length-weighted compositing service | — | No | Medium | **Done** — reference implementation |
| [T002](tasks/T002_sample_type_comparison.md) | DDH vs TR/FC population comparison | T001 | No | Medium | **Done** |
| [T003](tasks/T003_threshold_analysis.md) | Cut-off threshold analysis | T001 | No | Medium | **Done** |
| [T004](tasks/T004_composite_points.md) | Composite → 3D point extraction | T001 | Yes | Large | **Done** — see Q5 deviation |
| [T005](tasks/T005_grade_interpolant.md) | Anisotropic IDW grid interpolant | T004 | No | Large | **Blocked — Q1, Q4** |
| [T006](tasks/T006_isosurface.md) | Iso-surface mesh extraction | T005 | No | Medium | **Blocked — Q3** |
| [T007](tasks/T007_shell_validation.md) | Shell geometric + statistical validation | T006 | No | Medium | Ready |
| [T008](tasks/T008_api_endpoint.md) | `POST /projects/{id}/grade-shells` | T004–T007 | Yes | Medium | **Blocked — Q2, Q4** |
| [T009](tasks/T009_frontend_panel.md) | Grade-shell panel + rendering | T008 | — | Medium | **Blocked — Q1, Q2, Q4** |
| [T010](tasks/T010_trench_geometry_decision.md) | Resolve trench geometry (Q5) | T004 | Yes | Small | **Done** |
| [T011](tasks/T011_adel_face_channel_classification.md) | Adel face-channel classification | T004 | Yes | Small | **Done** — source corrected, re-imported |

**T001 is the canonical reference** for coding style, docstring depth, test
structure, fixture philosophy, and validation approach. Read
`backend/src/services/compositing.py` and
`backend/tests/unit/test_compositing.py` before implementing any other task,
and match them.

T001–T003 and T005–T007 are pure functions with no database and no I/O. They
can be implemented and tested in isolation, in any order after their listed
dependency. **Implement and get tests green one task at a time.** Do not open
the next task file until the current one's acceptance criteria all pass.

---

## Project conventions (binding)

**Language / stack.** Python 3.11+, FastAPI, SQLAlchemy 2.0. Frontend is
vanilla ES modules + Three.js — no framework, no build-time TypeScript.

**Imports.** Backend modules are imported as `backend.src.*` from the repo
root. Tests must be run from the repo root:

```bash
venv/Scripts/python.exe -m pytest backend/tests -q -c backend/pytest.ini
```

**New dependencies.** Only `numpy` and `scikit-image` may be added to
`backend/requirements.txt`, and only by the tasks that state so explicitly
(T005 and T006). Add nothing else. In particular: no pandas, no scipy, no
pyvista, no trimesh, no shapely.

**Naming.** `snake_case` for Python, `camelCase` for JavaScript. Service
modules live in `backend/src/services/`, one concern per file. Unit tests go in
`backend/tests/unit/test_<module>.py`.

---

## Domain conventions (binding — getting these wrong invalidates the output)

**Coordinates.** All 3D coordinates in this feature are raw project CRS:
`(easting, northing, elevation)`, elevation increasing upward, metres. **Do not
apply the Three.js Y-up swap anywhere in backend code.** The swap is applied by
the renderer at `frontend/src/scene/wireframes.js`. See the header comment in
`backend/src/services/obj_geometry.py` — it explains exactly this trap.

**Dip sign.** Dip is degrees from horizontal, **downward is negative**
(`-90` = vertical down, `0` = horizontal). This matches
`compute_minimum_curvature_trace()` in `backend/src/services/desurvey.py`.
Azimuth is degrees clockwise from North. Never re-derive a trajectory yourself
— always call the existing desurvey service.

**Grade values.**
- `AssayInterval.grade_value` is `Numeric` and **nullable**. `NULL` means
  *logged but never assayed* — it is **not** `0.0`. A `NULL` interval must be
  excluded from compositing entirely, and its length must not count toward any
  composite's length. Treating `NULL` as zero is the single most damaging bug
  available in this feature; it will silently dilute every shell.
- `below_detection_limit = True` rows keep whatever `grade_value` the importer
  stored. Use it as-is. Do not re-apply a ½-detection-limit rule here — that
  decision was already made at import time.
- `grade_unit` must be uniform across a run. If a project mixes units, raise —
  do not convert.

**Sample types.** `DDH` (from `Collar` rows, `hole_type` `DD` or similar) and
`TR/FC` (from `Trench` rows). These are **different sample support** and must
stay distinguishable end to end. Every composite carries a `sample_type` field.
No function in this feature may pool them without the caller having explicitly
asked for it.

**Superseded records.** Both `AssayInterval` and `Trench` carry
`superseded_by`. Every query in this feature must filter
`superseded_by IS NULL`. A superseded record is a corrected record's ancestor
and must never reach a shell.

**Trench geometry.** A trench is a **polyline**, ordered by `point_order`, not
a point. `Trench.dip` / `azimuth` describe the ground slope **at the collar
point only** — they are not a trajectory. Generated trench sample points stay
at collar elevation (`dz = 0`). This is stated in
`specs/006-combined-csv-import/tasks.md`; do not invent a different rule.

---

## Anti-patterns that apply to every task

- Treating a `NULL` grade as `0.0`.
- Pooling DDH and trench composites without being asked to.
- Forgetting the `superseded_by IS NULL` filter.
- Applying a Y-up axis swap in backend code.
- Compositing across a gap in sampling as if it were continuous ground.
- Adding a dependency not listed above.
- Widening scope into estimation, block models, or tonnage figures.
- Writing a test that asserts a value copied from the implementation's own
  output. Every numeric fixture in these tasks is hand-computed and stated in
  the task file — use those, and if the implementation disagrees with a stated
  fixture, the implementation is wrong.

---

## References

- Data model: `specs/data_model_spec.md`, `docs/architecture_baseline.md`
- Desurvey: `backend/src/services/desurvey.py`
- Existing wireframe path: `backend/src/api/projects.py` (`upload_wireframe`),
  `backend/src/api/scene.py`, `frontend/src/scene/wireframes.js`
- Combined-CSV trench rules: `specs/006-combined-csv-import/tasks.md`
