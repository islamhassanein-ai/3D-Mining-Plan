// Headline project figures. The rule these lock down is that a planned hole's
// intervals are targets, not results, and must never be averaged into numbers
// a reader will take as measured.
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { computeProjectSummary } from '../src/services/project_summary.js';

function hole(overrides = {}) {
  return {
    collar_id: 'c-1',
    hole_id: 'DDH-001',
    hole_status: 'drilled',
    assays: [],
    ...overrides,
  };
}

function assay(from, to, grade) {
  return { from_depth: from, to_depth: to, grade_value: grade, grade_unit: 'g/t' };
}

test('planned targets stay out of the grade figures', () => {
  const drilledOnly = computeProjectSummary({
    drillholes: [hole({ assays: [assay(0, 10, 0.2), assay(10, 20, 0.4)] })],
  });

  // The same project, plus a planned hole whose target grades are far higher
  // than anything actually intersected.
  const withPlanned = computeProjectSummary({
    drillholes: [
      hole({ assays: [assay(0, 10, 0.2), assay(10, 20, 0.4)] }),
      hole({
        collar_id: 'c-2',
        hole_id: 'PL-001',
        hole_status: 'planned',
        assays: [assay(30, 45, 12.0), assay(60, 72, 15.0)],
      }),
    ],
  });

  assert.equal(withPlanned.drillholes.avgGrade, drilledOnly.drillholes.avgGrade,
    'a planned target must not move the average grade');
  assert.equal(withPlanned.drillholes.peakGrade, drilledOnly.drillholes.peakGrade,
    'a planned target must not become the project peak grade');
  assert.equal(withPlanned.drillholes.meters, drilledOnly.drillholes.meters,
    'ground that has not been drilled contributes no metres');
  assert.equal(withPlanned.drillholes.sampleCount, 2,
    'target intervals are not samples');
});

test('drilled and planned are counted separately', () => {
  const summary = computeProjectSummary({
    drillholes: [
      hole(),
      hole({ collar_id: 'c-2' }),
      hole({ collar_id: 'c-3', hole_status: 'planned' }),
    ],
  });

  assert.equal(summary.drillholes.drilled, 2);
  assert.equal(summary.drillholes.planned, 1);
  // The combined figure stays available for anything that still wants it.
  assert.equal(summary.drillholes.holes, 3);
});

test('a hole with no status counts as drilled', () => {
  const h = hole({ assays: [assay(0, 5, 1.0)] });
  delete h.hole_status;

  const summary = computeProjectSummary({ drillholes: [h] });
  assert.equal(summary.drillholes.drilled, 1);
  assert.equal(summary.drillholes.planned, 0);
  assert.equal(summary.drillholes.peakGrade, 1.0);
});

test('null grades are skipped rather than counted as zero', () => {
  // An unassayed interval must not drag the average down -- "never assayed"
  // and "assayed at zero" are different statements.
  const summary = computeProjectSummary({
    drillholes: [hole({
      assays: [assay(0, 10, 2.0), { from_depth: 10, to_depth: 20, grade_value: null }],
    })],
  });

  assert.equal(summary.drillholes.sampleCount, 1);
  assert.equal(summary.drillholes.avgGrade, 2.0);
  // Metres still count the full sampled depth of the hole.
  assert.equal(summary.drillholes.meters, 20);
});

test('an empty project reports zeroes rather than NaN', () => {
  const summary = computeProjectSummary({});
  assert.equal(summary.drillholes.drilled, 0);
  assert.equal(summary.drillholes.planned, 0);
  assert.equal(summary.drillholes.avgGrade, 0);
  assert.equal(summary.trenches.count, 0);
});
