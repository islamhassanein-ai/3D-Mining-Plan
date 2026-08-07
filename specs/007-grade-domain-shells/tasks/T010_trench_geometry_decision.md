# T010 — Resolve trench geometry (Q5) and record the decision

> Read `specs/007-grade-domain-shells/tasks.md` and
> [`../analysis/Q5_trench_geometry_findings.md`](../analysis/Q5_trench_geometry_findings.md)
> before anything else. The findings document is the evidence base; this task is
> the decision and the small amount of work that follows from it.

| Field | Value |
|---|---|
| **Task ID** | T010 |
| **Phase** | 007 — Grade Domain Shells |
| **Priority** | P0 — blocks T005 |
| **Dependencies** | T004 (done) |
| **Complexity** | Small (documentation + two small code changes) |
| **Status** | **AWAITING GEOLOGIST DECISION** |

---

## Context

T004 put the real database through compositing and found that the trench
geometry rule written into its specification could not be implemented: trench
samples were to be composited along chainage and interpolated onto a polyline.
The investigation behind that is now complete and is recorded in the findings
document. In short:

- the stored coordinate is the **sample start point**;
- chainage means distance along the trench and, in surveyed data, agrees with
  the coordinates to ~1%;
- chainage is **not unique** — face lines carry paired samples at the same
  chainage, a metre apart vertically, with grades differing by up to 18 g/t;
- there is **no stored polyline** independent of the sample coordinates;
- 173 legacy rows have neither chainage nor order, but ~1 m spacing.

T004 currently places each assayed trench row at its own stored coordinates.
That was accepted as temporary ingestion behaviour. This task decides whether it
becomes the settled rule.

---

## Objective

A recorded decision on trench geometry, and the minimal code and specification
changes that follow from it.

---

## Decisions required

### D-A. Which geometry source is authoritative?

- **A1 — per-sample stored coordinates** (what T004 does today). Requires no
  inference, works for 100% of assayed rows, and is the only source that can
  separate the paired face samples.
- **A2 — chainage, where present, projected onto the polyline.** Requires a rule
  for the ~10% stretch in the demo data, a rule for non-unique chainage, and a
  fallback for the 173 rows that have none.

*The findings support A1. Recorded here as a decision, not applied.*

### D-B. What happens to the 173 legacy rows with no stated sample length?

- **B1 — keep excluding them** (today's default). Costs Abo Elmagd Hill its
  entire trench population, and with it that project's Q1 evidence.
- **B2 — include under an explicitly stated assumed length**, e.g. 1.0 m, which
  the ~1 m observed spacing supports. Already possible today via
  `trench_length_when_unspecified`; this decision is about whether it becomes a
  default, and whether the assumption is recorded per project.
- **B3 — record the length in the data** rather than assuming it at query time
  (see D-D).

### D-C. Does Q5 block T005?

**On the evidence, no.** Anisotropic IDW consumes *located point samples* and a
search ellipsoid; it never asks how two samples in a trench are connected, and
every trench sample already has an unambiguous position. Q5 blocks features that
reconstruct a trench *line* — sectional display, chainage-derived lengths,
trench-following geometry — not point interpolation.

Confirm or overrule. If confirmed, T005 unblocks on Q5 (it remains blocked on
Q1 and Q4).

### D-D. Is a data-model change wanted?

None is *required* for A1 + B1/B2. Two optional candidates:

- a nullable `sample_length_m` on `trench`, so a legacy sample's length is
  recorded once at import with its provenance, rather than assumed on every
  query. This is the clean way to do B2.
- a nullable `sample_height` / channel-identifier on `trench`, so the paired
  upper/lower face samples are explicit rather than inferred from elevation.

Both are additive and backward-compatible. Neither is needed to proceed.

---

## Work that follows regardless of the decision

### 1. Deterministic trench ordering (small, do this either way)

`extract_composite_points` queries `trench` with no `ORDER BY`, so the 173
legacy rows come back in planner order. This changes no current output — each
sample sits at its own coordinates and T002 is order-independent — but it is a
determinism gap and would become a correctness bug the moment anything
reconstructs a line.

Add `.order_by(Trench.trench_id, Trench.point_order, Trench.id)` and a test
asserting two extractions of the same project return composites in the same
order.

### 2. Correct the superseded claim in the T004 docstring

`backend/src/services/composite_points.py` states that chainage and polyline
distance disagree, citing AAF001. **That comparison was wrong** — it measured a
sample's end against a vertex position. Corrected text belongs in the docstring;
the conclusion (coordinates authoritative) stands, on the grounds of
non-uniqueness and the absence of a stored polyline instead.

---

## Deliverables

| # | File | Description |
|---|---|---|
| 1 | `specs/007-grade-domain-shells/analysis/Q5_trench_geometry_findings.md` | **Done** — evidence base |
| 2 | `specs/007-grade-domain-shells/OPEN_QUESTIONS.md` | Q5 updated with the decision once made |
| 3 | `backend/src/services/composite_points.py` | Deterministic ordering; corrected docstring |
| 4 | `backend/tests/integration/test_composite_points_flow.py` | Ordering determinism test |
| 5 | `specs/007-grade-domain-shells/tasks/T004_composite_points.md` | Requirements 8–10 rewritten to match the decision |
| 6 | *(only if D-D says yes)* Alembic migration + model change | |

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | D-A, D-B, D-C answered in writing in `OPEN_QUESTIONS.md`, with the reasoning |
| AC-2 | P0 | T004's specification rewritten so it matches the implementation — no task file left describing behaviour the code does not have |
| AC-3 | P0 | Trench query is deterministically ordered, with a test |
| AC-4 | P0 | The incorrect chainage-versus-polyline claim is corrected wherever it appears |
| AC-5 | P0 | No data is modified, migrated, or "cleaned" in application code |
| AC-6 | P1 | If D-D adds a column, the migration is additive with a working `downgrade()` |

---

## Anti-Patterns to Avoid

- **Reconciling the ~10% stretch** in the demo projects with a scale factor.
  That data was authored by hand in a CSV; a correction factor fitted to it
  would be applied to surveyed data too.
- **Deduplicating the paired face samples.** They are two real samples with
  grades differing by up to 18 g/t. Collapsing them to one would delete an assay.
- **Inferring the order of the 173 legacy rows** by nearest-neighbour chaining.
  It looks reasonable and would be an invented survey.
- **Defaulting the legacy sample length silently.** If B2 is chosen, the assumed
  length must appear in the extraction report every run.
- Treating "T005 is not blocked" as licence to start T005 — it remains blocked
  on **Q1** and **Q4**.
