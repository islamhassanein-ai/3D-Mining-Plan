# T009 — Grade-Shell Panel and Rendering

> Read `specs/007-grade-domain-shells/tasks.md` first.

| Field | Value |
|---|---|
| **Task ID** | T009 |
| **Priority** | P1 |
| **Dependencies** | T008 |
| **Complexity** | Medium |
| **Status** | **BLOCKED — Q1, Q2, Q4** |

> ## Blocked: do not implement yet
>
> This panel's defaults must match T008's exactly (AC-4), so it inherits every
> question T008 is blocked on, plus **Q1** — the trench-weight slider's default
> position is the trench-influence decision made visible, and `0.5` is a
> placeholder, not an approved value. See
> [`../OPEN_QUESTIONS.md`](../OPEN_QUESTIONS.md).
>
> Also binding: **D3** — the panel must not use "resource", "reserve",
> "Measured", "Indicated", "Inferred", "JORC", or "NI 43-101" to describe the
> output, and must show no tonnage. Volume and metal capture are permitted;
> they describe the shell, not the deposit. The panel presents evidence — the
> competent person signs off.

---

## Context

The threshold decision belongs to the geologist, and they can only make it if
the evidence is in front of them. This panel shows the DDH-vs-trench
comparison, the log-probability plot, and the metal-capture curve; lets them
set the threshold and search ellipsoid; generates the shell; and shows the
validation report.

The shell itself needs no new rendering code — it arrives through the scene's
existing `wireframes` list and `frontend/src/scene/wireframes.js` already draws
it. The work here is the panel, the layer toggle, and honest presentation of
the numbers.

---

## Objective

A new sidebar panel following this project's existing component conventions,
plus a distinct layer toggle for grade shells.

---

## Detailed Requirements

### Conventions to follow

1. Study `frontend/src/components/qaqc_panel.js` and
   `frontend/src/components/section_view_panel.js` first. Match their module
   shape, DOM construction, event wiring, and teardown. Do **not** introduce a
   framework, a template library, or a build step.
2. Styles go in `frontend/styles/app.css` reusing existing class names where
   they exist. No inline `style=` attributes beyond dynamic values.
3. All HTTP goes through `frontend/src/services/api_client.js`. Add methods
   there; do not call `fetch` from the component.

### Panel — analysis section

4. On open, call `GET /projects/{id}/grade-analysis` and render:
   - A **sample-type comparison table**: DDH and TR/FC rows with n, mean,
     length-weighted mean, CV, and the grade ratio.
   - The `comparable` flag and its `reasons`, displayed as **advisory text**.
     Wording must not read as approval — e.g. "Screening check: populations
     differ (ratio 2.05). Review before using trench data for grade." Never
     "Trench data validated" or "Safe to pool".
   - A **log-probability plot**: probability on a probit-scaled x-axis, grade
     on a log y-axis. Inline SVG. No charting library.
   - A **metal-capture curve**: metal fraction and length fraction vs
     threshold, inline SVG, with the currently selected threshold marked.
5. Clicking a point on the metal-capture curve sets the threshold input.
6. A **contact-analysis** button calls the contact endpoint at the current
   threshold and renders mean grade vs signed distance as a bar/step plot.

### Panel — generation section

7. Inputs: name, threshold, composite length, cell size, the five ellipsoid
   parameters, power, min/max samples, trench weight (`0.0`–`1.0` slider), min
   volume, split components.
8. Defaults must match T008's defaults exactly, so the panel and the API never
   disagree about what "default" means.
9. Generate button → `POST /projects/{id}/grade-shells`, disabled while in
   flight, with a spinner. On success, refresh the scene so the new shell
   appears without a page reload.
10. Render the **validation report** after generation: volume, watertight
    status, metal capture, internal dilution, and the per-sample-type table.
    Show `notes` verbatim.
11. Colour metal capture and internal dilution against the guideline bands
    (capture ≥0.90 good, 0.75–0.90 caution, <0.75 poor; dilution ≤0.25 good,
    0.25–0.40 caution, >0.40 poor) — but label them **guidelines**, and never
    block generation on them.
12. Errors from the API (`400`, `422`) surface through the existing toast
    component with the server's message. The node-budget `400` in particular
    must show its actual text — it tells the user to increase `cell_size`.
13. The "no material above threshold" `200` shows an informational message, not
    an error toast.

### Rendering and layers

14. Grade shells (`solid_type === "grade_shell"`) get their own layer toggle,
    separate from imported vein wireframes, in the Layers panel and the
    floating legend — following how `frontend/src/components/layer_toggles.js`
    and `scene_legend.js` already handle layers.
15. Render them semi-transparent (opacity ~0.45, `depthWrite: false`) so
    drillhole traces stay visible through the shell. A solid opaque shell hides
    the very data it was built from and is useless for review.
16. Default the layer **off** on load, consistent with the project's existing
    behaviour for interpretation layers.

### File Location

- `frontend/src/components/grade_shell_panel.js`
- Edits to `api_client.js`, `layer_toggles.js`, `scene_legend.js`,
  `wireframes.js` (transparency + type filter), `styles/app.css`, and wherever
  panels are registered.
- `frontend/tests/grade_shell_panel.test.mjs`

---

## Test Fixtures

Follow the existing `.test.mjs` node-test style in `frontend/tests/`.

**F1** — the metal-capture SVG renders one point per returned row, and the
threshold marker sits at the selected threshold.

**F2** — log-prob plot excludes non-positive grades and shows the excluded
count.

**F3** — clicking a capture-curve point updates the threshold input value.

**F4** — the generate request body matches T008's schema exactly, including
`sample_type_weights` built from the trench slider.

**F5** — a `400` response surfaces the server message through the toast.

**F6** — a `200` with `wireframe: null` shows an informational message and
raises no error toast.

**F7** — grade shells toggle independently of imported vein wireframes: turning
veins off leaves shells visible.

**F8** — shells default to hidden on first scene load.

---

## Acceptance Criteria

| # | Priority | Criterion |
|---|---|---|
| AC-1 | P0 | F1–F8 pass |
| AC-2 | P0 | No new frontend dependency, framework, or build step |
| AC-3 | P0 | All HTTP goes through `api_client.js` |
| AC-4 | P0 | Panel defaults match T008 defaults exactly |
| AC-5 | P0 | Validation numbers are shown, including when they look bad |
| AC-6 | P0 | Guideline colouring never blocks generation |
| AC-7 | P0 | `comparable` is presented as advisory, never as approval |
| AC-8 | P1 | Shells are semi-transparent and on their own layer, off by default |
| AC-9 | P1 | Existing frontend tests still pass |

---

## Anti-Patterns to Avoid

- Adding Chart.js, D3, or Plotly. These are three small inline-SVG plots and
  the project ships no charting dependency.
- Hiding a poor metal capture or high dilution because it looks bad. The number
  is the deliverable.
- Rendering the shell opaque.
- Wording that implies the tool has validated or approved a domain. It presents
  evidence; the competent person signs off.
- Duplicating scene-loading logic instead of refreshing through the existing
  scene loader.
- Letting the panel and API defaults drift apart.
