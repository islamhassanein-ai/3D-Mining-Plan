import * as THREE from 'three';

// Jump-to-feature search over the loaded scene.
//
// On a site with a few dozen holes and a couple of hundred channel samples,
// finding one by orbiting is slow and error-prone -- the whole reason a
// geologist opens the viewer is usually "show me AADD004 at 38 m". This
// indexes the three things worth naming (drillholes, trenches, samples),
// matches on substring, and flies the camera to the hit.
//
// The index is built from the scene payload rather than the Three.js objects
// because trench fences are merged into one mesh per grade bucket -- there is
// no per-trench object to search, but there is per-trench data.

const MAX_RESULTS = 12;

// Framing radius per result kind, in metres. A sample is a point and wants a
// tight frame; a whole hole or trench needs enough room to read its length.
const FRAME_RADIUS = { hole: 45, trench: 40, sample: 9 };

// Radius of the pulse drawn on the hit, in metres. Smaller than the framing
// radius so the ring sits ON the feature rather than ringing the whole view.
const FOCUS_RADIUS = { hole: 6, trench: 6, sample: 2.5 };

const KIND_META = {
  hole:   { tag: 'DD', color: '#e8c76b' },
  trench: { tag: 'TR', color: '#ff9d2b' },
  sample: { tag: 'SMP', color: '#94a3b8' },
};

export class SearchBar {
  constructor(container, viewport, options = {}) {
    this.container = typeof container === 'string'
      ? document.getElementById(container) : container;
    this.viewport = viewport;
    // Called with the entry when a drillhole result is chosen, so the host can
    // open the inspector on it.
    this.onPick = options.onPick || null;

    this.entries = [];
    this.results = [];
    this.activeIndex = -1;

    this.injectStyles();
    this.render();
  }

  /**
   * Builds the index from a scene payload.
   *
   * Trench rows arrive as a flat list of channel samples; they're folded into
   * one entry per trench_id positioned at the trench's midpoint, plus one
   * entry per named sample.
   */
  setData(data) {
    const entries = [];

    for (const dh of (data.drillholes || [])) {
      entries.push({
        kind: 'hole',
        label: dh.hole_id,
        sub: dh.hole_status === 'planned' ? 'Planned' : (dh.hole_type || 'Drillhole'),
        collarId: dh.collar_id,
        // Three.js Y-up: Easting -> X, Elevation -> Y, Northing -> Z.
        position: new THREE.Vector3(dh.easting, dh.elevation, dh.northing),
      });

      for (const a of (dh.assays || [])) {
        // start_pos/end_pos are UTM triples (E, N, RL) from the desurveyed
        // trace; the sample sits at their midpoint.
        const p = midpointOf(a.start_pos, a.end_pos);
        if (!p) continue;
        const depths = `${fmt(a.from_depth)}–${fmt(a.to_depth)} m`;
        const grade = a.grade_value != null
          ? ` · ${Number(a.grade_value).toFixed(2)} g/t` : '';
        entries.push({
          kind: 'sample',
          // Plenty of projects carry no Sample_ID column at all. Falling back
          // to hole + depth keeps every interval reachable -- "AADD004 at 38 m"
          // is how a geologist refers to it anyway.
          label: a.sample_id || `${dh.hole_id} @ ${depths}`,
          sub: a.sample_id ? `${dh.hole_id} · ${depths}${grade}` : `Interval${grade}`,
          collarId: dh.collar_id,
          intervalId: a.id,
          position: p,
        });
      }
    }

    const trenchGroups = new Map();
    for (const pt of (data.trenches || [])) {
      if (!trenchGroups.has(pt.trench_id)) trenchGroups.set(pt.trench_id, []);
      trenchGroups.get(pt.trench_id).push(pt);

      const grade = pt.grade_value != null
        ? ` · ${Number(pt.grade_value).toFixed(2)} g/t` : '';
      entries.push({
        kind: 'sample',
        label: pt.sample_id || `${pt.trench_id} @ ${fmt(pt.from_depth ?? 0)} m`,
        sub: pt.sample_id ? `${pt.trench_id}${grade}` : `Channel sample${grade}`,
        position: new THREE.Vector3(pt.easting, pt.elevation, pt.northing),
      });
    }

    for (const [trenchId, points] of trenchGroups) {
      const centre = new THREE.Vector3();
      for (const p of points) centre.add(new THREE.Vector3(p.easting, p.elevation, p.northing));
      centre.divideScalar(points.length);
      entries.push({
        kind: 'trench',
        label: trenchId,
        sub: `${points.length} sample${points.length === 1 ? '' : 's'}`,
        position: centre,
      });
    }

    this.entries = entries;
    this.close();
  }

