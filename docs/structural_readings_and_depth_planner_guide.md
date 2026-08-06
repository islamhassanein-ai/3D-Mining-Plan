# Structural Readings & Drillhole Depth Planner — Working Guide

A practical guide to the two related features in the 3D Mining Plan viewer: recording structural (dip/strike) measurements, and using them to predict where a proposed hole will cut a target zone.

Written against the current code. Where the tool cannot do something, this guide says so plainly rather than describing a workaround as a feature.

**Where things live in the code**

| Feature | Files |
|---|---|
| Structural readings API | `backend/src/api/structural.py` |
| Structural readings panel | `frontend/src/components/structural_panel.js` |
| Structural readings in 3D | `frontend/src/scene/structural_readings.js` |
| Depth Planner panel | `frontend/src/components/depth_planner_panel.js` |
| Depth Planner maths | `frontend/src/services/depth_planner.js` |
| Depth Plan 3D drawing | `frontend/src/scene/depth_plan_renderer.js` |
| Layer visibility | `frontend/src/components/layer_toggles.js` |
| Saved camera views | `frontend/src/components/view_bookmarks.js` |

---

## Part 1 — Structural Readings

### 1.1 What a reading is

A structural reading records the **orientation of a planar geological feature at a known point**: a vein wall, a fault, a bedding contact, a shear. Six fields:

| Field | Meaning | Required |
|---|---|---|
| `reading_type` | `dip_strike` or `fault_trace` | yes |
| `easting`, `northing`, `elevation` | where you stood, in the project's UTM zone | yes |
| `dip` | 0–90°, measured down from horizontal | required for `dip_strike` |
| `strike` | 0–360° | required for `dip_strike` |

`fault_trace` may carry dip/strike or leave them blank — a mapped trace with no measurement is still worth having in the scene. `dip_strike` **must** have both; the API rejects the row otherwise (400 on the single-entry form, silently skipped on CSV import).

Validation is strict on both paths: `dip` outside 0–90 and `strike` outside 0–360 are rejected. That is a deliberate constraint on the dip convention — see 1.5.

### 1.2 Adding readings

**Sidebar → Structural Readings.**

**One at a time** — fill the form, *Create Reading*. Good for the handful of measurements you took at a specific outcrop.

**Bulk CSV** — pick a file, *Import CSV*. Headers are case-insensitive and spaces become underscores, so `Reading Type` and `reading_type` both work. Column order does not matter.

```csv
reading_type,easting,northing,elevation,dip,strike
dip_strike,209341.2,2468117.5,412.0,62,145
dip_strike,209358.7,2468131.0,409.5,58,151
dip_strike,209372.4,2468144.8,407.2,65,139
fault_trace,209410.0,2468180.0,401.0,80,022
fault_trace,209455.3,2468212.6,398.4,,
```

Rows that fail validation are **skipped silently** and the response counts only what went in. If you import 40 rows and the message says 37, three rows had a bad dip, a bad strike, or a `dip_strike` with a blank measurement. Check the count every time.

### 1.3 Fixing bad data — the duplicate problem

**Collars and trenches supersede on re-import; structural readings did not.** A collar CSV re-imported with a corrected elevation matches on `hole_id` and replaces the old row. A structural CSV has no equivalent key — no reading ID, and coordinates alone cannot distinguish "I corrected this reading" from "I took another reading nearby". So every import was a pure append, and re-importing a corrected file left you with the bad readings *and* the good ones, both rendering, both feeding the planner's mean plane.

Three ways out, in order of preference:

**Replace mode (the fix for a corrected file).** Tick **"Replace existing readings"** below the file picker before importing. Every current reading in the project is retired, and only the rows in this CSV survive. Use this whenever the CSV you are importing is meant to be *the whole truth* for the project.

> Guard: if the CSV parses to zero valid rows, the import is refused and your existing readings are left alone. A file with a typo in the header cannot wipe your data.

**Delete one reading.** Each row in the Existing Readings table has an `×`. It disappears from the table, the 3D scene and the Depth Planner immediately.

**Remove all.** The *Remove all* button above the table clears the project's readings. Use it when the project has already accumulated duplicates from earlier appends: clear, then import the corrected file once.

All three are **soft deletes** — the row is marked superseded, not erased, so the import batch that created it still explains what was loaded and when. Every read path filters superseded rows out, so the effect is indistinguishable from deletion in the UI.

