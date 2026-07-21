// Layer visibility toggle list, styled after the reference viewer's
// "Layers" panel (checkbox + swatch per render group).
export class LayerTogglePanel {
  constructor(container, viewport) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.viewport = viewport;

    this.layers = [
      { key: 'traces', label: 'Drillhole Traces', color: '#9ca3af', get: () => viewport.tracesRenderer && viewport.tracesRenderer.group },
      { key: 'assays', label: 'Assay Intervals', color: '#ff00ff', get: () => viewport.assaysRenderer && viewport.assaysRenderer.mesh },
      { key: 'lithology', label: 'Lithology', color: '#fef08a', get: () => viewport.lithologiesRenderer && viewport.lithologiesRenderer.mesh },
      { key: 'topography', label: 'Topography', color: '#3b82f6', get: () => viewport.topographyRenderer && viewport.topographyRenderer.group },
      { key: 'trenches', label: 'Trenches', color: '#f72809', get: () => viewport.trenchesRenderer && viewport.trenchesRenderer.group },
      { key: 'wireframes', label: 'Vein Wireframes', color: '#ec4899', get: () => viewport.wireframesRenderer && viewport.wireframesRenderer.group },
      { key: 'structural', label: 'Structural Readings', color: '#eab308', get: () => viewport.structuralReadingsRenderer && viewport.structuralReadingsRenderer.group },
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
      });
    });
  }

  applyOne(key) {
    const layer = this.layers.find(l => l.key === key);
    if (!layer) return;
    const obj = layer.get();
    if (obj) obj.visible = this.state[key];
  }

  // Re-applies all stored toggle states -- call after reloading project
  // data, since assay/lithology InstancedMeshes are recreated on render().
  reapply() {
    this.layers.forEach(l => this.applyOne(l.key));
  }
}