  injectStyles() {
    if (document.getElementById('search-bar-styles')) return;
    const style = document.createElement('style');
    style.id = 'search-bar-styles';
    style.textContent = `
      .search-bar { position: relative; width: 100%; }
      .search-bar input {
        width: 100%;
        box-sizing: border-box;
        background: rgba(0, 0, 0, 0.28);
        border: 1px solid var(--border-light, #223049);
        color: var(--text-main, #e8edf5);
        padding: 7px 9px 7px 28px;
        border-radius: 6px;
        font-size: 0.78rem;
        outline: none;
      }
      .search-bar input:focus { border-color: var(--gold, #d4af37); }
      .search-bar input.search-hit { animation: search-hit-flash 0.6s ease-out; }
      @keyframes search-hit-flash {
        0%   { border-color: var(--gold, #d4af37); box-shadow: 0 0 0 0 rgba(212, 175, 55, 0.55); }
        100% { border-color: var(--border-light, #223049); box-shadow: 0 0 0 7px rgba(212, 175, 55, 0); }
      }
      .search-bar input::placeholder { color: var(--text-faint, #5f7091); }
      .search-bar .search-icon {
        position: absolute; left: 8px; top: 50%; transform: translateY(-50%);
        width: 13px; height: 13px; color: var(--text-faint, #5f7091);
        pointer-events: none;
      }
      .search-results {
        position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 40;
        background: var(--bg-dark, #101828);
        border: 1px solid var(--border-light, #223049);
        border-radius: 7px;
        box-shadow: 0 10px 26px rgba(0, 0, 0, 0.45);
        max-height: 260px; overflow-y: auto; display: none;
      }
      .search-results.open { display: block; }
      .search-results .row {
        display: flex; align-items: center; gap: 8px;
        padding: 6px 9px; cursor: pointer; font-size: 0.75rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      }
      .search-results .row:last-child { border-bottom: none; }
      .search-results .row:hover,
      .search-results .row.active { background: rgba(212, 175, 55, 0.13); }
      .search-results .kind {
        flex-shrink: 0; min-width: 30px; text-align: center;
        font-size: 0.6rem; font-weight: 800; letter-spacing: 0.4px;
        padding: 1px 4px; border-radius: 3px;
        background: rgba(255, 255, 255, 0.07);
      }
      .search-results .txt { min-width: 0; flex: 1; }
      .search-results .lbl {
        color: var(--text-main, #e8edf5); font-weight: 600;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .search-results .sub {
        color: var(--text-faint, #5f7091); font-size: 0.68rem;
        overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      }
      .search-results .empty {
        padding: 10px; text-align: center;
        color: var(--text-faint, #5f7091); font-size: 0.72rem;
      }
    `;
    document.head.appendChild(style);
  }

  render() {
    this.container.innerHTML = `
      <div class="search-bar">
        <svg class="search-icon" viewBox="0 0 24 24"><path fill="currentColor" d="M9.5,3A6.5,6.5 0 0,1 16,9.5C16,11.11 15.41,12.59 14.44,13.73L14.71,14H15.5L20.5,19L19,20.5L14,15.5V14.71L13.73,14.44C12.59,15.41 11.11,16 9.5,16A6.5,6.5 0 0,1 3,9.5A6.5,6.5 0 0,1 9.5,3M9.5,5C7,5 5,7 5,9.5C5,12 7,14 9.5,14C12,14 14,12 14,9.5C14,7 12,5 9.5,5Z"/></svg>
        <input type="text" id="scene-search-input" autocomplete="off" spellcheck="false"
               placeholder="Find hole, trench or sample…">
        <div class="search-results" id="scene-search-results"></div>
      </div>
    `;

    this.input = this.container.querySelector('#scene-search-input');
    this.list = this.container.querySelector('#scene-search-results');

    this.input.addEventListener('input', () => this.search(this.input.value));
    this.input.addEventListener('focus', () => {
      if (this.input.value.trim()) this.search(this.input.value);
    });
    this.input.addEventListener('keydown', (e) => this.onKeydown(e));
    // A click inside the list would blur the input first, so the close has to
    // wait for the click handler to have run.
    this.input.addEventListener('blur', () => setTimeout(() => this.close(), 140));
  }

