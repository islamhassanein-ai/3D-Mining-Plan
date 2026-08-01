import {
  computePlan,
  meanPlane,
  signedDip,
  dipDirectionFromStrike,
  isNum
} from '../services/depth_planner.js';

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
  constructor(container, viewport, sceneData) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.viewport = viewport;
    this.data = sceneData || {};
    this.renderer = viewport && viewport.depthPlanRenderer;
    this.result = null;
    this.debounce = null;

    this.trenches = this.groupTrenches(this.data.trenches || []);
    this.readings = (this.data.structural_readings || []).filter(r => isNum(r.dip) && isNum(r.strike));

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

  render() {
    const trenchOptions = [...this.trenches.keys()]
      .map(id => `<option value="${id}">${id}</option>`).join('');

    const readingOptions = this.readings.map((r, i) => {
      const dd = dipDirectionFromStrike(r.strike);
      return `<option value="${i}">${Math.round(r.strike)}/${Math.round(r.dip)} → dd ${Math.round(dd)}  (${r.reading_type})</option>`;
    }).join('');

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

          <div id="dp-results"></div>

          <div class="dp-section-title">6 &nbsp;Post-drill calibration</div>
          <div class="dp-row dp-row-2">
            <div><label>Actual intersection (m)</label><input type="number" step="any" id="dp-observed" class="dp-input" placeholder="e.g. 45"></div>
            <div><label>&nbsp;</label><button class="btn-small dp-fill" id="dp-clear-observed">Clear</button></div>
          </div>
          <div id="dp-calibration" class="dp-note"></div>

          <div class="dp-actions">
            <button class="btn-small" id="dp-copy">Copy report</button>
            <button class="btn-small" id="dp-clear">Clear plan</button>
          </div>
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
    if (this.readings.length) {
      const select = this.container.querySelector('#dp-readings');
      for (const opt of select.options) opt.selected = true;
      this.loadReadings();
    }
    // Collar defaults to an existing planned hole if the project has one --
    // that is usually exactly the hole being sized.
    const holes = this.data.drillholes || [];
    const seed = holes.find(h => h.hole_status === 'planned') || holes[0];
    if (seed) {
      this.container.querySelector('#dp-collar-e').value = seed.easting;
      this.container.querySelector('#dp-collar-n').value = seed.northing;
      this.container.querySelector('#dp-collar-z').value = seed.elevation;
      this.container.querySelector('#dp-holeid').value = seed.hole_status === 'planned' ? seed.hole_id : '';
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
        collarZDelta: orDefault(num(q('#dp-z-delta')), 2)
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
    if (r.top.parallel) {
      this.resultsEl.innerHTML =
        `<div class="dp-section-title">5 &nbsp;Result</div>
         <div class="dp-note dp-err">The hole runs parallel to this plane — it never intersects.
         Change the azimuth or the dip.</div>`;
      this.calibrationEl.innerHTML = '';
      return;
    }

    if (r.top.behindCollar) {
      this.resultsEl.innerHTML =
        `<div class="dp-section-title">5 &nbsp;Result</div>
         <div class="dp-note dp-err">The plane sits behind the collar (${r.top.depth.toFixed(1)} m).
         This hole is drilled away from the zone.</div>`;
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
      <div class="dp-section-title">5 &nbsp;Result</div>

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

    if (r.projected.length) {
      lines.push('', 'TRENCH METRE -> DOWNHOLE DEPTH');
      for (const s of r.projected) {
        if (s.grade === null) continue;
        lines.push(`  m${String(s.meter ?? '?').padStart(5)}  ${s.grade.toFixed(2).padStart(6)} g/t  ->  ${s.depth.toFixed(1)} m`);
      }
    }

    const text = lines.join('\n');
    navigator.clipboard.writeText(text).then(
      () => { if (window.toast) window.toast('Plan copied to clipboard'); },
      () => { if (window.toast) window.toast('Could not copy to clipboard'); }
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

  close() {
    this.container.classList.remove('open');
    if (this.renderer) this.renderer.render(null);
  }

  isOpen() {
    return this.container.classList.contains('open');
  }
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
