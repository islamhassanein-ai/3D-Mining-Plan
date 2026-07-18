# Feature Specification: Core Platform Architecture Baseline

**Feature Branch**: `002-architecture-baseline`

**Created**: 2026-07-16

**Status**: Draft

**Input**: User description: "Create a master technical specification based on mining_tool_planning_Final_claude4-7-2026.md, covering Section 2 (Product Definition), Section 6 (Data Model), Section 7 (System Architecture), Section 8 (NFRs), and Section 9 (UX/UI Direction) to serve as our project's technical architecture baseline."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consult a single scope authority before starting any feature (Priority: P1)

As the developer (or an AI implementer) about to spec or build a new capability, I want
one authoritative statement of the product's vision, target users, and explicit
non-goals, so I can check any proposed feature against what's actually in scope
without re-reading the entire master planning document each time.

**Why this priority**: Scope drift is the most common way a solo project loses
coherence; this is the cheapest possible check before any other work starts.

**Independent Test**: Given any proposed feature idea, this document's Product
Definition content alone is sufficient to say in/out of scope and cite the kill
criterion, without consulting any other file.

**Acceptance Scenarios**:

1. **Given** a proposed feature that matches a listed V1 non-goal (e.g., multi-tenant
   orgs, billing), **When** it's checked against this document, **Then** it is
   correctly identified as out of scope for the current phase.
2. **Given** the kill criterion, **When** real messy CSV import requires excessive
   manual correction, **Then** this document states clearly what "failure of the core
   premise" looks like and what happens next.

---

### User Story 2 - Build every Phase 0 feature against one canonical data model (Priority: P1)

As the developer, I want the canonical entities, fields, relationships,
coordinate/unit/BDL handling rules, and bad-import error behavior captured in one
place, so that every future Phase 0 feature spec references the same schema instead
of each one re-deriving or drifting from it.

**Why this priority**: The data model is the foundation every other Phase 0 feature
(import, rendering, inspection) is built on; divergence here is expensive to unwind
later — this directly echoes the constitution's Geological Data Integrity and CRS
Rigor principles.

**Independent Test**: Given any new Phase 0 feature spec that touches drillhole,
assay, or lithology data, its data requirements can be verified against this
document's entity list without contradiction.

**Acceptance Scenarios**:

1. **Given** an assay value below detection limit, **When** it's stored per this
   document's rules, **Then** it is flagged `below_detection_limit = true` with the
   detection limit preserved, never zeroed.
2. **Given** a CSV import with an ambiguous or wrong UTM zone, **When** it's processed
   per this document's error-handling table, **Then** the system flags it and
   requires explicit user confirmation before commit.
3. **Given** overlapping or gapped survey/assay/lithology intervals, **When**
   encountered, **Then** they are flagged for geologist review, never silently
   auto-corrected.

---

### User Story 3 - Build every Phase 0 feature against one fixed architecture (Priority: P1)

As the developer, I want the chosen system architecture (component boundaries,
rendering/backend/database technology, multi-tenancy model, and the client/server
performance split) documented as a settled baseline, so future feature specs don't
re-litigate already-decided architecture.

**Why this priority**: The constitution already fixes the technology stack; without a
single reference document, each new feature spec risks re-opening decisions that are
already closed, wasting effort and risking inconsistency.

**Independent Test**: Given any new Phase 0 feature spec, its proposed component
placement (client vs. server, which service owns which responsibility) can be checked
against this document's architecture diagram without ambiguity.

**Acceptance Scenarios**:

1. **Given** a new feature that requires 3D rendering, **When** its plan is checked
   against this document, **Then** it must render client-side using the fixed
   rendering technology, not introduce an alternative.
2. **Given** a new feature that requires spatial/CRS conversion, **When** its plan is
   checked against this document, **Then** that processing happens server-side at
   import time, not client-side.

---

### User Story 4 - Check every Phase 0 feature against fixed quality baselines (Priority: P2)

As the developer, I want the non-functional requirements (security/isolation,
audit/provenance, performance targets, offline behavior) captured as measurable
baselines, so any new feature can be checked against them before being considered
done.

**Why this priority**: Important for professional-grade trust, but each individual
feature spec can restate the relevant subset; this document is the fallback reference
rather than a blocking gate for every task.

**Independent Test**: Given any new Phase 0 feature involving the 3D scene, its
performance can be checked against this document's stated interaction target without
needing a separate NFR discussion.

