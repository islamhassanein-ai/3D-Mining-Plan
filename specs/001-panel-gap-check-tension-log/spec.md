# Feature Specification: Panel Gap-Check + Tension Log

**Feature Branch**: `001-panel-gap-check-tension-log`

**Created**: 2026-07-15

**Status**: Draft

**Input**: User description: "Read mining_tool_planning_Final_claude4-7-2026.md and create specification for phase ## 1. PANEL GAP-CHECK + TENSION LOG only."

## Clarifications

### Session 2026-07-15

- Q: Should the Panel Gap-Check + Tension Log process repeat for every future phase, or does this spec only document the Phase 0 review already in the master planning doc? → A: This spec only references and aligns with the Phase 0 decisions already established in the master planning document and the constitution. The process is not required to repeat for individual feature specs.
- Q: Where should a completed Phase Review (role assessments + tension entries) be persisted? → A: In `reviews/phase0_review.md`, centralizing all review artifacts in the project's `reviews/` directory.
- Q: What determines that a Phase Review is "complete" and allowed to gate planning? → A: (1) explicit approval by the project owner, (2) all blocking items and tensions resolved or documented with clear justification, and (3) this spec's quality checklist (`checklists/requirements.md`) fully validated and compliant with the constitution.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Surface per-role non-negotiables and blind spots before a phase begins (Priority: P1)

As the project owner (solo geologist/architect) about to start a new phase of the Gold
Prospect 3D Visualization Tool, I want a documented review of what each relevant
discipline considers non-negotiable and commonly overlooked, so that I catch decisions
that would be expensive to retrofit before any implementation work starts.

**Why this priority**: This is the core purpose of the review — missing a
non-negotiable (e.g., CRS handling, desurveying method) is exactly the kind of mistake
that is cheap to prevent up front and costly to fix once code and data already exist.

**Independent Test**: Can be fully tested by reading `reviews/phase0_review.md` and
confirming every discipline relevant to Phase 0 has a documented
non-negotiable/blind-spot entry, independent of whether any tensions were logged.

**Acceptance Scenarios**:

1. **Given** a phase is about to move from idea to implementation planning, **When**
   the gap-check review is produced, **Then** it lists, for each relevant discipline,
   at least one non-negotiable requirement and at least one commonly-forgotten risk.
2. **Given** a discipline has no non-negotiables for a given phase, **When** the
   review is produced, **Then** the review explicitly states "none identified" for
   that discipline rather than omitting it silently.

---

### User Story 2 - Log and resolve real trade-off tensions between disciplines (Priority: P1)

As the project owner, I want disagreements between disciplines about a phase's scope
or approach captured as explicit tensions with a stated resolution and rationale, so
that trade-off decisions are traceable later and are not silently made or forgotten.

**Why this priority**: Undocumented trade-offs are the most common source of "why did
we do it this way?" confusion in a solo project, and the resolution rationale is what
lets the owner (or a future collaborator) trust a decision without re-litigating it.

**Independent Test**: Can be fully tested by reviewing the tension log in
`reviews/phase0_review.md` and confirming each entry has a described conflict, the
positions involved, and a single documented resolution with rationale.

**Acceptance Scenarios**:

1. **Given** two disciplines have conflicting non-negotiables for a phase, **When**
   this is identified, **Then** it is recorded as a tension entry with both positions,
   the resolution chosen, and why.
2. **Given** a resolution is recorded, **When** implementation later needs to deviate
   from it, **Then** the deviation must be recorded as a new or updated tension entry
   rather than silently overridden in code or data.

---

### User Story 3 - Use the completed Phase 0 log as a gate before planning starts (Priority: P2)

As the project owner, I want Phase 0's gap-check and tension log to be complete before
implementation planning for Phase 0 begins, so that planning decisions are grounded in
the disciplines' stated non-negotiables rather than made in isolation. This gate
applies to Phase 0 only; whether a future phase needs its own review is a separate
decision, not something this specification mandates.

**Why this priority**: This ties the artifact into the actual workflow — without this
gating, the review becomes documentation theater rather than something that shapes
what gets built.

**Independent Test**: Can be tested by confirming that, for a completed phase, the
plan references or is consistent with every resolution recorded in that phase's
tension log.

**Acceptance Scenarios**:

1. **Given** Phase 0's gap-check and tension log is incomplete — not yet approved by
   the project owner, or its checklist not fully passing — **When** implementation
   planning for Phase 0 is attempted, **Then** this is flagged before planning
   proceeds.
2. **Given** all tensions for Phase 0 are resolved and the review is approved, **When**
   implementation planning proceeds, **Then** no resolution is contradicted without an
   explicit new tension entry explaining why.

