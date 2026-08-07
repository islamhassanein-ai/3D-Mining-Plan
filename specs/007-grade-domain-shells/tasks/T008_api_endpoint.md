# T008 — Grade-Shell API Endpoints

> Read `specs/007-grade-domain-shells/tasks.md` first.

| Field | Value |
|---|---|
| **Task ID** | T008 |
| **Priority** | P0 |
| **Dependencies** | T004, T005, T006, T007 |
| **Complexity** | Medium |
| **Status** | **BLOCKED — Q2, Q4** |

> ## Blocked: do not implement yet
>
> **Q2** — the default threshold list on `GET /grade-analysis` and the single
> default generation threshold are unconfirmed. **Q4** — whether the ellipsoid
> ranges and orientation are required inputs or carry defaults is undecided,
> and that changes the Pydantic model directly.
>
> Both are in [`../OPEN_QUESTIONS.md`](../OPEN_QUESTIONS.md). The example
> request body below uses illustrative values, not approved defaults.
>
> Also binding: **D3** — no response field, message, or persisted label may
> describe the output as a resource or reserve, and no tonnage figure may be
> returned.

---

## Context

T001–T007 are pure services. This task wires them into the app: two analysis
endpoints that let the geologist choose a threshold with evidence, and one
generation endpoint that builds the shell and persists it as a `Wireframe` row
so the existing scene and export paths render it with no further work.

Study `backend/src/api/projects.py::upload_wireframe` before writing anything —
it is the pattern for storage, the `Wireframe` row, and the response shape.
Match it rather than inventing a parallel one.

---

## Objective

Three endpoints on the existing projects router, reusing the project's auth,
ownership, and storage conventions.

---

## Detailed Requirements

### Endpoints

**1. `GET /projects/{project_id}/grade-analysis`**

Query params: `composite_length` (default `1.0`), `thresholds` (repeatable
float; default `[0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0]`).

Runs T004 → T002 → T003. Returns sample-type comparison, log-probability
points, and the metal-capture table, plus T004's extraction report. No shell is
built and nothing is written.

**2. `GET /projects/{project_id}/grade-analysis/contact?threshold=0.5`**

Runs T004 → T003's `contact_analysis` at one threshold. Separate endpoint
because it is per-threshold and more expensive.

**3. `POST /projects/{project_id}/grade-shells`**

Body:

```json
{
  "name": "Main Zone 0.5 g/t shell",
  "threshold": 0.5,
  "composite_length": 1.0,
  "cell_size": 5.0,
  "ellipsoid": {
    "range_major": 80.0, "range_semi": 40.0, "range_minor": 15.0,
    "strike_azimuth": 45.0, "dip": -70.0
  },
  "power": 2.0,
  "max_samples": 16,
  "min_samples": 2,
  "sample_type_weights": {"DDH": 1.0, "TR": 0.5},
  "min_volume": 0.0,
  "split_components": true
}
```

Runs T004 → T005 → T006 → T007, writes the OBJ via the storage backend, and
creates a `Wireframe` row with **`solid_type = "grade_shell"`**.

Response includes the wireframe `id`, `name`, `solid_type`, `file_ref`, plus
the full T007 `ValidationReport` and the parameters used.

### Persistence and provenance

1. Store the OBJ using the existing storage abstraction
   (`backend/src/storage/`), filename pattern
   `grade_shell_{uuid4().hex}_{safe_name}.obj`.
2. **The generation parameters must be persisted**, not just returned. A shell
   whose threshold and search ellipsoid are unknown is not defensible and
   cannot be reproduced. Add a nullable `parameters` JSON column to
   `wireframe` via a new Alembic migration in
   `backend/alembic/versions/`, following the existing migration style, and
   store the full request plus the validation report there.
3. Migration must have a working `downgrade()`.
4. `Wireframe.solid_type == "grade_shell"` is the marker the frontend keys on.
   Do not reuse `"topography"` or a blank type.

