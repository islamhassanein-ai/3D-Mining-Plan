// Plot geometry and request building for the grade-shell panel.
//
// Everything here is pure: it takes API responses and form values and returns
// numbers. The panel does the DOM. That split is what makes this testable --
// `node --test` has no DOM, so logic living in a render method cannot be
// checked, and the arithmetic in a log-probability axis is exactly the kind of
// thing that is wrong by a little in a way nobody notices.
//
// Three plots, drawn as inline SVG. No charting library: these are small, and
// the project ships no chart dependency.

// Acklam's rational approximation to the inverse normal CDF. A probability
// axis is what makes a log-normal population plot as a straight line, so the
// inflection that marks a population boundary is visible as a kink rather than
// hidden in the curve of a linear axis.
const A = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
  1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00];
const B = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
  6.680131188771972e+01, -1.328068155288572e+01];
const C = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
  -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00];
const D = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
  3.754408661907416e+00];

const P_LOW = 0.02425;
const P_HIGH = 1 - P_LOW;

export function probit(p) {
  if (!(p > 0) || !(p < 1)) return NaN;
  let q;
  let r;
  if (p < P_LOW) {
    q = Math.sqrt(-2 * Math.log(p));
    return (((((C[0] * q + C[1]) * q + C[2]) * q + C[3]) * q + C[4]) * q + C[5]) /
      ((((D[0] * q + D[1]) * q + D[2]) * q + D[3]) * q + 1);
  }
  if (p > P_HIGH) {
    q = Math.sqrt(-2 * Math.log(1 - p));
    return -(((((C[0] * q + C[1]) * q + C[2]) * q + C[3]) * q + C[4]) * q + C[5]) /
      ((((D[0] * q + D[1]) * q + D[2]) * q + D[3]) * q + 1);
  }
  q = p - 0.5;
  r = q * q;
  return (((((A[0] * r + A[1]) * r + A[2]) * r + A[3]) * r + A[4]) * r + A[5]) * q /
    (((((B[0] * r + B[1]) * r + B[2]) * r + B[3]) * r + B[4]) * r + 1);
}

function scale(value, lo, hi, outLo, outHi) {
  if (hi - lo === 0) return (outLo + outHi) / 2;
  return outLo + ((value - lo) / (hi - lo)) * (outHi - outLo);
}

// --- log-probability ---------------------------------------------------------

export function buildLogProbPlot(logProbability, options = {}) {
  const width = options.width || 320;
  const height = options.height || 200;
  const pad = options.pad || 28;
  const points = (logProbability && logProbability.points) || [];

  if (points.length < 2) {
    return { points: [], excluded: (logProbability && logProbability.n_excluded_non_positive) || 0, width, height };
  }

  const grades = points.map(p => p.grade).filter(g => g > 0);
  const logLo = Math.log10(Math.min(...grades));
  const logHi = Math.log10(Math.max(...grades));
  const probs = points.map(p => probit(p.cumulative_probability));
  const pLo = Math.min(...probs);
  const pHi = Math.max(...probs);

  const plotted = points.map((p, i) => ({
    cumulative_probability: p.cumulative_probability,
    grade: p.grade,
    x: scale(probs[i], pLo, pHi, pad, width - pad),
    y: scale(Math.log10(p.grade), logLo, logHi, height - pad, pad),
  }));

  return {
    points: plotted,
    excluded: logProbability.n_excluded_non_positive || 0,
    gradeRange: [Math.min(...grades), Math.max(...grades)],
    width,
    height,
  };
}

// --- metal capture -----------------------------------------------------------

export function buildCaptureCurve(rows, options = {}) {
  const width = options.width || 320;
  const height = options.height || 200;
  const pad = options.pad || 28;
  const usable = (rows || []).filter(r => r.threshold > 0);

  if (usable.length < 2) return { metal: [], length: [], width, height, marker: null };

  const logs = usable.map(r => Math.log10(r.threshold));
  const lo = Math.min(...logs);
  const hi = Math.max(...logs);

  const project = (row, fraction) => ({
    threshold: row.threshold,
    fraction,
    x: scale(Math.log10(row.threshold), lo, hi, pad, width - pad),
    y: scale(fraction === null ? 0 : fraction, 0, 1, height - pad, pad),
  });

  const metal = usable.map(r => project(r, r.metal_fraction));
  const length = usable.map(r => project(r, r.length_fraction));

  let marker = null;
  if (options.threshold > 0) {
    marker = {
      threshold: options.threshold,
      x: scale(Math.log10(options.threshold), lo, hi, pad, width - pad),
    };
  }

  return { metal, length, marker, width, height, thresholdRange: [usable[0].threshold, usable[usable.length - 1].threshold] };
}

// Nearest candidate threshold to an x position, so clicking the curve sets the
// input to a value that was actually evaluated rather than an interpolated one.
export function thresholdAtX(curve, x) {
  if (!curve.metal || curve.metal.length === 0) return null;
  let best = curve.metal[0];
  for (const point of curve.metal) {
    if (Math.abs(point.x - x) < Math.abs(best.x - x)) best = point;
  }
  return best.threshold;
}

// --- contact analysis --------------------------------------------------------

