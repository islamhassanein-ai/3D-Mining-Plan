import * as THREE from 'three';
import { SlicingPlane } from '../scene/slicing_plane.js';
import { Section2DView } from '../scene/section_2d_view.js';

export class SectionViewPanel {
  constructor(container, viewportInstance) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.viewport = viewportInstance; // init3DViewport result
    
    // Create slicing plane instance in 3D scene
    this.slicingPlane = new SlicingPlane(this.viewport.scene);
    
    // State
    this.active = false;
    this.type = 'EW'; // 'EW', 'NS', 'AZIMUTH'
    this.offset = 0;
    this.thickness = 20;
    this.azimuth = 0;
    
    this.drillholesData = [];
    this.view2D = null;
    
    this.init();
  }

  init() {
    this.injectStyles();
    this.render();
  }

  injectStyles() {
    if (document.getElementById('section-view-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'section-view-panel-styles';
    style.textContent = `
      .section-view-container {
        background: rgba(15, 23, 42, 0.9);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        color: #e2e8f0;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(12px);
        display: flex;
        flex-direction: column;
        gap: 16px;
        height: 100%;
        overflow: hidden;
      }
      .panel-header-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .panel-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .toggle-switch {
        position: relative;
        display: inline-block;
        width: 44px;
        height: 22px;
      }
      .toggle-switch input {
        opacity: 0;
        width: 0;
        height: 0;
      }
      .slider-round {
        position: absolute;
        cursor: pointer;
        top: 0; left: 0; right: 0; bottom: 0;
        background-color: rgba(255,255,255,0.1);
        transition: .3s;
        border-radius: 34px;
        border: 1px solid rgba(255,255,255,0.15);
      }
      .slider-round:before {
        position: absolute;
        content: "";
        height: 14px;
        width: 14px;
        left: 3px;
        bottom: 3px;
        background-color: #94a3b8;
        transition: .3s;
        border-radius: 50%;
      }
      input:checked + .slider-round {
        background-color: #3b82f6;
        border-color: #60a5fa;
      }
      input:checked + .slider-round:before {
        transform: translateX(22px);
        background-color: white;
      }
      .controls-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        background: rgba(255,255,255,0.02);
        border: 1px solid rgba(255,255,255,0.05);
        border-radius: 8px;
        padding: 12px;
      }
      .control-item {
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .control-lbl {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #64748b;
      }
      .control-input-group {
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .control-input-group input[type="range"] {
        flex: 1;
        accent-color: #3b82f6;
      }
      .control-input-group span {
        font-size: 0.75rem;
        font-weight: 700;
        color: #f1f5f9;
        width: 48px;
        text-align: right;
      }
      .btn-group {
        display: flex;
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px;
        overflow: hidden;
      }
      .btn-tab {
        flex: 1;
        background: transparent;
        border: none;
        color: #94a3b8;
        padding: 6px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
      }
      .btn-tab:hover {
        background: rgba(255,255,255,0.05);
      }
      .btn-tab.active {
        background: #3b82f6;
        color: white;
      }
      .canvas-wrapper {
        flex: 1;
        background: #0b0f19;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        position: relative;
        overflow: hidden;
      }
      .canvas-wrapper canvas {
        display: block;
        width: 100%;
        height: 100%;
      }
    `;
    document.head.appendChild(style);
  }

  render() {
    this.container.innerHTML = `
      <div class="section-view-container">
        <div class="panel-header-row">
          <div class="panel-title">
            <svg style="width:20px;height:20px;color:#3b82f6" viewBox="0 0 24 24"><path fill="currentColor" d="M3,5H21V19H3V5M5,7V17H19V7H5Z"/></svg>
            2D Vertical Cross-Section
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="slice-active-toggle" ${this.active ? 'checked' : ''}>
            <span class="slider-round"></span>
          </label>
        </div>

        <div class="controls-grid" style="display: ${this.active ? 'grid' : 'none'};">
          <div class="control-item" style="grid-column: span 2">
            <span class="control-lbl">Slice Direction</span>
            <div class="btn-group">
              <button class="btn-tab ${this.type === 'EW' ? 'active' : ''}" data-type="EW">East-West (E-W)</button>
              <button class="btn-tab ${this.type === 'NS' ? 'active' : ''}" data-type="NS">North-South (N-S)</button>
              <button class="btn-tab ${this.type === 'AZIMUTH' ? 'active' : ''}" data-type="AZIMUTH">Custom Azimuth</button>
            </div>
          </div>

          <div class="control-item" style="grid-column: span 2">
            <span class="control-lbl">Plane Offset (m)</span>
            <div class="control-input-group">
              <input type="range" id="offset-range" min="-1000" max="1000" step="10" value="${this.offset}">
              <span id="offset-val">${this.offset}m</span>
            </div>
          </div>

          <div class="control-item">
            <span class="control-lbl">Envelope Thickness (m)</span>
            <div class="control-input-group">
              <input type="range" id="thick-range" min="2" max="200" step="2" value="${this.thickness}">
              <span id="thick-val">${this.thickness}m</span>
            </div>
          </div>

          <div class="control-item" id="azimuth-ctrl-item" style="opacity: ${this.type === 'AZIMUTH' ? '1' : '0.3'};">
            <span class="control-lbl">Azimuth Rotation (°)</span>
            <div class="control-input-group">
              <input type="range" id="azimuth-range" min="0" max="360" step="5" value="${this.azimuth}" ${this.type === 'AZIMUTH' ? '' : 'disabled'}>
              <span id="azimuth-val">${this.azimuth}°</span>
            </div>
          </div>
        </div>

        <div class="canvas-wrapper">
          <canvas id="section-canvas"></canvas>
        </div>
      </div>
    `;

    // Initialize 2D Canvas View
    const canvas = this.container.querySelector('#section-canvas');
    this.view2D = new Section2DView(canvas);
    
    // Fit canvas initially
    const wrapper = this.container.querySelector('.canvas-wrapper');
    this.view2D.resize(wrapper.clientWidth, wrapper.clientHeight);

    // Watch for size changes
    const resizeObserver = new ResizeObserver(() => {
      if (wrapper.clientWidth > 0 && wrapper.clientHeight > 0) {
        this.view2D.resize(wrapper.clientWidth, wrapper.clientHeight);
        this.updateSliceAndDraw();
      }
    });
    resizeObserver.observe(wrapper);

    this.bindEvents();
    this.updateSliceAndDraw();
  }

  setDrillholes(drillholes) {
    this.drillholesData = drillholes;
    
    // Compute center of drillholes to set plane center
    if (drillholes && drillholes.length > 0) {
      const bbox = new THREE.Box3();
      for (const dh of drillholes) {
        bbox.expandByPoint(new THREE.Vector3(dh.easting, dh.elevation, dh.northing));
        for (const p of dh.trace) {
          bbox.expandByPoint(new THREE.Vector3(p.x, p.z, p.y));
        }
      }
      const center = new THREE.Vector3();
      bbox.getCenter(center);
      this.slicingPlane.setCenter(center);
    }
    
    this.updateSliceAndDraw();
  }

  bindEvents() {
    // 1. Toggle Slice
    const toggle = this.container.querySelector('#slice-active-toggle');
    toggle.addEventListener('change', (e) => {
      this.active = e.target.checked;
      this.slicingPlane.setVisible(this.active);
      
      const grid = this.container.querySelector('.controls-grid');
      grid.style.display = this.active ? 'grid' : 'none';
      
      this.updateSliceAndDraw();
    });

    // 2. Tab Type Selection
    const tabs = this.container.querySelectorAll('.btn-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.type = tab.getAttribute('data-type');
        
        // Enable/Disable Azimuth range
        const azRange = this.container.querySelector('#azimuth-range');
        const azItem = this.container.querySelector('#azimuth-ctrl-item');
        if (this.type === 'AZIMUTH') {
          azRange.removeAttribute('disabled');
          azItem.style.opacity = '1';
        } else {
          azRange.setAttribute('disabled', 'true');
          azItem.style.opacity = '0.3';
        }
        
        this.updateSliceAndDraw();
      });
    });

    // 3. Offset Slider
    const offsetSlider = this.container.querySelector('#offset-range');
    const offsetVal = this.container.querySelector('#offset-val');
    offsetSlider.addEventListener('input', (e) => {
      this.offset = Number(e.target.value);
      offsetVal.textContent = `${this.offset}m`;
      this.updateSliceAndDraw();
    });

    // 4. Thickness Slider
    const thickSlider = this.container.querySelector('#thick-range');
    const thickVal = this.container.querySelector('#thick-val');
    thickSlider.addEventListener('input', (e) => {
      this.thickness = Number(e.target.value);
      thickVal.textContent = `${this.thickness}m`;
      this.updateSliceAndDraw();
    });

    // 5. Azimuth Slider
    const azSlider = this.container.querySelector('#azimuth-range');
    const azVal = this.container.querySelector('#azimuth-val');
    azSlider.addEventListener('input', (e) => {
      this.azimuth = Number(e.target.value);
      azVal.textContent = `${this.azimuth}°`;
      this.updateSliceAndDraw();
    });
  }

  updateSliceAndDraw() {
    if (!this.slicingPlane || !this.view2D) return;
    
    // Apply parameters to 3D slicing plane helper
    this.slicingPlane.setParams(this.type, this.offset, this.thickness, this.azimuth);
    
    if (!this.active || this.drillholesData.length === 0) {
      // Clear 2D view if inactive
      this.view2D.draw({ traces: [], assays: [], lithologies: [], limits: { minU:-10, maxU:10, minV:-10, maxV:10 } });
      return;
    }
    
    // Get sliced details
    const sliced = this.slicingPlane.sliceDrillholes(this.drillholesData);
    
    // Draw on 2D viewport
    this.view2D.draw(sliced);
  }

  destroy() {
    if (this.slicingPlane) this.slicingPlane.dispose();
  }
}
