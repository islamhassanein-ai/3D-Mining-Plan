# Implementation Plan: Phase 2 — Breadth & Scale

**Branch**: `005-phase2-breadth-scale` | **Date**: 2026-07-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/005-phase2-breadth-scale/spec.md`

## Summary

Extend the existing Phase 0/1 backend and frontend with three breadth capabilities
(DXF wireframe import, Shapefile trench/topography import, DXF/PDF/CSV export), three
deferred-field activations (structural/fault data, RQD/core recovery, QA/QC sample
flags), and one scale capability (level-of-detail rendering for dense prospects). No
new top-level project — this is additive to `backend/` and `frontend/` from features
003 and 004.

## Technical Context

**Language/Version**: Unchanged — Python 3.11+ (backend), Vanilla JavaScript
(frontend).

**Primary Dependencies**: Existing stack (FastAPI, SQLAlchemy 2.0, GeoAlchemy2,
Alembic, Pydantic, Three.js) plus three new, narrowly-scoped backend libraries:
`ezdxf` (DXF parsing and writing), `pyshp` (pure-Python Shapefile parsing, no GDAL
dependency), and `reportlab` (2D vector PDF generation for section export). See
Constitution Check below for why these are additions, not violations. No new
frontend dependency — LOD rendering is built on Three.js primitives already in use.

**Storage**: Unchanged — PostgreSQL 16 + PostGIS; uploaded DXF/Shapefile source files
go through the existing storage abstraction from feature 003.

**Testing**: pytest is REQUIRED for DXF/Shapefile parsing correctness and for the new
range-validation rules (RQD/core recovery 0-100%, QA/QC standard out-of-range
flagging) — these carry the same "must not silently corrupt or misrepresent
geological data" risk tier the constitution flags for Phase 0's CSV path. Export
fidelity (DXF/PDF/CSV) is validated manually via `quickstart.md` by opening the
exported files in real software, not asserted byte-for-byte in unit tests. LOD
rendering behavior is validated manually, consistent with features 003/004's testing
scope decisions.

**Target Platform**: Unchanged — desktop web browser; API server on any
Linux-compatible host.

**Project Type**: Web application — extends the existing `backend/`/`frontend/` from
features 003 and 004.

**Performance Goals**: The 3D scene stays smoothly interactive well beyond the Phase
0 baseline (~5,000 intervals) — research.md sets a concrete LOD activation threshold.
Export operations complete promptly for typical project sizes (no specific hard
budget stated in the spec; "promptly" is validated manually per quickstart.md).

**Constraints**: New import/export capabilities must not alter the existing CSV
import path's schema or behavior. LOD/tiling must never reduce data completeness on
inspection or export — only rendering fidelity may degrade (spec Edge Cases). RQD/
core-recovery and QA/QC activation reuse the fields already reserved in the Phase 0
data model; only the two genuinely new entities (Structural Reading, QA/QC Standard
Reference) add new tables.

**Scale/Scope**: Same 1-3 user assumption as prior features. Target dense-prospect
scale for LOD activation: research.md Decision 4.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Geological Data Integrity | **PASS** — DXF/Shapefile parsing follows the same flag-don't-silently-alter discipline as Phase 0's CSV path (FR-002, FR-004); QA/QC out-of-range results are flagged, never auto-corrected (FR-013). |
| II. CRS and Coordinate Rigor | **PASS** — Shapefile imports require the same CRS confirmation as CSV imports (FR-004); no new coordinate system is introduced. |
| III. Boring & Maintainable Architecture | **PASS, with justification for new dependencies** — `ezdxf` and `pyshp` are the standard, single-purpose, pure-Python (no GDAL/native-binary) libraries for their respective formats; `reportlab` is a mature, minimal PDF-generation library. All three are narrowly scoped to one task each, not general-purpose frameworks. Validation logic extends the existing `import_validation.py` module rather than fragmenting across new files, keeping one place for "what makes an import valid." |
| IV. Visual Performance & CAD-Feel | **PASS (by design commitment)** — LOD is implemented as client-side, distance-based visibility management on the existing `InstancedMesh` buffers from feature 003 (research.md Decision 3 there), not a new rendering system. |
| V. Soft Versioning & Audit Trail | **PASS** — Structural Reading rows carry `import_batch_id` like every other importable entity; no hard deletes anywhere in this plan. |
| Technology Stack Constraints | **PASS, with a recommended follow-up** — see note below. |
| Development Workflow & Quality Gates | **PASS** — continues the established `specs/` + `docs/` + `reviews/` structure; spec checklist is 16/16 passing. |

**Technology Stack Constraints — considered explicitly**: The constitution's
Technology Stack Constraints section doesn't name a DXF or Shapefile library, because
Phase 0 was deliberately CSV-only. That same section, however, explicitly says
*"Importing other formats like DXF or Shapefiles is strictly deferred to Phase
2"* — meaning Phase 2 needing these libraries was already anticipated, not merely
tolerated. Choosing which specific library to use (research.md Decisions 1-3) is an
implementation-level decision of the same kind as feature 003's choice of Alembic for
migrations, not a new architectural direction requiring a vote. That said, once these
libraries are adopted, the constitution's Technology Stack Constraints section should
be updated (a MINOR amendment, per its own Governance section) to name them
explicitly for future reference — this plan recommends that follow-up but is not
blocked on it happening first, since it is implementing scope the constitution
already carved out for this exact phase.

No blocking violations identified. Complexity Tracking table is not needed.

**Post-Phase 1 re-check**: `data-model.md`, `contracts/api.md`, and `quickstart.md`
add exactly two new entities (Structural Reading, QA/QC Standard Reference), reuse
every existing entity and endpoint pattern from features 003/004 unchanged, and keep
LOD entirely client-side with no backend/data changes. Nothing in Phase 1 design
widened the three new dependencies beyond their single stated purpose each. All
gates above still **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/005-phase2-breadth-scale/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── api.md
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

Additive to the existing `backend/` and `frontend/` trees from features 003 and 004
— no new top-level directories.

```text
backend/src/models/structural_reading.py    # new
backend/src/models/qaqc_standard.py         # new
backend/src/services/dxf_service.py         # new — parse (import) and write (export)
backend/src/services/shapefile_service.py   # new — parse trench/topography Shapefiles
backend/src/services/pdf_export.py          # new — section view -> PDF
backend/src/services/csv_export.py          # new — drillhole data -> CSV
backend/src/services/import_validation.py   # extended — RQD/core-recovery range
                                             # check, QA/QC out-of-range flagging
