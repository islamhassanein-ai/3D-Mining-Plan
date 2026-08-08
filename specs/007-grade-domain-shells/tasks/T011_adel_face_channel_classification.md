# T011 — Adel face-channel classification: correct the source, not the code

> Read `specs/007-grade-domain-shells/tasks.md` first.

| Field | Value |
|---|---|
| **Task ID** | T011 |
| **Phase** | 007 — Grade Domain Shells |
| **Priority** | P0 — blocks the Q1 trench-influence decision |
| **Dependencies** | T004 (done) |
| **Complexity** | Small |
| **Status** | **DONE — option A applied 2026-08-08** |

> **Resolved by option A: the source CSV was corrected and re-imported.**
>
> `sample_data/Adel/Adel2.csv` — 236 AAF rows changed `Type` from `TR` to `FC`;
> the 189 AAT rows were left untouched. The edit was verified byte-for-byte:
> identical file size, and masking the `Type` field makes the before and after
> files identical, so nothing else moved. A pre-edit copy is kept beside it as
> `Adel2.csv.bak-pre-fc`. Neither file is in git — `sample_data/*/` is
> gitignored, as real project data should be.
>
> Re-imported through the application's own import path (`POST
> /projects/{id}/imports` then `/commit`), batch
> `1355dea7-1564-4ab3-92ce-be1164aab83f`. Preview reported zone `Adel` →
> the existing project, `{'DD': 22, 'TR': 6, 'FC': 6}`, 0 errors. The 424
> previous trench rows were superseded, not deleted, and active counts are
> unchanged at 424 rows / 23 collars.
>
> Verified end to end with no code change:
> `analyze_sample_types.py "Adel"` now reports
> `{'DDH': 247, 'FC': 236, 'TR': 188}`.
>
> **AAF004A is FC**, confirmed as a re-sampled face — samples were taken again
> for verification. See the note at the end of this file.

---

## The problem

Confirmed from Adel field data: **`AAF` lines are Face Channel (FC)** and
**`AAT` lines are Trench (TR)**.

The database does not record that. All 424 Adel trench rows carry
`hole_type = 'TR'`, the six AAF lines included. The misclassification did **not**
come from the importer or the database — the source import payload
(`c738728d69e34c64b2c8a0a2147fc3cb.json`, batch
`137aed86-11e7-42b2-9915-212a554c3035`) declares `hole_type = 'TR'` for all
twelve lines, so it originates in the CSV that was imported.

| Line | rows | true type | stored type |
|---|---|---|---|
| AAF001, AAF002, AAF003, AAF004, AAF004A, AAF005 | 236 | **FC** | `TR` |
| AAT001–AAT006 | 188 | TR | `TR` |

## Why it matters

The two populations are not alike, and pooling them was hiding it:

| Population | n | lw mean | median | p75 | cv |
|---|---|---|---|---|---|
| DDH | 247 | 0.167 | 0.020 | 0.030 | 4.65 |
| FC | 236 | 3.908 | 0.720 | 5.985 | 1.66 |
| TR | 188 | 0.527 | 0.050 | 0.185 | 3.34 |

FC reads **7.4×** TR. Against core, FC is 23.5× and TR is 3.2×; pooled they gave
the 14.32 that Q1 was about to be decided on. **Q1 cannot be answered correctly
until this is fixed** — it is at least two decisions, one per surface type, and
FC is the population most likely to warrant geometry-only treatment.

## What must NOT be done

**Do not derive the type from the `trench_id` prefix in application code.**
Pattern-matching `AAF` inside `composite_points` would be a project-specific
rule buried in a generic service, it would silently reclassify any future
dataset whose naming happens to collide, and it would leave the database still
holding the wrong value for every other consumer — the scene, exports, QAQC.

The classification belongs in the data.

## Options

**A — Correct the source CSV and re-import (recommended).**
Set the type column to `FC` on the six AAF lines in the source file, re-import,
and let the existing supersede machinery retire the old rows. The data becomes
correct at its origin, re-imports stay idempotent, and every consumer sees it.
Cost: requires the original CSV and a re-import cycle.

**B — One-off data correction script against the database.**
`UPDATE trench SET hole_type = 'FC' WHERE project_id = <adel> AND trench_id LIKE 'AAF%'`,
written as a reviewable script under `backend/`, run once, with the row count
reported. Faster than A. Cost: **a later re-import of the same CSV would undo
it**, because the source still says `TR`.

**C — A recorded line-to-type mapping applied at import.**
An explicit, stored mapping consulted by the importer. Most robust for repeated
imports of a file that cannot be edited. Cost: new concept, new storage, most
work of the three.

**A is recommended**, with B acceptable as an interim if the source file is not
readily editable — provided the source is corrected before any re-import.

## Deliverables (once an option is chosen)

| # | File | Description |
|---|---|---|
| 1 | source CSV / `backend/fix_adel_face_channels.py` | The correction, per the option chosen |
| 2 | `specs/007-grade-domain-shells/OPEN_QUESTIONS.md` | Q1 evidence table re-run against corrected data |
| 3 | — | Confirmation that `analyze_sample_types.py "Adel"` reports `{'DDH': 247, 'FC': 236, 'TR': 188}` |

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | `extract_composite_points` reports FC and TR as separate populations for Adel, with no code change to `composite_points.py` |
| AC-2 | P0 | No `trench_id` string matching exists anywhere in `backend/src/services/` |
| AC-3 | P0 | If option B is used, the script is committed, reviewable, reports its row count, and does not run automatically |
| AC-4 | P0 | The Q1 evidence table is re-run against the corrected data before any trench-influence decision is made |
| AC-5 | P1 | If the source is not corrected, the risk that a re-import reverts the fix is recorded in the task |

## AAF004A — answered, with a consequence still open

**AAF004A is FC, and it is a re-sampled face: samples were taken from it again
to confirm the earlier results.** Its classification is settled and applied.

What that raises, and what this task does **not** decide: a verification
re-sample is a second measurement of ground that has already been sampled, not
new ground. Three of its rows share a chainage with an earlier row about a metre
away in elevation, and the paired grades are far apart — 0.06 against 7.86, 0.06
against 6.38, 0.54 against 18.43 g/t.

That spread is itself worth understanding before the pairs are used: a
verification duplicate that disagrees by two orders of magnitude is either
sampling a genuinely different position on the face, or it is telling you
something about repeatability on this material. Either reading matters to how
much weight FC should carry.

For interpolation it also poses a plain double-counting question — two samples
at nearly the same location both voting on the same node, with one of them 130×
the other. Options are to keep both, keep the later verification sample, or
average the pair. **Not decided here**; recorded against Q1, where the FC
weighting decision sits.
