# Phase 0 Research: Core Platform Architecture Baseline

No `NEEDS CLARIFICATION` markers remain in the Technical Context — this feature
consolidates already-ratified decisions rather than making new ones. The following
are the implementation-shaping decisions this plan still had to make.

## Decision 1: Deliverable location and format

**Decision**: The baseline document is `docs/architecture_baseline.md` at the
repository root — a single Markdown file with five top-level sections mirroring the
spec's FR groups: Product Definition, Data Model, System Architecture, Non-Functional
Requirements, and UX/UI Direction, plus a short "Governance of this Document" footer
(FR-015).

**Rationale**: Matches the precedent set by feature 001-panel-gap-check-tension-log,
where `spec.md` defines requirements and a separate concrete artifact
(`reviews/phase0_review.md`) holds the actual content. A new `docs/` directory is more
appropriate here than `reviews/`, since this is a forward-looking reference baseline
every future spec consults, not a point-in-time approval record.

**Alternatives considered**:
- *Treat `spec.md` itself as the final artifact* — rejected. `spec.md` is
  deliberately abstract/WHAT-oriented per Spec Kit convention (no literal ERD, no
  concrete performance numbers duplicated verbatim) and doesn't satisfy FR-004's
  requirement to enumerate concrete entity fields.
- *Append to `mining_tool_planning_Final_claude4-7-2026.md`* — rejected. That file is
  an unversioned planning narrative recording how decisions were reached, not meant to
  be the single forward-looking source of truth; mixing narrative history with an
  authoritative baseline would make future amendments (FR-015) harder to track.

## Decision 2: Avoiding technology-stack duplication and drift

**Decision**: `docs/architecture_baseline.md` names concrete technologies (e.g., the
3D rendering library, backend framework, database) only inside a single "Technology
Stack" subsection of System Architecture, which states them once and points to
`.specify/memory/constitution.md` § Technology Stack Constraints as the authoritative
source — it does not restate versions or rationale.

**Rationale**: The constitution already owns this fact. Duplicating full details in
two independently-editable places is exactly the drift risk flagged in the spec's
Assumptions section.

**Alternatives considered**:
- *Full duplication of the stack table* — rejected: drift risk (a future constitution
  amendment could silently desync from this document).
- *Omitting all technology mentions* — rejected: would make the document less useful
  as a fast-reference architecture baseline, which is the user's explicit goal.

## Decision 3: Validation approach

**Decision**: Correctness is validated via a mechanical checklist in `quickstart.md`
(structural presence checks: all 5 sections present, all 9 entities listed with
required fields, all FR-mapped facts present, tech-stack cross-reference rule
respected) rather than automated tests.

**Rationale**: This is a static Markdown reference document with no runtime behavior
to unit-test. A structural + content-fidelity checklist is the proportionate
verification method, consistent with the constitution's Boring & Maintainable
Architecture principle (no tooling overhead for a documentation deliverable) and with
the approach already used for feature 001.

**Alternatives considered**:
- *No validation* — rejected: SC-001–SC-006 need to be demonstrably true, not merely
  asserted.
- *Automated Markdown linting/schema validation tooling* — rejected as
  over-engineering for a single hand-maintained document on a solo project (Principle
  III).
