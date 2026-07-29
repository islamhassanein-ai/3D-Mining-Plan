# Quickstart / Verification: Standalone HTML Export

Manual verification for `006-standalone-html-export`. Record **actual** observed
results, including failures. Do not mark a human-judgment check ("orbits smoothly")
as passed unless it was genuinely performed in a browser.

**Prerequisites**: `./run.ps1` works, Postgres reachable, the seeded
`Monark Gold Prospect` project loads, and the project has topography, trenches, and
at least one vein wireframe (upload from `sample_data/` if not — the export path for
those is otherwise untested).

---

## §1 — Live-app regression gate (run after T010, and again after T011)

This section protects the shipped app from the refactor. It is the gate before any
export-specific work begins.

```bash
npm --prefix frontend run build
```

Then `./run.ps1`, open <http://localhost:8000>, and confirm — **owner mode**:

| # | Check | Expected |
|---|---|---|
| 1.1 | Project loads from the switcher | Scene renders: traces, assays, lithology, topography, trenches, wireframes, labels |
| 1.2 | Header summary stats | Hole count, metres, avg g/t, peak g/t and the trench group match the values seen before the refactor |
| 1.3 | Cutoff slider | Intervals below cutoff vanish in the same frame; histogram tracks |
| 1.4 | Click a trace, then an interval | Inspector loads collar detail; the clicked interval row is highlighted and scrolled to |
| 1.5 | True thickness | Enter dip direction + dip on a selected interval — value appears and matches the pre-refactor value |
| 1.6 | 2D section panel | Opens, slicing plane drags, section updates |
| 1.7 | Ruler, go-to-coordinate, camera presets, `P`/`N`/`E`/`I`/`?` | All behave as before |
| 1.8 | Panel collapse tabs | Left, right, and bottom panels slide; the WebGL canvas keeps up with no stretch |
| 1.9 | Layout at 1280×800 and 1600×900 | **Pixel-identical to pre-refactor** (T011 CSS extraction) — compare screenshots |
| 1.10 | DevTools console | No new errors or warnings |

And **share-link mode**: create a share link, open `?share=<token>` in a private
window, and repeat 1.1, 1.3, 1.4, 1.5, 1.6. Owner-only controls stay hidden.

> Any difference here is a refactor defect. Fix it before Phase 2.

---

## §2 — Produce an export

1. In the live app: **Export Project Data** → **Interactive 3D Viewer (HTML)** →
   leave *Include topography surface* checked → **Download**.
2. Confirm: exactly one `.html` file, named `{Project}_3D_Viewer_{YYYYMMDD}.html`,
   no `.zip`, no sidecar files.
3. Note the file size. Against NFR-003, ≤ 15 MB for the seeded demo project.

| # | Check | Expected |
|---|---|---|
| 2.1 | File count | One `.html`, nothing else |
| 2.2 | Filename | Project name + `_3D_Viewer_` + export date |
| 2.3 | Size | ≤ 15 MB for the demo project (record the actual number) |
| 2.4 | Open in a text editor, search `mining_session_token`, `Bearer`, `localhost:8000`, `uploads/` | Zero hits |
| 2.5 | Search `fonts.googleapis`, `src="http`, `href="http` | Zero hits |

---

## §3 — Offline open (the core guarantee, NFR-001)

Do this on a machine — or in a browser profile — with **networking disabled**.
Turning off Wi-Fi is sufficient; a VM without a NIC is better.

1. Disable networking.
2. Double-click the `.html` file so it opens as `file:///...` (**not** via
   `localhost` — that would invalidate the whole test; check the address bar).
3. Open DevTools **before** reloading, go to the Network panel, then reload.

| # | Check | Expected |
|---|---|---|
| 3.1 | Scene renders | Full model, as in §1.1 |
| 3.2 | Network panel | **Zero** requests beyond the document itself |
| 3.3 | Console | No errors; specifically no CSP violation reports |
| 3.4 | Address bar | `file://` scheme |

Repeat 3.1–3.4 in **Chrome**, **Edge**, and **Firefox** (NFR-004). Record each
separately — Firefox's `file://` behaviour differs enough from Chromium's that
testing one does not cover the other.

---

## §4 — Interaction parity (US2)

In the offline file, with the live app open side by side on the same project:

| # | Check | Expected |
|---|---|---|
| 4.1 | Orbit / zoom / pan | Identical feel to live (same damped controls) |
| 4.2 | Camera presets + reset + `P`/`N`/`E`/`I` | Same viewpoints |
| 4.3 | Orientation gizmo | Tracks the camera |
| 4.4 | Layer toggles | Each layer shows/hides |
| 4.5 | Cutoff slider | Same intervals hidden at the same value; same-frame response |
| 4.6 | Grade histogram | Same distribution and cutoff marker |
| 4.7 | Hover a trace | Gold highlight sleeve + tooltip, as live |
| 4.8 | Click trace / interval | Inspector shows the same collar, surveys, assays, lithologies, merged timeline |
| 4.9 | True thickness | Same value as live to 2 dp — **and no network request appears** |
| 4.10 | 2D section + slicing plane | Same section content at the same offset/thickness |
| 4.11 | 3D ruler | Same distance / dX / dY / dZ between the same two points |
| 4.12 | Go-to-coordinate | Camera moves; coordinate flag flashes |
| 4.13 | Topography mesh ↔ point cloud | Both modes render; the mesh surface reads correctly (no sliver artefacts from decimation) |
| 4.14 | Panel collapse tabs, hint card, `?` help overlay, `Esc` | As live |
| 4.15 | **Performance** | First frame ≤ 3 s; sustained ≥ 30 fps while orbiting (DevTools FPS meter). Record the numbers and the machine. |

---

## §5 — Provenance and omissions (US3)

| # | Check | Expected |
|---|---|---|
| 5.1 | Header | `STATIC EXPORT` chip visible and persistent |
| 5.2 | Footer | Project name, UTM zone, export timestamp (UTC), exporter, record counts |
| 5.3 | Notices | Any decimation or dropped wireframe is stated in the footer |
| 5.4 | Absent controls | No import, upload, share, history, delete, project switcher, CSV/PDF/DXF export, UTM zone editing — anywhere, including keyboard paths |
| 5.5 | `include_author=false` | Re-export with the parameter; search the file for the email — zero hits |
| 5.6 | Browser tab title | `{Project} — 3D Model (Static Export)` |

---

## §6 — Automated tests

```bash
venv\Scripts\python.exe -m pytest backend/tests -q -c backend/pytest.ini
```

```bash
npm --prefix frontend test
```

Both must pass. The pytest run must include `test_html_export.py`,
`test_true_thickness_vectors.py`, and the extended `test_export.py`. Note: pytest
must run with the repo root as `rootdir` (imports are `backend.src.*`) — see
`README.md`.

---

## §7 — Failure paths (US4 and operability)

| # | Scenario | How to produce | Expected |
|---|---|---|---|
| 7.1 | Missing viewer bundle | `rm frontend/dist/export_viewer.js`, then export | HTTP 503 with the exact build command; **no** file downloads |
| 7.2 | Oversized export | Upload a very dense topography CSV, or temporarily lower `MAX_EXPORT_BYTES` | HTTP 413 naming the contributor and the remedy; no partial download |
| 7.3 | Topography above the decimation cap | Upload > 60 000 topography points | Export succeeds; footer discloses the reduction; surface still reads correctly |
| 7.4 | Topography excluded | Uncheck *Include topography surface* | Smaller file; no terrain; footer notes the exclusion |
| 7.5 | Empty project | Export a project with no drillholes | Valid file that opens to an empty scene with a readable message — not an error page |
| 7.6 | Non-owner | Call the endpoint with another user's session | 404, indistinguishable from an unknown project |
| 7.7 | Hostile project name | Rename a project to `</script><img src=x onerror=alert(1)>` and export | File opens normally; the name renders as literal text; no alert |

---

## Sign-off

Record for each section: **PASS / FAIL / NOT RUN**, the browser and version, the
machine, and any deviation. `NOT RUN` is an acceptable and expected outcome for
checks that were genuinely skipped — a fabricated `PASS` is not.

| Section | Result | Browser / machine | Notes |
|---|---|---|---|
| §1 Live regression | | | |
| §2 Export produced | | | |
| §3 Offline open | | | |
| §4 Interaction parity | | | |
| §5 Provenance | | | |
| §6 Automated tests | | | |
| §7 Failure paths | | | |