**Deciding between append and replace:** append when you are adding *new* fieldwork to what is already there. Replace when you are correcting *what is already there*. Getting this wrong in the append direction is recoverable (*Remove all*, re-import); getting it wrong in the replace direction means re-importing the readings you lost.

### 1.4 Seeing them in the scene

Readings render as small oriented discs — the pole and plane of each measurement — coloured by type.

**The Structural Readings layer starts switched OFF.** So does Vein Wireframes. Both are interpretation rather than measurement, and both sit *through* the drilling rather than beside it: a solid vein shell hides the assay intervals that justify it, and a field of dip discs speckles the ground surface. Turn them on in **Layers** when you are reading structure. If you toggled the layer on and still see nothing, the project genuinely has no readings — check the Structural Readings panel table.

### 1.5 Dip convention — read this before trusting a number

The tool stores **dip as a positive magnitude (0–90°) plus a strike (0–360°)**. It does not store dip direction as a field; the planner derives it.

Two conventions are in circulation and they differ by 180°:

- **strike − 90** — the older "quadrant" habit, still common in field notebooks
- **strike + 90** — the right-hand rule (RHR), where the dip is always 90° clockwise from strike

The Depth Planner exposes this as the **"Strike → dip dir"** dropdown, because it is the one assumption in the whole workflow that will silently invert your answer. Get it wrong and the planner will confidently tell you the zone is *up*-dip of the collar when it is down-dip.

**How to check which one your data uses:** pick a reading where you know from the outcrop which way the plane leans. Set the dropdown, read the computed **Dip dir** field, and compare it to the ground. If it points the wrong way, switch the dropdown. Do this **once per dataset**, at the start, and note the answer.

---

## Part 2 — Drillhole Depth Planner

### 2.1 What it does

Given:
- a **target zone** — where it is at surface, and how it is oriented
- a **proposed hole** — collar, azimuth, dip

it computes **how far down that hole the zone will be cut**, and — more usefully — **how wrong that number could be**.

It is a what-if tool. Nothing it produces is saved to the project. The output lives in the 3D scene and in the clipboard report.

Open it from the sidebar. It is a floating card, not a modal, deliberately: you tune a dip by two degrees and watch the intersection slide up the hole in the 3D view, so the viewport has to stay orbitable while the panel is open. Drag it by its header.

### 2.2 Where its data comes from

The planner reads the **already-loaded scene payload**, not the API. Trench samples, structural readings and collars are all in there. Two consequences:

- it works inside the standalone HTML export, offline, with no server
- data added while the planner is open does not appear in its dropdowns — reload the project

### 2.3 The panel, section by section

#### 1 — Target zone

The zone is defined by **two anchor points**: a *top* and a *base*. Together with the plane orientation from section 2, they define the slab the hole has to hit.

The fastest way to fill them is the **Trench dropdown**. It lists every trench in the project. Pick one, type the From/To metres of the mineralized interval, click **Load** — the planner finds the trench samples nearest those metres and writes their real surveyed coordinates into the anchor boxes.

Only the top anchor is required. Without a base you get a single intersection depth instead of a target *interval*, and no true-thickness or core-length estimate.

Every auto-filled box stays editable. The trench gives you a starting point; the whole value of the tool is asking "what if the top is really two metres further west".

#### 2 — Structure

The **Readings** multi-select lists every `dip`+`strike` reading in the project.

On first open, the planner **pre-selects the three readings nearest the zone anchor**. Not all of them — averaging every reading in a project mixes a bedding, a shear and a joint into one meaningless mean plane, and the resulting depth looks exactly as authoritative as a good one. Three nearby readings is about the most a projection like this can honestly lean on.

Ctrl-click to change the selection, then **Use mean**. The planner computes a **vector mean of the poles** (not an arithmetic mean of the angles — that gives nonsense across 360°) and writes strike / dip / dip dir into the boxes below.

Read the note underneath:

- *"poles 8° apart"* — a tight, coherent set. Trust it.
- *"poles 34° apart — these may not be the same structure"* — you have mixed two structures, or the zone is folded. Narrow the selection.
- *"Single reading — no averaging"* — one measurement projected tens of metres. The number will be precise and may not be accurate.

**Strike** and **Dip dir** are linked: edit either and the other follows the convention dropdown. They cannot silently disagree.

