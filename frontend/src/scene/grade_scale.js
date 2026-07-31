// Canonical Au grade scale (g/t) -- kept in sync with the backend's
// authoritative version at backend/src/services/grade_coloring.py.
//
// Six graded buckets plus a separate Unsampled category. Unsampled is NOT a
// bucket: it covers null/NaN grades and placeholder Sample_ID values, which
// must never be coerced to 0.0 g/t -- "barren" and "never assayed" are
// different geological statements.
// Shades are tuned for separation on the dark 3D viewport (#0d1524). What
// matters is perceptual distance between ADJACENT buckets -- those sit next to
// each other on a drill trace and must be told apart at a glance. Worst
// adjacent pair is dE(CIE76) ~56; the previous orange/red boundary was ~35,
// which read as one colour under scene shading.
//
// `from`/`to` are the explicit bracket bounds, so the UI can label ranges
// rather than bare numbers. `to: null` is the open-ended top bucket.
export const GRADE_BUCKETS = [
  { from: 0.00, to: 0.10, upper: 0.10, color: '#9aa7b8', label: '< 0.10', tag: null },
  { from: 0.10, to: 0.30, upper: 0.30, color: '#2b7fff', label: '0.10 - 0.30', tag: null },
  { from: 0.30, to: 0.50, upper: 0.50, color: '#21d07a', label: '0.30 - 0.50', tag: null },
  { from: 0.50, to: 1.00, upper: 1.00, color: '#ffc233', label: '0.50 - 1.00', tag: null },
  { from: 1.00, to: 3.00, upper: 3.00, color: '#ff5a1f', label: '1.00 - 3.00', tag: null },
  { from: 3.00, to: null, upper: null, color: '#ff2bd6', label: '>= 3.00', tag: 'High' },
];

// "0.10 – 0.30" / "≥ 3.00" -- the From–To form used under the grade bars.
export function formatBucketRange(bucket, decimals = 2) {
  const from = bucket.from.toFixed(decimals);
  if (bucket.to === null) return `≥ ${from}`;
  return `${from} – ${bucket.to.toFixed(decimals)}`;
}

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

// Radial segment count for interval tubes. 20 keeps the silhouette round at
// inspection zoom -- the facet edges were still catching the light at 16 --
// while staying cheap, since every instance shares this one geometry.
export const DRILL_TUBE_RADIAL_SEGMENTS = 20;

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
