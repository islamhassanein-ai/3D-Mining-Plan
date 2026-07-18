# Phase 0 Research: Core Platform — Phase 0 Core Visualization & Modeling

No `NEEDS CLARIFICATION` markers remain in the Technical Context. The technology
stack itself is already fixed by the constitution; the decisions below are the
implementation-level choices needed to build against it.

## Decision 1: CSV parsing without a DataFrame library

**Decision**: Use Python's built-in `csv` module plus explicit per-row validation
functions, not pandas or a similar DataFrame library.

**Rationale**: The import flow's core requirement (FR-003) is a row-by-row diff view
of raw vs. interpreted data with per-row error flags (FR-006, FR-007, FR-009) — this
maps naturally onto simple row iteration and is easier to reason about and unit-test
than DataFrame-vectorized logic. Avoiding pandas also keeps the dependency surface
minimal, consistent with constitution Principle III (Boring & Maintainable
Architecture — no unnecessary tooling for a solo maintainer).

**Alternatives considered**: pandas — rejected; adds a large dependency for a benefit
(vectorized transforms) this feature doesn't need, and DataFrame semantics make
per-row error attribution less direct than plain row iteration.

## Decision 2: Database migrations via Alembic

**Decision**: Use Alembic for schema migrations alongside SQLAlchemy 2.0.

**Rationale**: Alembic is the standard, well-documented migration tool for
SQLAlchemy — the "boring" choice per Principle III — and every schema change in this
project must be append-only/reconcilable (constitution Principle V), which a tracked
migration history directly supports.

**Alternatives considered**: Hand-written SQL migration scripts — rejected, more
error-prone and less standard for a solo maintainer to keep consistent over time.

## Decision 3: Instanced rendering for assay and lithology intervals

**Decision**: Render assay-interval and lithology-interval cylinders using Three.js
`InstancedMesh` (one draw call per interval *type*, not per interval), with
per-instance color set from grade value via an instance color buffer.

**Rationale**: Constitution Principle IV explicitly requires instanced rendering for
"thousands of assay cylinders and lithology intervals." At the ~5,000-interval scale
targeted by SC-003, one draw call per mesh would be prohibitively slow; `InstancedMesh`
keeps this to a small, fixed number of draw calls regardless of interval count.

**Alternatives considered**: Individual `Mesh` objects per interval — rejected,
directly violates the constitution and would not hit the 60fps target at scale.

## Decision 4: Minimum curvature desurveying implementation

**Decision**: Implement minimum curvature as a pure, unit-tested Python function in
`backend/src/services/desurvey.py`, using the standard ratio-factor formulation, with
explicit test cases at near-vertical (dip ≈ -90°) and near-horizontal (dip ≈ 0°)
survey stations.

**Rationale**: Tension 1 in `reviews/phase0_review.md` and the master plan's own risk
table (§7) flag numerical edge cases at these angles as the specific place minimum
curvature is hardest to get right. A pure function with dedicated edge-case tests is
the smallest amount of engineering that directly addresses the documented risk.

**Alternatives considered**: Tangential method — explicitly prohibited by
constitution Principle I; not considered further.

## Decision 5: UTM zone auto-detection heuristic

**Decision**: Detect the likely UTM zone from Easting/Northing coordinate ranges in
the imported Collar CSV (valid UTM Easting is roughly 100,000–900,000m; Northing
range and hemisphere inferred from the project's expected region), and present the
detected zone to the user for one-click confirmation before commit — never assumed
silently.

**Rationale**: Directly implements FR-004 and the CRS rule already fixed in
`docs/architecture_baseline.md` § 2, and mirrors Tension 4's resolution in the panel
review (auto-detect, one-click confirm — friction reduced, rigor preserved).

**Alternatives considered**: Requiring manual zone entry on every import — rejected,
adds friction against the 60-second import bar (SC-001) without a rigor benefit over
auto-detect-then-confirm.

## Decision 6: Authentication approach

**Decision**: Lightweight passwordless magic-link authentication (emailed one-time
login link) issuing a short-lived JWT session token for subsequent API requests.

**Rationale**: The constitution allows either magic-link or hosted JWT auth; magic-link
avoids storing any password at all, which is the simplest secure option for a 1-3
user system (Tension 2 in the panel review: cheap to add now, expensive to bolt on
later, but shouldn't add real setup overhead for a solo tool).

**Alternatives considered**: Full OAuth2/SSO provider integration — rejected as
over-engineering for this user scale (Principle III); plain password auth — rejected,
constitution requires "real auth," and password storage/reset adds more surface area
than magic-link for no benefit at this scale.

## Decision 7: Object storage abstraction

**Decision**: A thin storage interface (`backend/src/storage/`) with a local-filesystem
implementation now, matching the constitution's Phase 0→Phase 1 storage migration
requirement (local FS → S3/MinIO) — callers depend only on the interface, never on
filesystem paths directly.

**Rationale**: Constitution Technology Stack Constraints explicitly requires this
abstraction so the future migration doesn't require rewriting business logic.

**Alternatives considered**: Direct filesystem calls throughout the codebase —
rejected, would require touching every call site during the Phase 1 migration,
violating the constitution's explicit requirement.

## Decision 8: Testing scope

**Decision**: Automated pytest coverage is required for the desurvey algorithm
(Decision 4) and import-validation rules (FR-005–FR-009); everything else (API
wiring, frontend rendering/interaction) is validated manually via `quickstart.md`.

**Rationale**: These two areas are exactly where the constitution and the panel
review flag correctness risk (silent data corruption, trace errors); testing
everything else would add tooling and maintenance burden disproportionate to a solo
project (Principle III), and CAD "feel" isn't meaningfully unit-testable regardless.

**Alternatives considered**: Full TDD across frontend and backend — rejected, not
requested in the spec and disproportionate to solo-maintainer scope; zero automated
tests — rejected, leaves the highest-risk logic (per the constitution itself)
unverified.
