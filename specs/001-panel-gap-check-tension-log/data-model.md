# Data Model: Panel Gap-Check + Tension Log

This "data model" is a Markdown document schema, not a database schema — it defines
the exact structure `reviews/phase0_review.md` must follow so that both a human
reviewer and a task-executing model can validate it mechanically.

## Entity: Phase Review

The top-level document. Exactly one instance: `reviews/phase0_review.md`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `phase` | string | Yes | Fixed value: `Phase 0 — Core Visualization & Modeling` |
| `source_reference` | string | Yes | Points to `mining_tool_planning_Final_claude4-7-2026.md` Section 1, and to the constitution version (`1.0.0`) it aligns with |
| `role_assessments` | list of Role Assessment | Yes | Exactly 8 entries, one per discipline listed below |
| `tensions` | list of Tension Entry | Yes | Minimum 3 entries |
| `completion_status` | enum: `draft` \| `complete` | Yes | `complete` only once FR-006's three conditions all hold |
| `approved_by` | string | Only when `complete` | Name/identifier of the project owner approving it |
| `approved_date` | date (YYYY-MM-DD) | Only when `complete` | Date of approval |
| `checklist_reference` | string | Yes | Link to `specs/001-panel-gap-check-tension-log/checklists/requirements.md` and a one-line statement of its pass state |

## Entity: Role Assessment

One per discipline. `role_assessments` must contain exactly these 8 disciplines, in
this order (matching the source document's order):

1. Exploration/Resource Geologist
2. Mining Engineer (open-pit)
3. Geotechnical Engineer
4. Data/Database Architect
5. Cloud/Software Architect
6. 3D Visualization Engineer
7. Professional Tool Strategist
8. UX/UI Designer (technical/CAD tools)

| Field | Type | Required | Notes |
|---|---|---|---|
| `discipline` | string | Yes | One of the 8 names above, verbatim |
| `non_negotiables` | list of string | Yes, min 1 | Each item: the requirement + why it is expensive/risky to add after implementation starts. If genuinely none apply, a single entry reading exactly `None identified` is allowed (per spec.md Acceptance Scenario 2) |
| `blind_spots` | list of string | Yes, min 1 | "Commonly forgotten" risks, distinct from non-negotiables. Same `None identified` allowance applies |

**Source mapping**: Each Role Assessment is transcribed from the corresponding
numbered role entry in Section "1a. Per-Role Non-Negotiables & Blind Spots" of
`mining_tool_planning_Final_claude4-7-2026.md` (lines 9–50). "Non-negotiable" bullets
map to `non_negotiables`; "Commonly forgotten" bullets map to `blind_spots`.

## Entity: Tension Entry

Minimum 3 entries, transcribed from Section "1b. Tension/Trade-off Log" of the master
planning document (lines 52–68), which already contains 4.

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | Yes | `Tension 1`, `Tension 2`, etc. — sequential, matches source numbering |
| `title` | string | Yes | Short label, e.g. "Desurveying precision vs solo build effort" |
| `positions` | string | Yes | The conflicting positions and which discipline(s) hold each |
| `resolution` | string | Yes | The single chosen resolution |
| `rationale` | string | Yes | Why that resolution was chosen over the alternative(s) |

**Source mapping**: Each Tension Entry is transcribed from one "Tension N — ..." block
in Section 1b. The block's opening paragraph maps to `positions`; the **Resolution:**
paragraph maps to `resolution` and `rationale` (split at the first sentence that gives
the reason, if a clean split exists — otherwise both fields may repeat the same text).

## Validation Rules (mechanical checks against spec.md Functional Requirements)

- `role_assessments` length == 8 → satisfies FR-001, FR-002, SC-001
- `tensions` length >= 3 → satisfies FR-003, SC-002
- Every Tension Entry has non-empty `resolution` and `rationale` → satisfies FR-004
- `completion_status` == `complete` requires `approved_by`, `approved_date`, and
  `checklist_reference` confirming all checkboxes in `checklists/requirements.md` are
  checked → satisfies FR-006
- No field in `reviews/phase0_review.md` may be edited to contradict a resolved
  Tension Entry without adding a new dated entry explaining the change → satisfies
  FR-007
