// Plot geometry and request building for the grade-shell panel.
//
// These target the pure module rather than the panel, because `node --test`
// has no DOM. The rules worth locking down are that the generated request
// matches the API schema exactly (defaults drifting apart between panel and
// server is a silent way to produce a shell nobody asked for), and that the
// form refuses to fill in an ellipsoid or a sample weight on the user's behalf.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  buildCaptureCurve,
  buildContactPlot,
  buildLogProbPlot,
  buildShellRequest,
  classifyDilution,
  classifyMetalCapture,
  probit,
  thresholdAtX,
  validateForm,
} from '../src/services/grade_shell_plots.js';

function completeForm(overrides = {}) {
  return {
    name: 'Main zone',
    threshold: 0.3,
    range_major: 80,
    range_semi: 40,
    range_minor: 15,
    strike_azimuth: 45,
    dip: -70,
    composite_length: 1.0,
    cell_size: 5.0,
    padding: 20.0,
    power: 2.0,
    max_samples: 16,
    min_samples: 2,
    min_volume: 0.0,
    split_components: true,
    weights: { DDH: 1.0, TR: 0.5, FC: 0.0 },
    ...overrides,
  };
}

// --- probability axis --------------------------------------------------------

test('probit is symmetric about the median', () => {
  assert.ok(Math.abs(probit(0.5)) < 1e-9);
  assert.ok(Math.abs(probit(0.975) - 1.959964) < 1e-4);
  assert.ok(Math.abs(probit(0.025) + 1.959964) < 1e-4);
});

test('probit rejects probabilities outside the open unit interval', () => {
  assert.ok(Number.isNaN(probit(0)));
  assert.ok(Number.isNaN(probit(1)));
});

// --- log-probability plot ----------------------------------------------------

test('log-probability plots one point per grade and reports exclusions', () => {
  const plot = buildLogProbPlot({
    points: [
      { cumulative_probability: 0.125, grade: 0.01 },
      { cumulative_probability: 0.375, grade: 0.1 },
      { cumulative_probability: 0.625, grade: 1.0 },
      { cumulative_probability: 0.875, grade: 10.0 },
    ],
    n_excluded_non_positive: 3,
  });

  assert.equal(plot.points.length, 4);
  assert.equal(plot.excluded, 3);
  // Grade rises up the page, so y decreases as grade increases.
  assert.ok(plot.points[0].y > plot.points[3].y);
  assert.ok(plot.points[0].x < plot.points[3].x);
});

test('log-probability copes with too few points to draw', () => {
  const plot = buildLogProbPlot({ points: [], n_excluded_non_positive: 5 });

  assert.deepEqual(plot.points, []);
  assert.equal(plot.excluded, 5);
});

// --- capture curve -----------------------------------------------------------

const CAPTURE_ROWS = [
  { threshold: 0.1, metal_fraction: 0.945, length_fraction: 0.220 },
  { threshold: 0.2, metal_fraction: 0.919, length_fraction: 0.157 },
  { threshold: 0.3, metal_fraction: 0.889, length_fraction: 0.114 },
  { threshold: 1.0, metal_fraction: 0.796, length_fraction: 0.058 },
];

test('capture curve draws one point per evaluated threshold', () => {
  const curve = buildCaptureCurve(CAPTURE_ROWS, { threshold: 0.3 });

  assert.equal(curve.metal.length, CAPTURE_ROWS.length);
  assert.equal(curve.length.length, CAPTURE_ROWS.length);
  assert.equal(curve.metal[0].threshold, 0.1);
});

test('the current cut-off is marked on the curve', () => {
  const curve = buildCaptureCurve(CAPTURE_ROWS, { threshold: 0.3 });
  const atThreshold = curve.metal.find(p => p.threshold === 0.3);

  assert.ok(curve.marker);
  assert.ok(Math.abs(curve.marker.x - atThreshold.x) < 1e-6);
});

test('no marker is drawn when no cut-off is chosen', () => {
  assert.equal(buildCaptureCurve(CAPTURE_ROWS, {}).marker, null);
});

test('clicking the curve picks an evaluated cut-off, not an interpolated one', () => {
  const curve = buildCaptureCurve(CAPTURE_ROWS, {});
  const target = curve.metal[2];

  const picked = thresholdAtX(curve, target.x + 1);

  assert.equal(picked, 0.3);
  assert.ok(CAPTURE_ROWS.some(r => r.threshold === picked));
});

test('a null metal fraction does not break the curve', () => {
  const curve = buildCaptureCurve(
    [{ threshold: 0.1, metal_fraction: null, length_fraction: null },
     { threshold: 1.0, metal_fraction: null, length_fraction: null }], {});

  assert.equal(curve.metal.length, 2);
  assert.ok(Number.isFinite(curve.metal[0].y));
});

// --- contact plot ------------------------------------------------------------

