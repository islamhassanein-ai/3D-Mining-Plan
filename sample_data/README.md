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

All files except `02_bom_excel.csv` are plain UTF-8 (no BOM).
`02_bom_excel.csv` contains a real BOM (`\xef\xbb\xbf`) written by Python to simulate Excel.
