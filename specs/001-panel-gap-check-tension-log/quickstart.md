# Quickstart: Validating `reviews/phase0_review.md`

No build, install, or run steps apply — this is a Markdown document, not software.
This guide is the manual validation procedure to confirm the deliverable satisfies
spec.md before it can gate Phase 0 planning (FR-006).

## Prerequisites

- `reviews/phase0_review.md` exists.
- `specs/001-panel-gap-check-tension-log/checklists/requirements.md` exists and has
  been reviewed.

## Validation steps

1. **Open** `reviews/phase0_review.md`.
2. **Count Role Assessments**: confirm there are exactly 8, one for each discipline
   listed in `data-model.md`, in the specified order. Fail if any are missing,
   duplicated, or renamed.
3. **Check each Role Assessment**: confirm `non_negotiables` and `blind_spots` each
   have at least one entry (or the literal `None identified`). Fail on empty lists.
4. **Count Tension Entries**: confirm there are at least 3. Fail if fewer.
5. **Check each Tension Entry**: confirm `positions`, `resolution`, and `rationale`
   are all present and non-empty. Fail on any missing field.
6. **Check cross-reference fields**: confirm `source_reference` names
   `mining_tool_planning_Final_claude4-7-2026.md` and constitution version `1.0.0`.
7. **Check completion fields**: if `completion_status` is `complete`, confirm
   `approved_by`, `approved_date`, and `checklist_reference` are all present.
8. **Cross-check the checklist**: open
   `specs/001-panel-gap-check-tension-log/checklists/requirements.md` and confirm
   every checkbox is `[x]`. If any are `[ ]`, `completion_status` MUST be `draft`, not
   `complete`.
9. **Timing check** (SC-003): time how long it takes to read
   `reviews/phase0_review.md` end-to-end and explain every Tension Entry's resolution
   aloud or in writing. Fail if it takes more than 10 minutes.

## Expected outcome

All 9 steps pass → `reviews/phase0_review.md` is complete and Phase 0 implementation
planning (a future `/speckit-plan` run for the actual Phase 0 software feature) may
proceed. Any failed step → the document stays `draft` and the specific gap must be
fixed before re-validating.
