# 007 — Open Questions and Recorded Decisions

Two sections. **Decisions** are settled and are already reflected in the task
files — implement them as written. **Open questions** are unresolved
geological choices; the task they block must not be implemented until the
question is answered here.

Raised by the geologist on 2026-08-07, after T001 was specified.

---

## Scope of evidence (binding — set 2026-08-08)

**Adel is the only real project dataset.** Every other project in the
application — Abo Elmagd Hill (Gold), Abo Elmajd, El Kharga, Nabil, Samir,
Tallat, Adel Area, and the QA/sample projects — is test or mock data.

Geological rules, defaults, trench weighting, sample-type behaviour, and
modelling assumptions **must be derived from Adel only**. Statistics from any
other project may be used to exercise code paths and nothing else.

Code stays generic — nothing about Adel is hard-coded — but every *decision*
recorded in this document is an Adel decision.

**Adel's composition**, for reference:

| | |
|---|---|
| Collars | 23 DD (12 drilled, 11 planned), **0 RC** |
| Assays | 250 assayed intervals, unit `g/t`, 1 unassayed |
| Trenches | 424 rows across 12 lines: **6 AAF lines = Face Channel (236 rows)**, **6 AAT lines = Trench (188 rows)**. All currently stored as `TR` — see [T011](tasks/T011_adel_face_channel_classification.md) |
| Trench sample XYZ | the sample interval **midpoint**, accurate and authoritative |
| Trench chainage | present on **all 424** rows |
| Trench sample lengths | 406 × 1.0 m, 18 × 2.0 m |
| Missing elevations | none |

---

## Recorded decisions (settled — implement as written)

### D1. Extrapolation — conservative, confirmed

Unsampled (`nan`) nodes are never estimated, and the shell must not extrapolate
into unsupported ground. Preserved in T005 (`min_samples` guard, `nan` output)
and T006 (`nan` closes the surface inward).

**No later task may relax this without an explicit written change here.** A
task that quietly fills `nan` with zero, a global mean, or a nearest-neighbour
value is implementing a different geological claim than the one approved.

### D2. Interpolation engine — IDW now, replaceable later

Anisotropic IDW is accepted as the initial engine. The architecture must keep
it swappable for RBF or another method.

**Consequence for T005:** the interpolation engine is defined behind a named
protocol, not hard-wired. `interpolate_grade_grid` keeps its signature, but the
weighting kernel is a separate, injectable callable so an RBF engine can be
added later without touching the grid construction, search, or `nan` policy.
T005's acceptance criteria are amended accordingly (see AC-9 there).

### D3. What the output represents

The generated shell is a **3D grade-shell visualisation and modelling product**.
It is not a Mineral Resource or Reserve, and nothing in the UI, API responses,
exports, or documentation may imply that it is.

Concretely, this bans: the words "resource", "reserve", "Measured",
"Indicated", "Inferred", "JORC", or "NI 43-101" as descriptions of the output;
any tonnage figure; any contained-metal figure presented as an estimate.
Volume in cubic metres and metal *capture fraction* are geometry and validation
statistics and are allowed — they describe the shell, not the deposit.

### D5. Repeat samples on the same metre are averaged (set 2026-08-08)

**Where more than one sample represents the same metre of the same trench, they
are combined into one modelling value by arithmetic mean.** Two situations in
Adel produce this:

1. **A stretch was sampled again** to verify the first result. The repeat is not
   an independent spatial observation.
2. **Additional vertical samples within one metre**, testing whether a
   mineralised vein continues upward or downward. These should not get several
   votes in the interpolation merely because several measurements exist.

**The grouping key is identity, not proximity:** same `trench_id`, same stated
chainage interval. Samples are **never** merged for being geographically close —
two rows a hand's breadth apart on different intervals stay separate, and rows
with no stated chainage are never merged at all, because without an interval
nothing says they share a metre.

The merged grade is the arithmetic mean of the members' grades; the merged
position is the arithmetic mean of their coordinates, which for a vertical pair
places the value at the mid-height of the column the pair jointly describes.

**Source records are never altered.** This happens in the modelling layer, in
`composite_points._merge_repeat_samples`, and it is deterministic: groups are
emitted in ascending chainage order and the mean does not depend on order within
a group. `ExtractionReport.n_trench_intervals_merged` and
`n_trench_rows_absorbed` report what was merged on every run.

