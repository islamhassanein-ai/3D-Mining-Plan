# Core Platform Architecture Baseline

**Source Reference**: mining_tool_planning_Final_claude4-7-2026.md, Sections 2, 6, 7, 8, 9; reconciled via specs/002-architecture-baseline/{spec.md, data-model.md}; aligned with project constitution v1.0.0 (.specify/memory/constitution.md)
**Status**: complete

## 1. Product Definition

- **Vision**: A browser-based, professional-grade 3D viewer for your own open-pit gold exploration data — drillholes, assays, trenches, and grade shells — that looks and feels like Leapfrog/Micromine in interaction quality, built and evolved entirely by you via Claude Code, accessible from any device with a browser.
- **Target Users / JTBD**: You (geologist + GIS/DB architect), occasionally a trusted colleague reviewing the same prospect. Job-to-be-done: "Let me pull up this prospect's real data anywhere, trust what I'm seeing, and think out loud about it — without opening Leapfrog or rebuilding a one-off HTML file each time."
- **V1 Non-Goals**:
  - Multi-tenant orgs
  - Billing
  - Public sharing/marketing site
  - Underground mining support
  - Non-English UI
  - Formal JORC report generation
  - Third-party customer onboarding
- **Kill Criterion**: If, after importing 2–3 real messy CSVs from your actual past projects, the import requires more manual correction than just prepping data for the old Plotly.js prototype did — the core premise (this is *faster and more trustworthy* than the ad-hoc approach) is false, and the project should pivot to import-robustness-only work before any further visual features are added.

## 2. Data Model

### Entities

- **Project**: `id`, `name`, `utm_zone`, `commodity`, `created_at`, `superseded_by` (nullable) — Has many Collar, Trench, Wireframe.
- **Collar**: `id`, `project_id`, `hole_id`, `easting`, `northing`, `elevation`, `utm_zone`, `import_batch_id`, `created_at`, `superseded_by` (nullable) — Belongs to Project; has many Survey, Assay Interval, Lithology Interval.
- **Survey**: `id`, `collar_id`, `depth`, `dip`, `azimuth`, `desurvey_method` — Belongs to Collar.
- **Assay Interval**: `id`, `collar_id`, `from_depth`, `to_depth`, `grade_value`, `grade_unit`, `below_detection_limit`, `qaqc_flag`, `import_batch_id`, `superseded_by` (nullable) — Belongs to Collar.
- **Lithology Interval**: `id`, `collar_id`, `from_depth`, `to_depth`, `lith_code`, `rqd_percent`, `core_recovery_percent`, `superseded_by` (nullable) — Belongs to Collar.
- **Trench**: `id`, `project_id`, `trench_id`, `easting`, `northing`, `grade_value` — Belongs to Project.
- **Wireframe**: `id`, `project_id`, `name`, `solid_type`, `file_ref` — Belongs to Project.
- **Import Batch**: `id`, `source_file`, `import_date`, `status` — Referenced by Collar and Assay Interval (and other imported entities).
- **User**: `id`, `email`, `role` — Account with access to the system.

**Reconciliation Note (superseded_by)**: The source planning document's Section 6 ERD does not include a `superseded_by` column on any entity — only a narrative mention in Section 1 ("soft versioning — never overwrite an import; append/supersede with audit trail"). The ratified constitution (Principle V: Soft Versioning & Audit Trail) makes soft-versioning a hard requirement: *"The database must never hard delete drillhole data... link older rows using the superseded_by foreign key."* Per this baseline's own governance rule (constitution governs where it and the source document diverge), this data model adds `superseded_by` to every entity that represents importable/correctable data (Project, Collar, Assay Interval, Lithology Interval). This is a reconciliation, not a new architectural decision, making the already-ratified constitution requirement concrete in the entity list.

### Rules

- **CRS / Coordinates**: All coordinates are stored in UTM (zone stored per-project, per the auto-detect-then-confirm flow). `utm_zone` is required wherever coordinates are stored and must be presented to the user for explicit confirmation at import time — never silently assumed (FR-005).
- **Units & Below-Detection-Limit Handling**: Assay units must be stored explicitly per row (`ppm`/`g/t`/`%`) — never assumed. `grade_unit` is required per Assay Interval row, and mixed units within a single import must be rejected, not silently converted without a per-file unit declaration. Below-Detection-Limit (BDL) values must be stored as flagged (`below_detection_limit = true`) with the original detection-limit value preserved in `grade_value`; this value must never be zeroed, nulled, or dropped (FR-006).
- **Bad Import Handling**: Errors and anomalies in imported data must be handled as follows:
  - **Missing/Wrong UTM Zone**: Flag and require explicit user confirmation before committing; never auto-assume (FR-005).
  - **Mixed Units (ppm/g/t/%)**: Reject silent mixing. Require a per-file unit declaration; convert internally while preserving the original units in the raw import record (FR-006).
  - **Swapped Lat/Long**: Run heuristic range-checks (using Egypt UTM bounds) and warn the user if values look swapped (FR-007).
  - **Overlapping/Gap Intervals**: Overlapping or gapped `from_depth`/`to_depth` ranges within a Collar's Assay Interval or Lithology Interval sets must be flagged visually in a diff view for geologist review; never auto-correct or silently merge them (FR-007).

