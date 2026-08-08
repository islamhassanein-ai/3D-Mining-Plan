// Grade-domain shell panel: threshold evidence, generation, validation.
//
// The panel presents evidence and generates geometry. It does not approve
// anything: the screening flag is shown as advisory, the guideline bands are
// colour only and never block generation, and nothing here describes the output
// as a resource or a reserve. The competent person signs off, not the tool.
//
// All plot geometry and request building lives in services/grade_shell_plots.js
// so it can be tested without a DOM. This file is DOM and event wiring.
import { ApiClient } from '../services/api_client.js';
import {
  DEFAULT_FORM,
  buildCaptureCurve,
  buildContactPlot,
  buildLogProbPlot,
  buildShellRequest,
  classifyDilution,
  classifyMetalCapture,
  thresholdAtX,
  validateForm,
} from '../services/grade_shell_plots.js';

const BAND_COLOURS = {
  good: '#22c55e',
  caution: '#eab308',
  poor: '#ef4444',
  unknown: 'var(--text-light, #ddd)',
};

function fmt(value, digits = 3) {
  if (value === null || value === undefined || Number.isNaN(value)) return 'n/a';
  return Number(value).toFixed(digits);
}

function pct(value) {
  if (value === null || value === undefined) return 'n/a';
  return `${(value * 100).toFixed(1)}%`;
}

