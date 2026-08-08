import {
  computePlan,
  meanPlane,
  signedDip,
  dipDirectionFromStrike,
  isNum
} from '../services/depth_planner.js';
import { ApiClient } from '../services/api_client.js';
import { buildPlanSection } from '../export/plan_section_svg.js';
import { svgBlob, svgToPngBlob, downloadBlob, sectionFilename } from '../export/section_image.js';

// Drillhole Depth Planner.
//
// A floating card rather than a modal: the geologist tunes a dip by a couple of
// degrees and watches the intersection slide up the hole in the 3D view, so the
// viewport must stay orbit-able the whole time. A .modal-overlay would swallow
// those drags.
//
// Data comes from the already-loaded scene payload, not the API. Everything the
// planner needs -- trench sample coordinates and grades, structural readings,
// collars -- is in there, which is also why this keeps working inside the
// standalone HTML export.
//
// Auto-filled fields are always left editable. Loading a trench and a pair of
// readings is a starting point, not an answer; the whole value of the tool is
// asking "what if the dip is really 36" and seeing the number move.

const num = (el) => {
  const raw = el ? el.value : '';
  return raw === '' || raw === null ? NaN : Number(raw);
};

export class DepthPlannerPanel {
  /**
   * @param container  host element inside the viewport
   * @param viewport   object returned by init3DViewport
   * @param sceneData  the payload from SceneLoader.load()
   */
  constructor(container, viewport, sceneData, options = {}) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.viewport = viewport;
    this.data = sceneData || {};
    this.renderer = viewport && viewport.depthPlanRenderer;
    // Both optional: without them the planner still works as a scratchpad, it
    // just cannot persist. The standalone HTML export has neither.
    this.projectId = options.projectId || null;
    this.projectName = options.projectName || null;
    this.onSaved = options.onSaved || null;
    this.result = null;
    this.debounce = null;
    this.saving = false;

    this.trenches = this.groupTrenches(this.data.trenches || []);
    this.readings = (this.data.structural_readings || []).filter(r => isNum(r.dip) && isNum(r.strike));
    this.holes = this.sortHoles(this.data.drillholes || []);