backend/src/api/exports.py                  # new — DXF/PDF/CSV export endpoints
backend/src/api/structural.py               # new — structural reading CRUD
backend/src/api/qaqc.py                     # new — QA/QC standard reference CRUD
backend/tests/unit/test_dxf_service.py      # new
backend/tests/unit/test_shapefile_service.py # new
backend/tests/unit/test_rqd_qaqc_validation.py # new

frontend/src/scene/lod_manager.js           # new — distance-based visibility culling
                                             # over feature 003's InstancedMesh buffers
frontend/src/scene/structural_readings.js   # new — fault trace / dip-strike rendering
frontend/src/components/export_panel.js     # new — DXF/PDF/CSV export triggers
frontend/src/components/structural_panel.js # new — enter structural readings
frontend/src/components/qaqc_panel.js       # new — configure standards, view flags
```

**Structure Decision**: Additive to features 003/004's web-application layout. LOD is
deliberately kept backend-unchanged and client-side only (the scene endpoint keeps
returning the full payload; the frontend manages rendering visibility), which is
simpler and sufficient at this project's stated 1-3 user, single-prospect scale
(research.md Decision 4) — avoiding server-side tiling infrastructure that Principle
III would flag as premature complexity.

## Complexity Tracking

*No violations — table not needed.*
