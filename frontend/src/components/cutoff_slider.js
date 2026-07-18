export class CutoffSlider {
  constructor(container, onChangeCallback) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.onChange = onChangeCallback;
    this.value = 0.0;
    this.min = 0.0;
    this.max = 10.0;
    this.step = 0.1;

    this.init();
  }

  init() {
    this.injectStyles();
    this.render();
  }

  injectStyles() {
    if (document.getElementById('cutoff-slider-styles')) return;
    const style = document.createElement('style');
    style.id = 'cutoff-slider-styles';
    style.textContent = `
      .cutoff-container {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 12px 16px;
        color: #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(8px);
        display: flex;
        flex-direction: column;
        gap: 8px;
        width: 240px;
        pointer-events: auto;
      }
      .cutoff-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .cutoff-title {
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        color: #94a3b8;
      }
      .cutoff-value {
        font-size: 0.875rem;
        font-weight: 700;
        color: #3b82f6;
      }
      .cutoff-input-row {
        display: flex;
        align-items: center;
        gap: 10px;
      }
      .cutoff-input-row input[type="range"] {
        flex: 1;
        -webkit-appearance: none;
        appearance: none;
        background: rgba(255,255,255,0.1);
        height: 6px;
        border-radius: 3px;
        outline: none;
      }
      .cutoff-input-row input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #3b82f6;
        cursor: pointer;
        transition: transform 0.1s ease;
      }
      .cutoff-input-row input[type="range"]::-webkit-slider-thumb:hover {
        transform: scale(1.2);
      }
      .cutoff-limits {
        display: flex;
        justify-content: space-between;
        font-size: 0.65rem;
        color: #64748b;
      }
    `;
    document.head.appendChild(style);
  }

  render() {
    this.container.innerHTML = `
      <div class="cutoff-container">
        <div class="cutoff-header">
          <span class="cutoff-title">Grade Cutoff</span>
          <span class="cutoff-value" id="cutoff-display">${this.value.toFixed(2)} ppm</span>
        </div>
        <div class="cutoff-input-row">
          <input type="range" id="cutoff-range" min="${this.min}" max="${this.max}" step="${this.step}" value="${this.value}">
        </div>
        <div class="cutoff-limits">
          <span>0.00 ppm</span>
          <span>10.00 ppm</span>
        </div>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    const rangeInput = this.container.querySelector('#cutoff-range');
    const display = this.container.querySelector('#cutoff-display');

    rangeInput.addEventListener('input', (e) => {
      this.value = Number(e.target.value);
      display.textContent = `${this.value.toFixed(2)} ppm`;
      if (this.onChange) {
        this.onChange(this.value);
      }
    });
  }

  setValue(val) {
    this.value = Number(val);
    const rangeInput = this.container.querySelector('#cutoff-range');
    const display = this.container.querySelector('#cutoff-display');
    if (rangeInput) rangeInput.value = this.value;
    if (display) display.textContent = `${this.value.toFixed(2)} ppm`;
  }
}