**Acceptance Scenarios**:

1. **Given** a scene with up to ~5,000 assay intervals, **When** interacted with
   (orbit/pan/zoom), **Then** it sustains the frame-rate target stated in this
   document.
2. **Given** a typical CSV import, **When** processed, **Then** it completes within
   the time budget stated in this document.

---

### User Story 5 - Keep every UI feature visually and interactionally consistent (Priority: P2)

As the developer, I want the UX/UI direction (theme, layout regions, and the core
interaction patterns judged in the first five minutes) captured as a baseline, so new
UI work doesn't drift into an inconsistent look or feel.

**Why this priority**: Important for the "beats Leapfrog on friction" positioning, but
is a consistency check applied per-feature rather than a blocking prerequisite for
backend work.

**Independent Test**: Given a new UI feature (e.g., a new inspector panel), its layout
placement and interaction feel can be checked against this document's described
regions and patterns.

**Acceptance Scenarios**:

1. **Given** any new panel or control, **When** placed in the interface, **Then** it
   fits one of this document's described regions (persistent sidebar, floating
   inspector, top toolbar) rather than introducing a new, inconsistent region.
2. **Given** camera interaction on any new 3D view, **When** used, **Then** it matches
   this document's described damping/orbit-around-cursor behavior and exposes the
   same camera presets.

---

### Edge Cases

- What happens when a future feature needs something this baseline doesn't cover
  (e.g., a new entity, a new NFR)? This document must be amended, not silently
  contradicted by a feature spec, so it stays authoritative (see FR-015).
- What happens when this baseline and the constitution disagree? The constitution
  governs (per its own Governance section); this document must be corrected to match,
  not the other way around.
- What happens when a Phase 2-deferred item (RQD/core recovery, structural data,
  QA/QC) is referenced by a Phase 0 feature? The feature must treat the relevant
  fields as reserved-but-inactive, per this document's data model, not build UI or
  validation logic for them early.

## Requirements *(mandatory)*

### Functional Requirements

**Product Definition**

- **FR-001**: This document MUST state the product vision, primary target users, and
  the job-to-be-done in one place.
- **FR-002**: This document MUST list V1 non-goals explicitly (multi-tenant orgs,
  billing, public sharing/marketing site, underground mining support, non-English UI,
  formal JORC report generation, third-party customer onboarding).
- **FR-003**: This document MUST state the kill criterion — the condition under which
  the core premise (faster/more trustworthy than the prior ad-hoc workflow) is
  considered false, and that this triggers a pivot to import-robustness work before
  further visual features.

**Data Model**

- **FR-004**: This document MUST enumerate every core entity (Project, Collar, Survey,
  Assay Interval, Lithology Interval, Trench, Wireframe, Import Batch, User), its key
  fields, and its relationships to other entities.
- **FR-005**: This document MUST state that all coordinates are stored in UTM meters,
  with the zone recorded per project/collar, and that arbitrary local coordinate
  systems are not permitted (consistent with the constitution's CRS and Coordinate
  Rigor principle).
