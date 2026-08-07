# 007 — Open Questions and Recorded Decisions

Two sections. **Decisions** are settled and are already reflected in the task
files — implement them as written. **Open questions** are unresolved
geological choices; the task they block must not be implemented until the
question is answered here.

Raised by the geologist on 2026-08-07, after T001 was specified.

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

*Suggested resolution path: implement T002, run it on the actual project, and
choose the default from the observed grade ratio and Q–Q plot.*

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

## Status

| # | Question | Blocks | Status |
|---|---|---|---|
| D1 | Extrapolation conservative | T005, T006 | **Decided** |
| D2 | IDW now, replaceable | T005 | **Decided** |
| D3 | Not a resource estimate | all | **Decided** |
| D4 | Implementer boundary | all | **Decided** |
| Q1 | Trench influence default | T005, T009 | **Open** |
| Q2 | Cut-off default + sensitivity set | T003, T008, T009 | **Open** |
| Q3 | Minimum mining width | T006 | **Open** |
| Q4 | Structural orientation inputs | T005, T008, T009 | **Open** |

T001 is unaffected by all four open questions and is **implemented**.
T002 is unaffected and may proceed.
