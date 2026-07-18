---

description: "Task list for feature implementation"
---

# Tasks: Panel Gap-Check + Tension Log

**Input**: Design documents from `specs/001-panel-gap-check-tension-log/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md (all present)

**Tests**: Not applicable — this feature produces a Markdown document, not executable
code. No test tasks are included.

**Note for the executor**: Every task below is self-contained. It names the exact
source file and line range to read, and the exact target file and section to write.
Do not skip ahead or infer content that isn't explicitly quoted or referenced — if a
task says to transcribe lines 11-15, use only that text (condensed/restructured into
the schema fields, not paraphrased into new claims).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All tasks in this feature write to the same single file, `reviews/phase0_review.md`,
  so **no task below is marked [P]** — they must run in the sequence given to avoid
  overwriting each other's edits.

## Path Conventions

- Deliverable: `reviews/phase0_review.md` (repository root)
- Design docs: `specs/001-panel-gap-check-tension-log/` (already created by `/speckit-plan`)
- Source material: `mining_tool_planning_Final_claude4-7-2026.md` (repository root)
- Schema reference: `specs/001-panel-gap-check-tension-log/data-model.md`

---

## Phase 1: Setup

**Purpose**: Create the deliverable file with its full structural skeleton, empty.

- [X] T001 Create the `reviews/` directory at the repository root if it does not
  already exist. Create `reviews/phase0_review.md` with exactly this skeleton
  (copy verbatim, do not fill in values yet):

  ```markdown
  # Phase 0 Panel Gap-Check + Tension Log

  **Phase**: Phase 0 — Core Visualization & Modeling
  **Source Reference**: TBD
  **Completion Status**: draft

  ## Role Assessments

  ### 1. Exploration/Resource Geologist
  - Non-negotiables: TBD
  - Blind spots: TBD

  ### 2. Mining Engineer (open-pit)
  - Non-negotiables: TBD
  - Blind spots: TBD

  ### 3. Geotechnical Engineer
  - Non-negotiables: TBD
  - Blind spots: TBD

  ### 4. Data/Database Architect
  - Non-negotiables: TBD
  - Blind spots: TBD

  ### 5. Cloud/Software Architect
  - Non-negotiables: TBD
  - Blind spots: TBD

  ### 6. 3D Visualization Engineer
  - Non-negotiables: TBD
  - Blind spots: TBD

  ### 7. Professional Tool Strategist
  - Non-negotiables: TBD
  - Blind spots: TBD

  ### 8. UX/UI Designer (technical/CAD tools)
  - Non-negotiables: TBD
  - Blind spots: TBD

  ## Tensions

  (none added yet)

  ## Completion

  - Approved by: TBD
  - Approved date: TBD
  - Checklist reference: TBD
  ```

**Checkpoint**: `reviews/phase0_review.md` exists with all 8 role headings and the
empty Tensions/Completion sections present, in this exact order.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fill in the two header fields every later task depends on.

**⚠️ CRITICAL**: Complete before any Role Assessment or Tension Entry task.

- [X] T002 In `reviews/phase0_review.md`, replace `**Source Reference**: TBD` with:
  `**Source Reference**: mining_tool_planning_Final_claude4-7-2026.md, Section "1. PANEL GAP-CHECK + TENSION LOG"; aligned with project constitution v1.0.0 (.specify/memory/constitution.md)`.
  Leave every other line unchanged.

**Checkpoint**: Source Reference field is filled. Role Assessment and Tension work can
now begin.

---

## Phase 3: User Story 1 - Surface per-role non-negotiables and blind spots (Priority: P1) 🎯 MVP (part 1 of 2)

**Goal**: Every one of the 8 disciplines has its non-negotiables and blind spots
documented in `reviews/phase0_review.md`.

**Independent Test**: Open `reviews/phase0_review.md` and confirm all 8 `###` role
headings have non-`TBD` content under both "Non-negotiables" and "Blind spots".

### Implementation for User Story 1

