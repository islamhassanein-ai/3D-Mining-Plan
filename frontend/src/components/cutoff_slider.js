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
        font-size: 0.875rem;
        font-weight: 700;
        color: #d4af37;
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
        background: #d4af37;
        cursor: pointer;
        transition: transform 0.1s ease;
      }
      .cutoff-input-row input[type="range"]::-webkit-slider-thumb:hover {
        transform: scale(1.2);
      }
      .cutoff-number-input {
        width: 60px;
        flex-shrink: 0;
        background: rgba(0,0,0,0.35);
        border: 1px solid rgba(212,175,55,0.35);
        border-radius: 5px;
        color: #d4af37;
        font-size: 0.78rem;
        font-weight: 700;
        text-align: right;
        padding: 3px 5px;
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
          <span class="cutoff-value" id="cutoff-display">${this.value.toFixed(2)} ppm</span>
        </div>
        <div class="cutoff-input-row">
          <input type="range" id="cutoff-range" min="${this.min}" max="${this.max}" step="${this.step}" value="${this.value}">
          <input type="number" id="cutoff-number" class="cutoff-number-input"
                 min="${this.min}" max="${this.max}" step="${this.step}" value="${this.value.toFixed(2)}">
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
    const rangeInput  = this.container.querySelector('#cutoff-range');
    const numberInput = this.container.querySelector('#cutoff-number');
    const display     = this.container.querySelector('#cutoff-display');

    const apply = (val) => {
      this.value = Math.max(this.min, Math.min(this.max, Number(val)));
      rangeInput.value  = this.value;
      numberInput.value = this.value.toFixed(2);
      if (display) display.textContent = `${this.value.toFixed(2)} ppm`;
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
    if (display)     display.textContent = `${this.value.toFixed(2)} ppm`;
  }
}
