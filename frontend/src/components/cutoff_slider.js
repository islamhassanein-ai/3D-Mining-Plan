import { GRADE_BUCKETS } from '../scene/grade_scale.js';

// The range track is painted with the project's own six grade colours rather
// than a generic accent, so the thumb's position reads directly as "everything
// left of here is hidden" against the same scale used in the 3D view and the
// legend. Hard colour stops (not a smooth blend) because the buckets are
// discrete -- a gradient would imply grade is continuous across them.
function buildTrackGradient() {
  const stops = [];
  const n = GRADE_BUCKETS.length;
  GRADE_BUCKETS.forEach((b, i) => {
    const from = (i / n) * 100;
    const to = ((i + 1) / n) * 100;
    stops.push(`${b.color} ${from}%`, `${b.color} ${to}%`);
  });
  return `linear-gradient(90deg, ${stops.join(', ')})`;
}

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
        color: #e2e8f0;
        display: flex;
        flex-direction: column;
        gap: 6px;
        width: 100%;
        box-sizing: border-box;
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
        font-size: 1rem;
        font-weight: 800;
        letter-spacing: 0.2px;
        color: var(--gold, #d4af37);
      }
      .cutoff-input-row {
        display: flex;
        align-items: center;
        gap: 8px;
        flex-wrap: nowrap;
        width: 100%;
        box-sizing: border-box;
        overflow: hidden;
      }
      .cutoff-input-row input[type="range"] {
        flex: 1;
        min-width: 0;
        -webkit-appearance: none;
        appearance: none;
        background: ${buildTrackGradient()};
        height: 6px;
        border-radius: 3px;
        outline: none;
        border: 1px solid rgba(0,0,0,0.45);
        box-shadow: inset 0 1px 2px rgba(0,0,0,0.5);
        cursor: pointer;
      }
      .cutoff-input-row input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 15px;
        height: 15px;
        border-radius: 50%;
        background: var(--gold, #d4af37);
        border: 2px solid #fff;
        box-shadow: 0 0 7px rgba(0,0,0,0.65);
        cursor: pointer;
        transition: transform 0.1s ease;
      }
      .cutoff-input-row input[type="range"]::-moz-range-thumb {
        width: 15px;
        height: 15px;
        border-radius: 50%;
        background: var(--gold, #d4af37);
        border: 2px solid #fff;
        box-shadow: 0 0 7px rgba(0,0,0,0.65);
        cursor: pointer;
      }
      .cutoff-input-row input[type="range"]::-moz-range-track {
        height: 6px;
        border-radius: 3px;
        background: ${buildTrackGradient()};
      }
      .cutoff-input-row input[type="range"]::-webkit-slider-thumb:hover {
        transform: scale(1.2);
      }
      .cutoff-note {
        font-size: 0.65rem;
        line-height: 1.5;
        color: var(--text-faint, #5f7091);
        margin: 0;
      }
      .cutoff-number-input {
        width: 60px;
        min-width: 0;
        flex-shrink: 0;
        box-sizing: border-box;
        padding: 2px 6px;
        text-align: center;
        font-size: 12px;
        border-radius: 4px;
        border: 1px solid #444;
        background: #222;
        color: #fff;
        outline: none;
        -moz-appearance: textfield;
      }
      .cutoff-number-input::-webkit-outer-spin-button,
      .cutoff-number-input::-webkit-inner-spin-button { -webkit-appearance: none; }
      .cutoff-number-input:focus { border-color: #d4af37; }
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
          <span class="cutoff-value" id="cutoff-display">${this.value.toFixed(2)} g/t</span>
        </div>
        <div class="cutoff-input-row">
          <input type="range" id="cutoff-range" min="${this.min}" max="${this.max}" step="${this.step}" value="${this.value}">
          <input type="number" id="cutoff-number" class="cutoff-number-input"
                 min="${this.min}" max="${this.max}" step="${this.step}" value="${this.value.toFixed(2)}">
        </div>
        <div class="cutoff-limits">
          <span>${this.min.toFixed(2)} g/t</span>
          <span>${this.max.toFixed(2)} g/t</span>
        </div>
        <p class="cutoff-note">Samples below the cutoff are hidden in the 3D view.</p>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    const rangeInput  = this.container.querySelector('#cutoff-range');
    const numberInput = this.container.querySelector('#cutoff-number');
    const display     = this.container.querySelector('#cutoff-display');

    const apply = (val) => {
      this.value = Math.max(this.min, Math.min(this.max, Number(val)));
      rangeInput.value  = this.value;
      numberInput.value = this.value.toFixed(2);
      if (display) display.textContent = `${this.value.toFixed(2)} g/t`;
      if (this.onChange) this.onChange(this.value);
    };

    rangeInput.addEventListener('input',  (e) => apply(e.target.value));

    // Commit on blur (so partial typing like "0." doesn't fire mid-entry)
    numberInput.addEventListener('change', (e) => {
      const v = parseFloat(e.target.value);
      if (!isNaN(v)) apply(v);
    });
    // Also fire on Enter key for quick workflow
    numberInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); numberInput.blur(); }
    });
  }

  setValue(val) {
    this.value = Math.max(this.min, Math.min(this.max, Number(val)));
    const rangeInput  = this.container.querySelector('#cutoff-range');
    const numberInput = this.container.querySelector('#cutoff-number');
    const display     = this.container.querySelector('#cutoff-display');
    if (rangeInput)  rangeInput.value  = this.value;
    if (numberInput) numberInput.value = this.value.toFixed(2);
    if (display)     display.textContent = `${this.value.toFixed(2)} g/t`;
  }
}
