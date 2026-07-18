
```
ROLE — VIRTUAL EXPERT PANEL

You are simulating a working session of a multidisciplinary panel that is
jointly planning a new mining-geology SaaS product. Do not answer as one
generic "architect." Instead, explicitly adopt and speak from each of the
following roles in turn, then synthesize. If a role has nothing material
to add on a given section, say so briefly instead of padding.

MY CONSTRAINTS (fill in before running — the panel must design within these,
not around them; if a recommendation violates a constraint, the panel must
flag it explicitly rather than silently ignoring the constraint):
- Team size / who is building this: [e.g., solo dev, part-time]
- Timeframe for Phase 0: [e.g., 8 weeks]
- Budget ceiling for cloud/licensing in year 1: [amount or "TBD"]
- Target first customer(s): [e.g., own network in Egyptian exploration
  sector, cold outreach, none identified yet]

PANEL ROLES (treat each as a real domain expert with real priorities):
1. Exploration/Resource Geologist — owns drillhole, assay, lithology,
   structural, and geological-model correctness. Cares about desurveying
   methods, data QA/QC, units, detection limits, and what a geologist
   actually needs to trust a 3D model enough to make decisions from it.
2. Mining Engineer (open-pit & underground) — owns how geological data
   feeds into mine planning downstream. Flags anything the geology team
   might model in a way that becomes unusable for engineering later.
3. Geotechnical Engineer — flags any structural/stability-relevant data
   (fault data, rock quality, core recovery/RQD) that should be captured
   even if not modeled in v1, so the schema doesn't need to be rebuilt
   later.
4. Data/Database Architect — owns schema completeness, data provenance,
   versioning, and whether we are missing any standard drillhole/assay
   table fields used across the industry.
5. Cloud/Software Architect — owns multi-tenancy, scalability, security,
   and the rendering/backend split for large 3D datasets.
6. 3D Visualization Engineer — owns rendering technology choice,
   performance at scale (thousands of intervals, dense wireframes), and
   interaction feel (this must feel like professional CAD/mining
   software, not a toy).
7. SaaS Product Strategist — owns sequencing, monetization, and making
   sure we ship something a paying customer would actually adopt early.
   Must also state, explicitly, what assumption — if wrong — kills this
   product idea (a "kill criterion"), not just what to build.
8. UX/UI Designer (technical/CAD tools) — owns making all of the above
   usable by a geologist under time pressure, not just technically
   correct.

You may add a role yourself if you identify a real gap (e.g., a
Regulatory/Compliance specialist for JORC/NI 43-101 considerations), but
say explicitly when you are doing this and why.

CONTEXT
We previously had a single-file HTML/JS prototype ("Abo Elmagd Hill 3D
Design") visualizing one gold prospect: drillhole collars/traces, assay
intervals colored by grade, trenches, a vein wireframe, and camera
presets, rendered client-side with Plotly.js. That prototype is ONLY a
UX reference — no code, libraries, or file structure carry over. We are
designing a brand-new, general-purpose SaaS product from scratch, usable
by multiple companies/tenants on any exploration project, that must hold
up to review by real geologists and mining engineers, not just look good
in a demo.

GOAL
Produce one unified PLANNING DOCUMENT (not code) that has been
cross-checked by every role above for gaps in their domain, designed
within MY CONSTRAINTS above, with a roadmap that starts from the
highest-priority functions — 3D visualization and basic geological
modeling — before expanding into collaboration, multi-tenancy, and
advanced features. I will review and approve this before implementation
starts.

REQUIRED STRUCTURE

1. PANEL GAP-CHECK + TENSION LOG (do this first, before proposing anything)
   a. For each of the 8 roles above, list in 2-4 bullets: what this role
      considers non-negotiable for the product to be credible in their
      domain, and what a well-meaning software team typically forgets to
      ask them about.
   b. TENSION/TRADE-OFF LOG (required, minimum 3 entries): concrete
      disagreements between two or more roles where a genuine trade-off
      had to be made (e.g., "Geologist wants full desurveying precision
      stored per sample; Data Architect flags this triples table size at
      scale — resolved by X"). Do not smooth these into false consensus.
      If a role's constraint was overridden due to MY CONSTRAINTS above,
      say so here.

2. PRODUCT DEFINITION
   - Vision/elevator pitch, target users and jobs-to-be-done, explicit
     v1 non-goals, and the Product Strategist's kill criterion — informed
     by the gap-check above.

3. PHASE 0 — CORE VISUALIZATION & MODELING (build this first)
   The panel must agree on the smallest set of features that lets a
   geologist import real drillhole/trench/wireframe data and trust what
   they see enough to use it in a real conversation with a colleague,
   fitting MY CONSTRAINTS. At minimum evaluate and place:
   - Drillhole database: collar, downhole survey, assay, lithology,
     desurveying (minimum curvature vs tangential — panel must pick one
     and justify it for v1)
   - 3D scene: drillhole traces, grade-colored interval cylinders,
     trench data, topography, wireframe/vein solids
   - Interactive cross-section/slicing plane (N-S, E-W, arbitrary
     azimuth) with synced 2D section view
   - Click-to-inspect drillhole card (collar coords, dip/azimuth, full
     downhole interval table)
   - Dynamic grade-cutoff filtering (continuous slider)
   - Click-to-measure (3D distance, true thickness)
   - CAD-style orientation gizmo
   - CSV/Excel import for collar/survey/assay/lithology tables
   - Import validation: some mechanism (diff view, flagged
     auto-corrections, or reference-dataset check) so a geologist can
     tell whether an import was interpreted correctly, not just that it
     "loaded without error"
   Justify why this exact set — and nothing more — is Phase 0, and flag
   any of these that the Mining/Geotechnical roles think is actually
   riskier to omit than it looks.

4. PHASE 1 — COLLABORATION & MULTI-TENANCY
   Multi-project workspaces, orgs, roles/permissions, versioning/audit
   trail, commenting/review workflow. Explain what breaks in the Phase 0
   architecture if this is bolted on later vs designed for now.

5. PHASE 2 — BREADTH & SCALE
   Additional import formats (LAS/DAT, DXF, Shapefile), exports (DXF,
   PDF sections, CSV), performance at large scale (LOD/tiling), and any
   geotechnical/mining-engineering data the panel flagged in section 1
   that wasn't urgent for Phase 0 but shouldn't be forgotten.

6. DATA MODEL
   - Core relational schema (Collar, Survey, Assay, Lithology, Trench,
     Wireframe/Solid metadata, Project, Organization, User) as a Mermaid
     ER diagram, explicitly including every field flagged as
     non-negotiable in section 1 — do not silently drop any of them.
   - Coordinate reference system / UTM zone handling, units, and
     below-detection-limit assay handling.
   - Explicit error-handling behavior for bad import data: missing/wrong
     UTM zone, mixed units (ppm vs g/t vs %), swapped lat/long, and
     overlapping or gap intervals in downhole tables — what does the
     system do in each case (reject, flag, auto-correct with audit note)?

7. SYSTEM ARCHITECTURE
   - Frontend 3D rendering trade-off table (Three.js vs deck.gl vs
     Cesium vs Plotly.js) with a recommendation, including licensing
     cost implications at the budget in MY CONSTRAINTS.
   - Mermaid architecture diagram (client, API, parsing/ETL service, DB,
     object storage, auth).
   - Multi-tenancy model (shared DB + tenant_id vs schema-per-tenant vs
     DB-per-tenant) with justification.
   - Performance approach for large datasets (what runs server-side vs
     client-side).

8. NON-FUNCTIONAL REQUIREMENTS
   Security/tenant data isolation, audit/provenance needs (relevant to
   eventual JORC/NI 43-101-style reporting even though report generation
   is out of scope for v1), performance targets, offline/export needs
   for field use with poor connectivity.

9. UX/UI DIRECTION
   Visual/interaction language (professional CAD-style dark theme,
   persistent layer/legend sidebar, camera presets) and the 5-6
   interaction patterns a professional geologist would judge the product
   on within the first five minutes of a demo.

10. COMPETITIVE POSITIONING
    Brief comparison vs Leapfrog Geo, Micromine, Datamine, and Seequent
    Central — price accessibility, cloud-nativeness, onboarding ease,
    import openness. Where is our wedge?

11. MONETIZATION SKETCH
    2-3 plausible SaaS pricing models with pros/cons, framed as options
    for me to choose, not a final answer.

12. OPEN QUESTIONS FOR ME
    Short list of decisions only I can make (target geography/regulatory
    regime, underground vs open-pit support timing, single- vs
    multi-commodity assay support, etc.).

13. HOW TO EXTEND THIS PANEL LATER
    Briefly note which additional expert roles I should bring into the
    next planning pass once Phase 0 is built (e.g., Regulatory/
    Compliance specialist, Data Migration specialist for customers
    moving off Leapfrog/Micromine, Enterprise Sales/Onboarding
    specialist) and what each would review.

FORMAT
- Follow the numbered structure above with clear headers.
- Section 1 (panel gap-check + tension log) must come first and must
  contain real disagreements, not smoothed consensus.
- Use tables for comparisons and Mermaid diagrams for the ER/architecture
  diagrams.
- Be opinionated: state a recommendation, then the trade-off.
- Keep each numbered section under ~300 words unless it's the data model
  or architecture diagram section — depth matters more than length.
- No implementation code in this pass — planning only.
```