test('contact plot keeps only populated bins and marks each side', () => {
  const plot = buildContactPlot([
    { distance_bin_center: -15, n: 4, mean_grade: 0.02, length_weighted_mean_grade: 0.02 },
    { distance_bin_center: -5, n: 9, mean_grade: 0.06, length_weighted_mean_grade: 0.06 },
    { distance_bin_center: 5, n: 7, mean_grade: 2.5, length_weighted_mean_grade: 2.5 },
    { distance_bin_center: 15, n: 0, mean_grade: null, length_weighted_mean_grade: null },
  ]);

  assert.equal(plot.bars.length, 3);
  assert.equal(plot.bars.filter(b => b.inside).length, 1);
  assert.equal(plot.bars.filter(b => !b.inside).length, 2);
  // The tallest bar is the high-grade side.
  const tallest = plot.bars.reduce((a, b) => (b.height > a.height ? b : a));
  assert.equal(tallest.inside, true);
});

test('contact plot copes with no populated bins', () => {
  assert.deepEqual(buildContactPlot([{ distance_bin_center: 5, n: 0 }]).bars, []);
});

// --- guideline bands ---------------------------------------------------------

test('metal capture bands follow the guideline thresholds', () => {
  assert.equal(classifyMetalCapture(0.95), 'good');
  assert.equal(classifyMetalCapture(0.90), 'good');
  assert.equal(classifyMetalCapture(0.80), 'caution');
  assert.equal(classifyMetalCapture(0.50), 'poor');
  assert.equal(classifyMetalCapture(null), 'unknown');
});

test('dilution bands follow the guideline thresholds', () => {
  assert.equal(classifyDilution(0.10), 'good');
  assert.equal(classifyDilution(0.25), 'good');
  assert.equal(classifyDilution(0.35), 'caution');
  assert.equal(classifyDilution(0.60), 'poor');
  assert.equal(classifyDilution(null), 'unknown');
});

// --- request building --------------------------------------------------------

test('the request matches the API schema', () => {
  const request = buildShellRequest(completeForm());

  assert.deepEqual(Object.keys(request).sort(), [
    'cell_size', 'composite_length', 'ellipsoid', 'max_samples', 'min_samples',
    'min_volume', 'name', 'padding', 'power', 'sample_type_weights',
    'split_components', 'threshold',
  ]);
  assert.deepEqual(Object.keys(request.ellipsoid).sort(), [
    'dip', 'range_major', 'range_minor', 'range_semi', 'strike_azimuth',
  ]);
});

test('form values are coerced to numbers, including from text inputs', () => {
  const request = buildShellRequest(completeForm({
    threshold: '0.45', range_major: '80', dip: '-70',
    weights: { DDH: '1', TR: '0.5', FC: '0' },
  }));

  assert.equal(request.threshold, 0.45);
  assert.equal(request.ellipsoid.range_major, 80);
  assert.equal(request.ellipsoid.dip, -70);
  assert.deepEqual(request.sample_type_weights, { DDH: 1, TR: 0.5, FC: 0 });
});

test('a zero weight survives into the request rather than being dropped', () => {
  // Decision D6: face channels are geometry-only. A falsy-value filter here
  // would silently restore them to full weight.
  const request = buildShellRequest(completeForm());

  assert.ok('FC' in request.sample_type_weights);
  assert.equal(request.sample_type_weights.FC, 0);
});

// --- form validation ---------------------------------------------------------

test('a complete form has no problems', () => {
  assert.deepEqual(validateForm(completeForm(), ['DDH', 'TR', 'FC']), []);
});

test('the ellipsoid is required, never defaulted', () => {
  const problems = validateForm(
    completeForm({ strike_azimuth: '', dip: '' }), ['DDH']);

  assert.ok(problems.some(p => p.includes('Strike azimuth')));
  assert.ok(problems.some(p => p.includes('Dip is required')));
});

test('a missing sample weight is refused rather than assumed', () => {
  const problems = validateForm(
    completeForm({ weights: { DDH: 1.0 } }), ['DDH', 'TR']);

  assert.ok(problems.some(p => p.includes('TR')));
});

test('a zero weight counts as stated, not missing', () => {
  const problems = validateForm(
    completeForm({ weights: { DDH: 1.0, FC: 0 } }), ['DDH', 'FC']);

  assert.deepEqual(problems, []);
});

test('out-of-range and inconsistent values are caught', () => {
  assert.ok(validateForm(completeForm({ dip: -120 }), []).some(p => p.includes('Dip must be')));
  assert.ok(validateForm(completeForm({ threshold: 0 }), []).some(p => p.includes('Threshold')));
  assert.ok(validateForm(completeForm({ range_minor: 0 }), []).some(p => p.includes('range minor')));
  assert.ok(validateForm(completeForm({ name: '  ' }), []).some(p => p.includes('Name')));
  assert.ok(validateForm(completeForm({ min_samples: 8, max_samples: 4 }), [])
    .some(p => p.includes('Max samples')));
  assert.ok(validateForm(completeForm({ weights: { DDH: -1 } }), ['DDH'])
    .some(p => p.includes('negative')));
});