Applied to Adel: **16 rows across 8 intervals** merge into 8 values — 5
intervals in AAF002 (case 2) and 3 in AAF004A (case 1).

### D4. Implementer boundary

The implementing model implements the specified behaviour only. It must not
independently change: geological assumptions, coordinate conventions, dip
conventions, cut-off values, trench weighting, or extrapolation rules.

**If the specification is ambiguous, stop and report the ambiguity. Do not
invent a rule.** A plausible invented rule is worse than a blocked task,
because it produces output that looks correct and is not.

---

## Open questions (block the listed task)

### Q1. Trench (TR/FC) influence on grade interpolation — **blocks T005, T009**

Should TR/FC composites be geometry-only (weight `0.0`), partially weighted, or
fully used (`1.0`)?

**The `0.5` currently written into T005 is a placeholder, not a geological
finding.** It was chosen as a neutral middle value and has no basis in this
deposit's data. Do not treat it as approved.

What is already settled: the influence must be **configurable** end to end —
`sample_type_weights` in the service, in the API request, and as a control in
the panel. That part of T005/T009 can be built now.

What is not settled: the **default**. T002's comparison output on the real
project data should inform it — if trench grades run materially higher than
core at the same locations, geometry-only is the defensible default.

**T002 is now implemented** and produces the evidence for this question:

| Output | What it answers |
|---|---|
| `grade_ratio` (length-weighted, TR+FC vs DDH) | how much higher or lower surface sampling reads overall |
| `mean_ratio` | whether the gap survives length weighting, or is a sample-support artefact |
| `by_type[...]` mean vs `length_weighted_mean` | whether short high-grade samples are carrying a type's mean |
| `by_type[...].cv` | whether trench sampling is materially noisier — a support difference, distinct from a grade difference |
| `qq_points` | **whether the difference is a uniform uplift or confined to the upper tail.** A ratio alone cannot separate these, and they imply different decisions: a uniform uplift points to oxide/supergene enrichment (a domaining problem), an upper-tail-only divergence points to selective sampling (a weighting problem) |
| `p10/p25/p75/p90`, `min`, `max` | where in the distribution the two populations part company |
| `reasons` | the failed screening checks, with numbers |

**Limitation that must be weighed when reading it.** The comparison is
**global, not spatially paired**. Trenches sit at surface and drillholes mostly
do not, so a grade difference may be genuine vertical zonation — oxide
enrichment, a supergene blanket — rather than a sampling artefact. A large
`grade_ratio` means "these populations differ, find out why", not "trench
sampling is biased".

Separating the two requires comparing DDH and TR/FC **only where they overlap
in space** — e.g. restricting DDH composites to those above the base of
oxidation, or within some distance of a trench. That is not implemented and is
not in any current task. `TypedComposite` already carries `x/y/z`, which T004
populates, so it is a small addition if wanted.

### Q1 evidence from the real database (T004 landed 2026-08-07)

```bash
venv/Scripts/python.exe -m backend.analyze_sample_types "Adel"
```

**Confirmed from Adel field data, 2026-08-08:** trench sample XYZ is the sample
**midpoint**; **`AAF` lines are Face Channel (FC)** and **`AAT` lines are Trench
(TR)**.

That last confirmation splits what had been one surface population into two, and
they are not alike:

Current figures, with the D5 repeat-sample merge applied:

| Population | n | lw mean | median | p75 | max | cv |
|---|---|---|---|---|---|---|
| **DDH** (23 DD collars) | 247 | 0.167 | 0.020 | 0.030 | 6.98 | 4.65 |
| **FC** (6 AAF lines) | 228 | **3.845** | 0.740 | 5.690 | 49.46 | 1.64 |
| **TR** (6 AAT lines) | 188 | **0.527** | 0.050 | 0.185 | 16.68 | 3.34 |

| Comparison | length-weighted grade ratio |
|---|---|
| FC vs DDH | **23.08** |
| TR vs DDH | **3.16** |
| **FC vs TR** | **7.30** |
| *(FC + TR pooled) vs DDH — the misleading figure* | *13.95* |

*(Before the D5 merge these read FC n=236, lw 3.908, FC vs DDH 23.46, FC vs TR
7.42, pooled 14.32. The merge affects FC only — all 8 merged intervals are on
AAF lines.)*

