# Feature Specification: Phase 1 — Collaboration & Multi-Tenancy

**Feature Branch**: `004-phase1-collaboration-sharing`

**Created**: 2026-07-17

**Status**: Draft

**Input**: User description: "Please read the master plan in `mining_tool_planning_Final_claude4-7-2026.md` and the approved baseline document in `docs/architecture_baseline.md`. We want to run the full `spec-kit` workflow to specify, plan, and generate tasks for the remaining execution phases described in the master plan: Section 4: Phase 1 — Collaboration & Multi-Tenancy."

## Clarifications

### Session 2026-07-17

- Q: When a colleague opens a project's read-only share link, should they need to log in at all? → A: Zero-setup link (no account/login required), but the link token is long/unguessable and short-lived, auto-expiring with the owner able to renew it — no bare, permanently-valid link.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Switch between multiple prospects in one workspace (Priority: P1)

As the project owner, I want to switch between multiple gold prospects within one
workspace, so I can manage several projects without separate installs or logins.

**Why this priority**: Master plan §4 flags project-scoping as something that "must
exist from Phase 0's first migration — retrofitting it means rewriting every query
and import path." The data layer already supports this (per
`docs/architecture_baseline.md`); this story is what makes it usable.

**Independent Test**: Given a user with 3+ existing projects, they can switch between
them and see only the selected project's data, independent of sharing or audit-trail
features existing yet.

**Acceptance Scenarios**:

1. **Given** multiple projects exist for a user, **When** they open the workspace,
   **Then** they see a list or switcher of all their projects.
2. **Given** a user selects a different project, **When** the switch happens,
   **Then** the 3D scene and all panels reload scoped to that project only, with no
   data from the previously viewed project visible.

---

### User Story 2 - Share a project as read-only with a colleague (Priority: P1)

As the project owner, I want to generate a read-only link for a trusted colleague to
view a specific project, so they can review data without needing full access or a
heavy account-setup process.

**Why this priority**: This is the explicit "lightweight sharing" scope for Phase 1
per master plan §4 — the core collaboration capability this phase exists to deliver.

**Independent Test**: Given an existing project, a share link can be generated,
opened by someone else, and confirmed read-only, independent of multi-project
switching or audit-trail features.

**Acceptance Scenarios**:

1. **Given** a project, **When** the owner generates a share link, **Then** a unique
   read-only link scoped to that project is created.
2. **Given** a colleague opens the read-only link, **When** they view the project,
   **Then** they can see the 3D scene, drillhole inspection, grade cutoff, slicing,
   and measurement, but cannot import, edit, or delete anything.
3. **Given** the owner wants to end access, **When** they revoke the share link,
   **Then** it immediately stops working.

---

### User Story 3 - See who changed what and when (Priority: P2)

As the project owner, I want a basic audit trail of who changed what and when for a
project, so I can track changes even with just myself and one occasional
collaborator using it.

**Why this priority**: Master plan §4 notes this is "cheap to add now, painful to
backfill later." The underlying fields already exist in the Phase 0 data model; this
story is about making that history visible and useful, which matters less urgently
than the two P1 stories above.

**Independent Test**: Given a project with import history, a user can view who
imported or changed a given piece of data and when, independent of the sharing or
multi-project-switching features.

**Acceptance Scenarios**:

1. **Given** data has been imported into a project over time, **When** the user
   views the project's history, **Then** they can see each import batch's source
   file, import date, and importing user.
2. **Given** a record was superseded by a correction, **When** the user inspects the
   older record, **Then** they can trace it forward to the newer record that
   replaced it.

---

### Edge Cases

- What happens when someone opens a share link after it has been revoked or has
  expired? They MUST see a clear "access no longer available" message, never an
  error page or crash — the two cases (revoked vs. expired) need not be
  distinguished to the viewer.
- What happens if the underlying project data changes while someone is viewing it via
  a share link? The viewer MUST see the current committed state, consistent with what
  the owner would see — no separate stale copy.