- **FR-006**: This document MUST state that assay units are stored explicitly per row
  and never assumed, and that below-detection-limit values are flagged
  (`below_detection_limit = true`) with the detection limit preserved, never zeroed or
  dropped (consistent with the constitution's Geological Data Integrity principle).
- **FR-007**: This document MUST state the required behavior for each class of bad
  import (missing/wrong UTM zone, mixed units, swapped lat/long, overlapping/gap
  intervals) — flag and require user confirmation or geologist review, never silently
  auto-correct.

**System Architecture**

- **FR-008**: This document MUST state the chosen client-side 3D rendering approach
  and the reasoning for it relative to the alternatives considered, so future features
  don't re-open the choice.
- **FR-009**: This document MUST describe the high-level component boundaries (client,
  API server, parsing/ETL, database, object storage, auth service) and how they
  connect.
- **FR-010**: This document MUST state the multi-tenancy model appropriate to a 1-3
  user scale (simple project-level scoping, not schema- or database-per-tenant).
- **FR-011**: This document MUST state which processing happens server-side (parsing,
  desurveying, CRS conversion) versus client-side (rendering, slicing-plane math,
  measurement), so future features are placed consistently.

**Non-Functional Requirements**

- **FR-012**: This document MUST state the security/isolation baseline (real
  lightweight auth, encrypted transport, per-project storage scoping), the
  audit/provenance baseline (every import batch and edit timestamped and
  attributable), the performance targets (interaction frame-rate at a stated interval
  count, import processing time budget), and the offline/field-use expectation
  (cached last-loaded project, not full offline support).

**UX/UI Direction**

- **FR-013**: This document MUST describe the baseline visual theme and the four
  fixed interface regions (persistent layer sidebar, floating inspector panel, top
  toolbar, main 3D viewport).
- **FR-014**: This document MUST list the core interaction patterns a professional
  user judges in the first few minutes (smooth damped orbit/pan/zoom, instant
  drillhole card on click, real-time grade-cutoff response, synced section-view
  slicing, one-flow CSV import with validation, keyboard-accessible camera presets).

**Governance of this document**

- **FR-015**: This document MUST be treated as authoritative for product scope, data
  model, architecture, NFRs, and UX direction until formally amended; any future
  feature spec that needs to diverge from it MUST update this document rather than
  silently contradicting it, mirroring the amendment discipline the project
  constitution already requires of itself.

### Key Entities

- **Project**: A single gold prospect being tracked — id, name, UTM zone, commodity,
  creation time. Owns all other entities below.
- **Collar**: A drillhole's surface location — hole id, easting/northing/elevation,
  UTM zone, source import batch. Has many Surveys and Intervals.
- **Survey**: A downhole deviation reading for a Collar — depth, dip, azimuth,
  desurvey method used.
- **Assay Interval**: A sampled interval on a Collar — from/to depth, grade value,
  grade unit, below-detection-limit flag, QA/QC flag, source import batch.
- **Lithology Interval**: A geological interval on a Collar — from/to depth, lithology
  code, and reserved (Phase 0: inactive) RQD/core-recovery fields.
- **Trench**: A surface sample location — trench id, easting/northing, grade value.
- **Wireframe**: An imported solid/vein model — name, solid type, file reference.
- **Import Batch**: Provenance record for any imported data — source file, import
  date, status.
- **User**: An account with access to the system — email, role.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Any team member (including a future collaborator) can determine whether
  a proposed feature is in or out of scope for the current phase using only this
  document, in under 5 minutes.
- **SC-002**: 100% of Phase 0 feature specs that touch drillhole, assay, or lithology
  data reference entities and fields defined in this document, with zero fields
  invented outside it.
- **SC-003**: 100% of Phase 0 feature specs that involve rendering, parsing, or
  storage correctly place that work on the client or server side as defined in this
  document, verifiable by review without needing a separate architecture discussion.
- **SC-004**: A 3D scene populated with up to 5,000 assay intervals remains smoothly
  interactive (no perceptible stutter during orbit/pan/zoom) as stated in this
  document's performance baseline.
- **SC-005**: A typical CSV import completes within the time budget stated in this
  document, measured from file selection to validation-diff display.
- **SC-006**: Any new UI element added to the product can be placed into one of this
  document's four described interface regions without inventing a fifth.

## Assumptions

- This document captures Sections 2, 6, 7, 8, and 9 of
  `mining_tool_planning_Final_claude4-7-2026.md` as a stable baseline; it does not
  re-litigate decisions already made and resolved in that document or in the ratified
  project constitution (v1.0.0) — where the two might seem to conflict, the
  constitution governs, per its own Governance section.
- The specific technologies named as the chosen approach in this document (e.g., the
  client-side 3D rendering technology, backend framework, and database) are treated as
  already-decided project constraints inherited from the constitution's Technology
  Stack Constraints section, not as open implementation choices being made by this
  specification.
- This document is consumed primarily by the project owner and any AI assistant
  implementing features, not by end users of the finished tool; "user" in the User
  Scenarios above refers to that implementer, not a geologist using the finished
  product.
- Fields and entities marked as reserved for Phase 2 (structural/fault data,
  RQD/core recovery, QA/QC duplicates/standards/blanks) are included in the data
  model now (per the constitution's Soft Versioning & Audit Trail principle and the
  source document's "schema-complete, feature-deferred" resolution) but remain
  inactive — no UI or validation logic — until Phase 2.
- No new architecture, data model, or NFR decisions are introduced here beyond what
  Sections 2, 6, 7, 8, and 9 of the master planning document and the constitution
  already establish; this specification's role is to consolidate and formalize them
  as a single referenceable baseline, not to re-derive them from scratch.
