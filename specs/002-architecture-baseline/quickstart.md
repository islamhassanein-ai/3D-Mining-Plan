# Quickstart Validation: Core Platform Architecture Baseline

No code to run — this validates a Markdown document. Work through these steps against
`docs/architecture_baseline.md` in order; if any step fails, fix the gap before
continuing.

1. **File exists**: `docs/architecture_baseline.md` exists at the repository root.
2. **Product Definition present** (FR-001–FR-003): the document states the product
   vision, primary target users/JTBD, all 7 listed V1 non-goals, and the kill
   criterion (including what happens when it's triggered).
3. **Data Model — entities present** (FR-004): all 9 entities from
   [data-model.md](data-model.md) appear — Project, Collar, Survey, Assay Interval,
   Lithology Interval, Trench, Wireframe, Import Batch, User — each with its key
   fields and relationships, including the `superseded_by` reconciliation note.
4. **Data Model — rules present** (FR-005–FR-007): the document states UTM-only
   coordinate storage with auto-detect-then-confirm at import, per-row explicit grade
   units with no silent mixing, below-detection-limit preservation, and the
   flag-don't-auto-correct rule for bad imports (wrong zone, mixed units, swapped
   lat/long, overlapping/gap intervals).
5. **System Architecture present** (FR-008–FR-011): the document states the chosen
   client-side rendering approach and why, the component boundaries (client, API
   server, parsing/ETL, database, object storage, auth service), the multi-tenancy
   model, and the client/server processing split.
6. **Technology Stack cross-reference only** (Research Decision 2): concrete
   technology names appear in exactly one subsection, and that subsection points to
   `.specify/memory/constitution.md` § Technology Stack Constraints rather than
   restating versions or rationale.
7. **NFRs present** (FR-012): the document states the security/isolation baseline,
   audit/provenance baseline, performance targets (frame-rate at a stated interval
   count, import time budget), and offline/field-use expectation.
8. **UX/UI Direction present** (FR-013–FR-014): the document states the visual theme,
   all 4 fixed interface regions, and all 6 interaction patterns judged in the first
   few minutes.
9. **Governance footer present** (FR-015): the document states that it is
   authoritative until formally amended and that diverging feature specs must update
   it rather than silently contradict it.
10. **No orphan fields** (SC-002): every entity/field named in
    `docs/architecture_baseline.md`'s Data Model section matches
    [data-model.md](data-model.md) exactly — nothing invented in one but missing from
    the other.
11. **5-minute scope check** (SC-001, human-verified): pick any feature idea not yet
    built, and confirm a person can determine in/out of scope using only
    `docs/architecture_baseline.md` in under 5 minutes. This step requires an actual
    human read — do not mark it passed without one.
