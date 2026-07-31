# Sample CSV Files — Combined Importer

Drop any of these into the **Import Panel → Combined CSV** input to test specific features.

| File | What it exercises |
|---|---|
| `01_basic_multizone.csv` | 3 zones, all 5 hole types — happy path |
| `02_bom_excel.csv` | UTF-8 BOM (what Excel exports) — encoding fix |
| `03_no_type_column.csv` | Missing Type column → warning, all rows default to DD |
| `04_flat_trenches.csv` | TR/CH/FC polylines — verify end elevation == start elevation |
| `05_dd_visible_trace.csv` | DD with inline survey — verify 2-point trace in 3D scene |
| `06_reimport_idempotent.csv` | Upload twice — counts must stay the same |
| `07_zone_case_variants.csv` | `"abo elmajd"` / `"Abo Elmajd"` / `"  Abo  elmajd "` → one project |
| `08_invalid_rows.csv` | Mix of valid + invalid rows — only bad rows are rejected |
| `09_planned_and_unsampled.csv` | `Status` column (planned vs drilled), unsampled top zones, blank/placeholder grades |
| `10_collar_with_planned.csv` | Four-file **collar.csv** with `hole_type` + `status` — planned holes without the combined CSV |

All files except `02_bom_excel.csv` are plain UTF-8 (no BOM).
`02_bom_excel.csv` contains a real BOM (`\xef\xbb\xbf`) written by Python to simulate Excel.

## Planned boreholes

A planned (proposed) hole renders with a **dashed cyan trace** and
**translucent target intervals**, has its own **Planned Boreholes** switch in
the Layers panel, and shows `Status: Planned` in the inspector and hover
tooltip.

Both import paths support it.

### Combined CSV — add a `Status` column

```
Hole Id,Zone,X,Y,Z,Dip,Azimuth,Total_Length,Type,Status,Sample_ID,From,To,Grade
AAPL001,Abo Elmajd,208270,2467915,300,-65,110,90.0,DD,planned,AAPL001-T01,30,45,1.20
AAPL001,,,,,,,,,,AAPL001-T02,60,72,2.80
```

The `From`/`To`/`Grade` on a planned hole are the **target** interval and its
expected grade — they render as translucent tubes rather than solid ones.
See `09_planned_and_unsampled.csv`.

### Four-file import — add `status` to `collar.csv`

```
hole_id,easting,northing,elevation,hole_type,status
DDH-001,515000,4515000,1050,DD,drilled
PLAN-001,515180,4515060,1038,DD,planned
```

`survey.csv` and `assay.csv` are unchanged — reference the planned hole by its
`hole_id` exactly as you would a drilled one. `hole_type` is optional
(DD/RC/TR/CH/FC). See `10_collar_with_planned.csv`.

## The `Status` column (optional)

Marks a hole as completed or proposed. Omit it entirely and every hole is
treated as `drilled` — existing CSVs need no change. Accepted under the header
`Status` or `hole_status` in both import paths.

* **drilled** — also accepts `drill`, `completed`, `complete`, `existing`,
  `actual`, `no`, `false`, `0`
* **planned** — also accepts `plan`, `proposed`, `target`, `design`, `yes`,
  `true`, `1`

Values are case-insensitive, and a blank cell on a sample continuation row
inherits the status from the hole's first row. Planned holes render with a
dashed cyan trace and translucent target intervals, and have their own
visibility switch in the **Layers** panel.

## Unsampled intervals

Two ways to record a depth range that was logged but never assayed:

1. Leave the `Grade` cell blank (stored as NULL, not `0.0`).
2. Use a placeholder `Sample_ID`: `Unsampled`, `NSR`, `NS`, `No Sample`, or
   `No Samples`.

Either way the interval is classified as **No Sample**, drawn with no tube in
the 3D scene (the bare trace line shows through), and listed explicitly in the
inspector's downhole log. Depth ranges with no row at all are detected
automatically and appear as `No Sample` rows too, so the log always runs
unbroken from 0.0 m to end of hole.
