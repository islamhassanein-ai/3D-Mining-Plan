# Frontend assets

## `MGM.jpeg` — project logo

The official **Mallogrim Gold Mine** logo (1254 × 1254 JPEG, ~230 KB).

It is consumed in three places, all of which read the file at this exact path:

| Surface | How it loads |
| --- | --- |
| App navbar (`frontend/index.html`) | `<img src="assets/MGM.jpeg">`, served by the static mount |
| Standalone HTML export | Base64 data URI embedded at assembly time (`backend/src/services/html_export.py:load_logo_data_uri`) — the export's CSP allows `img-src data:` only, so an external reference would be blocked |
| Section PDF report | Drawn into the title strip (`backend/src/services/pdf_service.py:_project_logo_path`) |

### Replacing it

Overwrite this file, keeping the name. A roughly square image works best — the
navbar renders it at 36 × 36 px with `object-fit: cover`, and the PDF at
30 × 30 pt with the aspect ratio preserved.

Keep it under ~250 KB. The file is base64-inlined into **every** standalone
HTML export, which inflates it by about 4/3 of the file size and counts
against that export's 60 MB limit.

### If the file is missing

Nothing breaks. Every consumer degrades gracefully: the navbar and HTML export
fall back to the built-in gold SVG mark (via the `<img onerror>` handler), and
the PDF renders its title block at the left margin instead. No error is raised.
