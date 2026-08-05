// Floating legend over the 3D canvas, modelled on the reference viewer's
// "Legend (click to toggle)" card.
//
// It deliberately carries only the four things a geologist reads the scene by
// -- trenches, drilled holes, planned holes, and the ground surface -- rather
// than mirroring the full Layers panel in the sidebar. The sidebar is where
// you go to manage every layer; this is where you go to answer "what am I
// looking at, and can I get that out of the way".
//
// Clicking a row HIDES the layer outright (not dimmed), and re-frames the
// camera on whatever is left visible, so turning off the topography zooms in
// on the drilling instead of leaving the camera parked around empty ground.

const LEGEND_LAYERS = [
  {
    key: 'trenches',
    label: 'Trenches',
    color: '#ff9d2b',
    objects: (v) => [v.trenchesRenderer && v.trenchesRenderer.group],
  },
  {
    key: 'drillholes',
    // "DD" is the industry shorthand the collar CSV already uses in its
    // hole_type column, so the legend speaks the same language as the data.
    label: 'DD (Drillholes)',
    color: '#c49a6c',
    objects: (v) => [
      v.tracesRenderer && v.tracesRenderer.group,
      v.assaysRenderer && v.assaysRenderer.group,
      v.lithologiesRenderer && v.lithologiesRenderer.mesh,
    ],
  },
  {
    key: 'planned',
    // Round teal collar over a dashed teal trace -- see drillhole_traces.js
    // for why shape, not just colour, carries the drilled/planned split.
    label: 'Planned Holes',
    color: '#78b7b7',
    dashed: true,
    round: true,
    objects: (v) => [
      v.tracesRenderer && v.tracesRenderer.plannedGroup,
      v.assaysRenderer && v.assaysRenderer.plannedGroup,
    ],
  },
  {
    key: 'topography',
    label: 'Earth Surface',
    color: '#a98352',
    objects: (v) => [v.topographyRenderer && v.topographyRenderer.group],
  },
];

export class SceneLegend {
  /**
   * @param container  element (or id) positioned over the 3D canvas
   * @param viewport   the object returned by init3DViewport
   * @param options.onToggle  called with (key, visible) after each change --
   *        used to keep the sidebar Layers panel in step.
   */
  constructor(container, viewport, options = {}) {
    this.container = typeof container === 'string'
      ? document.getElementById(container) : container;
    this.viewport = viewport;
    this.onToggle = options.onToggle || null;

    this.state = {};
    LEGEND_LAYERS.forEach(l => { this.state[l.key] = true; });

    // Set by setSurfaceDerived() when the ground surface was interpolated
    // from collars/trenches rather than uploaded -- the label has to say so.
    this.surfaceDerived = false;

    this.injectStyles();
    this.render();
  }

  injectStyles() {
    if (document.getElementById('scene-legend-styles')) return;
    const style = document.createElement('style');
    style.id = 'scene-legend-styles';
    style.textContent = `
      .scene-legend {
        position: absolute; left: 16px; bottom: 16px; z-index: 8;
        background: rgba(18, 26, 43, 0.86);
        border: 1px solid var(--border-light, #223049);
        border-radius: 9px; padding: 9px 10px 8px;
        backdrop-filter: blur(6px);
        box-shadow: 0 8px 22px rgba(0,0,0,0.45);
        font-size: 11.5px; user-select: none; pointer-events: auto;
        min-width: 156px;
      }
      .scene-legend .sl-title {
        font-size: 9.5px; font-weight: 700; letter-spacing: 0.8px;
        text-transform: uppercase; color: var(--gold, #d4af37);
        margin-bottom: 7px;
      }
      .scene-legend .sl-title span {
        color: var(--text-faint, #5f7091); font-weight: 500;
        letter-spacing: 0.3px; text-transform: none;
      }
      .scene-legend .sl-row {
        display: flex; align-items: center; gap: 8px;
        padding: 4px 3px; border-radius: 5px; cursor: pointer;
        color: var(--text-main, #e8edf5); transition: background 0.12s ease;
      }
      .scene-legend .sl-row:hover { background: rgba(255,255,255,0.06); }
      .scene-legend .sl-key {
        width: 18px; height: 4px; border-radius: 2px; flex-shrink: 0;
      }
      .scene-legend .sl-row.sl-off .sl-key { background: transparent !important; }
      /* An off row keeps its label readable but visibly struck through, so
         "hidden" never gets mistaken for "absent from this project". */
      .scene-legend .sl-row.sl-off .sl-label {
        color: var(--text-faint, #5f7091); text-decoration: line-through;
      }
      .scene-legend .sl-label { flex: 1; }
      .scene-legend .sl-eye {
        width: 13px; height: 13px; flex-shrink: 0;
        color: var(--text-faint, #5f7091);
      }
      .scene-legend .sl-row:not(.sl-off) .sl-eye { color: var(--gold, #d4af37); }
    `;
    document.head.appendChild(style);
  }

