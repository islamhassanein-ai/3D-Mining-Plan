# Q5 — Trench geometry: what the database actually supports

Findings only. No rule is proposed as settled, nothing was changed in the data,
and no reconciliation between chainage and coordinates has been invented. The
decision itself is [T010](../tasks/T010_trench_geometry_decision.md).

Investigated 2026-08-08 against the live `mining_db`, all queries filtered
`superseded_by IS NULL`. Reproduction scripts are described at the end.

---

## Correction to an earlier claim

The T004 commit message and the first version of Q5 stated that *"chainage and
polyline distance disagree"*, citing AAF001 ending at chainage 12–13 m against a
polyline reaching 11.89 m.

**That comparison was wrong.** It measured the *end* of the last sample against
the *position* of the last vertex. Since the stored coordinate is the sample's
start point (see Finding 1), the correct comparison is chainage 12.0 against
11.89 m — a 0.9% agreement, not a discrepancy.

Corrected below. The conclusion that coordinates should be authoritative
survives, but for entirely different reasons than originally given.

---

## Finding 1 — The stored XYZ is the sample START point

For every trench line carrying chainage, cumulative 3-D distance along
`point_order` was fitted against three hypotheses — that the coordinate marks
the sample's start, midpoint, or end — and the mean absolute residual recorded.

**Where every sample in a line is the same length, the three hypotheses are
mathematically indistinguishable** (all three differ from cumulative distance by
the same constant), which is why most lines report identical residuals. Only
lines with *varying* sample lengths discriminate. Those are:

| Line | n | start | mid | end | verdict |
|---|---|---|---|---|---|
| AAT001 | 23 | **0.042** | 0.095 | 0.161 | START |
| AAT002 | 24 | **0.082** | 0.091 | 0.112 | START |
| AAT003 | 28 | **0.104** | 0.181 | 0.306 | START |
| AAF003 | 29 | 0.329 | **0.294** | 0.634 | MID by 3.5 cm — inside noise |

Three of four discriminating lines say START, and the fourth prefers MID by
3.5 cm, which is below the survey precision of the other residuals. **The stored
coordinate is the sample's start point.**

## Finding 2 — Chainage means distance along the trench, and surveyed data honours it to ~1%

Chainage (`from_depth`/`to_depth`) is distance from the trench origin along the
trench. Comparing each line's chainage span against its cumulative 3-D
coordinate span:

| Project | lines | chainage span vs coordinate span |
|---|---|---|
| Adel | 10 | agrees to **1–2%** (12.00 → 11.89, 64.00 → 64.42, 70.00 → 69.63, 24.00 → 24.02, 29.00 → 28.96, 39.00 → 39.14) |
| Abo Elmajd, El Kharga, Nabil, Samir, Tallat | 13 | coordinates run **~10% long** consistently (9.00 → 11.11, 16.00 → 18.00, 133.00 → 137.50, 23.00 → 24.97) |

Step-by-step, the ratio of coordinate spacing to chainage step has median 1.01
in Adel and 1.12–1.15 in the others.

Adel is surveyed field data. The other five are the demo/sample projects whose
coordinates were authored by hand in a CSV; their ~10% systematic stretch is a
property of how those files were written, not a geological measurement.

**Intent is therefore unambiguous and, in real surveyed data, well honoured.**

## Finding 3 — Chainage cannot position a sample, because it is not unique

Two Adel lines carry samples sharing a chainage: AAF002 (5 pairs) and AAF004A
(3 pairs). These are not data errors:

| Line | chainage | sample_id | E, N separation | **elevation separation** | grades |
|---|---|---|---|---|---|
| AAF002 | 0–1 | 11951 / 11952 | 0.150 m | **0.84 m** | 5.86 / 2.82 |
| AAF002 | 1–2 | 11953 / 11954 | 0.231 m | **1.16 m** | 8.54 / 35.90 |
| AAF002 | 3–4 | 11957 / 11958 | 0.488 m | **1.38 m** | 0.30 / 1.26 |
| AAF004A | 23–24 | 13207 / 13217 | 0.448 m | **1.08 m** | 0.06 / 7.86 |
| AAF004A | 25–26 | 13209 / 13219 | 0.323 m | **0.67 m** | 0.54 / 18.43 |

Consecutive sample numbers, near-identical plan position, roughly one metre
apart **vertically**. This reads as a face sampled at two heights — an upper and
a lower channel on the same face — which the `AAF` prefix (as against `AAT` for
the trench-floor lines) supports.

The consequence is structural: **chainage is a one-dimensional coordinate
describing a two-dimensional face.** It cannot distinguish the upper sample from
the lower one. Elevation can, and elevation lives only in the stored
coordinates. Grades of 0.06 and 7.86 g/t at the same chainage are not
interchangeable.

## Finding 4 — There is no stored polyline to be authoritative

`Trench` stores **points**. The "polyline" exists only as those points joined in
`point_order`; the schema holds no independent trajectory, no surveyed
centreline, and no separate geometry record. So "polyline versus per-sample
coordinates" is a false choice — the polyline is *derived from* the coordinates
and can carry no information they do not already hold.

