// Layer visibility toggle list, styled after the reference viewer's
// "Layers" panel (checkbox + swatch per render group).
export class LayerTogglePanel {
  /**
   * @param options.onChange  called with (key, visible) after a user toggle,
   *        so the floating scene legend can stay in step. Not fired by
   *        setVisible(), which is how the legend pushes state back here --
   *        that would loop.
   */
  constructor(container, viewport, options = {}) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.viewport = viewport;
    this.onChange = options.onChange || null;

    this.layers = [
      { key: 'traces', label: 'Drillhole Traces', color: '#9b6b43', get: () => viewport.tracesRenderer && viewport.tracesRenderer.group },
      { key: 'assays', label: 'Assay Intervals', color: '#ec4899', get: () => viewport.assaysRenderer && viewport.assaysRenderer.mesh },
      // Planned holes are their own layer: both the dashed trace group and
      // the translucent target-interval mesh follow this one switch.
      { key: 'planned', label: 'Planned Boreholes', color: '#78b7b7', get: () => [
        viewport.tracesRenderer && viewport.tracesRenderer.plannedGroup,
        viewport.assaysRenderer && viewport.assaysRenderer.plannedMesh,
      ] },
      { key: 'lithology', label: 'Lithology', color: '#fef08a', get: () => viewport.lithologiesRenderer && viewport.lithologiesRenderer.mesh },
      { key: 'topography', label: 'Topography', color: '#3b82f6', get: () => viewport.topographyRenderer && viewport.topographyRenderer.group },
      { key: 'trenches', label: 'Trenches', color: '#ef4444', get: () => viewport.trenchesRenderer && viewport.trenchesRenderer.group },
      // Wireframes and structural readings start hidden. Both are
      // interpretation rather than measurement, and both sit *through* the
      // drilling rather than beside it -- a solid vein shell hides the assay
      // intervals that justify it, and a field of dip discs speckles the
      // surface. The geologist turns them on when reading structure, which is
      // a deliberate act, not the default question asked of the scene.
      { key: 'wireframes', label: 'Vein Wireframes', color: '#ec4899', get: () => viewport.wireframesRenderer && viewport.wireframesRenderer.group, defaultOff: true },
      // Generated grade shells are their own layer, separate from imported vein
      // solids: one is an interpretation this tool produced from the assays in
      // view, the other is geometry someone else drew, and a reviewer needs to
      // be able to show and hide them independently.
      { key: 'gradeShells', label: 'Grade Shells', color: '#38bdf8', get: () => viewport.wireframesRenderer && viewport.wireframesRenderer.gradeShellGroup, defaultOff: true },
      { key: 'structural', label: 'Structural Readings', color: '#eab308', get: () => viewport.structuralReadingsRenderer && viewport.structuralReadingsRenderer.group, defaultOff: true },
      // The Depth Planner's zone slab, proposed hole and depth call-outs. Empty
      // until the planner is opened, so the toggle is harmless before then.
      { key: 'depthPlan', label: 'Depth Plan', color: '#f97316', get: () => viewport.depthPlanRenderer && viewport.depthPlanRenderer.group },
      { key: 'labels', label: 'Borehole Labels', color: '#e8c76b', get: () => viewport.boreholeLabelsRenderer && viewport.boreholeLabelsRenderer.group, defaultOff: true },
      { key: 'trenchLabels', label: 'Trench Labels', color: '#fca5a5', get: () => viewport.trenchLabelsRenderer && viewport.trenchLabelsRenderer.group, defaultOff: true },
    ];

    // Track desired visibility per layer so it survives re-renders
    // (assay/lithology meshes get recreated whenever grade cutoff or
    // project data reloads). Borehole labels default off -- they read as
    // clutter on dense sites until the user opts in.
    this.state = {};
    this.layers.forEach(l => { this.state[l.key] = !l.defaultOff; });

    this.init();
  }

  init() {
    this.injectStyles();
    this.render();
    this.reapply();
  }

  injectStyles() {
    if (document.getElementById('layer-toggle-styles')) return;
    const style = document.createElement('style');
    style.id = 'layer-toggle-styles';
    style.textContent = `
      .layer-toggle-list { display: flex; flex-direction: column; }
      .layer-toggle-row {
        display: flex; align-items: center; justify-content: space-between;
        padding: 6px 2px; font-size: 12px; color: var(--text-main, #e8edf5);
        border-bottom: 1px solid rgba(255,255,255,0.04);
      }
      .layer-toggle-row:last-child { border-bottom: none; }
      .layer-toggle-row .lbl { display: flex; align-items: center; gap: 8px; }
      .layer-toggle-row .swatch { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
      .layer-switch { position: relative; width: 32px; height: 17px; flex-shrink: 0; }
      .layer-switch input { opacity: 0; width: 0; height: 0; }
      .layer-slider {
        position: absolute; cursor: pointer; inset: 0; background: #26344a;
        border-radius: 20px; transition: 0.2s;
      }
      .layer-slider::before {
        position: absolute; content: ""; height: 13px; width: 13px; left: 2px; top: 2px;
        background: #8a97ad; border-radius: 50%; transition: 0.2s;
      }
      .layer-switch input:checked + .layer-slider { background: #5a4a1a; }
      .layer-switch input:checked + .layer-slider::before { background: var(--gold, #d4af37); transform: translateX(15px); }
    `;
    document.head.appendChild(style);
  }

  render() {
    this.container.innerHTML = `
      <div class="layer-toggle-list">
        ${this.layers.map(l => `
          <div class="layer-toggle-row">
            <span class="lbl"><span class="swatch" style="background:${l.color}"></span>${l.label}</span>
            <label class="layer-switch">
              <input type="checkbox" data-layer="${l.key}" ${this.state[l.key] ? 'checked' : ''}>
              <span class="layer-slider"></span>
            </label>
          </div>
        `).join('')}
      </div>
    `;

    this.container.querySelectorAll('input[data-layer]').forEach(input => {
      input.addEventListener('change', (e) => {
        const key = e.target.dataset.layer;
        this.state[key] = e.target.checked;
        this.applyOne(key);
        if (this.onChange) this.onChange(key, this.state[key]);
      });
    });
  }

  // A layer's get() may return a single Object3D or an array of them (the
  // planned-borehole layer spans two renderers).
  applyOne(key) {
    const layer = this.layers.find(l => l.key === key);
    if (!layer) return;
    const result = layer.get();
    const objects = Array.isArray(result) ? result : [result];
    for (const obj of objects) {
      if (obj) obj.visible = this.state[key];
    }
  }

  // Programmatic set, used by the floating scene legend. Updates the checkbox
  // and the scene but does NOT fire onChange, so the two controls can mirror
  // each other without echoing back and forth.
  setVisible(key, visible) {
    if (!(key in this.state) || this.state[key] === visible) return;
    this.state[key] = visible;
    const input = this.container.querySelector(`input[data-layer="${key}"]`);
    if (input) input.checked = visible;
    this.applyOne(key);
  }

  // Re-applies all stored toggle states -- call after reloading project
  // data, since assay/lithology InstancedMeshes are recreated on render().
  reapply() {
    this.layers.forEach(l => this.applyOne(l.key));
  }
}