#### 3 — Proposed hole

**From existing hole** lists every collar in the project, planned holes first. Pick one and the collar E/N/Z, the hole ID, and the **azimuth and dip** are all filled from the hole's desurveyed trace. A planned hole loads back exactly as it was drafted; a drilled hole loads as it was collared.

This is the answer to "do I have to retype coordinates every time" — you do not, for either the trench or the hole. Every loaded value stays editable, and editing a box does not reset the dropdown.

Loading a **drilled** hole clears the Hole ID box on purpose: you are planning *from* that pad, not renaming an existing hole.

Manual entry still works for a collar that does not exist yet — leave the dropdown on "manual entry" and type.

- **Azimuth** — 0–360°, grid north
- **Dip (below h.)** — enter the magnitude, e.g. `60` for a hole drilled 60° down

#### 4 — Uncertainty

Three tolerances, and they are the point of the tool:

| Field | Default | What it means |
|---|---|---|
| Dip ±° | 5 | how well you know the zone's dip |
| Dip dir ±° | 10 | how well you know its dip direction |
| Collar Z ±m | 2 | how well you know the collar's elevation |

Defaults are reasonable for compass-and-clinometer readings on a DEM-derived collar elevation. Tighten them if you have surveyed collars and structural readings from oriented core; loosen them if the dip is one measurement from a weathered outcrop.

#### 5 — Result

- **Target x – y m** — predicted downhole depths to the zone top and base
- **Start logging** — where to begin paying attention
- **EOH** — a recommended end-of-hole, below the deepest estimate in the envelope
- **Full envelope** — the range across every combination of your tolerances. *This is the number that matters.* A 42 m prediction with an 18–71 m envelope is not a 42 m prediction.
- **Intersection angle** — below ~30° you get a warning: an oblique cut is long and its depth is poorly constrained
- **Core length / true thickness** — how much core the interval will produce for a given true width
- **Collar elevation sensitivity** — metres of target movement per metre of collar error

The **Sensitivity table** ranks each assumption by how much it moves the answer, and names the biggest control. If it says *dip direction (24.3 m of spread)*, another dip measurement will not help you — a second dip-direction reading will.

The **Trench metre → downhole depth** table maps each trench sample to the depth its projection lands at, with grade. This is how you carry a trench's grade profile into the core log: "the 4.1 g/t at trench metre 12 should appear around 47 m downhole."

#### 6 — Post-drill calibration

After drilling, enter the depth the zone **actually** appeared at.

The planner re-solves the geometry and reports the two explanations for the miss:

> Predicted 42.0 m, observed 51.5 m — off by +9.5 m.
> Either the collar is really 405.2 m (−6.8 m), or the dip is really 68.4° (+8.4°).
> **These two are indistinguishable from one intersection.**

That last line is not a hedge, it is the geometry. One intersection cannot separate a collar-elevation error from a dip error. Core logging or a second intersection is what separates them. Use this to decide which measurement to go back and re-check — not to "correct" the model on one data point.

### 2.4 The Depth Plan layer

**"Depth Plan" in the Layers panel is the planner's 3D output.** It is empty until you open the planner and enter a plan, which is why the toggle looks like it does nothing on a freshly loaded project.

It contains four things:

| Element | Look | What it is |
|---|---|---|
| Zone slab | translucent red box with bright edges | the target zone, projected from your anchors at the plane's attitude |
| Proposed hole | dashed cyan trace, round teal collar | the hole you are planning |
| Depth call-outs | orange rings around the trace, with labels | the predicted top and base intersections |
| Uncertainty sleeve | amber | the envelope — the spread of possible intersection depths |

Everything is dashed or translucent **on purpose**. A planned intersection sitting next to real assay intervals must never be mistakable for a result. The cyan is the same cyan `drillhole_traces.js` reserves for planned holes, so the two read as the same kind of object.

The slab is sized for legibility, not surveyed — it is flagged out of the camera-fit calculation so it cannot make the viewer frame the project around a drawing choice.

Turning the layer off hides the plan without clearing it; *Clear plan* in the panel removes it.

---

## Part 3 — Saved camera views

The four presets (Plan / Section N-S / Section E-W / Isometric) answer "show me a standard orientation". They cannot answer "put me back on the oblique view I read this deposit from", which is the view you actually return to twenty times a day.

