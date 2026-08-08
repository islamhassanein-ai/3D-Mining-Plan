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
| **Status** | **DONE — 2026-08-08** |

> **Resolved 2026-08-08.** The stored trench XYZ is accurate and authoritative
> and represents the **midpoint of the sample interval**. D-A is answered:
> per-sample coordinates are the geometry source, which is what T004 already
> does. D-B is moot — all 424 Adel trench rows carry chainage; the 173 rows
> without it are mock data. D-C is confirmed: **Q5 does not block T005**.
>
> What remains is the cleanup in "Work that follows" below, plus D-D if wanted.

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

### D-D. Is a data-model change wanted? — **No change made**

Neither candidate below was taken. Adel states chainage on all 424 trench rows,
so nothing needs recording that the schema does not already hold, and both
columns would be speculative additions serving no current consumer. They stay
on record here in case a future dataset needs them.

None is *required* for A1 + B1/B2. Two optional candidates:

- a nullable `sample_length_m` on `trench`, so a legacy sample's length is
  recorded once at import with its provenance, rather than assumed on every
  query. This is the clean way to do B2.
- a nullable `sample_height` / channel-identifier on `trench`, so the paired
  upper/lower face samples are explicit rather than inferred from elevation.

Both are additive and backward-compatible. Neither is needed to proceed.

---

## Work that follows regardless of the decision

### 1. Deterministic trench ordering — **DONE**

`.order_by(Trench.trench_id, Trench.point_order, Trench.id)` added to the trench
query in `extract_composite_points`. The `id` tiebreak is what makes the order
*total* rather than merely stable-by-luck: legacy rows carry no `point_order`,
so without it their sequence was whatever the planner returned.

Two integration tests added — one asserting that two extractions of a project
containing `point_order IS NULL` rows return identical composites in identical
order, and one asserting trench lines are grouped and ordered when inserted out
of order.

Worth recording: ordering those legacy rows by `id` gives a **deterministic but
geologically meaningless** sequence — `Trench` has no insertion-order column, so
a UUID is the only total order available. That is the honest position. Their
real order is not in the database, and inventing one by nearest-neighbour
chaining would be a fabricated survey.

### 2. Correct the superseded claims — **DONE**

Two wrong claims were corrected in `composite_points.py`, `OPEN_QUESTIONS.md`,
the findings document, and the T004 task file:

- that chainage and polyline distance disagree (it compared a sample's *end*
  against a *point position*; Adel agrees to ~1–2%);
- that the stored coordinate is the sample *start* (it is the **midpoint**; the
  analysis could not distinguish the two on 96% uniform-length samples).

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

| # | Priority | Criterion | Outcome |
|---|---|---|---|
| AC-1 | P0 | D-A, D-B, D-C answered in writing in `OPEN_QUESTIONS.md`, with the reasoning | **Met** |
| AC-2 | P0 | T004's specification rewritten so it matches the implementation — no task file left describing behaviour the code does not have | **Met** — requirements 3–12, the interface contract, fixtures F5–F7d, and the acceptance criteria all rewritten |
| AC-3 | P0 | Trench query is deterministically ordered, with a test | **Met** — 2 tests |
| AC-4 | P0 | The incorrect chainage-versus-polyline claim is corrected wherever it appears | **Met** — corrected in the service docstring, `OPEN_QUESTIONS.md`, the findings document and the T004 task file; the start-vs-midpoint claim corrected in the same places |
| AC-5 | P0 | No data is modified, migrated, or "cleaned" in application code | **Met** — the only data change was T011's source-CSV correction and re-import, done through the application's own import path |
| AC-6 | P1 | If D-D adds a column, the migration is additive with a working `downgrade()` | **N/A** — no column added |

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