function esc(text) {
  return String(text === null || text === undefined ? '' : text)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

export class GradeShellPanel {
  constructor(container, projectId, options = {}) {
    this.container = typeof container === 'string'
      ? document.getElementById(container) : container;
    this.projectId = projectId;
    this.onSceneChanged = options.onSceneChanged || null;
    this.toast = options.toast || null;
    this.form = { ...DEFAULT_FORM, weights: {} };
    this.analysis = null;
    this.sampleTypes = [];
    this.render();
    this.loadAnalysis();
  }

  notify(message, kind = 'info') {
    if (this.toast && typeof this.toast === 'function') {
      this.toast(message, kind);
      return;
    }
    if (window.showToast) window.showToast(message, kind);
  }

  render() {
    this.container.innerHTML = `
      <div class="gs-panel">
        <p class="gs-preamble">
          A grade-domain envelope built from the assays in this project.
          It is a modelling and visualisation product, not an estimate of
          contained metal.
        </p>

        <section>
          <h4>Sample populations</h4>
          <div id="gs-populations">Loading analysis…</div>
          <div id="gs-screening" class="gs-advisory"></div>
        </section>

        <section>
          <h4>Log-probability</h4>
          <div id="gs-logprob"></div>
        </section>

        <section>
          <h4>Metal capture</h4>
          <div id="gs-capture"></div>
          <p class="gs-hint">Click a point to use that cut-off.</p>
        </section>

        <section>
          <h4>Contact analysis</h4>
          <button type="button" class="btn-small" id="gs-contact-btn">
            Run at current cut-off
          </button>
          <div id="gs-contact"></div>
        </section>

        <hr class="gs-rule">

        <section>
          <h4>Generate a shell</h4>
          <form id="gs-form" class="gs-form"></form>
          <div id="gs-form-problems" class="gs-problems"></div>
          <button type="button" class="btn-small gs-generate" id="gs-generate">
            Generate shell
          </button>
        </section>

        <section id="gs-validation-section" hidden>
          <h4>Validation</h4>
          <div id="gs-validation"></div>
        </section>
      </div>
    `;

    this.populationsEl = this.container.querySelector('#gs-populations');
    this.screeningEl = this.container.querySelector('#gs-screening');
    this.logProbEl = this.container.querySelector('#gs-logprob');
    this.captureEl = this.container.querySelector('#gs-capture');
    this.contactEl = this.container.querySelector('#gs-contact');
    this.formEl = this.container.querySelector('#gs-form');
    this.problemsEl = this.container.querySelector('#gs-form-problems');
    this.generateBtn = this.container.querySelector('#gs-generate');
    this.validationSection = this.container.querySelector('#gs-validation-section');
    this.validationEl = this.container.querySelector('#gs-validation');

    this.renderForm();
    this.generateBtn.addEventListener('click', () => this.generate());
    this.container.querySelector('#gs-contact-btn')
      .addEventListener('click', () => this.loadContact());
  }

  async loadAnalysis() {
    try {
      this.analysis = await ApiClient.getGradeAnalysis(this.projectId);
    } catch (err) {
      this.populationsEl.textContent = err.message;
      this.notify(err.message, 'error');
      return;
    }

    this.sampleTypes = Object.keys(this.analysis.populations || {}).sort();
    for (const type of this.sampleTypes) {
      if (this.form.weights[type] === undefined) this.form.weights[type] = '';
    }

    this.renderPopulations();
    this.renderScreening();
    this.renderLogProb();
    this.renderCapture();
    this.renderForm();
  }

  renderPopulations() {
    const populations = this.analysis.populations || {};
    const rows = Object.keys(populations).sort().map((type) => {
      const s = populations[type].statistics;
      return `
        <tr>
          <td>${esc(type)}</td>
          <td>${s.n}</td>
          <td>${fmt(s.mean)}</td>
          <td>${fmt(s.length_weighted_mean)}</td>
          <td>${fmt(s.cv)}</td>
          <td>${fmt(s.median)}</td>
          <td>${fmt(s.maximum, 2)}</td>
        </tr>`;
    }).join('');

    this.populationsEl.innerHTML = `
      <table class="gs-table">
        <thead>
          <tr><th>Type</th><th>n</th><th>mean</th><th>lw mean</th>
              <th>CV</th><th>median</th><th>max</th></tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  renderScreening() {
    const c = this.analysis.comparison || {};
    const ratio = c.grade_ratio === null || c.grade_ratio === undefined
      ? 'n/a' : fmt(c.grade_ratio, 2);
    // Deliberately not phrased as approval. `comparable: true` means nothing
    // obvious showed up in three coarse checks, not that pooling is authorised.
    const headline = c.comparable
      ? `Screening check: nothing obvious separates the populations (ratio ${ratio}).`
      : `Screening check: populations differ (ratio ${ratio}). Review before using surface samples for grade.`;
    const reasons = (c.reasons || []).map(r => `<li>${esc(r)}</li>`).join('');
    this.screeningEl.innerHTML = `
      <p>${esc(headline)}</p>
      ${reasons ? `<ul>${reasons}</ul>` : ''}
      <p class="gs-note">${esc(c.note || '')}</p>`;
  }

  renderLogProb() {
    const plot = buildLogProbPlot(this.analysis.log_probability, { width: 320, height: 190 });
    if (plot.points.length === 0) {
      this.logProbEl.textContent = 'Not enough positive grades to plot.';
      return;
    }
    const path = plot.points
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(' ');

    this.logProbEl.innerHTML = `
      <svg viewBox="0 0 ${plot.width} ${plot.height}" class="gs-svg" role="img"
           aria-label="Log-probability plot">
        <path d="${path}" fill="none" stroke="#38bdf8" stroke-width="1.6"/>
      </svg>
      <p class="gs-hint">
        Grade on a log axis against probability. A straight line is one
        population; a kink marks a boundary.
        ${plot.excluded ? `${plot.excluded} non-positive grade(s) excluded.` : ''}
      </p>`;
  }

  renderCapture() {
    const rows = this.analysis.metal_capture_all || [];
    const curve = buildCaptureCurve(rows, {
      width: 320, height: 190, threshold: Number(this.form.threshold) || 0,
    });
    if (curve.metal.length === 0) {
      this.captureEl.textContent = 'No capture curve available.';
      return;
    }

    const line = (points, colour) => `<path d="${points
      .map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(' ')}" fill="none" stroke="${colour}" stroke-width="1.6"/>`;

    const dots = curve.metal.map(p =>
      `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3"
               fill="#38bdf8" data-threshold="${p.threshold}"><title>${p.threshold} g/t — ${pct(p.fraction)} of metal</title></circle>`
    ).join('');

    const marker = curve.marker
      ? `<line x1="${curve.marker.x.toFixed(1)}" y1="8" x2="${curve.marker.x.toFixed(1)}"
               y2="${curve.height - 20}" stroke="#e8c76b" stroke-dasharray="4 3"/>`
      : '';

    this.captureEl.innerHTML = `
      <svg viewBox="0 0 ${curve.width} ${curve.height}" class="gs-svg gs-clickable"
           role="img" aria-label="Metal capture curve">
        ${line(curve.length, '#94a3b8')}
        ${line(curve.metal, '#38bdf8')}
        ${marker}${dots}
      </svg>
      <p class="gs-hint">
        <span style="color:#38bdf8">■</span> metal retained
        <span style="color:#94a3b8">■</span> ground retained
      </p>`;

    const svg = this.captureEl.querySelector('svg');
    svg.addEventListener('click', (event) => {
      const box = svg.getBoundingClientRect();
      const x = ((event.clientX - box.left) / box.width) * curve.width;
      const picked = thresholdAtX(curve, x);
      if (picked !== null) {
        this.form.threshold = picked;
        this.renderForm();
        this.renderCapture();
      }
    });
  }

  async loadContact() {
    const threshold = Number(this.form.threshold);
    if (!(threshold > 0)) {
      this.notify('Set a cut-off first.', 'error');
      return;
    }
    this.contactEl.textContent = 'Loading…';
    try {
      const data = await ApiClient.getContactAnalysis(this.projectId, threshold);
      const plot = buildContactPlot(data.bins, { width: 320, height: 150 });
      if (plot.bars.length === 0) {
        this.contactEl.textContent = 'No composites within range of the boundary.';
        return;
      }
      const bars = plot.bars.map(b => `
        <rect x="${b.x.toFixed(1)}" y="${b.y.toFixed(1)}"
              width="${b.width.toFixed(1)}" height="${b.height.toFixed(1)}"
              fill="${b.inside ? '#38bdf8' : '#94a3b8'}">
          <title>${b.distance} m — mean ${fmt(b.meanGrade)} (n=${b.n})</title>
        </rect>`).join('');
      this.contactEl.innerHTML = `
        <svg viewBox="0 0 ${plot.width} ${plot.height}" class="gs-svg" role="img"
             aria-label="Contact analysis">
          ${bars}
          <line x1="${plot.zeroX.toFixed(1)}" y1="6" x2="${plot.zeroX.toFixed(1)}"
                y2="${plot.height - 20}" stroke="#e8c76b"/>
        </svg>
        <p class="gs-note">${esc(data.note || '')}</p>`;
    } catch (err) {
      this.contactEl.textContent = err.message;
      this.notify(err.message, 'error');
    }
  }

  renderForm() {
    const field = (key, label, attrs = 'type="number" step="any"') => `
      <label class="gs-field">
        <span>${esc(label)}</span>
        <input ${attrs} data-form="${key}" value="${esc(this.form[key])}">
      </label>`;

    const weightFields = this.sampleTypes.map(type => `
      <label class="gs-field">
        <span>${esc(type)} weight</span>
        <input type="number" step="0.05" min="0" data-weight="${esc(type)}"
               value="${esc(this.form.weights[type])}" placeholder="required">
      </label>`).join('');

    this.formEl.innerHTML = `
      ${field('name', 'Name', 'type="text"')}
      ${field('threshold', 'Cut-off (g/t)')}
      <fieldset class="gs-group">
        <legend>Search ellipsoid — no defaults</legend>
        ${field('range_major', 'Range along strike (m)')}
        ${field('range_semi', 'Range down dip (m)')}
        ${field('range_minor', 'Range across structure (m)')}
        ${field('strike_azimuth', 'Strike azimuth (° from N)')}
        ${field('dip', 'Dip (° from horizontal, down negative)')}
      </fieldset>
      <fieldset class="gs-group">
        <legend>Sample weights — 0.0 excludes a type from grade</legend>
        ${weightFields || '<p class="gs-hint">Loading sample types…</p>'}
      </fieldset>
      <fieldset class="gs-group">
        <legend>Grid and search</legend>
        ${field('composite_length', 'Composite length (m)')}
        ${field('cell_size', 'Cell size (m)')}
        ${field('padding', 'Padding (m)')}
        ${field('power', 'IDW power')}
        ${field('min_samples', 'Min samples')}
        ${field('max_samples', 'Max samples')}
        ${field('min_volume', 'Min component volume (m³)')}
      </fieldset>`;

    this.formEl.querySelectorAll('[data-form]').forEach((input) => {
      input.addEventListener('input', (e) => {
        this.form[e.target.dataset.form] = e.target.value;
      });
    });
    this.formEl.querySelectorAll('[data-weight]').forEach((input) => {
      input.addEventListener('input', (e) => {
        this.form.weights[e.target.dataset.weight] = e.target.value;
      });
    });
  }

  async generate() {
    const problems = validateForm(this.form, this.sampleTypes);
    if (problems.length) {
      this.problemsEl.innerHTML = problems.map(p => `<li>${esc(p)}</li>`).join('');
      return;
    }
    this.problemsEl.innerHTML = '';

    this.generateBtn.disabled = true;
    this.generateBtn.textContent = 'Generating…';
    try {
      const response = await ApiClient.createGradeShell(
        this.projectId, buildShellRequest(this.form));

      if (!response.wireframe) {
        // A legitimate geological answer, not an error.
        this.notify(response.message, 'info');
        this.validationSection.hidden = false;
        this.validationEl.innerHTML = `<p>${esc(response.message)}</p>`;
        return;
      }

      this.renderValidation(response.validation);
      this.notify(`Shell "${response.wireframe.name}" generated.`, 'success');
      if (this.onSceneChanged) await this.onSceneChanged();
    } catch (err) {
      // The server's message is shown verbatim: the node-budget refusal names
      // the cell size to increase, and paraphrasing loses that.
      this.notify(err.message, 'error');
      this.problemsEl.innerHTML = `<li>${esc(err.message)}</li>`;
    } finally {
      this.generateBtn.disabled = false;
      this.generateBtn.textContent = 'Generate shell';
    }
  }

  renderValidation(validation) {
    this.validationSection.hidden = false;
    const geometry = validation.geometry;
    const stats = validation.statistics;

    const captureBand = classifyMetalCapture(stats.metal_capture);
    const dilutionBand = classifyDilution(stats.internal_dilution);

    const typeRows = (stats.by_sample_type || []).map(s => `
      <tr>
        <td>${esc(s.sample_type)}</td>
        <td>${s.n_inside}</td>
        <td>${s.n_outside}</td>
        <td>${fmt(s.length_inside, 1)}</td>
        <td>${fmt(s.mean_grade_inside)}</td>
      </tr>`).join('');

    this.validationEl.innerHTML = `
      <ul class="gs-metrics">
        <li>Watertight: <strong style="color:${geometry.is_watertight ? BAND_COLOURS.good : BAND_COLOURS.poor}">
          ${geometry.is_watertight ? 'yes' : 'no'}</strong></li>
        <li>Volume: <strong>${Number(geometry.total_volume_m3).toLocaleString()} m³</strong></li>
        <li>Components: <strong>${geometry.n_components}</strong></li>
        <li>Metal capture: <strong style="color:${BAND_COLOURS[captureBand]}">
          ${pct(stats.metal_capture)}</strong> <span class="gs-hint">(guideline ≥ 90%)</span></li>
        <li>Internal dilution: <strong style="color:${BAND_COLOURS[dilutionBand]}">
          ${pct(stats.internal_dilution)}</strong> <span class="gs-hint">(guideline ≤ 25%)</span></li>
        <li>Mean grade inside: <strong>${fmt(stats.mean_grade_inside)}</strong></li>
      </ul>
      <table class="gs-table">
        <thead><tr><th>Type</th><th>inside</th><th>outside</th>
                   <th>length in</th><th>mean in</th></tr></thead>
        <tbody>${typeRows}</tbody>
      </table>
      ${(validation.notes || []).length
        ? `<ul class="gs-notes">${validation.notes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>`
        : ''}
      <p class="gs-note">
        Guideline colours are advisory. They do not block generation, and the
        numbers stand as reported.
      </p>`;
  }
}