**Sidebar → Saved Views.**

1. Orbit, pan and zoom to the view you want.
2. Type a name and hit **Save** (or press Enter).
3. Click the name any time to jump back to that exact framing — angle, distance and centring.
4. The **★** marks one view as the **startup view**: the project opens on it instead of the automatic fit-to-data framing, and *Reset Camera* **[R]** returns there too.
5. **×** deletes a view. Saving under a name that already exists updates that view rather than adding a second row.

Views are stored per project in the browser's local storage. They are a personal habit rather than project data, so they do **not** travel to whoever you share the project with, and they do **not** follow you to another machine or another browser. Twenty views per project.

---

## Part 4 — Worked example

> **Setting.** Trench `TR-014` cut a quartz-sulphide vein from 12 m to 18 m along the trench, best sample 6.2 g/t. Three dip/strike readings on and beside the vein average about 60° toward 145°. You want to test it at depth from a pad 40 m away, and you need a metreage for the drilling contractor.

**Step 0 — settle the convention.** Open the planner. In section 2, set **Strike → dip dir**. Your readings are `145/62` style with dip direction written separately in the notebook as ~235°; `strike + 90` reproduces that, so pick RHR. Confirm the computed **Dip dir** matches the notebook before going further.

**Step 1 — anchor the zone.** Section 1: **Trench** → `TR-014`. **From** `12`, **To** `18`. Click **Load**. The six anchor boxes fill with the real surveyed coordinates of the samples at those metres.

**Step 2 — take the structure.** Section 2: the planner has already pre-selected the three readings closest to the anchor. The note reads *"Vector mean of 3 readings: 145 / 61 / 235 — poles 7° apart"*. Tight and coherent — accept it. Click **Use mean** if you changed the selection.

**Step 3 — the hole.** Section 3: your pad has an existing planned hole `MGM-PL-07` drafted at azimuth 315°, −60°. Pick it in **From existing hole** — collar, azimuth, dip and hole ID all load. If the pad is new instead, leave the dropdown on manual and type the collar E/N/Z, azimuth `315`, dip `60`.

**Step 4 — be honest about uncertainty.** The collar elevation came off a 5 m DEM, not a survey, so change **Collar Z ±m** from `2` to `4`. Compass readings on a partly weathered outcrop: leave dip at ±5 and widen dip dir to ±15.

**Step 5 — read the answer.**

```
Target        38.4 – 47.9 m
Start logging 30 m   ·   EOH 75 m
Full envelope 27.1 – 62.8 m
Intersects the plane at 71°.
Expect 9.5 m in the core for 6.0 m true thickness.
Biggest control: dip direction (14.2 m of spread).
```

**Step 6 — act on the sensitivity, not just the depth.** The 38–48 m target is only worth as much as the ±15° on dip direction, which is contributing 14 m of spread on its own. Two more dip-direction readings along strike would cut the envelope more than anything else you could do — and they cost an afternoon rather than a hole.

**Step 7 — brief the driller.** *Copy report* puts the whole plan, sensitivity table and trench-metre mapping on the clipboard as plain text. Paste it into the drill instruction. It carries the envelope and the EOH, not just the headline depth.

**Step 8 — after drilling.** The vein came in at 52.0 m. Enter `52` in **Actual intersection**:

> Predicted 38.4 m, observed 52.0 m — off by +13.6 m. Either the collar is really 396.1 m (−9.9 m), or the dip is really 69.8° (+8.8°).

A 9.9 m collar error on a DEM-derived elevation is implausible; a 9° dip error on three compass readings is not. **Survey the collar** to rule out one of them, then re-run the planner with the corrected dip for the next hole on the section.

---

## Part 5 — Known gaps

| Gap | Current state | Impact |
|---|---|---|
| Edit a structural reading in place | No update route — delete and re-create | Fixing one typo is two actions |
| Match structural readings on re-import | No natural key exists; replace mode is all-or-nothing per project | A CSV correcting *some* readings cannot be merged selectively |
| Saved views across devices | Browser localStorage only | Views do not follow you to another machine, and are not shared |
| Save a depth plan to the project | Nothing is persisted; the plan lives in the session | Re-open the planner and re-enter to reproduce a plan |
| Structural readings in the standalone export | Rendered in the scene and readable by the planner, but not editable | The export is a viewer, by design |
