import { GRADE_BUCKETS } from '../scene/grade_scale.js';

// The cutoff slider is piecewise-linear in grade: every bucket gets an equal
// share of the track, and the value moves linearly *within* each share.
//
// The point is that colour and number always agree. Wherever the thumb sits on
// the yellow band the readout is between 0.50 and 1.00, and it reads exactly
// 1.00 at the yellow/red boundary -- because the boundary IS the boundary.
//
// A track linear in grade would satisfy that too, but only in theory: with the
// scale running to 10 g/t, the 0-1 range where nearly every cutoff actually
// sits would be squeezed into a tenth of the width, and 0.10/0.30/0.50 would
// land within a few pixels of each other. Equal shares put the resolution
// where the decisions are made, and cost nothing in correctness.
//
// The top bucket is open-ended, so its share maps its lower bound up to MAX.
const SLIDER_STEPS = 1000;   // internal position units on the range input
const MAX_GRADE = 10.0;

// Upper bound used for a bucket when mapping, treating the open top bucket as
// ending at MAX_GRADE.
function bucketUpper(i) {
  const to = GRADE_BUCKETS[i].to;
  return to === null ? MAX_GRADE : to;
}

// position (0..1 across the track) -> grade
function positionToValue(pos) {
  const n = GRADE_BUCKETS.length;
  const clamped = Math.min(1, Math.max(0, pos));
  if (clamped >= 1) return MAX_GRADE;
  const scaled = clamped * n;
  const i = Math.min(n - 1, Math.floor(scaled));
  const frac = scaled - i;
  return GRADE_BUCKETS[i].from + frac * (bucketUpper(i) - GRADE_BUCKETS[i].from);
}

// grade -> position (0..1 across the track)
function valueToPosition(value) {
  const n = GRADE_BUCKETS.length;
  const v = Math.min(MAX_GRADE, Math.max(0, value));
  for (let i = 0; i < n; i++) {
    const from = GRADE_BUCKETS[i].from;
    const to = bucketUpper(i);
    if (v <= to || i === n - 1) {
      const span = to - from;
      const frac = span > 0 ? (v - from) / span : 0;
      return (i + Math.min(1, Math.max(0, frac))) / n;
    }
  }
  return 1;
}

// Hard colour stops, one equal band per bucket -- matching the mapping above,
// which is what makes the band under the thumb the bucket the number is in.
// Not a smooth blend: the buckets are discrete, and a gradient would imply
// grade is continuous across them.
function buildTrackGradient() {
  const n = GRADE_BUCKETS.length;
  const stops = [];
  GRADE_BUCKETS.forEach((bucket, i) => {
    stops.push(`${bucket.color} ${(i / n) * 100}%`, `${bucket.color} ${((i + 1) / n) * 100}%`);
  });
  return `linear-gradient(90deg, ${stops.join(', ')})`;
}

export class CutoffSlider {
  constructor(container, onChangeCallback) {
    this.container = typeof container === 'string' ? document.getElementById(container) : container;
    this.onChange = onChangeCallback;
    // Opens at the bottom of the first real grade bucket rather than 0, so
    // the initial view is already free of the sub-0.10 background samples
    // that otherwise dominate a trace visually while saying nothing.
    this.value = 0.1;
    this.min = 0.0;
    this.max = MAX_GRADE;

    this.init();
  }

