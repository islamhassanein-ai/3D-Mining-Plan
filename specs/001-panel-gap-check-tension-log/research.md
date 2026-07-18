# Phase 0 Research: Panel Gap-Check + Tension Log

No `NEEDS CLARIFICATION` markers remain in the Technical Context — all were resolved
either by reasonable defaults (this is a documentation-only feature) or by the
`/speckit-clarify` session recorded in spec.md's Clarifications section
(2026-07-15). This file records the two remaining decisions needed before design.

## Decision 1: Content sourcing for `reviews/phase0_review.md`

- **Decision**: The 8 Role Assessments and the Tension Entries are transcribed and
  restructured from Section 1 ("PANEL GAP-CHECK + TENSION LOG") of
  `mining_tool_planning_Final_claude4-7-2026.md`, mapped into the Role
  Assessment / Tension Entry schema defined in `data-model.md`, not authored from
  scratch.
- **Rationale**: spec.md's Assumptions and Clarifications both establish that this
  deliverable must "align with and reference" the Phase 0 content already drafted in
  the master planning document and ratified by the constitution. The source material
  already contains 8 role write-ups and 4 tension/resolution entries — more than the
  minimum of 3 required by FR-003 — so no new analysis is required, only faithful
  restructuring.
- **Alternatives considered**: Drafting a fresh independent analysis per role — rejected
  because it risks diverging from the already-ratified constitution (e.g., re-opening
  the desurveying-method or CRS-rigor decisions that Tensions 1 and 4 already closed),
  and duplicates work with no added value.

## Decision 2: Minimum-capability implementer assumption

- **Decision**: Every task in `tasks.md` must be self-contained — it must name the
  exact source lines/section to read, the exact target file and section to write, and
  the exact content shape expected — so that a smaller/faster model (e.g. Gemini Flash
  3.5) can execute it without needing to infer intent or hold prior task context.
- **Rationale**: Explicitly requested by the user for this planning pass. Because this
  feature is pure transcription/restructuring (Decision 1) rather than original
  synthesis, it is well suited to explicit, mechanical task instructions.
- **Alternatives considered**: Writing fewer, larger tasks ("produce the full review
  document") — rejected because a single large open-ended task is exactly the shape
  most likely to produce inconsistent or incomplete output from a lower-capability
  model; smaller, mechanically-specified tasks reduce that risk.

**Output**: Both decisions resolved. Proceeding to Phase 1 design.
