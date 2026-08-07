# Q6 — RC versus diamond core: a modelling decision record

> ## NOT APPLICABLE to the current implementation
>
> **Adel — the only real dataset — contains 23 DD collars and zero RC.** All 26
> RC collars in the database sit in mock projects, and per the scope rule in
> `OPEN_QUESTIONS.md` the modelling workflow must not be designed around them.
>
> This document is retained for when a real RC dataset arrives. Until then Q6 is
> a **labelling** matter only: typing every collar-borne composite `DDH` is
> accurate for Adel today. **No implementation change; T004 is not to be
> modified.**
>
> The exposure table below is mock data and is kept only as a record of what is
> in the database.

Documentation only. **No implementation change is proposed here**, and T004 is
not to be modified until this is decided.

---

## The situation

`composite_points` types every collar-borne composite as `DDH`, per the T004
specification. The database holds RC collars alongside diamond core, so the
label is currently inaccurate:

> **T002's "DDH vs TR/FC" comparison is presently Core + RC vs Trench.**

The four sample types that exist in the data, and how they are currently
handled:

| Type | Meaning | Stored as | Current `sample_type` |
|---|---|---|---|
| **DD** | Diamond core | `collar.hole_type = 'DD'` | `DDH` |
| **RC** | Reverse circulation | `collar.hole_type = 'RC'` | `DDH` ← **pooled** |
| **TR** | Trench | `trench.hole_type = 'TR'` | `TR` |
| **CH** | Channel | `trench.hole_type = 'CH'` | `CH` |
| **FC** | Face channel | `trench.hole_type = 'FC'` | `FC` |

`ExtractionReport.collars_by_hole_type` reports the DD/RC/unspecified split on
every run, so the pooling is visible in output even though it is invisible in
the `sample_type` label.

## Why RC is a real distinction, not bookkeeping

Reverse circulation returns rock chips carried up the hole by compressed air,
not an intact core. Compared with diamond drilling it typically shows poorer and
more variable sample recovery, down-hole contamination where material sloughs
from the walls, a larger and less precisely bounded sample volume, and no
ability to log structure or measure true widths. Whether those differences move
grade in a given deposit is an empirical question about that deposit — which is
exactly the question T002 exists to answer, one level down from the trench
question.

## Current exposure — small, but not zero

| Project | DD collars | RC collars | DD assays | RC assays | trench rows |
|---|---|---|---|---|---|
| Adel | 12 | **0** | 250 | 0 | 424 |
| Adel Area | 25 | 0 | 787 | 0 | 0 |
| Abo Elmagd Hill (Gold) | 0 (3 unspecified) | 0 | 0 | 0 | 173 |
| Abo Elmajd | 7 | 4 | 5 | 3 | 37 |
| El Kharga | 5 | 3 | 0 | 0 | 28 |
| Nabil | 3 | 2 | 0 | 0 | 20 |
| Samir | 4 | 2 | 0 | 0 | 24 |
| Tallat | 4 | 2 | 0 | 0 | 23 |

**The Q1 trench evidence is unaffected.** Adel — the 14.32 grade ratio, the
substantive result — contains **zero RC collars**, and Abo Elmagd Hill contains
none either. The only project where RC assays and trenches coexist is Abo
Elmajd, with 3 RC assay intervals against 5 DD, on a population already too
small for T002's screening threshold.

So Q6 currently changes no conclusion. It matters for correctness of labelling
now, and it will matter substantively as soon as an RC-bearing dataset with real
assay coverage is imported.

## The three options

**1. Group RC with DD (status quo).**
The reference population becomes "drilled" as against "surface", which is the
distinction the trench question actually turns on. Simplest, and no code change.
Cost: the `DDH` label is inaccurate, and a real RC-vs-core support difference is
invisible — it would show up as inflated variance inside the reference
population and be silently attributed to the drilling as a whole.

**2. Treat RC as its own population.**
Most informative, and the only option that can *detect* an RC-vs-core
difference. Cost: `compare_sample_types` splits the world into a reference type
and everything else, so a bare `RC` type would land in the **non-reference**
population and be averaged in with trenches — making the trench ratio
meaningless. Taking this option therefore requires T002 to gain an explicit
notion of which types form the comparison groups, rather than reference-vs-rest.
That is a real change to a task that is already implemented and committed.

**3. Exclude RC from the trench-equivalence comparison.**
Keeps the trench comparison clean core-vs-surface, and does not pretend RC and
core are equivalent. Cost: RC assays are dropped from the Q1 evidence base
entirely, and a separate decision is still needed about whether RC then feeds
grade interpolation in T005 — exclusion from a comparison is not exclusion from
a model.

## What is not in question

Whichever option is chosen, `TR`, `CH`, and `FC` stay distinct in
`ExtractionReport.composites_by_type` and in `ComparisonResult.by_type`, as they
already are. Abo Elmajd currently yields `{'DDH': 60, 'TR': 15, 'CH': 3,
'FC': 3}`.

## Recommendation offered, not applied

**Option 2, with the sample types carried honestly** — emit `DD` and `RC` as
distinct `sample_type` values, and give `compare_sample_types` an explicit
grouping so that a comparison can be stated as "`{DD, RC}` versus `{TR, CH,
FC}`" or "`DD` versus `RC`" as needed. That preserves every current result,
makes the label true, and makes an RC support difference detectable rather than
absorbed.

It is the largest of the three changes, and it touches committed work in T002.
Given that no current conclusion depends on it, deferring until an RC-bearing
dataset arrives is also defensible.

**Decision required from the geologist. No code changes until then.**