  search(query) {
    const q = query.trim().toLowerCase();
    if (!q) { this.close(); return; }

    const scored = [];
    for (const entry of this.entries) {
      const idx = entry.label.toLowerCase().indexOf(q);
      if (idx === -1) continue;
      // Prefix matches first, then shorter labels -- typing "AADD004" should
      // put the hole above every sample whose id contains it.
      scored.push({ entry, score: idx * 1000 + entry.label.length });
    }
    scored.sort((a, b) => a.score - b.score);

    this.results = scored.slice(0, MAX_RESULTS).map(s => s.entry);
    this.activeIndex = this.results.length ? 0 : -1;
    this.renderResults();
  }

  renderResults() {
    if (!this.results.length) {
      this.list.innerHTML = '<div class="empty">No match in this project</div>';
      this.list.classList.add('open');
      return;
    }

    this.list.innerHTML = this.results.map((entry, i) => {
      const meta = KIND_META[entry.kind];
      return `
        <div class="row ${i === this.activeIndex ? 'active' : ''}" data-index="${i}">
          <span class="kind" style="color:${meta.color}">${meta.tag}</span>
          <span class="txt">
            <div class="lbl">${escapeHtml(entry.label)}</div>
            <div class="sub">${escapeHtml(entry.sub)}</div>
          </span>
        </div>`;
    }).join('');
    this.list.classList.add('open');

    this.list.querySelectorAll('[data-index]').forEach(row => {
      row.addEventListener('mousedown', (e) => {
        e.preventDefault(); // keep focus so blur-close doesn't race the pick
        this.pick(this.results[Number(row.dataset.index)]);
      });
    });
  }

  onKeydown(e) {
    if (e.key === 'Escape') { this.close(); this.input.blur(); return; }
    if (!this.results.length) return;

    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const step = e.key === 'ArrowDown' ? 1 : -1;
      this.activeIndex = (this.activeIndex + step + this.results.length) % this.results.length;
      this.renderResults();
      const active = this.list.querySelector('.row.active');
      if (active) active.scrollIntoView({ block: 'nearest' });
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (this.activeIndex >= 0) this.pick(this.results[this.activeIndex]);
    }
  }

  pick(entry) {
    if (!entry) return;
    this.viewport.controls.frameOn(entry.position, FRAME_RADIUS[entry.kind]);
    // Moving the camera is not by itself an answer to "where is it" -- on a
    // site with thirty holes the user is left diffing the before and after.
    // Pulse the hit and leave a marker on it.
    if (this.viewport.focusHighlight) {
      this.viewport.focusHighlight.focusOn(entry.position, FOCUS_RADIUS[entry.kind]);
    }
    this.close();
    this.input.value = entry.label;
    this.flashInput();
    if (this.onPick) this.onPick(entry);
  }

  // Brief confirmation on the field itself, so pressing Enter visibly does
  // something even when the target is already on screen and the camera barely
  // moves -- otherwise the keypress looks like it was swallowed.
  flashInput() {
    if (!this.input) return;
    this.input.classList.remove('search-hit');
    // Forcing a reflow restarts the animation when picking twice in a row.
    void this.input.offsetWidth;
    this.input.classList.add('search-hit');
  }

  close() {
    this.results = [];
    this.activeIndex = -1;
    if (this.list) {
      this.list.classList.remove('open');
      this.list.innerHTML = '';
    }
  }

  focus() {
    if (this.input) { this.input.focus(); this.input.select(); }
  }
}

function midpointOf(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b)) return null;
  // UTM (E, N, RL) -> Three.js Y-up (X, Y, Z).
  return new THREE.Vector3(
    (a[0] + b[0]) / 2,
    (a[2] + b[2]) / 2,
    (a[1] + b[1]) / 2
  );
}

function fmt(v) {
  return Number(v).toFixed(1);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}
