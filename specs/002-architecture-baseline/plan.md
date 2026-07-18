# Implementation Plan: Core Platform Architecture Baseline

**Branch**: `002-architecture-baseline` | **Date**: 2026-07-16 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-architecture-baseline/spec.md`

## Summary

Consolidate Sections 2, 6, 7, 8, and 9 of `mining_tool_planning_Final_claude4-7-2026.md`
— Product Definition, Data Model, System Architecture, Non-Functional Requirements, and
UX/UI Direction — plus the ratified project constitution, into one authoritative
reference document (`docs/architecture_baseline.md`) that every future Phase 0 feature
spec can be checked against without re-reading the master planning doc. This feature
produces no runtime code; its only output is that single Markdown document.

## Technical Context

**Language/Version**: N/A — this feature produces a Markdown reference document, not
executable code.

**Primary Dependencies**: N/A

**Storage**: N/A — a git-tracked Markdown file in the repository; no database or
external storage involved.

**Testing**: N/A — no automated tests apply to a static reference document.
Correctness is validated via the mechanical checklist in `quickstart.md` (structural
and content-fidelity checks), the same approach used for feature
001-panel-gap-check-tension-log.

**Target Platform**: Markdown document consulted by the project owner and any AI
implementer during future feature specification and planning work.

**Project Type**: Single documentation artifact — not a runtime software project.

**Performance Goals**: N/A for this feature itself. The document *records* the
product's performance targets (FR-012 — frame-rate, import time budget) as reference
content that future Phase 0 rendering/import work must satisfy; this feature does not
build or measure that behavior.

**Constraints**: MUST NOT introduce new architecture, data-model, or NFR decisions
beyond what Sections 2/6/7/8/9 of the master planning document and constitution v1.0.0
already establish (spec Assumptions). MUST NOT duplicate concrete technology
names/versions outside the constitution's Technology Stack Constraints section, to
avoid two independently-editable sources of the same fact (checklist note in
`checklists/requirements.md`).

**Scale/Scope**: One reference document covering 9 entities, 5 requirement areas
(FR-001–FR-015), and 6 success criteria (SC-001–SC-006).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Assessment |
|---|---|
| I. Geological Data Integrity | **PASS** — The document restates (does not alter) the minimum-curvature, BDL-preservation, and interval-flagging rules already ratified in the constitution. No data-handling logic is implemented by this feature. |
| II. CRS and Coordinate Rigor | **PASS** — The document restates UTM-only storage and the auto-detect-then-confirm import flow; no code is produced that could violate it. |
| III. Boring & Maintainable Architecture | **PASS** — The deliverable is a single Markdown file with no frameworks or abstractions. The Three-Tier AI Workflow (tasks/outputs/reviews) is satisfied via this project's established equivalent: `specs/` for requirements and `docs/` for durable reference output (the same pattern feature 001 established using `reviews/` for its point-in-time artifact). |
| IV. Visual Performance & CAD-Feel | **N/A for this feature** — No rendering code is produced. The document records the 60fps/CAD-control targets as reference content for future Phase 0 work to satisfy. |
| V. Soft Versioning & Audit Trail | **PASS (by analogy)** — FR-015 requires this document to be amended, never silently contradicted, mirroring the append/supersede spirit of the principle even though it governs a document rather than a database row. |
| Technology Stack Constraints | **PASS** — No new technology is introduced. The document deliberately avoids re-naming stack choices, deferring to the constitution as the single source of truth (see Constraints above). |
| Development Workflow & Quality Gates | **PASS** — This plan continues the same `specs/` + supporting-artifact structure already in use; the quality checklist for the spec is complete (15/16, one knowingly-accepted exception documented in its Notes). |

No violations identified. Complexity Tracking table is not needed.

**Post-Phase 1 re-check**: `data-model.md` added a `superseded_by` field to every
importable/correctable entity, which the source planning document's ERD omitted but
constitution Principle V requires. This is a reconciliation toward stricter
compliance, not a new violation — see `data-model.md`'s Reconciliation Note. All gates
above still **PASS**.

## Project Structure

### Documentation (this feature)

```text
specs/002-architecture-baseline/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

No `contracts/` directory: this feature exposes no API, CLI, or other external
interface — its only output is a Markdown document.

### Source Code (repository root)

```text
docs/
└── architecture_baseline.md   # The single deliverable this feature produces
```

**Structure Decision**: This feature has no source code footprint. Its only output is
`docs/architecture_baseline.md`, a new git-tracked reference document at the
repository root (parallel to `reviews/phase0_review.md` from feature
001-panel-gap-check-tension-log, but under `docs/` since this is a durable,
forward-looking baseline rather than a point-in-time approval record). No `src/` or
`tests/` directories apply.

## Complexity Tracking

*No violations — table not needed.*