export function buildContactPlot(bins, options = {}) {
  const width = options.width || 320;
  const height = options.height || 160;
  const pad = options.pad || 28;
  const populated = (bins || []).filter(b => b.n > 0);

  if (populated.length === 0) return { bars: [], width, height };

  const centers = populated.map(b => b.distance_bin_center);
  const lo = Math.min(...centers);
  const hi = Math.max(...centers);
  const maxGrade = Math.max(...populated.map(b => b.mean_grade || 0), 1e-9);
  const barWidth = Math.max(2, (width - 2 * pad) / Math.max(populated.length, 1) - 2);

  return {
    bars: populated.map(b => {
      const y = scale(b.mean_grade || 0, 0, maxGrade, height - pad, pad);
      return {
        distance: b.distance_bin_center,
        n: b.n,
        meanGrade: b.mean_grade,
        lengthWeightedMeanGrade: b.length_weighted_mean_grade,
        inside: b.distance_bin_center > 0,
        x: scale(b.distance_bin_center, lo, hi, pad, width - pad) - barWidth / 2,
        y,
        width: barWidth,
        height: Math.max(0, (height - pad) - y),
      };
    }),
    zeroX: scale(0, lo, hi, pad, width - pad),
    maxGrade,
    width,
    height,
  };
}

// --- validation presentation -------------------------------------------------

export const METAL_CAPTURE_GOOD = 0.90;
export const METAL_CAPTURE_CAUTION = 0.75;
export const DILUTION_GOOD = 0.25;
export const DILUTION_CAUTION = 0.40;

// Bands are guidelines shown as colour. They never block generation -- the
// number is the deliverable, and a poor one is exactly what the reader needs
// to see.
export function classifyMetalCapture(value) {
  if (value === null || value === undefined) return 'unknown';
  if (value >= METAL_CAPTURE_GOOD) return 'good';
  if (value >= METAL_CAPTURE_CAUTION) return 'caution';
  return 'poor';
}

export function classifyDilution(value) {
  if (value === null || value === undefined) return 'unknown';
  if (value <= DILUTION_GOOD) return 'good';
  if (value <= DILUTION_CAUTION) return 'caution';
  return 'poor';
}

// --- request building --------------------------------------------------------

// Mirrors the POST /grade-shells schema. Defaults live here and in the API and
// must not drift apart; the panel reads its initial form values from this.
export const DEFAULT_FORM = {
  name: '',
  threshold: '',
  composite_length: 1.0,
  cell_size: 5.0,
  padding: 20.0,
  power: 2.0,
  max_samples: 16,
  min_samples: 2,
  min_volume: 0.0,
  split_components: true,
  range_major: '',
  range_semi: '',
  range_minor: '',
  strike_azimuth: '',
  dip: '',
  weights: {},
};

export function buildShellRequest(form) {
  const weights = {};
  for (const [type, weight] of Object.entries(form.weights || {})) {
    weights[type] = Number(weight);
  }

  return {
    name: form.name,
    threshold: Number(form.threshold),
    ellipsoid: {
      range_major: Number(form.range_major),
      range_semi: Number(form.range_semi),
      range_minor: Number(form.range_minor),
      strike_azimuth: Number(form.strike_azimuth),
      dip: Number(form.dip),
    },
    sample_type_weights: weights,
    composite_length: Number(form.composite_length),
    cell_size: Number(form.cell_size),
    padding: Number(form.padding),
    power: Number(form.power),
    max_samples: Number(form.max_samples),
    min_samples: Number(form.min_samples),
    min_volume: Number(form.min_volume),
    split_components: Boolean(form.split_components),
  };
}

// The ellipsoid and the weights carry no defaults on purpose (decisions D6 and
// D7), so the panel has to refuse an incomplete form rather than quietly
// filling one in.
export function validateForm(form, sampleTypes = []) {
  const problems = [];
  if (!form.name || !String(form.name).trim()) problems.push('Name is required.');
  if (!(Number(form.threshold) > 0)) problems.push('Threshold must be greater than zero.');
  for (const key of ['range_major', 'range_semi', 'range_minor']) {
    if (!(Number(form[key]) > 0)) {
      problems.push(`${key.replace('_', ' ')} must be greater than zero.`);
    }
  }
  if (form.strike_azimuth === '' || form.strike_azimuth === null || Number.isNaN(Number(form.strike_azimuth))) {
    problems.push('Strike azimuth is required — there is no default.');
  }
  if (form.dip === '' || form.dip === null || Number.isNaN(Number(form.dip))) {
    problems.push('Dip is required — there is no default.');
  } else if (Number(form.dip) < -90 || Number(form.dip) > 90) {
    problems.push('Dip must be between -90 and 90 degrees.');
  }
  for (const type of sampleTypes) {
    const weight = form.weights ? form.weights[type] : undefined;
    if (weight === undefined || weight === '' || Number.isNaN(Number(weight))) {
      problems.push(`A weight is required for ${type} — 0.0 excludes it from grade.`);
    } else if (Number(weight) < 0) {
      problems.push(`Weight for ${type} cannot be negative.`);
    }
  }
  if (Number(form.max_samples) < Number(form.min_samples)) {
    problems.push('Max samples must be at least min samples.');
  }
  return problems;
}