- What happens if the owner and a colleague (via share link) view the same project at
  the same time? Both MUST see consistent, correctly project-scoped data; real-time
  collaborative features (live cursors, simultaneous editing) are explicitly out of
  scope (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Users MUST be able to view a list of all their projects and switch
  between them within one workspace, without a separate login per project.
- **FR-002**: Switching the active project MUST fully scope the 3D scene and all
  panels to that project only, with no data from a previously viewed project
  remaining visible after the switch.
- **FR-003**: The project owner MUST be able to generate a read-only share link
  scoped to a single project.
- **FR-004**: A read-only share link MUST allow viewing the 3D scene, drillhole
  inspection, grade cutoff, slicing, and measurement, but MUST NOT allow import,
  edit, or delete actions of any kind.
- **FR-005**: A read-only share link MUST require no account or login for the
  recipient to use — opening the link is sufficient. The link's token MUST be long
  and unguessable, and MUST expire automatically after a bounded period; the owner
  MUST be able to renew (extend) an active link without generating a new URL.
- **FR-006**: The project owner MUST be able to revoke a previously generated share
  link at any time (in addition to its automatic expiry from FR-005), after which it
  immediately stops granting access.
- **FR-007**: The system MUST expose, for every import batch already recorded in the
  Phase 0 data model, its source file, import date, and importing user as a viewable
  history within the project.
- **FR-008**: The system MUST let a user trace any superseded record forward to the
  record that replaced it, using the existing `superseded_by` chain from the Phase 0
  data model.
- **FR-009**: Access to a project's data — via the workspace or a share link — MUST
  be scoped so a user can only see projects they own or have been explicitly granted
  access to.

### Key Entities

- **Project, User, Import Batch**: Already defined in
  `docs/architecture_baseline.md` § 2 and the Phase 0 data model
  (`specs/003-phase0-core-visualization/data-model.md`) — this feature adds no new
  fields to them beyond what's needed to expose existing history (FR-007, FR-008).
- **Share Link** *(new)*: A revocable, read-only access token for one Project —
  a unique long/unguessable token, which project it grants access to, when it was
  created, who created it, when it expires, and whether/when it was revoked ahead
  of expiry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with 3 or more projects can switch between them and see only
  the newly selected project's data within 5 seconds.
- **SC-002**: A generated share link lets a colleague view a project's 3D scene and
  drillhole details; attempting any write action (import, edit, delete) through that
  link is rejected 100% of the time.
- **SC-003**: Revoking a share link takes effect immediately — any access attempt
  using the revoked link fails on the very next try, with no delay window. An
  unrevoked link that has passed its expiry behaves identically — access fails
  without the owner needing to take any action.
- **SC-004**: For any project with import history, a user can identify who imported
  or changed a given piece of data and when, entirely within the tool.

## Assumptions

- This specification covers only Phase 1 (Section 4 of
  `mining_tool_planning_Final_claude4-7-2026.md`). Phase 2 (Breadth & Scale, Section
  5) is a separate feature to be specified independently.
- "Multi-tenancy" in this phase's title means a multi-project workspace plus
  single-collaborator read-only sharing for a 1-3 person total user base — not
  multi-tenant SaaS organizations or billing, consistent with
  `docs/architecture_baseline.md`'s V1 Non-Goals (which excludes multi-tenant orgs)
  and its § 3 multi-tenancy model (simple `project_id` scoping in one shared
  database, not schema- or database-per-tenant).
- The `project_id` scoping and audit-trail fields (`import_batch_id`,
  `superseded_by`) this feature depends on already exist from the Phase 0 data model
  — this feature is additive (workspace switching, sharing, and surfacing that
  history in the UI), not a data-model redesign.
- No real-time collaborative editing (live cursors, simultaneous comments, etc.) is
  in scope — "collaboration" here means asynchronous, read-only visibility for a
  colleague, per the master plan's explicit downscoping of this phase.
- Archiving or deleting an entire project is out of scope for this feature; only the
  existing record-level soft-versioning (no hard deletes, per constitution Principle
  V) applies.
