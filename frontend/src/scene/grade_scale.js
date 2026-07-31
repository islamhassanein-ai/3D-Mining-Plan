// Canonical Au grade scale (g/t) -- kept in sync with the backend's
// authoritative version at backend/src/services/grade_coloring.py.
//
// Six graded buckets plus a separate Unsampled category. Unsampled is NOT a
// bucket: it covers null/NaN grades and placeholder Sample_ID values, which
// must never be coerced to 0.0 g/t -- "barren" and "never assayed" are
// different geological statements.
export const GRADE_BUCKETS = [
  { upper: 0.10, color: '#64748b', label: '< 0.10', tag: null },
  { upper: 0.30, color: '#2563eb', label: '0.10 - 0.30', tag: null },
  { upper: 0.50, color: '#22c55e', label: '0.30 - 0.50', tag: null },
  { upper: 1.00, color: '#f97316', label: '0.50 - 1.00', tag: null },
  { upper: 3.00, color: '#ef4444', label: '1.00 - 3.00', tag: null },
  { upper: null, color: '#ec4899', label: '>= 3.00', tag: 'High' },
];

// Near-black rather than pure #000000 so unsampled tubes still catch scene
// lighting and read as geometry instead of a hole in the depth buffer.
export const UNSAMPLED_COLOR = '#141414';
export const UNSAMPLED_LABEL = 'No Sample';
export const UNSAMPLED_BUCKET_INDEX = -1;

// Case-insensitive Sample_ID placeholders meaning "never assayed".
export const UNSAMPLED_SAMPLE_IDS = new Set([
  'unsampled', 'nsr', 'ns', 'no sample', 'no samples',
]);

// Uniform drill-core tube radius (m). Previously the radius varied per grade
// bucket, which made adjacent intervals meet at mismatched diameters and
// produced the stepped/blocky joints along the trajectory. A single radius
// keeps the hole reading as one continuous pipe (Leapfrog convention);
// grade is communicated by color alone.
export const DRILL_TUBE_RADIUS = 0.4;

// Radial segment count for interval tubes. 16 is smooth enough to lose the
// faceted silhouette at inspection zoom while staying cheap for instancing.
export const DRILL_TUBE_RADIAL_SEGMENTS = 16;

// Trenches are rendered as a vertical "grade profile fence" standing along
// the channel-sample line rather than a round tube (round cross-sections
// read as drill core, which is misleading for a surface channel sample) --
// see trenches.js for the rationale. Height in meters per grade bucket.
export const TRENCH_HEIGHT_BY_BUCKET = [0.4, 0.9, 1.8, 3.0, 4.8, 7.0];

// Fence height used for unsampled trench segments -- deliberately minimal so
// a gap in sampling never reads as a grade result.
export const TRENCH_UNSAMPLED_HEIGHT = 0.25;

export function isUnsampled(gradeValue, sampleId = null) {
  if (sampleId !== null && sampleId !== undefined) {
    if (UNSAMPLED_SAMPLE_IDS.has(String(sampleId).trim().toLowerCase())) return true;
  }
  if (gradeValue === null || gradeValue === undefined || gradeValue === '') return true;
  const val = Number(gradeValue);
  return !Number.isFinite(val);
}

// Returns 0..5, or UNSAMPLED_BUCKET_INDEX (-1) when the interval has no
// usable assay result. Callers that index an array by the result MUST handle
// -1 first.
export function getGradeBucketIndex(gradeValue, gradeUnit = 'g/t', sampleId = null) {
  if (isUnsampled(gradeValue, sampleId)) return UNSAMPLED_BUCKET_INDEX;

  let val = Number(gradeValue);
  if (gradeUnit === '%') val *= 10000.0; // 1% = 10,000 ppm = 10,000 g/t

  for (let i = 0; i < GRADE_BUCKETS.length; i++) {
    const upper = GRADE_BUCKETS[i].upper;
    if (upper === null || val < upper) return i;
  }
  return GRADE_BUCKETS.length - 1;
}

export function getGradeColor(gradeValue, gradeUnit = 'g/t', sampleId = null) {
  const idx = getGradeBucketIndex(gradeValue, gradeUnit, sampleId);
  if (idx === UNSAMPLED_BUCKET_INDEX) return UNSAMPLED_COLOR;
  return GRADE_BUCKETS[idx].color;
}