For each task below: open `mining_tool_planning_Final_claude4-7-2026.md`, read only
the given line range, then in `reviews/phase0_review.md` replace that role's
`- Non-negotiables: TBD` and `- Blind spots: TBD` lines. Turn each "Non-negotiable:"
sentence from the source into one bullet under "Non-negotiables", and each "Commonly
forgotten:" sentence into one bullet under "Blind spots". Keep the original wording;
do not add new claims.

- [X] T003 [US1] Fill Role Assessment #1 "Exploration/Resource Geologist" in
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 11-15.
- [X] T004 [US1] Fill Role Assessment #2 "Mining Engineer (open-pit)" in
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 17-20.
- [X] T005 [US1] Fill Role Assessment #3 "Geotechnical Engineer" in
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 22-25.
- [X] T006 [US1] Fill Role Assessment #4 "Data/Database Architect" in
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 27-30.
- [X] T007 [US1] Fill Role Assessment #5 "Cloud/Software Architect" in
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 32-35.
- [X] T008 [US1] Fill Role Assessment #6 "3D Visualization Engineer" in
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 37-40.
- [X] T009 [US1] Fill Role Assessment #7 "Professional Tool Strategist" in
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 42-45.
- [X] T010 [US1] Fill Role Assessment #8 "UX/UI Designer (technical/CAD tools)" in
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 47-50.

**Checkpoint**: All 8 Role Assessments are filled. FR-001 and FR-002 satisfied.

---

## Phase 4: User Story 2 - Log and resolve real trade-off tensions (Priority: P1) 🎯 MVP (part 2 of 2)

**Goal**: At least 3 (this feature has 4 available) genuine tensions are logged with
resolutions in `reviews/phase0_review.md`.

**Independent Test**: Open `reviews/phase0_review.md` and confirm the Tensions section
has 4 entries, each with a Positions, Resolution, and Rationale line filled in.

### Implementation for User Story 2

For task T011, first replace the `(none added yet)` placeholder line under
`## Tensions` with nothing (delete that line) before adding the first entry. For each
task, read only the given line range from
`mining_tool_planning_Final_claude4-7-2026.md`, then append one entry to the Tensions
section of `reviews/phase0_review.md` in this exact format:

```markdown
### Tension N — <title>
- Positions: <the conflicting positions and which disciplines hold them>
- Resolution: <the single chosen resolution, taken from the "Resolution:" sentence>
- Rationale: <why that resolution was chosen, from the rest of the "Resolution:" text>
```

- [X] T011 [US2] Add "Tension 1 — Desurveying precision vs solo build effort" to
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 54-56.
- [X] T012 [US2] Add "Tension 2 — Real auth/multi-user infrastructure vs 'it's just me'"
  to `reviews/phase0_review.md`, sourced from
  `mining_tool_planning_Final_claude4-7-2026.md` lines 58-60.
- [X] T013 [US2] Add "Tension 3 — Full JORC schema completeness vs Phase 0 scope" to
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 62-64.
- [X] T014 [US2] Add "Tension 4 — CRS rigor vs 'it's just my own prospect'" to
  `reviews/phase0_review.md`, sourced from `mining_tool_planning_Final_claude4-7-2026.md`
  lines 66-68.

**Checkpoint**: 4 Tension Entries present, each with Positions/Resolution/Rationale.
FR-003 and FR-004 satisfied. Content of `reviews/phase0_review.md` is now complete
(still `draft` status).

---

## Phase 5: User Story 3 - Use the completed log as a gate before planning starts (Priority: P2)

**Goal**: `reviews/phase0_review.md` is mechanically validated, then explicitly
approved by the project owner and marked `complete`.

**Independent Test**: `completion_status` reads `complete`, with `approved_by`,
`approved_date`, and `checklist_reference` all filled in, and every check in
`quickstart.md` passes.

### Implementation for User Story 3

- [X] T015 [US3] Run validation steps 1-8 from
  `specs/001-panel-gap-check-tension-log/quickstart.md` against
  `reviews/phase0_review.md`. If any step fails, stop and fix the specific gap in the
  relevant Phase 3/4 task's output before continuing — do not proceed to T016.
