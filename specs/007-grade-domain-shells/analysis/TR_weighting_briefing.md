# Briefing: should trench-floor samples inform grade at Adel?

**For review by the expert team. One decision is needed.** Everything else in
the surface-sample question is settled; this is the last open input to the grade
interpolation.

Prepared 2026-08-08 from the Adel database. Adel is the only real dataset — no
other project in the application was used.

---

## The question, in one sentence

**Should trench-floor (TR) samples contribute to interpolated grade, and if so at
what weight relative to diamond core?**

The options are a single number, the TR sample weight, between `0.0` (trench
floors define geometry only and cast no vote on grade) and `1.0` (treated as
equivalent support to core).

---

## What has already been decided

| | |
|---|---|
| **Face Channel (FC)** | **weight `0.0` — geometry only.** Cut on exposed mineralised faces, reading 23.08× core. They tell us where the vein outcrops; they do not set grade. |
| **Diamond core (DDH)** | weight `1.0`, the reference population |
| **Repeat samples** | where several samples describe the same metre of trench, they are averaged into one value before modelling |

Only TR is open.

---

## The evidence

Populations, after averaging repeat samples, length-weighted:

| Population | n | mean | length-wtd mean | median | p75 | max | CV |
|---|---|---|---|---|---|---|---|
| **DDH** | 247 | 0.166 | **0.167** | 0.020 | 0.030 | 6.98 | 4.65 |
| **TR** | 188 | 0.557 | **0.527** | 0.050 | 0.185 | 16.68 | 3.34 |
| *FC (excluded from grade)* | *228* | *3.962* | *3.845* | *0.740* | *5.690* | *49.46* | *1.64* |

**TR reads 3.16× core**, length-weighted. For comparison, FC reads 23.08×.

Proportion of each population above candidate cut-offs:

| cut-off | DDH | TR |
|---|---|---|
| 0.2 | 23 (9%) | 47 (25%) |
| 0.3 | 18 (7%) | 33 (18%) |
| 0.5 | 13 (5%) | 25 (13%) |
| 1.0 | 6 (2%) | 20 (11%) |

---

## What the 3.16× could mean

The comparison is **global, not spatially paired** — trenches sit at surface,
the drillholes mostly do not — so it cannot by itself separate these:

1. **Genuine near-surface enrichment.** Oxidation and supergene processes
   concentrate gold near surface in deposits of this style. If so, the trench
   grades are *real* for the ground they describe, and the right response is a
   weathering domain rather than a down-weight.
2. **Sampling support.** A hand-cut channel across a trench floor is a larger,
   less precisely bounded sample than core, with a natural tendency to follow
   the visible quartz. TR's CV of 3.34 against core's 4.65 is consistent with a
   larger sample averaging out some variability.
3. **Different ground.** Trenches were dug where mineralisation was expected;
   the twelve drilled holes may simply have tested different, poorer ground.

**Resolving this properly needs a co-located comparison** — DDH restricted to
above the base of oxidation, or to within some distance of a trench — which has
not been built. It is a small addition if the team wants it before deciding.

---

## The context that matters most

**Adel's drilling barely intersects mineralisation above cut-off.** Only 18 of
247 DDH composites exceed 0.3 g/t, from 12 drilled holes.

With FC already excluded from grade, the choice of TR weight decides how much
data the shell has at all:

| TR weight | composites above 0.3 g/t driving grade |
|---|---|
| `0.0` | **18** (DDH only) |
| any weight > 0 | **51** (DDH + TR) |

At `0.0` the interpolation has 18 above-cut-off points across the whole property.
That is very likely too sparse to produce a defensible domain, whatever one
thinks of trench sampling. This is a constraint on the drilling, not an argument
about the trenches — but it bears directly on the decision.

---

## Options

| Weight | Reading | Consequence |
|---|---|---|
| **0.0** | trench floors are geometry only | 18 points drive grade; almost certainly too sparse |
| **0.25** | mostly geometry, small grade contribution | core dominates locally, trenches fill gaps |
| **0.5** | real support difference acknowledged, data retained | *the option I would put first, absent expert input* |
| **1.0** | trench floors equivalent to core | the 3.16× propagates directly into the domain |

An alternative to any single number: **treat the oxide zone as its own domain**
and use TR at full weight *within it*, keeping core as the reference at depth.
That answers reading (1) directly rather than compromising with a weight. It is
more work and needs a base-of-oxidation surface, which the project does not
currently hold.

---

## What we need back

1. **A TR weight**, or a decision to build the co-located comparison first.
2. If the oxide-domain route is preferred, confirmation that a base-of-oxidation
   surface can be supplied.

The weight is configurable per run and is not baked into the code, so it can be
revised without rework. It will be recorded with every generated shell.