---

### Edge Cases

- What happens when a discipline's non-negotiable directly conflicts with the
  project's stated scope or kill criterion? It MUST be logged as a tension with an
  explicit resolution, not dropped silently.
- How does the review handle a phase where fewer than three genuine tensions exist
  between disciplines? The review must state why so few tensions were found (e.g.,
  strong alignment) rather than fabricating disagreements to hit a minimum count.
- What happens when a previously resolved tension turns out to be wrong once
  implementation is underway? It requires a new logged entry amending the prior
  resolution, not a silent code or data change.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The review MUST document, for each discipline relevant to Phase 0,
  at least one non-negotiable requirement that would be expensive or risky to add
  after implementation has started.
- **FR-002**: The review MUST document, for each discipline relevant to Phase 0,
  commonly-forgotten risks or blind spots distinct from its non-negotiables.
- **FR-003**: The review MUST log at least three real trade-off tensions for
  Phase 0 — genuine disagreements between disciplines, not restatements of a single
  discipline's requirements.
- **FR-004**: Each tension entry MUST record the conflicting positions, the chosen
  resolution, and the rationale for that resolution.
- **FR-005**: The review MUST distinguish between Phase 0 items addressed immediately
  and items intentionally deferred to a later phase, including why deferring is safe.
- **FR-006**: The Phase 0 gap-check and tension log MUST be considered complete, and
  therefore allowed to gate Phase 0's implementation plan, only when all three of the
  following hold: (1) it is explicitly approved by the project owner, (2) every
  blocking item and tension is either resolved or documented with a clear
  justification for remaining open, and (3) this specification's quality checklist
  (`checklists/requirements.md`) is fully validated and compliant with the
  constitution.
- **FR-007**: A resolution recorded in the tension log MUST NOT be contradicted during
  implementation without a corresponding new or updated tension entry documenting the
  change and its reason.
- **FR-008**: The completed Phase 0 review (all Role Assessments and Tension Entries)
  MUST be persisted as `reviews/phase0_review.md`, and MUST remain accessible and
  attributable to Phase 0 for the life of the project, so past decisions can be
  audited later.
- **FR-009**: This specification and its completion gate apply to Phase 0 only.
  Repeating the gap-check/tension-log process for individual feature specs, or for
  future phases (Phase 1, Phase 2, ...), is out of scope for this specification and
  would require a separate future decision.

### Key Entities

- **Role Assessment**: One discipline's perspective on a given phase — the
  discipline/role name, its non-negotiable requirements for that phase, and its
  commonly-forgotten risks/blind spots.
- **Tension Entry**: A single logged disagreement for a given phase — the conflict
  description, the disciplines/positions involved, the chosen resolution, and the
  rationale behind it.
- **Phase Review**: The complete gap-check + tension log for Phase 0, made up of one
  Role Assessment per relevant discipline plus a set of Tension Entries, with a
  completion state (draft/complete) determined per FR-006. Persisted as
  `reviews/phase0_review.md`, separate from this specification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Before Phase 0 implementation planning begins, 100% of the eight
  disciplines in scope have a recorded non-negotiable/blind-spot entry in
  `reviews/phase0_review.md`.
- **SC-002**: At least 3 genuine tensions are logged and resolved for Phase 0, with
  zero tensions left unresolved when planning begins.
- **SC-003**: A person unfamiliar with Phase 0's history can read
  `reviews/phase0_review.md` in under 10 minutes and correctly explain, for every
  logged tension, what was decided and why.
- **SC-004**: Across the life of the project, zero Phase 0 implementation decisions
  are made that contradict a logged resolution without a corresponding documented
  amendment.

## Assumptions

- The "phase" being reviewed in this specification is Phase 0 (Core Visualization &
  Modeling) of the Gold Prospect 3D Visualization Tool. Per the Clarifications above,
  `reviews/phase0_review.md` is expected to align with and reference the Phase 0
  content already drafted in the master planning document and ratified by the
  constitution, rather than re-deriving it from scratch.
- The disciplines reviewed are the eight identified in the source planning document:
  Exploration/Resource Geologist, Mining Engineer, Geotechnical Engineer,
  Data/Database Architect, Cloud/Software Architect, 3D Visualization Engineer,
  Professional Tool Strategist, and UX/UI Designer.
- This review is produced and consumed by a single project owner (with AI assistance)
  rather than a live multi-person panel meeting; "per-role" perspectives are
  analytical lenses applied during planning, not separate human stakeholders.
- The review is a planning/documentation deliverable that gates implementation
  planning; it does not itself require any runtime software feature (UI, API,
  database) to be built.