- [X] T016 [US3] Open `specs/001-panel-gap-check-tension-log/checklists/requirements.md`
  and confirm every checkbox is `[x]`. If any are `[ ]`, stop here — do not mark the
  review complete until the checklist is re-validated (re-run `/speckit-clarify`
  or update the checklist per its own validation rules).
- [X] T017 [US3] Present the completed `reviews/phase0_review.md` to the project owner
  and explicitly ask for approval. **Do not set `completion_status` to `complete`
  without an explicit "approved"/"yes" reply from the project owner in this
  conversation.** Once approved, update `reviews/phase0_review.md`:
  set `**Completion Status**: complete`, and replace the Completion section with:
  `- Approved by: <owner's stated name/identifier>`,
  `- Approved date: <today's date, YYYY-MM-DD>`,
  `- Checklist reference: specs/001-panel-gap-check-tension-log/checklists/requirements.md — all items passing`.

**Checkpoint**: `reviews/phase0_review.md` is `complete` and approved. FR-006, FR-008,
SC-001, SC-002 satisfied. Phase 0 implementation planning may now reference this file
as its gate.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final quality pass against the spec's success criteria.

- [ ] T018 [P] Time a full read-through of `reviews/phase0_review.md` (quickstart.md
  step 9 / SC-003) and confirm it takes under 10 minutes to read and explain every
  Tension Entry's resolution. Record the result as a one-line note appended after the
  Completion section, e.g. `<!-- SC-003 check: read in Xm, pass -->`.
- [X] T019 Re-read `reviews/phase0_review.md` against the Validation Rules list in
  `specs/001-panel-gap-check-tension-log/data-model.md` (the bullet list under
  "Validation Rules") one rule at a time, and confirm each holds. Fix any mismatch
  found.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Phase 1 (file must exist first).
- **User Story 1 (Phase 3)**: Depends on Phase 2 (Source Reference field must be set).
- **User Story 2 (Phase 4)**: Depends on Phase 2. Does not depend on Phase 3's content,
  but must run after it in this file since both edit `reviews/phase0_review.md`
  sequentially — run Phase 3 fully, then Phase 4.
- **User Story 3 (Phase 5)**: Depends on both Phase 3 and Phase 4 being complete (the
  whole document must be filled in before it can be validated and approved).
- **Polish (Phase 6)**: Depends on Phase 5 (only polish an approved, complete document).

### Within Each User Story

- T003-T010 (US1) must run in order given — each edits the same file.
- T011-T014 (US2) must run in order given, and only after T003-T010 — each edits the
  same file.
- T015 → T016 → T017 (US3) must run strictly in that order.

---

## Parallel Execution

No tasks in this feature can run in parallel — every task except T018 edits the same
single file, `reviews/phase0_review.md`, so concurrent edits would overwrite each
other. T018 could technically run alongside T019, but since T019 is a correctness
check, run them in sequence for simplicity.

---

## Implementation Strategy

### MVP First (User Stories 1 + 2, both P1)

1. Complete Phase 1: Setup.
2. Complete Phase 2: Foundational.
3. Complete Phase 3: User Story 1 (all 8 Role Assessments).
4. Complete Phase 4: User Story 2 (all 4 Tension Entries).
5. **STOP and VALIDATE**: `reviews/phase0_review.md` now has complete content
   (`draft` status) — this is the MVP. It already satisfies FR-001 through FR-005.

### Incremental Delivery

1. Setup + Foundational → file skeleton ready.
2. User Story 1 → all role perspectives captured → reviewable on its own.
3. User Story 2 → all tensions captured → content-complete MVP.
4. User Story 3 → validated, owner-approved, `complete` → ready to gate Phase 0
   planning.
5. Polish → SC-003 timing check and final rule-by-rule validation.

---

## Notes

- [Story] label maps task to specific user story for traceability.
- Every task names an exact source line range and an exact target file — no task
  requires inferring content that isn't already written in
  `mining_tool_planning_Final_claude4-7-2026.md`.
- Commit after each phase (or after each task, if preferred) so partial progress on
  the document is recoverable.
- Do not mark `completion_status: complete` (T017) without explicit owner sign-off —
  this is the one task in this file that requires a human decision, not just
  transcription.
