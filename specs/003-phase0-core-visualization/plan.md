# Implementation Plan: Phase 0 — Core Visualization & Modeling

**Branch**: `003-phase0-core-visualization` | **Date**: 2026-07-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-phase0-core-visualization/spec.md`

## Summary

Build the core drillhole database, CSV import pipeline (with pre-commit validation),
and an interactive Three.js 3D scene (traces, grade-colored intervals, topography,
trenches, wireframes, slicing plane, measurement, and CAD-style navigation) described
in master-plan §3. This is the first feature in this project with a real runtime
software footprint — a FastAPI backend over PostgreSQL/PostGIS, and a vanilla-JS
Three.js frontend, per the constitution's Technology Stack Constraints and the
architecture already fixed in `docs/architecture_baseline.md`.

## Technical Context

**Language/Version**: Python 3.11+ (backend); Vanilla JavaScript (ES2022+) and WebGL
via Three.js (frontend). No frontend framework (constitution forbids
React/Vue/Angular without a constitution amendment).

**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, GeoAlchemy2, Alembic (migrations),
Pydantic (via FastAPI), Three.js. Python's built-in `csv` module for CSV parsing
(see research.md Decision 1 — no pandas dependency).

**Storage**: PostgreSQL 16 + PostGIS. Raw uploaded files on local filesystem under a
dedicated uploads directory in Phase 0, behind a thin storage-abstraction interface
(constitution requirement, to ease the Phase 1 move to S3/MinIO).

**Testing**: pytest for backend logic — mandatory for the minimum-curvature
desurveying algorithm and import-validation rules (constitution Principle I; master
plan §7 risk table explicitly flags this). Frontend correctness (3D rendering, CAD
feel, interaction patterns) is validated manually via `quickstart.md`, not automated
— no JS test framework is introduced (Principle III: no tooling beyond what a solo
maintainer needs).

**Target Platform**: Desktop web browser (Chromium/Firefox-class, WebGL2-capable);
API server on any Linux-compatible host.

**Project Type**: Web application (frontend + backend).

**Performance Goals**: 60fps scene interaction with up to ~5,000 rendered assay
intervals (SC-003); CSV-to-committed-project flow under 60 seconds for a typical
prospect-sized dataset (SC-001); import processing under 30s (per
`docs/architecture_baseline.md` § 4).

**Constraints**: CSV-only import (no DXF/Shapefile in Phase 0); UTM-only coordinate
storage with auto-detect-then-confirm; minimum-curvature desurveying only; no hard
deletes (append + `superseded_by`); every table row traceable to an `import_batch_id`;
instanced rendering required in Three.js for assay/lithology intervals (constitution
Principle IV — explicit, non-negotiable).

**Scale/Scope**: 1-3 users (project owner + occasional colleague); a handful of
projects, each with tens of drillholes and up to a few thousand assay/lithology
intervals.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Geological Data Integrity | **PASS (by design commitment)** — FR-002 mandates minimum-curvature-only desurveying; FR-005 mandates BDL preservation; FR-006 mandates flag-not-autocorrect for overlapping/gap intervals. These become explicit backend service requirements and unit-test targets (see Testing above). |
| II. CRS and Coordinate Rigor | **PASS** — FR-004 mandates UTM-only storage with auto-detect-then-confirm; no local coordinate system is introduced. |
| III. Boring & Maintainable Architecture | **PASS** — Standard layered structure (models/services/api on the backend; scene/components/services on the frontend), no ORM-beyond-SQLAlchemy abstraction, no frontend framework, no bespoke build tooling beyond what FastAPI/Three.js conventionally need. The feature is large (8 user stories) because Phase 0 is inherently one release-worthy increment in the master plan — it is decomposed into independently-testable, priority-ordered user stories rather than split into multiple specs, which is the intended Spec Kit pattern, not a complexity violation. |
| IV. Visual Performance & CAD-Feel | **PASS (by design commitment)** — Three.js `InstancedMesh` is required for assay-interval and lithology-interval rendering (research.md Decision 3); camera controls must implement damped orbit-around-cursor with plan/section/isometric presets (FR-011, FR-012). |
| V. Soft Versioning & Audit Trail | **PASS** — Reuses the `superseded_by` and `import_batch_id` design already reconciled in feature 002's `data-model.md` and carried into `docs/architecture_baseline.md`; no hard deletes anywhere in this plan. |
| Technology Stack Constraints | **PASS** — Stack matches the constitution exactly: Three.js/vanilla JS/CSS frontend, Python 3.11+/FastAPI backend, PostgreSQL 16+PostGIS/SQLAlchemy 2.0/GeoAlchemy2, local filesystem storage in Phase 0, CSV-only import. |
| Development Workflow & Quality Gates | **PASS** — Continues this project's established `specs/` + `docs/` + `reviews/` structure; quality checklist for the spec is 16/16 passing. |

No violations identified. Complexity Tracking table is not needed.

**Post-Phase 1 re-check**: `data-model.md`, `contracts/api.md`, and `quickstart.md`
introduce implementation-level detail (indexes, endpoint contracts, validation
checkpoints) but no new entities, technologies, or architectural decisions beyond
what `docs/architecture_baseline.md` and the constitution already fix. All gates
above still **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/003-phase0-core-visualization/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   └── api.md
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── models/        # SQLAlchemy models: project, collar, survey, assay_interval,
│   │                  # lithology_interval, trench, wireframe, import_batch, user
│   ├── services/      # desurvey (minimum curvature), csv_import, crs (UTM
│   │                  # detection), grade_coloring, measurement (true thickness)
│   ├── api/           # FastAPI routers: projects, imports, scene, auth
│   ├── storage/       # thin object-storage abstraction (local FS now, S3/MinIO
│   │                  # later — Phase 1 swap point)
│   └── db/            # session management, Alembic migrations
└── tests/
    ├── unit/          # desurvey edge-angle cases, import validation rules
    └── integration/   # import -> commit -> query flow

frontend/
├── src/
│   ├── scene/         # Three.js scene, instanced rendering, camera controls,
│   │                  # slicing plane, orientation gizmo
│   ├── components/    # sidebar, inspector panel, toolbar, grade-cutoff slider,
│   │                  # import diff view
│   └── services/      # API client, client-side last-project cache
└── tests/             # none automated (see Technical Context); manual validation
                        # via quickstart.md
```

**Structure Decision**: Standard "web application" layout (Option 2) — frontend and
backend are clearly separate concerns per the constitution's fixed architecture
(`docs/architecture_baseline.md` § 3), with a `storage/` abstraction layer isolated
specifically so the Phase 1 local-filesystem → S3/MinIO migration doesn't touch
business logic.

## Complexity Tracking

*No violations — table not needed.*
