import * as THREE from 'three';

export class SceneToolbar {
  constructor(container, viewportInstance) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.viewport = viewportInstance; // Returned by init3DViewport
    
    this.showGrid = true;
    this.showAxes = true;
    
    this.init();
  }

  init() {
    this.injectStyles();
    this.render();
  }

  injectStyles() {
    if (document.getElementById('scene-toolbar-styles')) return;
    const style = document.createElement('style');
    style.id = 'scene-toolbar-styles';
    style.textContent = `
      .scene-toolbar {
        position: absolute;
        top: 20px;
        left: 20px;
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 6px;
        display: flex;
        gap: 6px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        backdrop-filter: blur(8px);
        z-index: 100;
        pointer-events: auto;
      }
      .toolbar-btn {
        background: transparent;
        color: #94a3b8;
        border: none;
        border-radius: 6px;
        width: 36px;
        height: 36px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: all 0.2s ease;
        position: relative;
      }
      .toolbar-btn:hover {
        background: rgba(255, 255, 255, 0.08);
        color: #f1f5f9;
      }
      .toolbar-btn.active {
        background: #3b82f6;
        color: white;
      }
      .toolbar-divider {
        width: 1px;
        background: rgba(255, 255, 255, 0.1);
        margin: 6px 2px;
      }
      /* Tooltip styles */
      .toolbar-btn::after {
        content: attr(data-tooltip);
        position: absolute;
        bottom: -32px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.95);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        white-space: nowrap;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.2s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
      }
      .toolbar-btn:hover::after {
        opacity: 1;
      }
    `;
    document.head.appendChild(style);
  }

  render() {
    this.container.innerHTML = `
      <div class="scene-toolbar">
        <button class="toolbar-btn" data-preset="plan" data-tooltip="Plan View [P]">
          <svg style="width:20px;height:20px" viewBox="0 0 24 24"><path fill="currentColor" d="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4M11,6V14H13V6H11Z"/></svg>
        </button>
        <button class="toolbar-btn" data-preset="section_ns" data-tooltip="Section N-S [N]">
          <svg style="width:20px;height:20px" viewBox="0 0 24 24"><path fill="currentColor" d="M19,15H5V9H19M20,3H4A2,2 0 0,0 2,5V19A2,2 0 0,0 4,21H20A2,2 0 0,0 22,19V5A2,2 0 0,0 20,3Z"/></svg>
        </button>
        <button class="toolbar-btn" data-preset="section_ew" data-tooltip="Section E-W [E]">
          <svg style="width:20px;height:20px" viewBox="0 0 24 24"><path fill="currentColor" d="M15,19V5H9V19M21,20V4A2,2 0 0,0 19,2H5A2,2 0 0,0 3,4V20A2,2 0 0,0 5,22H19A2,2 0 0,0 21,20Z"/></svg>
        </button>
        <button class="toolbar-btn" data-preset="isometric" data-tooltip="Isometric View [I]">
          <svg style="width:20px;height:20px" viewBox="0 0 24 24"><path fill="currentColor" d="M12,1.7L2,7l10,5.3L22,7L12,1.7M2,9v8.5l10,5.3V14.3L2,9m20,0l-10,5.3v8.5l10-5.3V9z"/></svg>
        </button>
        
        <div class="toolbar-divider"></div>
        
        <button class="toolbar-btn ${this.showGrid ? 'active' : ''}" id="toggle-grid-btn" data-tooltip="Toggle Grid">
          <svg style="width:20px;height:20px" viewBox="0 0 24 24"><path fill="currentColor" d="M10,4V8H14V4H10M16,4V8H20V4H16M16,10V14H20V10H16M16,16V20H20V16H16M10,10V14H14V10H10M10,16V20H14V16H10M4,4V8H8V4H4M4,10V14H8V10H4M4,16V20H8V16H4Z"/></svg>
        </button>
        <button class="toolbar-btn ${this.showAxes ? 'active' : ''}" id="toggle-axes-btn" data-tooltip="Toggle Axes">
          <svg style="width:20px;height:20px" viewBox="0 0 24 24"><path fill="currentColor" d="M12,2L1,21H23L12,2M12,6L19.5,19H4.5L12,6Z"/></svg>
        </button>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    const presetBtns = this.container.querySelectorAll('[data-preset]');
    presetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        const preset = btn.getAttribute('data-preset');
        this.viewport.controls.setPreset(preset);
      });
    });

    const gridBtn = this.container.querySelector('#toggle-grid-btn');
    gridBtn.addEventListener('click', () => {
      this.showGrid = !this.showGrid;
      gridBtn.classList.toggle('active', this.showGrid);
      this.viewport.scene.traverse(child => {
        if (child instanceof THREE.GridHelper) {
          child.visible = this.showGrid;
        }
      });
    });

    const axesBtn = this.container.querySelector('#toggle-axes-btn');
    axesBtn.addEventListener('click', () => {
      this.showAxes = !this.showAxes;
      axesBtn.classList.toggle('active', this.showAxes);
      this.viewport.scene.traverse(child => {
        if (child instanceof THREE.AxesHelper) {
          child.visible = this.showAxes;
        }
      });
    });
  }
}
