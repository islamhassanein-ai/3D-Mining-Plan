---

description: "Task list for feature implementation"
---

# Tasks: Core Platform Architecture Baseline

**Input**: Design documents from `specs/002-architecture-baseline/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (all
present). No `contracts/` â€” this feature exposes no API/CLI interface.

**Tests**: Not applicable â€” this feature produces a Markdown document, not executable
code. No test tasks are included; correctness is checked via `quickstart.md`.

**Note for the executor**: Every task below is self-contained. It names the exact
source (a line range in `mining_tool_planning_Final_claude4-7-2026.md`, a section of
`specs/002-architecture-baseline/data-model.md`, or a section of
`.specify/memory/constitution.md`) and the exact target section of
`docs/architecture_baseline.md` to fill in. Do not skip ahead or infer content that
isn't explicitly quoted or referenced â€” condense/restructure into the target section,
do not paraphrase into new claims. **Do not fabricate verification results** (e.g., a
timing or approval claim) â€” if a task requires a human check, say so honestly rather
than inventing a number, exactly as called out in T024 below.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1â€“US5)
- All tasks in this feature write to the same single file,
  `docs/architecture_baseline.md`, so **no task below is marked [P]** â€” they must run
  in the sequence given to avoid overwriting each other's edits.

## Path Conventions

- Deliverable: `docs/architecture_baseline.md` (repository root)
- Design docs: `specs/002-architecture-baseline/` (already created by `/speckit-plan`)
- Source material: `mining_tool_planning_Final_claude4-7-2026.md` (repository root)
- Governance source: `.specify/memory/constitution.md`

---

## Phase 1: Setup

**Purpose**: Create the deliverable file with its full structural skeleton, empty.

- [X] T001 Create the `docs/` directory at the repository root if it does not already
  exist. Create `docs/architecture_baseline.md` with exactly this skeleton (copy
  verbatim, do not fill in values yet):

  ```markdown
  # Core Platform Architecture Baseline

  **Source Reference**: TBD
  **Status**: draft

  ## 1. Product Definition

  - **Vision**: TBD
  - **Target Users / JTBD**: TBD
  - **V1 Non-Goals**: TBD
  - **Kill Criterion**: TBD

  ## 2. Data Model

  ### Entities

  TBD

  ### Rules

  - **CRS / Coordinates**: TBD
  - **Units & Below-Detection-Limit Handling**: TBD
  - **Bad Import Handling**: TBD

  ## 3. System Architecture

  - **Rendering Approach**: TBD
  - **Component Boundaries**: TBD
  - **Multi-Tenancy Model**: TBD
  - **Client/Server Processing Split**: TBD
  - **Technology Stack**: TBD

  ## 4. Non-Functional Requirements

  - **Security / Isolation**: TBD
  - **Audit / Provenance**: TBD
  - **Performance Targets**: TBD
  - **Offline / Field Use**: TBD

  ## 5. UX/UI Direction

  - **Visual Theme & Interface Regions**: TBD
  - **Core Interaction Patterns**: TBD

  ## Governance of This Document

  TBD
  ```

**Checkpoint**: `docs/architecture_baseline.md` exists with all 5 numbered sections
and the Governance footer present, in this exact order.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fill in the header field every later task depends on.

**âš ï¸ CRITICAL**: Complete before any section-filling task.

- [X] T002 In `docs/architecture_baseline.md`, replace `**Source Reference**: TBD`
  with: `**Source Reference**: mining_tool_planning_Final_claude4-7-2026.md, Sections 2, 6, 7, 8, 9; reconciled via specs/002-architecture-baseline/{spec.md, data-model.md}; aligned with project constitution v1.0.0 (.specify/memory/constitution.md)`.
  Leave every other line unchanged.

**Checkpoint**: Source Reference field is filled. Section-filling work can now begin.

---

## Phase 3: User Story 1 - Product Definition (Priority: P1) ðŸŽ¯ MVP (part 1 of 5)

**Goal**: Section 1 of `docs/architecture_baseline.md` states the vision, target
users, non-goals, and kill criterion.

**Independent Test**: Open `docs/architecture_baseline.md` and confirm all 4 bullets
under "1. Product Definition" have non-`TBD` content.

### Implementation for User Story 1

- [X] T003 [US1] In `docs/architecture_baseline.md` Â§ 1 Product Definition, replace
  `- **Vision**: TBD` and `- **Target Users / JTBD**: TBD` using only the text from
  `mining_tool_planning_Final_claude4-7-2026.md` lines 74 (the `**Vision:**` line) and
  76 (the `**Target users / JTBD:**` line). Keep the original wording; do not add new
  claims.
- [X] T004 [US1] In `docs/architecture_baseline.md` Â§ 1 Product Definition, replace
  `- **V1 Non-Goals**: TBD` using only the text from
  `mining_tool_planning_Final_claude4-7-2026.md` line 78 (the `**V1 Non-goals:**`
  line). List each non-goal as its own sub-bullet.
- [X] T005 [US1] In `docs/architecture_baseline.md` Â§ 1 Product Definition, replace
  `- **Kill Criterion**: TBD` using only the text from
  `mining_tool_planning_Final_claude4-7-2026.md` line 80 (the `**Kill criterion...**`
  line), including what happens when it's triggered.

**Checkpoint**: Section 1 fully filled. FR-001, FR-002, FR-003 satisfied.

---

## Phase 4: User Story 2 - Data Model (Priority: P1) ðŸŽ¯ MVP (part 2 of 5)

**Goal**: Section 2 of `docs/architecture_baseline.md` lists all 9 entities and the
CRS/units/BDL/bad-import rules.

**Independent Test**: Open `docs/architecture_baseline.md` and confirm Â§ 2 Data Model
lists all 9 entities from `data-model.md` (including the `superseded_by`
reconciliation) and all 3 Rules bullets have non-`TBD` content.

### Implementation for User Story 2

- [X] T006 [US2] In `docs/architecture_baseline.md` Â§ 2 Data Model â†’ Entities, replace
  `TBD` with a compact bullet list of all 9 entities from
  `specs/002-architecture-baseline/data-model.md` Â§ Entities: Project, Collar,
  Survey, Assay Interval, Lithology Interval, Trench, Wireframe, Import Batch, User.
  For each, use the format `**<Entity>**: <key fields> â€” <relationship>`, and include
  the `superseded_by` field where `data-model.md` lists it (Project, Collar, Assay
  Interval, Lithology Interval). Use only what `data-model.md` states; do not invent
  fields.
- [X] T007 [US2] In `docs/architecture_baseline.md` Â§ 2 Data Model â†’ Rules, replace
  `- **CRS / Coordinates**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 204 (the "CRS / units / BDL
  handling" paragraph, coordinate-storage portion) plus the `utm_zone` bullet from
  `data-model.md` Â§ Validation Rules.
- [X] T008 [US2] In `docs/architecture_baseline.md` Â§ 2 Data Model â†’ Rules, replace
  `- **Units & Below-Detection-Limit Handling**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 204 (the unit/BDL portion) plus
  the `grade_unit` and `below_detection_limit` bullets from `data-model.md` Â§
  Validation Rules.
- [X] T009 [US2] In `docs/architecture_baseline.md` Â§ 2 Data Model â†’ Rules, replace
  `- **Bad Import Handling**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` lines 206-212 (the error-handling
  table: missing/wrong UTM zone, mixed units, swapped lat/long, overlapping/gap
  intervals) plus the matching bullets from `data-model.md` Â§ Validation Rules.

**Checkpoint**: Section 2 fully filled. FR-004, FR-005, FR-006, FR-007 satisfied.

---

## Phase 5: User Story 3 - System Architecture (Priority: P1) ðŸŽ¯ MVP (part 3 of 5)

**Goal**: Section 3 of `docs/architecture_baseline.md` states the architecture
decisions, with technology names appearing only in the Technology Stack line.

**Independent Test**: Open `docs/architecture_baseline.md` and confirm all 5 bullets
under "3. System Architecture" have non-`TBD` content, and that no concrete
technology name (rendering library, backend framework, database product) appears
anywhere in this section except the "Technology Stack" bullet.

### Implementation for User Story 3

- [X] T010 [US3] In `docs/architecture_baseline.md` Â§ 3 System Architecture, replace
  `- **Rendering Approach**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` lines 218-227 (the frontend
  rendering trade-off table and recommendation). Describe the approach and reasoning
  in category terms (e.g., "an open-source, CAD-capable 3D rendering library" rather
  than naming it) â€” the concrete name belongs only in T014's Technology Stack line.
- [X] T011 [US3] In `docs/architecture_baseline.md` Â§ 3 System Architecture, replace
  `- **Component Boundaries**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` lines 229-237 (the architecture
  diagram: browser client, API server, parsing/ETL service, database, object
  storage, auth service, and how they connect). Describe the connections in prose;
  do not name specific products.
- [X] T012 [US3] In `docs/architecture_baseline.md` Â§ 3 System Architecture, replace
  `- **Multi-Tenancy Model**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 239 (the multi-tenancy model
  paragraph).
- [X] T013 [US3] In `docs/architecture_baseline.md` Â§ 3 System Architecture, replace
  `- **Client/Server Processing Split**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 241 (the performance approach
  paragraph: what runs server-side vs. client-side).
- [X] T014 [US3] In `docs/architecture_baseline.md` Â§ 3 System Architecture, replace
  `- **Technology Stack**: TBD` with a single line naming the rendering library,
  backend framework, and database product from `.specify/memory/constitution.md` Â§
  Technology Stack Constraints (lines 116-130), followed by:
  `See .specify/memory/constitution.md Â§ Technology Stack Constraints for the authoritative list â€” not restated here.`
  Do not copy versions or rationale into this document.

**Checkpoint**: Section 3 fully filled. FR-008, FR-009, FR-010, FR-011 satisfied.

---

## Phase 6: User Story 4 - Non-Functional Requirements (Priority: P2) (part 4 of 5)

**Goal**: Section 4 of `docs/architecture_baseline.md` states the four NFR
baselines.

**Independent Test**: Open `docs/architecture_baseline.md` and confirm all 4 bullets
under "4. Non-Functional Requirements" have non-`TBD` content.

### Implementation for User Story 4

- [X] T015 [US4] In `docs/architecture_baseline.md` Â§ 4 Non-Functional Requirements,
  replace `- **Security / Isolation**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 247 (the Security/isolation
  bullet).
- [X] T016 [US4] In `docs/architecture_baseline.md` Â§ 4 Non-Functional Requirements,
  replace `- **Audit / Provenance**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 248 (the Audit/provenance
  bullet).
- [X] T017 [US4] In `docs/architecture_baseline.md` Â§ 4 Non-Functional Requirements,
  replace `- **Performance Targets**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 249 (the Performance targets
  bullet).
- [X] T018 [US4] In `docs/architecture_baseline.md` Â§ 4 Non-Functional Requirements,
  replace `- **Offline / Field Use**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 250 (the Offline/field use
  bullet).

**Checkpoint**: Section 4 fully filled. FR-012 satisfied.

---

## Phase 7: User Story 5 - UX/UI Direction (Priority: P2) (part 5 of 5)

**Goal**: Section 5 of `docs/architecture_baseline.md` states the visual theme,
interface regions, and interaction patterns.

**Independent Test**: Open `docs/architecture_baseline.md` and confirm both bullets
under "5. UX/UI Direction" have non-`TBD` content, with 4 interface regions and 6
interaction patterns listed.

### Implementation for User Story 5

- [X] T019 [US5] In `docs/architecture_baseline.md` Â§ 5 UX/UI Direction, replace
  `- **Visual Theme & Interface Regions**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` line 256 (the theme/layout
  paragraph: dark CAD-style theme, persistent left sidebar, floating right-side
  inspector panel, top toolbar).
- [X] T020 [US5] In `docs/architecture_baseline.md` Â§ 5 UX/UI Direction, replace
  `- **Core Interaction Patterns**: TBD` using
  `mining_tool_planning_Final_claude4-7-2026.md` lines 258-264 (the 5-6 interaction
  patterns list). List all 6 items as sub-bullets.

**Checkpoint**: Section 5 fully filled. FR-013, FR-014 satisfied. Content of
`docs/architecture_baseline.md` is now complete (still `draft` status).

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Governance footer, then mechanical and human validation against the
spec's success criteria.

- [X] T021 Fill the `## Governance of This Document` section of
  `docs/architecture_baseline.md` (replacing `TBD`) with a statement that this
  document is authoritative for product scope, data model, architecture, NFRs, and
  UX direction until formally amended, and that any feature spec needing to diverge
  MUST update this document rather than silently contradict it (this is FR-015's own
  requirement â€” restate it in this document's voice, it is not sourced from the
  master planning doc).
- [X] T022 Run validation steps 1-10 from
  `specs/002-architecture-baseline/quickstart.md` against
  `docs/architecture_baseline.md`. If any step fails, stop and fix the specific gap
  in the relevant Phase 3-7 task's output before continuing.
- [X] T023 Cross-check step 10 (SC-002, no orphan fields) explicitly: re-read Â§ 2
  Data Model â†’ Entities in `docs/architecture_baseline.md` against
  `specs/002-architecture-baseline/data-model.md` field-by-field. Fix any entity or
  field present in one but not the other.
- [X] T024 Perform step 11 from `quickstart.md` (SC-001, the 5-minute scope check).
  This requires an actual human read-through â€” **do not fabricate a timing or
  pass/fail result.** Append a one-line note after the Governance section, e.g.
  `<!-- SC-001 check: not yet human-verified -->` if no human has done it, or
  `<!-- SC-001 check: human-verified by <name> on <date>, under 5 minutes -->` only
  if that verification genuinely happened. Once genuinely verified, also change
  `**Status**: draft` to `**Status**: complete`.

**Checkpoint**: `docs/architecture_baseline.md` is complete and, once T024 is
genuinely human-verified, ready to serve as the baseline for all future Phase 0
feature specs (FR-015).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 (file must exist first).
- **User Story 1 (Phase 3)**: Depends on Phase 2.
- **User Story 2 (Phase 4)**: Depends on Phase 2. Does not depend on Phase 3's
  content, but must run after it in this file since both edit
  `docs/architecture_baseline.md` sequentially.
- **User Story 3 (Phase 5)**: Depends on Phase 2; runs after Phase 4 for the same
  single-file reason.
- **User Story 4 (Phase 6)**: Depends on Phase 2; runs after Phase 5.
- **User Story 5 (Phase 7)**: Depends on Phase 2; runs after Phase 6.
- **Polish (Phase 8)**: Depends on all of Phases 3-7 being complete.

### Within Each User Story

- T003-T005 (US1), T006-T009 (US2), T010-T014 (US3), T015-T018 (US4), T019-T020 (US5)
  must each run in the order given â€” every task edits the same file.

---

## Parallel Execution

No tasks in this feature can run in parallel â€” every task edits the same single
file, `docs/architecture_baseline.md`, so concurrent edits would overwrite each
other. Run strictly in task-ID order.

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 + 3, all P1)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1 (Product Definition).
4. Complete Phase 4: User Story 2 (Data Model).
5. Complete Phase 5: User Story 3 (System Architecture).
6. **STOP and VALIDATE**: `docs/architecture_baseline.md` now covers scope, data
   model, and architecture â€” this is the MVP. It already satisfies FR-001 through
   FR-011.

### Incremental Delivery

1. Setup + Foundational â†’ file skeleton ready.
2. User Story 1 â†’ scope authority usable on its own.
3. User Story 2 â†’ data model authority added.
4. User Story 3 â†’ architecture authority added â†’ content-complete MVP.
5. User Story 4 â†’ NFR baseline added.
6. User Story 5 â†’ UX baseline added â†’ content-complete document.
7. Polish â†’ governance footer, mechanical validation, and the human SC-001 check.

---

## Notes

- [Story] label maps task to specific user story for traceability.
- Every task names an exact source (line range or design-doc section) and an exact
  target section â€” no task requires inferring content not already written in the
  cited source.
- Do not mark `**Status**: complete` (T024) without a genuine human SC-001
  verification â€” this is the one task in this file that requires a human check, not
  just transcription, and fabricating it was a real issue caught during feature
  001's review. Be honest if it hasn't happened yet.
- Commit after each phase (or after each task, if preferred) so partial progress is
  recoverable.