## Finding 5 — Legacy rows have no chainage and no order, but their spacing is ~1 m

173 rows across 12 lines in Abo Elmagd Hill (Gold) came through the legacy
four-file uploader: no `from_depth`, no `to_depth`, no `point_order`, no
`sample_id`, no `import_batch_id`. They do have full coordinates and grades.

Spacing between consecutive rows as stored:

| Line | n | min | median | max | steps within 0.8–1.25 m |
|---|---|---|---|---|---|
| AEC001 | 11 | 0.93 | 1.02 | 1.06 | 10/10 |
| AEF001 | 45 | 0.87 | 1.02 | 1.31 | 43/44 |
| AET004A | 24 | 0.87 | 1.00 | 1.34 | 21/23 |
| AET011 | 12 | 0.84 | 1.03 | 1.13 | 11/11 |
| AEF002 | 23 | 0.03 | 1.01 | 1.16 | 17/22 |
| AET004B | 6 | 1.09 | 1.19 | 2.06 | 3/5 |

Ten of twelve lines are almost entirely 1 m steps. This is **consistent with**
contiguous 1 m channel samples, and it is evidence for a 1 m assumed length
rather than a guess — but it is consistency, not proof, and AEF002 (a 0.03 m
step) and AET004B are exceptions.

A second, separate group of 105 rows across the demo projects also lacks
chainage: those are the *generated far-end vertices* of single-row trenches,
carry `grade_value IS NULL`, and were never samples. T004 already counts them as
unassayed.

## Finding 6 — Order is not stored for the legacy rows, and the query does not impose one

The 173 Abo Elmagd rows have `point_order IS NULL`. T004's trench query has no
`ORDER BY`, so their sequence is whatever the planner returns. Two consecutive
queries happened to agree, which is not a guarantee.

**This does not affect any current output** — each sample is placed at its own
coordinates, so order changes nothing about position, grade, or length, and T002
is order-independent (there is a test for that). It would matter immediately if
anything reconstructed a trench line. It is a determinism gap, not a correctness
bug, and it is listed in T010 as a small fix regardless of how Q5 resolves.

---

## Answers to the six questions

**1. What does the stored XYZ represent?** The **start point of the sample**
(Finding 1). For the paired face samples, the start of that particular channel.

**2. How was chainage intended to relate to the polyline?** As distance from the
trench origin along the trench. Surveyed data honours it to ~1%; the hand-built
demo CSVs run ~10% long (Finding 2).

**3. Which is authoritative?** **The per-sample coordinates.** Not because
chainage is wrong, but because (a) there is no stored polyline independent of
those coordinates (Finding 4), and (b) chainage is not unique — it cannot
separate the upper and lower samples of a face, which differ by up to 18 g/t
(Finding 3).

**4. How should legacy rows be interpreted?** They give position and grade
reliably. They give **no length and no order**. Their ~1 m spacing supports a 1 m
assumed length but does not establish it (Finding 5). Currently T004 excludes
them and counts them unless a length is explicitly passed.

**5. How should overlapping chainage be handled?** As **distinct samples**,
which is what they are — different elevations, different sample numbers,
materially different grades. Keying on coordinates handles them correctly and
already does. Keying on chainage would collide them or raise.

**6. Can the data be reconstructed from coordinates alone?**

| Property | From coordinates alone? |
|---|---|
| Sample position | **Yes** — all 1,326 chainage-bearing and 173 legacy assayed rows carry full E/N/Z, except 5 rows missing elevation |
| Sample length | **Partly** — stated for 1,326 rows, absent for 173 |
| Order / connectivity | **Mostly** — `point_order` on all but the 173 legacy rows |

---

## The finding that matters most for sequencing

**T005 does not consume trench trajectories.** An anisotropic IDW interpolant
takes *located point samples* and a search ellipsoid; it never asks how two
samples in the same trench are connected. Every trench sample already has an
unambiguous position that requires no inference.

So Q5 blocks any feature that reconstructs a trench **line** — sectional
display, a chainage-based length, trench-following geometry — but on the
evidence it does not block point-based interpolation. Whether to act on that is
T010's decision, not this document's.

---

## Reproduction

The three scripts used are not committed; they are straightforward to
reconstruct from the tables described. Each takes a project name and queries
`trench` with `superseded_by IS NULL`:

1. **Hypothesis fit** — group by `trench_id`, sort by `point_order`, accumulate
   3-D distance between consecutive rows, compare against `from_depth`,
   `(from_depth + to_depth) / 2`, and `to_depth` rebased to the first row.
2. **Duplicate chainage** — group by `(from_depth, to_depth)` within a
   `trench_id`, report groups of more than one with their 2-D and vertical
   separations.
3. **Legacy spacing** — for rows with `from_depth IS NULL`, report consecutive
   3-D spacing per line.

`backend/analyze_sample_types.py` reports the resulting composite counts per
sample type for any project.