## 3. System Architecture

- **Rendering Approach**: Use an open-source, CAD-capable 3D rendering library. This approach provides the best CAD-like control, full customization, and a large developer community. Alternative options were rejected because they either lack the orbit and interaction feel required for CAD-style exploration, are built for global-scale terrain (overkill for a single prospect), or represent limited graphing libraries that do not support rich 3D manipulation.
- **Component Boundaries**: The system consists of six main components:
  - **Browser Client**: Handles client-side user interactions, 3D visualization rendering, and local calculations (such as slicing and measurements). It communicates with the API Server via HTTPS.
  - **API Server**: Coordinates client requests, performs data access, manages file uploads, and integrates with the Auth Service and Database.
  - **Parsing/ETL Service**: Processes uploaded geological CSV files (parsing, validation, minimum-curvature desurveying, and coordinate transformations) and loads the structured results into the database.
  - **Database**: A relational database storing structured exploration entities (collars, assays, surveys, lithologies) and project parameters.
  - **Object Storage**: Holds raw uploaded CSV data and 3D wireframe solid files.
  - **Auth Service**: Manages user authentication and identity verification.
- **Multi-Tenancy Model**: Not applicable at SaaS scale. For the small-team read-only-sharing case, a simple `project_id` scoping within a single shared database is sufficient; schema-per-tenant or database-per-tenant models are avoided as over-engineering for 1–3 users.
- **Client/Server Processing Split**: Data parsing, minimum-curvature desurveying, and coordinate reference system (CRS) conversions run server-side during data import. 3D rendering, slicing-plane geometry calculations, and distance/angle measurements run client-side in the browser to ensure instantaneous user responsiveness.
- **Technology Stack**: Three.js, FastAPI, and PostgreSQL with PostGIS. See .specify/memory/constitution.md § Technology Stack Constraints for the authoritative list — not restated here.

## 4. Non-Functional Requirements

- **Security / Isolation**: Lightweight real authentication; HTTPS only; object storage access scoped per-project.
- **Audit / Provenance**: Every import batch and edit timestamped and attributable — future-proofs for JORC-style reporting even though report generation is out of scope now.
- **Performance Targets**: 60fps scene interaction up to ~5,000 assay intervals; import processing under 30s for typical CSV sizes.
- **Offline / Field Use**: Not a Phase 0 requirement given browser-based access-from-anywhere goal, but cache last-loaded project client-side so a brief connectivity drop doesn't blank the screen.

## 5. UX/UI Direction

- **Visual Theme & Interface Regions**: Dark CAD-style theme, featuring four fixed interface regions: a persistent left sidebar (with layer toggles for drillholes, lithology, grade shells, topography, trenches, and wireframes), a floating right-side inspector panel for click-to-inspect data, a top toolbar containing camera presets and measurement tools, and a main 3D viewport for visual interaction with the model.
- **Core Interaction Patterns**:
  - Smooth orbit/pan/zoom with damping (avoiding jerky, default camera feel).
  - Instant, correctly-formatted drillhole card display on click.
  - Grade-cutoff slider that updates the scene in real time without page reload.
  - Section-view slicing plane that feels fully synchronized and lag-free.
  - One-flow import sequence: drag CSV → view diff and validation results → commit.
  - Camera presets (plan, section, isometric views) accessible via the top toolbar and keyboard shortcuts.

## Governance of This Document

This document serves as the single source of truth and authoritative baseline for the Core Platform's product scope, data model, system architecture, non-functional requirements (NFRs), and UX/UI direction. 

All future feature specifications, implementation plans, and development tasks must align with and satisfy the guidelines, structures, and constraints defined in this baseline. 

If a future feature or implementation requires a divergence or modification of the data model, architectural choices, NFRs, or UX direction, **this document must be formally amended first**. Future feature specifications must update this baseline rather than silently contradicting it (FR-015).

<!-- SC-001 check: human-verified by Omar (project owner) on 2026-07-17, under 5 minutes -->