### Behaviour

5. Reuse the router's existing auth and project-ownership dependencies exactly
   as the neighbouring endpoints do. A user must not reach another user's
   project through these.
6. Validate the request: `threshold > 0`, all ranges `> 0`, `cell_size > 0`,
   `min_samples >= 1`, `max_samples >= min_samples`. Return `422` with a clear
   message otherwise — Pydantic validators are the right place.
7. **Guard the grid size.** Compute `nx*ny*nz` from the bounding box and
   `cell_size` before interpolating. If it exceeds `20_000_000` nodes, return
   `400` with a message naming the computed node count and suggesting a larger
   `cell_size`. Without this, a 1 m cell over a 3 km property will exhaust
   memory and take the server down.
8. If T004 returns no composites, return `400` — "no assayed intervals found
   for this project" — rather than writing an empty shell.
9. If T006 finds no surface at the threshold, return `200` with a `wireframe`
   of `null` and a message saying no material meets the threshold. This is a
   legitimate geological answer, not an error.
10. Requests are synchronous. Do not add a job queue, Celery, or background
    tasks — the app has none and this task is not the place to introduce one.

### File Location

- Extend `backend/src/api/projects.py` (or a new `backend/src/api/grade_shells.py`
  registered in `backend/src/api/main.py` if the router file is already large —
  either is acceptable, but follow the existing registration pattern).
- `backend/alembic/versions/<hash>_add_wireframe_parameters.py`
- `backend/tests/integration/test_grade_shell_flow.py`

---

## Test Fixtures

Use `backend/fixtures/reference_project/` and the existing conftest fixtures.

**F1** — `GET /grade-analysis` on the reference project returns `200` with
non-empty `metal_capture` rows and a populated extraction report.

**F2** — `POST /grade-shells` with sane parameters returns `200`, creates
exactly one `Wireframe` row with `solid_type == "grade_shell"`, and the stored
file parses through `obj_geometry.parse_obj` into non-empty vertices and faces.

**F3** — the created row's `parameters` JSON contains the threshold and the
ellipsoid, and round-trips.

**F4** — `threshold` of `-1.0` → `422`. `cell_size` of `0` → `422`.

**F5** — a `cell_size` small enough to blow the node budget → `400` with the
node count in the message, and **no** `Wireframe` row created.

**F6** — a threshold far above every assay → `200`, `wireframe` is `null`, no
row created, no file written.

**F7** — a project with no assays → `400`.

**F8** — another user's project → the same status the neighbouring endpoints
return for that case (check `project_access.py`; match it, don't invent one).

**F9** — the generated shell appears in `GET /projects/{id}/scene`'s
`wireframes` list without any change to `scene.py`. If it doesn't, the smallest
correct fix in `scene.py` is in scope; a parallel scene path is not.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | F1–F9 pass |
| AC-2 | P0 | Generation parameters and validation report are persisted, not just returned |
| AC-3 | P0 | Alembic migration applies and downgrades cleanly |
| AC-4 | P0 | Auth/ownership reuses existing dependencies — no new auth path |
| AC-5 | P0 | Node-count guard prevents runaway grids and writes nothing on rejection |
| AC-6 | P0 | Storage goes through `backend/src/storage/`, never raw `open()` |
| AC-7 | P0 | No shell row or file is created on any error path |
| AC-8 | P1 | Empty-surface case is a `200`, not an error |
| AC-9 | P1 | Existing test suite still passes |

---

## Anti-Patterns to Avoid

- Writing files with `open()` and a hard-coded `uploads/` path. There is a
  storage abstraction; use it.
- Returning the shell without its parameters. An unreproducible shell is
  worthless for reporting, which is the entire reason this feature exists.
- Editing an existing Alembic migration instead of adding a new one.
- Building the grid before checking its size.
- Introducing a task queue, websockets, or progress streaming.
- Treating "no material above threshold" as a `500`.