    this.render();
    this.bindEvents();
    this.prefill();
  }

  /** Flat sample rows -> { trenchId: [samples sorted by metre] }. */
  groupTrenches(rows) {
    const byId = new Map();
    for (const row of rows) {
      if (!row.trench_id) continue;
      if (!isNum(row.easting) || !isNum(row.northing) || !isNum(row.elevation)) continue;
      if (!byId.has(row.trench_id)) byId.set(row.trench_id, []);
      byId.get(row.trench_id).push(row);
    }
    for (const list of byId.values()) {
      list.sort((a, b) => (Number(a.from_depth) || 0) - (Number(b.from_depth) || 0));
    }
    return byId;
  }

  /** Usable collars, planned before drilled, each group alphabetical. */
  sortHoles(rows) {
    return rows
      .filter(h => h.hole_id && isNum(h.easting) && isNum(h.northing) && isNum(h.elevation))
      .slice()
      .sort((a, b) => {
        const rank = (h) => (h.hole_status === 'planned' ? 0 : 1);
        return rank(a) - rank(b) || String(a.hole_id).localeCompare(String(b.hole_id));
      });
  }

  render() {
    const trenchOptions = [...this.trenches.keys()]
      .map(id => `<option value="${id}">${id}</option>`).join('');

    const readingOptions = this.readings.map((r, i) => {
      const dd = dipDirectionFromStrike(r.strike);
      return `<option value="${i}">${Math.round(r.strike)}/${Math.round(r.dip)} → dd ${Math.round(dd)}  (${r.reading_type})</option>`;
    }).join('');

    // Planned holes first: re-planning an already-drafted hole is the common
    // case, and a drilled hole is normally loaded to re-plan a twin or a
    // step-out from the same pad.
    const holeOptions = this.holes.map((h, i) =>
      `<option value="${i}">${escapeAttr(h.hole_id)} (${h.hole_status === 'planned' ? 'planned' : 'drilled'})</option>`
    ).join('');

    this.container.innerHTML = `
      <div class="modal-card dp-card">
        <div class="modal-header dp-header">
          <span>Drillhole Depth Planner</span>
          <button class="modal-close" id="dp-close">&times;</button>
        </div>

        <div class="dp-body">
          <div class="dp-section-title">1 &nbsp;Target zone</div>

          <div class="dp-row">
            <label>Trench</label>
            <select id="dp-trench" class="dp-input">
              <option value="">— none / manual —</option>
              ${trenchOptions}
            </select>
          </div>
          <div class="dp-row dp-row-3">
            <div><label>From (m)</label><input type="number" step="any" id="dp-from" class="dp-input"></div>
            <div><label>To (m)</label><input type="number" step="any" id="dp-to" class="dp-input"></div>
            <div><label>&nbsp;</label><button class="btn-small dp-fill" id="dp-load-trench">Load</button></div>
          </div>

          <div class="dp-grid2">
            <div>
              <div class="dp-mini-title">Zone top (anchor)</div>
              <input type="number" step="any" id="dp-top-e" class="dp-input" placeholder="Easting">
              <input type="number" step="any" id="dp-top-n" class="dp-input" placeholder="Northing">
              <input type="number" step="any" id="dp-top-z" class="dp-input" placeholder="Elevation">
            </div>
            <div>
              <div class="dp-mini-title">Zone base (anchor)</div>
              <input type="number" step="any" id="dp-base-e" class="dp-input" placeholder="Easting">
              <input type="number" step="any" id="dp-base-n" class="dp-input" placeholder="Northing">
              <input type="number" step="any" id="dp-base-z" class="dp-input" placeholder="Elevation">
            </div>
          </div>

          <div class="dp-section-title">2 &nbsp;Structure</div>

          <div class="dp-row">
            <label>Readings <span class="dp-hint">(ctrl-click for several)</span></label>
            <select id="dp-readings" class="dp-input" multiple size="3">${readingOptions}</select>
          </div>
          <div class="dp-row dp-row-2">
            <div>
              <label>Strike &rarr; dip dir</label>
              <select id="dp-convention" class="dp-input">
                <option value="minus90">strike &minus; 90</option>
                <option value="plus90">strike + 90 (RHR)</option>
              </select>
            </div>
            <div><label>&nbsp;</label><button class="btn-small dp-fill" id="dp-load-readings">Use mean</button></div>
          </div>
          <div class="dp-row dp-row-3">
            <div><label>Strike</label><input type="number" step="any" id="dp-strike" class="dp-input"></div>
            <div><label>Dip</label><input type="number" step="any" id="dp-dip" class="dp-input"></div>
            <div><label>Dip dir</label><input type="number" step="any" id="dp-dipdir" class="dp-input"></div>
          </div>
          <div id="dp-mean-note" class="dp-note"></div>

          <div class="dp-section-title">3 &nbsp;Proposed hole</div>

          <div class="dp-row dp-row-2">
            <div>
              <label>From existing hole</label>
              <select id="dp-collar-hole" class="dp-input">
                <option value="">— manual entry —</option>
                ${holeOptions}
              </select>
            </div>
            <div><label>&nbsp;</label><button class="btn-small dp-fill" id="dp-load-hole">Load collar</button></div>
          </div>

          <div class="dp-row dp-row-3">
            <div><label>Collar E</label><input type="number" step="any" id="dp-collar-e" class="dp-input"></div>
            <div><label>Collar N</label><input type="number" step="any" id="dp-collar-n" class="dp-input"></div>
            <div><label>Collar Z</label><input type="number" step="any" id="dp-collar-z" class="dp-input"></div>
          </div>
          <div class="dp-row dp-row-3">
            <div><label>Azimuth</label><input type="number" step="any" id="dp-azimuth" class="dp-input" value="0"></div>
            <div><label>Dip (below h.)</label><input type="number" step="any" id="dp-holedip" class="dp-input" value="60"></div>
            <div><label>Hole ID</label><input type="text" id="dp-holeid" class="dp-input" placeholder="PLAN01"></div>
          </div>

          <div class="dp-section-title">4 &nbsp;Uncertainty</div>
          <div class="dp-row dp-row-3">
            <div><label>Dip &plusmn;&deg;</label><input type="number" step="any" id="dp-dip-delta" class="dp-input" value="5"></div>
            <div><label>Dip dir &plusmn;&deg;</label><input type="number" step="any" id="dp-dd-delta" class="dp-input" value="10"></div>
            <div><label>Collar Z &plusmn;m</label><input type="number" step="any" id="dp-z-delta" class="dp-input" value="2"></div>
          </div>

          <div class="dp-section-title">5 &nbsp;Drill pattern</div>
          <div class="dp-row">
            <label class="dp-check">
              <input type="checkbox" id="dp-pattern-on"> Plan a grid of holes, not just one
            </label>
          </div>
          <div id="dp-pattern-inputs" style="display:none;">
            <div class="dp-row dp-row-2">
              <div><label>Spacing along strike (m)</label><input type="number" step="any" min="1" id="dp-sp-strike" class="dp-input" value="20"></div>
              <div><label>Spacing down dip (m)</label><input type="number" step="any" min="1" id="dp-sp-dip" class="dp-input" value="20"></div>
            </div>
            <div class="dp-row dp-row-3">
              <div><label>Holes along strike</label><input type="number" step="1" min="1" id="dp-n-strike" class="dp-input" value="3"></div>
              <div><label>Rows down dip</label><input type="number" step="1" min="1" id="dp-n-dip" class="dp-input" value="2"></div>
              <div><label>Collar pad RL</label><input type="number" step="any" id="dp-pad-rl" class="dp-input"></div>
            </div>
            <div class="dp-row">
              <label>Hole ID prefix</label>
              <input type="text" id="dp-prefix" class="dp-input" value="PLAN">
            </div>
          </div>

          <div id="dp-results"></div>

          <div class="dp-section-title">7 &nbsp;Post-drill calibration</div>
          <div class="dp-row dp-row-2">
            <div><label>Actual intersection (m)</label><input type="number" step="any" id="dp-observed" class="dp-input" placeholder="e.g. 45"></div>
            <div><label>&nbsp;</label><button class="btn-small dp-fill" id="dp-clear-observed">Clear</button></div>
          </div>
          <div id="dp-calibration" class="dp-note"></div>

          <div class="dp-actions">
            <button class="btn-small" id="dp-copy">Copy report</button>
            <button class="btn-small" id="dp-clear">Clear plan</button>
          </div>

          <div class="dp-section-title">8 &nbsp;Section image</div>
          <div class="dp-note">
            A vertical section looking along strike — collar, zone, and the depths a
            driller is handed — to paste into a proposal.
          </div>
          <div class="dp-row" style="margin-top:6px;">
            <label class="dp-check">
              <input type="checkbox" id="dp-img-light"> White background (for printed reports)
            </label>
          </div>
          <div class="dp-actions" style="margin-top:8px;">
            <button class="btn-small" id="dp-img-png">Export PNG</button>
            <button class="btn-small" id="dp-img-svg">Export SVG</button>
          </div>
          <div id="dp-img-status" class="dp-note"></div>
        </div>
      </div>
    `;

    this.injectStyles();
    this.resultsEl = this.container.querySelector('#dp-results');
    this.calibrationEl = this.container.querySelector('#dp-calibration');
    this.meanNoteEl = this.container.querySelector('#dp-mean-note');
  }

  injectStyles() {
    if (document.getElementById('depth-planner-styles')) return;
    const style = document.createElement('style');
    style.id = 'depth-planner-styles';
    style.textContent = `
      #depth-planner-container {
        position: absolute; top: 74px; left: 20px; z-index: 120;
        display: none; pointer-events: auto;
      }
      #depth-planner-container.open { display: block; }
      .dp-card { width: 380px; max-height: calc(100vh - 140px); display: flex; flex-direction: column; }
      .dp-header { cursor: move; }
      .dp-body { overflow-y: auto; padding-right: 4px; font-size: 12px; }
      .dp-section-title {
        font-size: 10px; letter-spacing: 0.09em; text-transform: uppercase;
        color: var(--gold, #d4af37); font-weight: 700;
        margin: 14px 0 6px; padding-bottom: 4px;
        border-bottom: 1px solid rgba(255,255,255,0.08);
      }
      .dp-mini-title { font-size: 10px; color: var(--text-muted, #8a97ad); margin-bottom: 3px; }
      .dp-row { margin-bottom: 7px; }
      .dp-row label { display: block; font-size: 10px; color: var(--text-muted, #8a97ad); margin-bottom: 2px; }
      .dp-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
      .dp-row-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
      .dp-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 6px; }
      .dp-input {
        width: 100%; background: rgba(0,0,0,0.3); border: 1px solid var(--border-light, rgba(255,255,255,0.12));
        color: var(--text-main, #e8edf5); padding: 5px 6px; border-radius: 5px;
        font-size: 11px; margin-bottom: 3px;
      }
      .dp-input:focus { outline: none; border-color: var(--gold, #d4af37); }
      select.dp-input[multiple] { height: auto; }
      .dp-fill { width: 100%; }
      .dp-hint { color: var(--text-faint, #5f6b7f); font-weight: 400; text-transform: none; letter-spacing: 0; }
      .dp-note { font-size: 11px; color: var(--text-muted, #8a97ad); line-height: 1.55; margin-top: 4px; }
      .dp-note b { color: var(--text-main, #e8edf5); }
      .dp-table { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 4px; }
      .dp-table th {
        text-align: left; font-size: 9.5px; text-transform: uppercase; letter-spacing: 0.05em;
        color: var(--text-faint, #5f6b7f); font-weight: 600;
        padding: 3px 4px; border-bottom: 1px solid rgba(255,255,255,0.1);
      }
      .dp-table td { padding: 3px 4px; border-bottom: 1px solid rgba(255,255,255,0.045); }
      .dp-table tr.dp-base td { color: var(--gold, #d4af37); font-weight: 700; }
      .dp-num { text-align: right; font-variant-numeric: tabular-nums; }
      .dp-headline {
        background: rgba(212,175,55,0.08); border: 1px solid rgba(212,175,55,0.28);
        border-radius: 6px; padding: 8px 10px; margin-top: 6px; line-height: 1.6;
      }
      .dp-headline .dp-big { font-size: 17px; font-weight: 700; color: var(--gold, #d4af37); }
      .dp-warn { color: #fbbf24; }
      .dp-err { color: #f87171; }
      .dp-scroll { max-height: 170px; overflow-y: auto; }
      .dp-cand-table td { vertical-align: top; }
      .dp-cand-label { font-weight: 600; color: var(--text-main, #e8edf5); }
      .dp-cand-note { font-size: 9.5px; color: var(--text-faint, #5f6b7f); line-height: 1.4; }
      /* A better cut than the current orientation is the reason to look at the
         table at all, so it is the one thing that gets colour. */
      .dp-better { color: var(--accent-green, #22c55e); font-weight: 700; }
      .dp-undrillable { opacity: 0.55; }
      .dp-undrillable .dp-cand-note { color: #fbbf24; }
      .dp-apply { padding: 2px 8px; font-size: 10px; }
      .dp-apply:disabled { opacity: 0.4; cursor: not-allowed; }
      @keyframes dpFlash {
        0%, 100% { background: transparent; }
        30%      { background: rgba(212,175,55,0.28); }
      }
      .dp-flash { animation: dpFlash 1.1s ease-out 1; border-radius: 4px; }
      .dp-check {
        display: flex; align-items: center; gap: 7px; cursor: pointer;
        font-size: 11.5px; color: var(--text-main, #e8edf5); margin-bottom: 0;
        text-transform: none; letter-spacing: 0;
      }
      .dp-check input { width: 14px; height: 14px; accent-color: var(--gold, #d4af37); cursor: pointer; }
      @media (prefers-reduced-motion: reduce) { .dp-flash { animation: none; } }
      .dp-actions { display: flex; gap: 6px; margin: 14px 0 4px; }
      .dp-actions .btn-small { flex: 1; }
    `;
    document.head.appendChild(style);
  }

  /** Sensible starting values so the panel is never a wall of empty boxes. */
  prefill() {
    const first = [...this.trenches.keys()][0];
    if (first) {
      const samples = this.trenches.get(first);
      this.container.querySelector('#dp-trench').value = first;
      this.container.querySelector('#dp-from').value = samples[0].from_depth ?? 0;
      this.container.querySelector('#dp-to').value = samples[samples.length - 1].from_depth ?? 0;
      this.loadTrench();
    }
    // Pre-select by PROXIMITY to the zone, never "all". Averaging every
    // reading in a project mixes unrelated structures -- a bedding and a shear
    // and a joint -- into one meaningless mean plane, and the resulting depth
    // looks just as authoritative as a good one. Three nearby readings is the
    // most a projection like this can honestly lean on; the geologist adjusts
    // the selection from there.
    if (this.readings.length) {
      const anchor = {
        easting: Number(this.container.querySelector('#dp-top-e').value),
        northing: Number(this.container.querySelector('#dp-top-n').value),
        elevation: Number(this.container.querySelector('#dp-top-z').value)
      };
      const ranked = this.readings
        .map((r, i) => ({ i, d: distanceTo(r, anchor) }))
        .sort((a, b) => a.d - b.d)
        .slice(0, 3)
        .map(x => x.i);

      const select = this.container.querySelector('#dp-readings');
      for (const opt of select.options) opt.selected = ranked.includes(Number(opt.value));
      this.loadReadings();
    }
    // Collar defaults to the first hole in the sorted list -- planned holes
    // sort first, and a planned hole is usually exactly the one being sized.
    // Selecting it in the dropdown rather than only writing the numbers means
    // the choice is visible and re-selectable, and the azimuth/dip come across
    // with it.
    if (this.holes.length) {
      this.container.querySelector('#dp-collar-hole').value = '0';
      this.loadHole();
      if (this.holes[0].hole_status !== 'planned') {
        // A drilled hole is a location to plan *from*, not a hole ID to reuse
        // -- leaving its name in the field would label the proposal as an
        // existing hole.
        this.container.querySelector('#dp-holeid').value = '';
      }
    }
    this.recompute();
  }

  bindEvents() {
    const q = (sel) => this.container.querySelector(sel);

    q('#dp-close').onclick = () => this.close();
    q('#dp-load-trench').onclick = () => { this.loadTrench(); this.recompute(); };
    q('#dp-load-readings').onclick = () => { this.loadReadings(); this.recompute(); };
    q('#dp-clear').onclick = () => this.clearPlan();
    q('#dp-copy').onclick = () => this.copyReport();
    q('#dp-clear-observed').onclick = () => { q('#dp-observed').value = ''; this.recompute(); };

    q('#dp-img-png').onclick = () => this.exportSection('single', 'png');
    q('#dp-img-svg').onclick = () => this.exportSection('single', 'svg');

    q('#dp-load-hole').onclick = () => { this.loadHole(); this.recompute(); };
    q('#dp-collar-hole').onchange = () => { this.loadHole(); this.recompute(); };
    q('#dp-trench').onchange = () => { this.loadTrench(); this.recompute(); };
    q('#dp-convention').onchange = () => { this.loadReadings(); this.recompute(); };

    // Strike and dip direction are two views of one number; editing either
    // updates the other so the pair can never silently disagree.
    q('#dp-strike').addEventListener('input', () => {
      const s = num(q('#dp-strike'));
      if (Number.isFinite(s)) {
        q('#dp-dipdir').value = round(dipDirectionFromStrike(s, q('#dp-convention').value), 1);
      }
    });
    q('#dp-dipdir').addEventListener('input', () => {
      const dd = num(q('#dp-dipdir'));
      if (Number.isFinite(dd)) {
        const offset = q('#dp-convention').value === 'plus90' ? -90 : 90;
        q('#dp-strike').value = round(((dd + offset) % 360 + 360) % 360, 1);
      }
    });

    // The suggestions table is rebuilt on every recompute, so its Apply buttons
    // are handled by delegation on the (stable) results container.
    this.resultsEl.addEventListener('click', (e) => {
      const btn = e.target.closest('.dp-apply');
      if (btn && !btn.disabled) this.applySuggestion(Number(btn.dataset.cand));

      if (e.target.closest('#dp-copy-pattern')) this.copyPatternCsv();
      if (e.target.closest('#dp-save-pattern')) this.savePattern();
      // The pattern image is a PNG only: it is a picture of a programme, headed
      // for a proposal, and offering four buttons for one drawing is noise.
      if (e.target.closest('#dp-img-pattern')) this.exportSection('pattern', 'png');
    });

    // Showing the grid inputs only when the grid is switched on keeps the
    // single-hole case -- still the common one -- from growing six more fields.
    const patternToggle = q('#dp-pattern-on');
    patternToggle.onchange = () => {
      q('#dp-pattern-inputs').style.display = patternToggle.checked ? 'block' : 'none';
      this.recompute();
    };

    // Every input recomputes, debounced, so the 3D tracks typing without
    // rebuilding geometry on each keystroke.
    this.container.querySelectorAll('input, select').forEach(el => {
      el.addEventListener('input', () => this.scheduleRecompute());
      el.addEventListener('change', () => this.scheduleRecompute());
    });
  }

  scheduleRecompute() {
    clearTimeout(this.debounce);
    this.debounce = setTimeout(() => this.recompute(), 160);
  }

  /** Fill the two anchor points from the selected trench and metre range. */
  loadTrench() {
    const q = (sel) => this.container.querySelector(sel);
    const id = q('#dp-trench').value;
    if (!id || !this.trenches.has(id)) return;

    const samples = this.trenches.get(id);
    const from = num(q('#dp-from'));
    const to = num(q('#dp-to'));

    const nearest = (metre) => {
      if (!Number.isFinite(metre)) return null;
      let best = null, bestGap = Infinity;
      for (const s of samples) {
        const gap = Math.abs((Number(s.from_depth) || 0) - metre);
        if (gap < bestGap) { bestGap = gap; best = s; }
      }
      return best;
    };

    const top = nearest(from) || samples[0];
    const base = nearest(to) || samples[samples.length - 1];

    if (top) {
      q('#dp-top-e').value = round(top.easting, 3);
      q('#dp-top-n').value = round(top.northing, 3);
      q('#dp-top-z').value = round(top.elevation, 3);
    }
    if (base) {
      q('#dp-base-e').value = round(base.easting, 3);
      q('#dp-base-n').value = round(base.northing, 3);
      q('#dp-base-z').value = round(base.elevation, 3);
    }
  }

  /**
   * Fill the proposed-hole fields from an existing collar in the project.
   *
   * Orientation comes from the desurveyed trace rather than from a survey
   * table the scene payload doesn't carry: the first trace point holds the
   * azimuth and dip the hole actually starts at. A planned hole therefore
   * loads back exactly as it was drafted, and a drilled hole loads as it was
   * collared -- both are then free to be edited, which is the whole point of
   * the tool.
   *
   * The loaded values are a starting point, not a lock: nothing here is made
   * read-only, and editing a field does not clear the dropdown.
   */
  loadHole() {
    const q = (sel) => this.container.querySelector(sel);
    const idx = q('#dp-collar-hole').value;
    if (idx === '') return;
    const hole = this.holes[Number(idx)];
    if (!hole) return;

    q('#dp-collar-e').value = round(hole.easting, 3);
    q('#dp-collar-n').value = round(hole.northing, 3);
    q('#dp-collar-z').value = round(hole.elevation, 3);
    q('#dp-holeid').value = hole.hole_id;

    const start = Array.isArray(hole.trace) && hole.trace.length ? hole.trace[0] : null;
    if (start && isNum(start.azimuth)) {
      q('#dp-azimuth').value = round(start.azimuth, 1);
    }
    if (start && isNum(start.dip)) {
      // The trace stores dip below horizontal as negative; this field asks for
      // the magnitude and signedDip() re-applies the sign at compute time.
      q('#dp-holedip').value = round(Math.abs(start.dip), 1);
    }
  }

  /** Selected structural readings -> the mean plane, written into the form. */
  loadReadings() {
    const q = (sel) => this.container.querySelector(sel);
    const convention = q('#dp-convention').value;
    const chosen = this.selectedReadings(convention);

    if (!chosen.length) {
      this.meanNoteEl.textContent = '';
      return;
    }

    const mean = meanPlane(chosen);
    q('#dp-dip').value = round(mean.dip, 1);
    q('#dp-dipdir').value = round(mean.dipDirection, 1);
    q('#dp-strike').value = round(mean.strike, 1);

    if (mean.count > 1) {
      const spreadNote = mean.spreadDeg > 20
        ? `<span class="dp-warn">poles ${mean.spreadDeg.toFixed(0)}° apart — these may not be the same structure</span>`
        : `poles ${mean.spreadDeg.toFixed(0)}° apart`;
      this.meanNoteEl.innerHTML =
        `Vector mean of <b>${mean.count}</b> readings: <b>${round(mean.strike, 0)} / ${round(mean.dip, 0)} / ${round(mean.dipDirection, 0)}</b> — ${spreadNote}.`;
    } else {
      this.meanNoteEl.innerHTML = `Single reading — no averaging. A projection this long from one measurement carries real risk.`;
    }
  }

  selectedReadings(convention) {
    const select = this.container.querySelector('#dp-readings');
    const out = [];
    for (const opt of select.selectedOptions) {
      const r = this.readings[Number(opt.value)];
      if (!r) continue;
      out.push({
        dip: Number(r.dip),
        dipDirection: dipDirectionFromStrike(r.strike, convention),
        label: `${Math.round(r.strike)}/${Math.round(r.dip)}`
      });
    }
    return out;
  }

  /** Read the form, run the planner, push into the scene and the results pane. */
  recompute() {
    const q = (sel) => this.container.querySelector(sel);

    const collar = {
      easting: num(q('#dp-collar-e')),
      northing: num(q('#dp-collar-n')),
      elevation: num(q('#dp-collar-z'))
    };
    const top = {
      easting: num(q('#dp-top-e')),
      northing: num(q('#dp-top-n')),
      elevation: num(q('#dp-top-z'))
    };
    const base = {
      easting: num(q('#dp-base-e')),
      northing: num(q('#dp-base-n')),
      elevation: num(q('#dp-base-z'))
    };
    const plane = { dip: num(q('#dp-dip')), dipDirection: num(q('#dp-dipdir')) };
    const hole = { azimuth: num(q('#dp-azimuth')), dip: signedDip(num(q('#dp-holedip'))) };

    const complete = [collar, top].every(p => Object.values(p).every(Number.isFinite))
      && Number.isFinite(plane.dip) && Number.isFinite(plane.dipDirection)
      && Number.isFinite(hole.azimuth) && Number.isFinite(hole.dip);

    if (!complete) {
      this.result = null;
      this.resultsEl.innerHTML = `<div class="dp-note">Fill in the zone anchor, the structure and the collar to see depths.</div>`;
      this.calibrationEl.innerHTML = '';
      if (this.renderer) this.renderer.render(null);
      return;
    }

    const hasBase = Object.values(base).every(Number.isFinite);
    const trenchId = q('#dp-trench').value;

    const result = computePlan({
      collar,
      hole,
      plane,
      top,
      base: hasBase ? base : null,
      readings: this.selectedReadings(q('#dp-convention').value),
      trenchSamples: trenchId && this.trenches.has(trenchId) ? this.trenches.get(trenchId) : [],
      observedDepth: q('#dp-observed').value === '' ? null : num(q('#dp-observed')),
      options: {
        dipDelta: orDefault(num(q('#dp-dip-delta')), 5),
        dipDirDelta: orDefault(num(q('#dp-dd-delta')), 10),
        collarZDelta: orDefault(num(q('#dp-z-delta')), 2),
        pattern: q('#dp-pattern-on').checked ? {
          spacingStrike: orDefault(num(q('#dp-sp-strike')), 20),
          spacingDip: orDefault(num(q('#dp-sp-dip')), 20),
          countStrike: orDefault(num(q('#dp-n-strike')), 3),
          countDip: orDefault(num(q('#dp-n-dip')), 2),
          // Blank pad RL means "same bench as the reference collar".
          collarElevation: orDefault(num(q('#dp-pad-rl')), collar.elevation),
          holePrefix: (q('#dp-prefix').value || 'PLAN').trim()
        } : null
      }
    });

    result.topAnchor = top;
    result.baseAnchor = hasBase ? base : null;
    result.holeId = q('#dp-holeid').value.trim();

    this.result = result;
    this.renderResults(result);
    if (this.renderer) this.renderer.render(result);
  }

  renderResults(r) {
    // A hole that misses the zone is the case where suggestions matter MOST --
    // "this misses, here is one that hits" is the entire point of the tool. So
    // the failure branches report the miss and then fall through to the
    // suggestions table rather than leaving the panel empty.
    const miss = r.top.parallel
      ? `The hole runs parallel to this plane — it never intersects.`
      : r.top.behindCollar
        ? `The plane sits behind the collar (${r.top.depth.toFixed(1)} m). This hole is
           drilled away from the zone — the zone outcrops above or behind this collar.`
        : null;

    if (miss) {
      this.resultsEl.innerHTML = `
        <div class="dp-section-title">6 &nbsp;Result</div>
        <div class="dp-note dp-err">${miss}</div>
        ${this.suggestionsHtml(r)}`;
      this.calibrationEl.innerHTML = '';
      return;
    }

    const p = r.proposal;
    const env = r.envelope;

    const depthRows = [
      ['Zone top', r.top],
      ...(r.base ? [['Zone base', r.base]] : [])
    ].map(([label, hit]) => `
      <tr>
        <td>${label}</td>
        <td class="dp-num">${hit.depth.toFixed(1)}</td>
        <td class="dp-num">${hit.verticalDepth.toFixed(1)}</td>
        <td class="dp-num">${hit.point.u.toFixed(1)}</td>
      </tr>`).join('');

    const sensRows = env.rows.map(row => `
      <tr class="${row.group === 'base' ? 'dp-base' : ''}">
        <td>${row.label}</td>
        <td class="dp-num">${fmt(row.topDepth)}</td>
        <td class="dp-num">${fmt(row.baseDepth)}</td>
      </tr>`).join('');

    const projected = r.projected.filter(s => s.grade !== null);
    const trenchRows = projected.map(s => `
      <tr>
        <td class="dp-num">${s.meter ?? '—'}</td>
        <td class="dp-num">${s.grade.toFixed(2)}</td>
        <td class="dp-num">${s.depth.toFixed(1)}</td>
      </tr>`).join('');

    const compression = projected.length > 1
      ? (projected[projected.length - 1].depth - projected[0].depth) /
        Math.max(1e-6, (projected[projected.length - 1].meter - projected[0].meter))
      : null;

    const driver = topDriver(env.driver);

    this.resultsEl.innerHTML = `
      <div class="dp-section-title">6 &nbsp;Result</div>

      <div class="dp-headline">
        <div>Target <span class="dp-big">${r.top.depth.toFixed(1)} – ${r.base ? r.base.depth.toFixed(1) : '?'} m</span></div>
        <div>Start logging <b>${p.startLogging} m</b> &nbsp;·&nbsp; EOH <b>${p.eoh} m</b></div>
        <div>Full envelope <b>${env.min.toFixed(1)} – ${env.max.toFixed(1)} m</b></div>
      </div>

      <div class="dp-note">
        Intersects the plane at <b>${r.intersectionAngleDeg.toFixed(0)}°</b>${r.intersectionAngleDeg < 30 ? ' <span class="dp-warn">— a very oblique cut; the intersection is long and its depth is poorly constrained</span>' : ''}.
        ${r.coreLength !== null ? `Expect <b>${r.coreLength.toFixed(1)} m</b> in the core for <b>${r.trueThickness.toFixed(1)} m</b> true thickness.` : ''}
        Collar elevation moves the target <b>${Math.abs(r.elevationSensitivity).toFixed(2)} m</b> per metre.
      </div>

      <table class="dp-table">
        <thead><tr><th>Point</th><th class="dp-num">Downhole</th><th class="dp-num">Vertical</th><th class="dp-num">RL</th></tr></thead>
        <tbody>${depthRows}</tbody>
      </table>

      <div class="dp-section-title" style="margin-top:12px;">Sensitivity</div>
      <div class="dp-note">Biggest control: <b>${driver}</b>.</div>
      <div class="dp-scroll">
        <table class="dp-table">
          <thead><tr><th>Assumption</th><th class="dp-num">Top</th><th class="dp-num">Base</th></tr></thead>
          <tbody>${sensRows}</tbody>
        </table>
      </div>

      ${this.suggestionsHtml(r)}

      ${this.patternHtml(r)}

      ${projected.length ? `
        <div class="dp-section-title" style="margin-top:12px;">Trench metre &rarr; downhole depth</div>
        ${compression ? `<div class="dp-note">Each trench metre &asymp; <b>${compression.toFixed(2)} m</b> of core.</div>` : ''}
        <div class="dp-scroll">
          <table class="dp-table">
            <thead><tr><th class="dp-num">Metre</th><th class="dp-num">Grade</th><th class="dp-num">Depth</th></tr></thead>
            <tbody>${trenchRows}</tbody>
          </table>
        </div>` : ''}
    `;

    this.renderCalibration(r);
  }

  /**
   * Holes worth drilling into this zone, each optimal for a stated objective.
   *
   * The current orientation is shown alongside them so the comparison is
   * explicit -- the useful output is usually "your hole is fine but 8 degrees
   * off", not a bare list of alternatives.
   */
  suggestionsHtml(r) {
    const s = r.suggestions;
    // The current hole only has a meaningful cut angle if it actually reaches
    // the zone; quoting one for a hole drilled the wrong way is nonsense.
    const hits = !r.top.parallel && !r.top.behindCollar;

    if (!s || !s.candidates.length) {
      return `
        <div class="dp-section-title" id="dp-suggestions" style="margin-top:12px;">Suggested holes</div>
        <div class="dp-note">No orientation from this collar reaches the zone at
        ${s ? s.bounds.minAngle : 30}° or better within the depth budget. The zone probably
        outcrops above this collar, or lies behind it — move the collar down-dip
        (toward the direction the zone dips), or widen the limits above.</div>`;
    }

    const current = r.intersectionAngleDeg;

    const rows = s.candidates.map((c, i) => {
      // With no usable current hole, every candidate is an improvement.
      const better = !hits || c.angle > current + 0.5;
      return `
        <tr class="${c.drillable ? '' : 'dp-undrillable'}">
          <td>
            <div class="dp-cand-label">${c.label}</div>
            <div class="dp-cand-note">${c.note}</div>
          </td>
          <td class="dp-num">${Math.round(c.azimuth)}°/${Math.round(c.dip)}°</td>
          <td class="dp-num ${better ? 'dp-better' : ''}">${c.angle.toFixed(0)}°</td>
          <td class="dp-num">${c.topDepth.toFixed(0)}</td>
          <td class="dp-num">${c.eoh ?? '—'}</td>
          <td><button class="btn-small dp-apply" data-cand="${i}"
                ${c.drillable ? '' : 'disabled title="Outside the drillable dip band"'}>Apply</button></td>
        </tr>`;
    }).join('');

    return `
      <div class="dp-section-title" id="dp-suggestions" style="margin-top:12px;">Suggested holes</div>
      <div class="dp-note">
        ${hits
          ? `Your hole cuts at <b>${current.toFixed(0)}°</b>.`
          : `<b class="dp-warn">Your hole misses the zone.</b> These reach it:`}
        ${s.searched} orientations searched within ${s.bounds.minDip}–${s.bounds.maxDip}° dip.
        <b>Apply</b> writes an orientation into the form above and redraws the 3D view.
      </div>
      <div class="dp-scroll">
        <table class="dp-table dp-cand-table">
          <thead>
            <tr>
              <th>Objective</th><th class="dp-num">Azi/Dip</th><th class="dp-num">Cut</th>
              <th class="dp-num">Top</th><th class="dp-num">EOH</th><th></th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  }

  /**
   * The whole programme: every hole in the grid, what it costs, and where the
   * layout breaks down.
   *
   * Totals are the point. A geologist choosing between 20x20 and 40x40 is
   * really choosing between two budgets, and the metre count is the number that
   * decides it -- so it sits at the top, not buried under the table.
   */
  patternHtml(r) {
    const p = r.pattern;
    if (!p) return '';

    if (!p.totalHoles) {
      return `<div class="dp-section-title" style="margin-top:12px;">Drill pattern</div>
              <div class="dp-note">Nothing to lay out — check the spacing and counts.</div>`;
    }

    const rows = p.holes.map(h => `
      <tr class="${h.ok ? '' : 'dp-undrillable'}">
        <td>${h.id}</td>
        <td class="dp-num">${h.collar.easting.toFixed(1)}</td>
        <td class="dp-num">${h.collar.northing.toFixed(1)}</td>
        <td class="dp-num">${h.depthToTop.toFixed(0)}</td>
        <td class="dp-num">${h.eoh}</td>
        <td class="dp-num">${h.ok ? '' : `<span class="dp-warn" title="${escapeAttr(h.note)}">!</span>`}</td>
      </tr>`).join('');

    const warn = p.warnings.length
      ? `<div class="dp-note dp-warn">${p.warnings.join(' ')}</div>`
      : '';

    return `
      <div class="dp-section-title" id="dp-pattern-out" style="margin-top:12px;">Drill pattern</div>

      <div class="dp-headline">
        <div><span class="dp-big">${p.drillableHoles}</span> holes &nbsp;·&nbsp;
             <span class="dp-big">${Math.round(p.totalMetres)} m</span> total</div>
        <div>${p.cols} along strike &times; ${p.rows} down dip,
             at ${p.spacingStrike} &times; ${p.spacingDip} m on the zone plane</div>
        <div>Deepest hole <b>${p.deepestHole ?? '—'} m</b> &nbsp;·&nbsp;
             collars on a pad at <b>${p.collarElevation.toFixed(1)} m</b> RL</div>
      </div>
      ${warn}
      <div class="dp-note">
        Spacing is measured <b>on the zone plane</b>, not on the ground — that is what
        controls how much of the zone your data actually informs. Collar positions are
        derived by running each hole back to the pad RL, so
        <b>reconcile them against topography before drilling.</b>
      </div>

      <div class="dp-scroll">
        <table class="dp-table">
          <thead><tr>
            <th>Hole</th><th class="dp-num">Easting</th><th class="dp-num">Northing</th>
            <th class="dp-num">Zone</th><th class="dp-num">EOH</th><th></th>
          </tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="dp-actions" style="margin:8px 0 0;">
        <button class="btn-small" id="dp-copy-pattern">Copy as CSV</button>
        <button class="btn-small" id="dp-img-pattern" ${p.drillableHoles ? '' : 'disabled'}>Section image</button>
        ${this.projectId
          ? `<button class="btn-small" id="dp-save-pattern" ${p.drillableHoles ? '' : 'disabled'}>
               Save ${p.drillableHoles} holes to project
             </button>`
          : ''}
      </div>
      <div id="dp-save-status" class="dp-note"></div>`;
  }

  /**
   * The pattern in the same shape the project's own collar importer reads, so a
   * programme can go straight back in as planned holes without retyping.
   */
  patternCsv() {
    const p = this.result && this.result.pattern;
    if (!p) return '';
    const lines = ['hole_id,easting,northing,elevation,total_depth,azimuth,dip,hole_type,hole_status'];
    for (const h of p.holes) {
      if (!h.ok) continue;
      lines.push([
        h.id,
        h.collar.easting.toFixed(3),
        h.collar.northing.toFixed(3),
        h.collar.elevation.toFixed(3),
        h.eoh,
        h.azimuth,
        // Negative = below horizontal, matching the signed convention the
        // desurvey expects (backend/src/services/dip_convention.py).
        -Math.abs(h.dip),
        'DD',
        'planned'
      ].join(','));
    }
    return lines.join('\n');
  }

  /**
   * Persist the pattern as planned holes, then reload the scene so they appear
   * as real project data under the "Planned Boreholes" layer.
   *
   * Undrillable holes are never sent -- the panel already flags them, and
   * saving a hole the same calculation just called impossible would put a
   * contradiction in the database.
   *
   * A name clash with a DRILLED hole comes back as a 409 the server refuses in
   * full. That is a decision for the geologist, not a retry, so the message is
   * left on screen rather than flashed in a toast that disappears.
   */
  async savePattern() {
    const p = this.result && this.result.pattern;
    if (!p || !this.projectId || this.saving) return;

    const holes = p.holes.filter(h => h.ok).map(h => ({
      hole_id: h.id,
      easting: h.collar.easting,
      northing: h.collar.northing,
      elevation: h.collar.elevation,
      azimuth: h.azimuth,
      dip: h.dip,
      total_depth: h.eoh
    }));
    if (!holes.length) return;

    const status = this.container.querySelector('#dp-save-status');
    const button = this.container.querySelector('#dp-save-pattern');
    this.saving = true;
    if (button) { button.disabled = true; button.textContent = 'Saving…'; }
    if (status) status.innerHTML = '';

    try {
      const result = await ApiClient.createPlannedHoles(this.projectId, holes);
      const replacedNote = result.replaced
        ? ` (${result.replaced} replaced an earlier plan of the same name)`
        : '';
      if (window.toast) {
        window.toast.success(`${result.created} planned holes saved${replacedNote}`);
      }
      if (status) {
        status.innerHTML =
          `<span style="color:var(--accent-green,#22c55e)">Saved ${result.created} planned
           holes${replacedNote}. They are now in the Planned Boreholes layer.</span>`;
      }
      // Reloading rebuilds the panel from fresh scene data, so this instance is
      // on its way out -- do it last.
      if (this.onSaved) await this.onSaved();
    } catch (err) {
      if (status) status.innerHTML = `<span class="dp-err">${escapeAttr(err.message)}</span>`;
      if (window.toast) window.toast.error(err.message, { title: 'Could not save the pattern' });
    } finally {
      this.saving = false;
      if (button && button.isConnected) {
        button.disabled = false;
        button.textContent = `Save ${p.drillableHoles} holes to project`;
      }
    }
  }

  copyPatternCsv() {
    const csv = this.patternCsv();
    if (!csv) return;
    navigator.clipboard.writeText(csv).then(
      () => {
        const n = this.result.pattern.drillableHoles;
        if (window.toast) window.toast.success(`${n} planned collars copied as CSV`);
      },
      () => { if (window.toast) window.toast.error('Could not copy to clipboard'); }
    );
  }

  /**
   * The plan as a section drawing, downloaded as an image.
   *
   * `mode` is 'single' (the proposed hole on its own) or 'pattern' (every
   * drillable hole in the grid on one section). The drawing is built from the
   * SAME result object the panel and the 3D view are showing, so an exported
   * image can never quote a depth that is not on screen.
   *
   * A plan that cannot be drawn -- a hole that misses, a zone behind the collar
   * -- throws with a sentence explaining which, and that sentence is left on
   * screen rather than flashed away: it is the same information the Result
   * section is already reporting, and the user asked for a file they did not
   * get.
   */
  async exportSection(mode, format) {
    const status = this.container.querySelector('#dp-img-status');
    const write = (html) => { if (status) status.innerHTML = html; };

    if (!this.result) {
      write(`<span class="dp-err">Nothing to draw yet — complete the plan above.</span>`);
      return;
    }

    try {
      const { svg, holeCount } = buildPlanSection(this.result, {
        mode,
        theme: this.container.querySelector('#dp-img-light').checked ? 'light' : 'dark',
        projectName: this.projectName || null
      });

      const base = mode === 'pattern'
        ? `${(this.container.querySelector('#dp-prefix').value || 'PLAN').trim()}-pattern`
        : (this.result.holeId || 'drill-plan');

      if (format === 'svg') {
        downloadBlob(svgBlob(svg), sectionFilename(base, 'svg'));
      } else {
        downloadBlob(await svgToPngBlob(svg), sectionFilename(base, 'png'));
      }

      const what = mode === 'pattern' ? `${holeCount} holes` : 'the proposed hole';
      write(`<span style="color:var(--accent-green,#22c55e)">Section image of ${what} downloaded.</span>`);
      if (window.toast) window.toast.success(`Section image exported (${format.toUpperCase()})`);
    } catch (err) {
      write(`<span class="dp-err">${escapeAttr(err.message)}</span>`);
      if (window.toast) window.toast.error(err.message, { title: 'Could not export the section' });
    }
  }

  /** Write a suggested orientation into the hole fields and recompute. */
  applySuggestion(index) {
    const s = this.result && this.result.suggestions;
    if (!s || !s.candidates[index]) return;
    const c = s.candidates[index];

    const az = this.container.querySelector('#dp-azimuth');
    const dip = this.container.querySelector('#dp-holedip');
    az.value = round(c.azimuth, 1);
    dip.value = round(c.dip, 1);

    this.recompute();
    // `toast` is a manager object, not a callable -- see components/toast.js.
    if (window.toast) {
      window.toast.success(
        `Applied ${Math.round(c.azimuth)}°/${Math.round(c.dip)}° — cuts at ${c.angle.toFixed(0)}°`
      );
    }
  }

  renderCalibration(r) {
    const cal = r.calibration;
    if (!cal) {
      this.calibrationEl.innerHTML =
        `Enter the depth at which the zone actually appeared, and the model re-solves for
         the collar elevation or the dip that would have predicted it.`;
      return;
    }

    const dipText = cal.dipBranch
      ? `dip is really <b>${cal.dipBranch.dip.toFixed(1)}°</b> (${signed(cal.dipBranch.shift)}°)`
      : 'no dip between 0° and 90° reproduces this depth';

    this.calibrationEl.innerHTML = `
      Predicted <b>${cal.predicted.toFixed(1)} m</b>, observed <b>${cal.observed.toFixed(1)} m</b>
      — off by <b>${signed(cal.residual)} m</b>.<br>
      Either the collar is really <b>${cal.elevationBranch.collarElevation.toFixed(1)} m</b>
      (${signed(cal.elevationBranch.shift)} m), or the ${dipText}.<br>
      <span class="dp-warn">These two are indistinguishable from one intersection.</span>
      Core logging or a second intersection is what separates them.
    `;
  }

  copyReport() {
    if (!this.result) return;
    const r = this.result;
    const p = r.proposal;
    const lines = [
      `DRILLHOLE DEPTH PLAN${r.holeId ? ` — ${r.holeId}` : ''}`,
      ``,
      `Collar        ${r.collar.easting} / ${r.collar.northing} / ${r.collar.elevation}`,
      `Orientation   ${r.hole.azimuth}° azimuth, ${Math.abs(r.hole.dip)}° below horizontal`,
      `Zone plane    ${round(r.plane.dip, 1)}° toward ${round(r.plane.dipDirection, 1)}°`,
      `Intersection  ${r.intersectionAngleDeg.toFixed(0)}° to the plane`,
      ``,
      `Zone top      ${r.top.depth.toFixed(1)} m downhole (${r.top.verticalDepth.toFixed(1)} m vertical, RL ${r.top.point.u.toFixed(1)})`,
      ...(r.base ? [`Zone base     ${r.base.depth.toFixed(1)} m downhole (RL ${r.base.point.u.toFixed(1)})`] : []),
      ...(r.coreLength !== null ? [`Core length   ${r.coreLength.toFixed(1)} m  (true thickness ${r.trueThickness.toFixed(1)} m)`] : []),
      ``,
      `Envelope      ${r.envelope.min.toFixed(1)} – ${r.envelope.max.toFixed(1)} m`,
      `Start logging ${p.startLogging} m`,
      `EOH           ${p.eoh} m  (${p.eohMargin} m below the deepest estimate)`,
      ``,
      `SENSITIVITY`,
      ...r.envelope.rows.map(row =>
        `  ${row.label.padEnd(22)} ${fmt(row.topDepth).padStart(7)} ${fmt(row.baseDepth).padStart(8)}`),
      ``,
      `Collar elevation moves the target ${Math.abs(r.elevationSensitivity).toFixed(2)} m per metre.`
    ];

    if (r.suggestions && r.suggestions.candidates.length) {
      lines.push('', 'SUGGESTED ORIENTATIONS', '  (objective / azi / dip / cut angle / zone top / EOH)');
      for (const c of r.suggestions.candidates) {
        lines.push(
          `  ${c.label.padEnd(52)} ${String(Math.round(c.azimuth)).padStart(3)}° ` +
          `${String(Math.round(c.dip)).padStart(2)}°  ${c.angle.toFixed(0).padStart(3)}°  ` +
          `${c.topDepth.toFixed(1).padStart(6)} m  ${String(c.eoh ?? '—').padStart(4)} m` +
          (c.drillable ? '' : '   [outside drillable dip band]')
        );
      }
    }

    if (r.projected.length) {
      lines.push('', 'TRENCH METRE -> DOWNHOLE DEPTH');
      for (const s of r.projected) {
        if (s.grade === null) continue;
        lines.push(`  m${String(s.meter ?? '?').padStart(5)}  ${s.grade.toFixed(2).padStart(6)} g/t  ->  ${s.depth.toFixed(1)} m`);
      }
    }

    const text = lines.join('\n');
    navigator.clipboard.writeText(text).then(
      () => { if (window.toast) window.toast.success('Plan copied to clipboard'); },
      () => { if (window.toast) window.toast.error('Could not copy to clipboard'); }
    );
  }

  clearPlan() {
    this.result = null;
    if (this.renderer) this.renderer.render(null);
    this.resultsEl.innerHTML = `<div class="dp-note">Plan cleared.</div>`;
    this.calibrationEl.innerHTML = '';
  }

  open() {
    this.container.classList.add('open');
    this.recompute();
  }

  /**
   * Open straight at the suggestions.
   *
   * The suggestions sit below four sections of inputs, so from the sidebar they
   * are effectively invisible -- you have to know they exist to scroll to them.
   * This is the entry point for "just tell me where to drill": it opens the
   * panel, scrolls the table into view, and flashes it once so the eye lands in
   * the right place.
   */
  openAtSuggestions() {
    this.open();

    const heading = this.container.querySelector('#dp-suggestions');
    if (!heading) return;

    // Deliberately NOT inside requestAnimationFrame. The panel was display:none
    // a moment ago and scrollIntoView needs layout, but rAF does not fire at all
    // while the tab is not compositing -- so deferring to a frame means the
    // scroll silently never happens for anyone whose window is backgrounded when
    // they click. recompute() already rebuilt the DOM synchronously, and reading
    // offsetWidth forces the layout we need right here, on demand.
    //
    // That read doubles as the animation restart: removing the class, flushing
    // layout, then re-adding it makes a second press flash again rather than
    // doing nothing because the class was already present.
    heading.classList.remove('dp-flash');
    void heading.offsetWidth;
    // Instant, not smooth. Smooth scrolling is animated by the same frame loop
    // that rAF uses, so it makes no progress at all in a backgrounded window --
    // the panel opens and simply does not move. It is also the wrong feel here:
    // the target sits ~1200px down a 500px-tall panel, and animating that far is
    // slower and more disorienting than arriving. The flash marks the landing.
    heading.scrollIntoView({ block: 'start' });
    heading.classList.add('dp-flash');
  }

  close() {
    this.container.classList.remove('open');
    if (this.renderer) this.renderer.render(null);
  }

  isOpen() {
    return this.container.classList.contains('open');
  }
}

/** 3D distance from a structural reading to the zone anchor, for ranking. */
function distanceTo(reading, anchor) {
  if (!Number.isFinite(anchor.easting) || !Number.isFinite(anchor.northing)) return Infinity;
  const de = Number(reading.easting) - anchor.easting;
  const dn = Number(reading.northing) - anchor.northing;
  const dz = Number(reading.elevation) - (Number.isFinite(anchor.elevation) ? anchor.elevation : Number(reading.elevation));
  return Math.sqrt(de * de + dn * dn + dz * dz);
}

function escapeAttr(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

function round(v, dp) {
  return Number.isFinite(Number(v)) ? Number(Number(v).toFixed(dp)) : '';
}

function fmt(v) {
  return Number.isFinite(v) ? v.toFixed(1) : '—';
}

function signed(v) {
  return `${v >= 0 ? '+' : ''}${v.toFixed(1)}`;
}

function orDefault(v, fallback) {
  return Number.isFinite(v) ? v : fallback;
}

function topDriver(driver) {
  const entries = [
    ['dip', driver.dip],
    ['dip direction', driver.dipDirection],
    ['collar elevation', driver.collarElevation],
    ['disagreement between readings', driver.readingSpread]
  ].filter(([, v]) => Number.isFinite(v));
  entries.sort((a, b) => b[1] - a[1]);
  if (!entries.length) return 'unknown';
  return `${entries[0][0]} (${entries[0][1].toFixed(1)} m of spread)`;
}