**The 14.32 was an artefact of pooling two unlike populations.** Face channels
read 7.4× the trench floors. Any single "trench weight" would be applying one
number to populations that differ from each other by more than most deposits
differ from barren rock.

Geologically this is what one would expect — a face channel is cut on an exposed
mineralised face, a trench floor cross-cuts whatever it crosses — but it means
**Q1 is at least two decisions, not one**: FC influence and TR influence are
separate questions. FC is the population most likely to warrant geometry-only
treatment.

**The split is now in the data.** The source CSV was corrected and re-imported
on 2026-08-08 ([T011](tasks/T011_adel_face_channel_classification.md), option A),
so `analyze_sample_types.py "Adel"` reports
`{'DDH': 247, 'FC': 236, 'TR': 188}` directly, with no code change and no
`trench_id` string matching anywhere in the services.

**Resolved by D5:** the verification re-samples in `AAF004A` and the vertical
pairs in `AAF002` are averaged into one value per metre, so no metre of ground
votes twice.

**A correction while investigating this:** `AAF004A` is **not** a re-sample of
`AAF004`. Their elevation ranges are nearly disjoint (297.5–301.1 against
295.7–297.2), nearest-neighbour 3-D distances run 1.9–7.1 m, only 1 of 36 rows
shares a chainage with its nearest `AAF004` row, and grades at those neighbours
differ wildly (8.47 against 0.03). `AAF004A` is a **separate, lower face**. The
re-sampling is *within* `AAF004A` — its rows 33–35 repeat chainages 23–26 already
covered by rows 23–25.

**Withdrawn:** an earlier version of this table also listed Abo Elmagd Hill
(0.73) and Abo Elmajd (1.26), and argued from the spread between them that no
single default trench weight could be right. **Both of those are mock datasets**
and carry no geological weight, so that argument is withdrawn. Keeping the
trench influence configurable remains right as a design principle — a second
real deposit will not behave like Adel — but it is not a finding from data.

**The Adel evidence on its own:** trenches read **14× the drill population**,
length-weighted.

Adel's Q–Q shows the divergence runs across the whole distribution, not just
the upper tail — ratios of 40, 8.5, and 69 at q0.25, q0.51, and q0.75 — while
the DDH population there is close to barren (median 0.020 g/t, p75 0.030 g/t).
That pattern is at least as consistent with **the two sample sets testing
different ground** — trenches cut across outcropping veins while those twelve
holes largely missed them — as with a sampling bias in the trenching. The
global comparison cannot separate those, per the limitation above.

*Suggested resolution path: decide per project rather than globally, and settle
whether a co-located comparison is wanted before fixing Adel's default — a 14×
ratio on a near-barren drill population is a question about the drilling as
much as about the trenching.*

### Q2. Cut-off default and sensitivity set — **blocks T003, T008, T009**

Should the default remain **0.3 g/t Au**, with sensitivity testing available at
0.2 / 0.3 / 0.5 / 1.0 g/t?

T003 currently specifies a default threshold list of
`[0.1, 0.2, 0.3, 0.5, 1.0, 2.0, 5.0]` for the capture curve, and T008/T009 do
not currently define a single default threshold at all.

Needs confirming: (a) the single default threshold for shell generation, and
(b) whether the capture-curve list should be trimmed to the four values above
or keep the wider spread. These are different lists for different purposes —
the curve wants a wide spread to show the shape, the generator wants one
sensible starting value.

### Q3. Minimum mining width — **blocks T006**

Should the generator enforce a minimum width (e.g. 2.0 m), or is minimum mining
width a downstream/manual interpretation constraint?

**T006 as written enforces nothing.** A marching-cubes surface at a 5 m cell
size will produce lenses thinner than any mineable width, and `min_volume` is a
volume filter, not a width filter — it will not remove a thin, laterally
extensive sheet.

The options differ substantially in scope:
- **No enforcement** (current spec) — smallest change, shell is a pure grade
  iso-surface, width is the geologist's call downstream. Honest, but produces
  shells with unmineable slivers.
- **Report only** — measure minimum local thickness and surface it in T007's
  validation report without altering geometry. Moderate work, no geometry
  claims invented.
- **Enforce** — morphological dilation/erosion on the grid before extraction,
  or a post-extraction thickness filter. Largest change, and it makes the shell
  a *mining* shape rather than a *grade* shape, which is a different object
  with different meaning.

