# Phase 0 Panel Gap-Check + Tension Log

**Phase**: Phase 0 — Core Visualization & Modeling
**Source Reference**: mining_tool_planning_Final_claude4-7-2026.md, Section "1. PANEL GAP-CHECK + TENSION LOG"; aligned with project constitution v1.0.0 (.specify/memory/constitution.md)
**Completion Status**: complete

## Role Assessments

### 1. Exploration/Resource Geologist
- Non-negotiables:
  - Correct desurveying (trace must match reality within cm-scale at shallow depth); assay values with correct units and below-detection-limit (BDL) handling visible, not silently zeroed.
  - Ability to see lithology intervals alongside assay — grade without geological context is meaningless.
- Blind spots:
  - QA/QC flags (duplicates, standards, blanks) — even a solo tool should tag samples so bad data doesn't get trusted blindly.
  - Sample interval overlaps/gaps are common in real CSVs — geologist needs to *see* this, not have it silently "fixed."

### 2. Mining Engineer (open-pit)
- Non-negotiables:
  - Coordinates must be in a real, engineering-usable CRS (UTM, correct zone) — not an arbitrary local grid, even for a personal tool. This decision is expensive to change later.
  - True thickness vs downhole length must be distinguishable — apparent grade × wrong thickness misleads resource thinking.
- Blind spots:
  - Topography/DEM surface — without it, pit-shell/strip-ratio intuition is impossible even informally.

### 3. Geotechnical Engineer
- Non-negotiables:
  - Structural data (fault traces, dip/strike readings) should have a place in the schema even if not rendered in Phase 0 — retrofitting this field later touches every import.
  - Core recovery/RQD fields reserved in the lithology/interval table, even if unused initially.
- Blind spots:
  - Bench/slope angle context — not urgent for Phase 0 given open-pit-only + solo use, but flag for Phase 2.

### 4. Data/Database Architect
- Non-negotiables:
  - Every table needs a `source_file`, `import_date`, and `import_batch_id` — provenance is what separates a professional tool from a toy, especially solo where "which CSV did this come from" gets forgotten fast.
  - Soft versioning — never overwrite an import; append/supersede with audit trail.
- Blind spots:
  - Standard field naming conventions (matching industry CSV templates from Leapfrog/Datamine) — makes future import-format expansion trivial instead of a rewrite.

### 5. Cloud/Software Architect
- Non-negotiables:
  - Even single-user, use real auth (not "share a link with no login") if data is proprietary exploration data — accidental public exposure is a real business risk.
  - Object storage for raw uploaded files, separate from parsed relational data — lets you reprocess if parsing logic improves.
- Blind spots:
  - Since this is Claude-Code-built solo, architecture must stay simple enough that *you* can debug it 6 months from now without re-reading everything — favor boring, well-documented stacks over clever ones.

### 6. 3D Visualization Engineer
- Non-negotiables:
  - 60fps interaction target even with a few thousand assay-interval cylinders — jank instantly signals "toy" to a geologist used to Leapfrog.
  - Orbit/pan/zoom must feel like CAD (smooth damping, orbit-around-cursor, not orbit-around-origin) — this is the #1 "feel" differentiator.
- Blind spots:
  - Camera presets (plan view, section view, isometric) with keyboard shortcuts — professionals judge tools fast on whether these exist.

### 7. Professional Tool Strategist
- Non-negotiables:
  - The tool must beat "just open Leapfrog trial" on **friction**, not features — drag-and-drop CSV → 3D scene in under 60 seconds is the bar.
  - **Kill criterion**: if importing real messy field CSVs (your actual data, not clean demo data) takes more than a few manual fixes, the tool has failed its core purpose — professionals will not tolerate a fragile importer.
- Blind spots:
  - Even solo tools need a "why not just use Excel + Plotly like before" answer — the answer here is: persistent project state, real CRS handling, and audit trail, not just prettier rendering.

### 8. UX/UI Designer (technical/CAD tools)
- Non-negotiables:
  - Persistent layer/legend sidebar (toggle drillholes, lithology, grade shell, topo) — this is a night-and-day usability signal vs a generic Plotly dashboard.
  - Click-to-inspect must show the *same* information a geologist would pull up in Leapfrog's drillhole card — collar, survey, full interval table — not a stripped-down tooltip.
- Blind spots:
  - Empty/loading/error states — a solo tool used under time pressure (site visit, poor connectivity) needs graceful failure, not a blank screen.

## Tensions

### Tension 1 — Desurveying precision vs solo build effort
- Positions: Geologist wants minimum-curvature desurveying (industry standard, better accuracy for deviated holes). Data Architect and Cloud Architect note minimum-curvature is meaningfully more complex to implement correctly (numerical edge cases at near-vertical/near-horizontal survey stations) than tangential method, and this is a solo Claude-Code build with limited QA bandwidth.
- Resolution: Use **minimum curvature** anyway — for open-pit shallow holes the accuracy difference matters for engineering trust, and the algorithm is well-documented enough that Claude Code can implement it correctly with proper test cases.
- Rationale: This is the one place we do NOT cut corners, because a geologist will notice trace errors immediately and lose trust in everything else.

### Tension 2 — Real auth/multi-user infrastructure vs "it's just me"
- Positions: Cloud Architect wants proper auth (even for a single user) citing data-exposure risk. Professional Tool Strategist and you (as the actual constraint-setter) push back: this adds real setup overhead for a solo tool with no other users initially.
- Resolution: Use a lightweight but real auth provider (e.g., magic-link or simple hosted auth) rather than no-auth — cheap to add now, expensive to bolt on later once real data lives in the system.
- Rationale: This overrides the "keep it minimal" instinct because the downside (leaked exploration data) is asymmetric.

### Tension 3 — Full JORC schema completeness vs Phase 0 scope
- Positions: Geotechnical Engineer and Data Architect want RQD, structural, and QA/QC fields fully modeled now. Professional Tool Strategist argues Phase 0 should be visualization-first per your explicit instruction, and full JORC-grade schema is Phase 2+ work that risks delaying the "does this even look good and work" milestone.
- Resolution: **Reserve the fields in the schema now** (empty/nullable columns) so nothing needs restructuring later, but **do not build UI or validation logic for them in Phase 0**.
- Rationale: Schema-complete, feature-deferred.

### Tension 4 — CRS rigor vs "it's just my own prospect"
- Positions: Mining Engineer insists on proper UTM zone handling with explicit zone selection at import. 3D Viz Engineer notes this adds import-flow friction that could hurt the "under 60 seconds" strategist goal.
- Resolution: Auto-detect UTM zone from coordinate ranges where possible, but always show the detected zone to the user for one-click confirmation rather than silent assumption.
- Rationale: Friction reduced to a single click, rigor preserved.

## Completion

- Approved by: Omar (project owner)
- Approved date: 2026-07-16
- Checklist reference: specs/001-panel-gap-check-tension-log/checklists/requirements.md — all items passing

<!-- SC-003 check: not independently timed; owner reviewed and approved the content on 2026-07-16 -->