  init() {
    this.injectStyles();
    this.render();
    // The opening value is a real filter, not just a label -- push it to the
    // scene now, or the view shows every background sample while the readout
    // claims a 0.10 cutoff.
    if (this.onChange) this.onChange(this.value);
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
        height: 7px;
        border-radius: 4px;
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
      .cutoff-input-row input[type="range"]::-webkit-slider-thumb:hover {
        transform: scale(1.2);
      }
      .cutoff-scale {
        position: relative;
        height: 13px;
        margin-top: -2px;
      }
      .cutoff-scale .tick {
        position: absolute;
        top: 0;
        transform: translateX(-50%);
        font-size: 0.6rem;
        line-height: 1;
        color: var(--text-faint, #64748b);
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
      }
      .cutoff-scale .tick::before {
        content: '';
        position: absolute;
        left: 50%;
        top: -4px;
        width: 1px;
        height: 3px;
        background: currentColor;
        opacity: 0.6;
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

  /**
   * A label at every bucket boundary. They are evenly spaced because the
   * track is -- which is the whole point: 0.10, 0.30, 0.50, 1.00 and 3.00 all
   * get equal room instead of piling up in the first few pixels.
   */
  renderTicks() {
    const n = GRADE_BUCKETS.length;
    const out = [];
    for (let i = 0; i <= n; i++) {
      const value = i === 0 ? 0 : (i === n ? MAX_GRADE : GRADE_BUCKETS[i].from);
      const pct = (i / n) * 100;
      // Nudge the outermost labels inward so they aren't clipped by the panel.
      const align = i === 0 ? 'left:0;transform:none;'
        : i === n ? 'right:0;left:auto;transform:none;'
        : `left:${pct}%;`;
      out.push(`<span class="tick" style="${align}">${formatTick(value)}</span>`);
    }
    return out.join('');
  }

  render() {
    this.container.innerHTML = `
      <div class="cutoff-container">
        <div class="cutoff-header">
          <span class="cutoff-title">Grade Cutoff</span>
          <span class="cutoff-value" id="cutoff-display">${this.value.toFixed(2)} g/t</span>
        </div>
        <div class="cutoff-input-row">
          <input type="range" id="cutoff-range" min="0" max="${SLIDER_STEPS}" step="1"
                 value="${Math.round(valueToPosition(this.value) * SLIDER_STEPS)}"
                 style="background:${buildTrackGradient()}">
          <input type="number" id="cutoff-number" class="cutoff-number-input"
                 min="${this.min}" max="${this.max}" step="0.05" value="${this.value.toFixed(2)}">
        </div>
        <div class="cutoff-scale">${this.renderTicks()}</div>
        <p class="cutoff-note">Drillhole (DD) and trench (TR) samples below the cutoff are hidden in the 3D view. Track colours mark where each grade bucket falls.</p>
      </div>
    `;

    this.bindEvents();
  }

  bindEvents() {
    const rangeInput  = this.container.querySelector('#cutoff-range');
    const numberInput = this.container.querySelector('#cutoff-number');
    const display     = this.container.querySelector('#cutoff-display');

    const apply = (val, { fromRange = false } = {}) => {
      this.value = Math.max(this.min, Math.min(this.max, Number(val)));
      // Dragging the range must not fight the thumb by writing the position
      // back mid-gesture; typing a number does need the thumb to follow.
      if (!fromRange) {
        rangeInput.value = Math.round(valueToPosition(this.value) * SLIDER_STEPS);
      }
      numberInput.value = this.value.toFixed(2);
      if (display) display.textContent = `${this.value.toFixed(2)} g/t`;
      if (this.onChange) this.onChange(this.value);
    };

    rangeInput.addEventListener('input', (e) => {
      const raw = positionToValue(Number(e.target.value) / SLIDER_STEPS);
      // Round to a sensible precision for the readout: fine near zero, coarser
      // up top, where 0.01 steps would be noise.
      const grade = raw < 1 ? Math.round(raw * 100) / 100 : Math.round(raw * 20) / 20;
      apply(grade, { fromRange: true });
    });

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
    if (rangeInput)  rangeInput.value  = Math.round(valueToPosition(this.value) * SLIDER_STEPS);
    if (numberInput) numberInput.value = this.value.toFixed(2);
    if (display)     display.textContent = `${this.value.toFixed(2)} g/t`;
  }
}

// Bucket boundaries print as given (0.10, 0.30, 3.00); whole numbers stay bare.
function formatTick(value) {
  if (value === 0) return '0';
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(2);
}