*Recommendation: "report only" for this feature. Enforcement changes what the
shell means, and mixing a mining constraint into a grade domain is exactly the
conflation D3 is meant to prevent.*

### Q4. Structural orientation configurability — **blocks T005, T008, T009**

Should strike / dip / dip direction be entirely user-configurable with no
project-specific values hard-coded?

Substantially settled already — T005's `SearchEllipsoid` takes
`strike_azimuth` and `dip` as parameters and hard-codes nothing. Two points
still need a decision:

1. T005 currently exposes **strike azimuth + dip** and fixes plunge at 0. Is
   dip *direction* also needed as a separate input, or is
   `dip_direction = strike + 90` an acceptable convention? Stating the
   convention explicitly matters more than which one is chosen — an unstated
   one is how a shell ends up rotated 90° from the structure.
2. Should defaults be **required inputs with no default at all** (forcing a
   deliberate choice), or should the API default to isotropic
   (`range_major == range_semi == range_minor`, azimuth 0)? An isotropic
   default is safe in the sense that it makes no structural claim, but it
   produces geologically meaningless blobs if the user does not notice.

*Recommendation: no defaults for the ranges and orientation — make them
required. A shell built on an unnoticed default orientation is worse than one
the user was forced to think about.*

---

### Q5. Trench sample placement and length — **raised by T004, blocks T005 geometry**

**Investigated 2026-08-08 — full evidence in
[`analysis/Q5_trench_geometry_findings.md`](analysis/Q5_trench_geometry_findings.md),
decision task [`T010`](tasks/T010_trench_geometry_decision.md).**

The T004 specification said to treat trench `from_depth`/`to_depth` as chainage
along the trench floor, composite along it, and interpolate each composite's
position along the polyline. The real database does not support that:

### RESOLVED by the geologist, 2026-08-08

**The stored XYZ on each trench sample is accurate and authoritative, and
represents the MIDPOINT of the sample interval.** This is a statement of
provenance from the person who collected the data and it settles the question.

T004's existing behaviour — placing each assayed trench row at its own stored
coordinates — is therefore correct as written, and is now consistent with the
drillhole path, which also places each composite at its midpoint.

**Correcting my own analysis.** The findings document reported the coordinate as
the sample *start*. That conclusion was weaker than it was presented:

- **406 of Adel's 424 trench samples are a uniform 1.0 m**, and for uniform
  lengths the start and midpoint hypotheses are *mathematically
  indistinguishable* under the test used — both advance by the same step.
- The entire "start" finding rested on **4 lines containing the 18 two-metre
  samples**, and split 3–1 (AAT001/002/003 start, AAF003 midpoint) with margins
  of **4–8 cm**.
- 18 samples out of 424, at centimetre margins, is not a basis for overriding
  the data's provenance. It was reported with more confidence than it earned.

The practical difference is length/2 — 0.5 m for a 1 m sample — against a
default 5 m interpolation cell, so nothing downstream shifts materially either
way.

### What still stands (real Adel data)

1. **Chainage is not unique.** AAF002 (5 pairs) and AAF004A (3 pairs) carry
   samples sharing a chainage — 0–1 m holds both 5.86 and 2.82 g/t — separated by
   0.15–0.49 m in plan but ~1 m in **elevation**, with consecutive sample
   numbers. A face sampled at two heights. Chainage is a 1-D coordinate on a 2-D
   face; elevation separates them and lives only in the coordinates. One AAF004A
   pair differs by 0.06 against 7.86 g/t.
2. **There is no stored polyline.** `trench` holds points; the line is only those
   points joined in `point_order`. No surveyed centreline exists in the schema.

Both reinforce the resolution above: the coordinates are the geometry.

**Also withdrawn:** the claim that chainage and polyline distance disagree
(AAF001 at chainage 12–13 m against a polyline of 11.89 m) compared a sample's
*end* against a *point position*. Chainage in Adel agrees with cumulative
coordinate distance to ~1–2%. The ~10% stretch reported earlier was entirely in
mock projects and is not a real-data finding.

### No longer applicable

- **Legacy rows with no chainage** — all 173 are in Abo Elmagd Hill (mock). All
  424 Adel rows carry chainage, so the assumed-sample-length question does not
  arise for real modelling. `trench_length_when_unspecified` stays in the code as
  generic handling; it needs no geological default.