  render() {
    const rows = LEGEND_LAYERS.map(l => {
      const on = this.state[l.key];
      const label = l.key === 'topography' && this.surfaceDerived
        ? 'Surface (derived)' : l.label;
      // A dashed key for planned holes so the legend swatch matches the
      // line style actually drawn in the scene.
      // Round for planned, square for everything else, mirroring the collar
      // marker shapes -- so the swatch is readable without relying on colour.
      const key = (l.dashed
        ? `background: repeating-linear-gradient(90deg, ${l.color} 0 4px, transparent 4px 7px);`
        : `background: ${l.color};`)
        + (l.round ? ' border-radius: 50%;' : '');
      return `
        <div class="sl-row ${on ? '' : 'sl-off'}" data-legend="${l.key}"
             role="switch" aria-checked="${on}" tabindex="0">
          <span class="sl-key" style="${key}"></span>
          <span class="sl-label">${label}</span>
          ${this.eyeIcon(on)}
        </div>`;
    }).join('');

    this.container.innerHTML = `
      <div class="scene-legend">
        <div class="sl-title">Legend <span>(click to toggle)</span></div>
        ${rows}
      </div>
    `;

    this.container.querySelectorAll('[data-legend]').forEach(row => {
      const fire = () => this.toggle(row.dataset.legend);
      row.addEventListener('click', fire);
      row.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fire(); }
      });
    });
  }

  eyeIcon(on) {
    const path = on
      ? 'M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z'
      : 'M11.83,9L15,12.16C15,12.11 15,12.05 15,12A3,3 0 0,0 12,9C11.94,9 11.89,9 11.83,9M7.53,9.8L9.08,11.35C9.03,11.56 9,11.77 9,12A3,3 0 0,0 12,15C12.22,15 12.44,14.97 12.65,14.92L14.2,16.47C13.53,16.8 12.79,17 12,17A5,5 0 0,1 7,12C7,11.21 7.2,10.47 7.53,9.8M2,4.27L4.28,6.55L4.73,7C3.08,8.3 1.78,10 1,12C2.73,16.39 7,19.5 12,19.5C13.55,19.5 15.03,19.2 16.38,18.66L16.81,19.08L19.73,22L21,20.73L3.27,3M12,7A5,5 0 0,1 17,12C17,12.64 16.87,13.26 16.64,13.82L19.57,16.75C21.07,15.5 22.27,13.86 23,12C21.27,7.61 17,4.5 12,4.5C10.6,4.5 9.26,4.75 8,5.2L10.17,7.35C10.74,7.13 11.35,7 12,7Z';
    return `<svg class="sl-eye" viewBox="0 0 24 24"><path fill="currentColor" d="${path}"/></svg>`;
  }

  refreshRow(key) {
    const row = this.container.querySelector(`[data-legend="${key}"]`);
    if (!row) return;
    const on = this.state[key];
    row.classList.toggle('sl-off', !on);
    row.setAttribute('aria-checked', String(on));
    const eye = row.querySelector('.sl-eye');
    if (eye) eye.outerHTML = this.eyeIcon(on);
  }

  toggle(key) {
    this.setVisible(key, !this.state[key]);
  }

  setVisible(key, visible, { silent = false } = {}) {
    const layer = LEGEND_LAYERS.find(l => l.key === key);
    if (!layer || this.state[key] === visible) return;
    this.state[key] = visible;
    this.apply(key);
    // Patch the row in place rather than re-rendering the list: a full
    // innerHTML rebuild would replace the element the user just clicked,
    // dropping keyboard focus mid-interaction.
    this.refreshRow(key);
    // Framing follows what's on screen, so hiding the widest layer tightens
    // the view onto the rest instead of leaving it zoomed out around nothing.
    if (this.viewport.sceneLoader) this.viewport.sceneLoader.fitCameraToData();
    if (!silent && this.onToggle) this.onToggle(key, visible);
  }

  apply(key) {
    const layer = LEGEND_LAYERS.find(l => l.key === key);
    if (!layer) return;
    for (const obj of layer.objects(this.viewport)) {
      if (obj) obj.visible = this.state[key];
    }
  }

  // Re-applies every stored state. Call after a scene reload, since the
  // assay/lithology meshes are recreated on each render().
  reapply() {
    LEGEND_LAYERS.forEach(l => this.apply(l.key));
  }

  setSurfaceDerived(derived) {
    this.surfaceDerived = !!derived;
    this.render();
  }
}

export { LEGEND_LAYERS };