**What T004 does instead, provisionally:** one composite per assayed trench row,
placed at the coordinates that row states, with length from `to_depth −
from_depth` where present. Rows stating no length are **excluded and counted**
by default; `trench_length_when_unspecified` includes them under a stated
assumption. Nothing is interpolated and no reconciliation is invented.

### T010 — closed 2026-08-08

The geometry source is settled: **authoritative midpoint coordinates**. The
follow-up work is done — T004's specification rewritten to match the code, a
total `ORDER BY` on the trench query with two determinism tests, and the
start-vs-midpoint and chainage-vs-polyline claims corrected everywhere they
appeared. No data-model change was made: Adel states chainage on all 424 rows,
so a `sample_length_m` column would serve no consumer.

**Q5 does not block T005.** Anisotropic IDW consumes located point samples and a
search ellipsoid — it never asks how two samples in a trench are connected, and
every Adel trench sample has an authoritative midpoint position. Q5 blocks
features that reconstruct a trench *line*, not point interpolation. **T005
remains blocked on Q1 and Q4.**

### Q6. RC holes pooled with diamond core — **NOT APPLICABLE to Adel**

**Adel contains 23 DD collars and zero RC.** All RC in the database (26 collars)
sits in mock projects. Per the scope rule above, **the modelling workflow must
not be designed around it**, and Q6 therefore decides nothing for the current
implementation.

Held open as a **labelling** matter only: `composite_points` types every
collar-borne composite `DDH`, which is accurate for Adel today and would become
inaccurate the moment a real RC dataset is imported. No implementation change;
T004 is not to be modified.

Options and costs remain documented in
[`analysis/Q6_rc_vs_core.md`](analysis/Q6_rc_vs_core.md) for when real RC data
arrives. The one design consequence worth remembering: `compare_sample_types`
splits reference-vs-rest, so a bare `RC` type would land in the *non-reference*
population and be averaged in with trenches — separating RC later means giving
T002 explicit comparison groups.

Everything below this line describes the mock data and is retained only as
background.

The four types the data distinguishes: **DD** (diamond core) and **RC** (reverse
circulation) from `collar.hole_type`; **TR**, **CH**, **FC** from
`trench.hole_type`. TR/CH/FC are already kept separate end to end. Only DD and
RC are pooled.

**Current exposure is small.** Adel — the 14.32 ratio, the substantive Q1
result — has **zero** RC collars, and so does Abo Elmagd Hill. The only project
where RC assays and trenches coexist is Abo Elmajd: 3 RC assay intervals against
5 DD, on a population already below T002's screening threshold. No current
conclusion depends on this.

Three options, with costs, are set out in the analysis document: **group**
(status quo, label inaccurate), **separate** (most informative, but requires
T002 to gain explicit comparison groups — a bare `RC` type would land in the
non-reference population and be averaged in with trenches), or **exclude**
(clean core-vs-surface, but drops RC from the evidence base and still needs a
separate answer for T005).

`ExtractionReport.collars_by_hole_type` reports the DD/RC/unspecified split on
every run so the pooling stays visible in output.

## Status

| # | Question | Blocks | Status |
|---|---|---|---|
| D1 | Extrapolation conservative | T005, T006 | **Decided** |
| D2 | IDW now, replaceable | T005 | **Decided** |
| D3 | Not a resource estimate | all | **Decided** |
| D4 | Implementer boundary | all | **Decided** |
| Q1 | Surface-sample influence | T005, T009 | **Open** — two decisions now (FC and TR), evidence ready |
| Q2 | Cut-off default + sensitivity set | T003, T008, T009 | **Open** |
| Q3 | Minimum mining width | T006 | **Open** |
| Q4 | Structural orientation inputs | T005, T008, T009 | **Open** |
| Q5 | Trench sample geometry | — | **Resolved 2026-08-08**: stored XYZ is the authoritative sample **midpoint**. Cleanup in [T010](tasks/T010_trench_geometry_decision.md) |
| Q6 | RC pooled with diamond core | — | **Not applicable** — Adel has no RC. Labelling matter only |

T001, T002 and T004 are implemented. Q1 now has real evidence (table above);
Q5 and Q6 were raised by putting the real database through T004 and did not
exist when the specs were written.
