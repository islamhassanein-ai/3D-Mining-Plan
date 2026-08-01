// Canonical Au grade scale (g/t) -- kept in sync with the backend's
// authoritative version at backend/src/services/grade_coloring.py.
//
// Six graded buckets plus a separate Unsampled category. Unsampled is NOT a
// bucket: it covers null/NaN grades and placeholder Sample_ID values, which
// must never be coerced to 0.0 g/t -- "barren" and "never assayed" are
// different geological statements.
// Shades are tuned for separation on the dark 3D viewport (#0d1524). What
// matters is perceptual distance between ADJACENT buckets -- those sit next to
// each other on a drill trace and must be told apart at a glance. The hue walk
// is grey -> blue -> green -> yellow -> red -> violet-magenta, which puts a
// large hue AND lightness step at every boundary. The weakest pair used to be
// amber/orange-red (dE ~35, reading as one colour under scene shading); the
// 0.50-1.00 bucket is now a pure yellow and 1.00-3.00 a pure red, which widens
// that boundary to the point where it survives the tube's specular highlight.
//
// `from`/`to` are the explicit bracket bounds, so the UI can label ranges
// rather than bare numbers. `to: null` is the open-ended top bucket.
export const GRADE_BUCKETS = [
  { from: 0.00, to: 0.10, upper: 0.10, color: '#94a3b8', label: '< 0.10', tag: null },
  { from: 0.10, to: 0.30, upper: 0.30, color: '#1f6fff', label: '0.10 - 0.30', tag: null },
  { from: 0.30, to: 0.50, upper: 0.50, color: '#00e57a', label: '0.30 - 0.50', tag: null },
  { from: 0.50, to: 1.00, upper: 1.00, color: '#ffd21e', label: '0.50 - 1.00', tag: null },
  { from: 1.00, to: 3.00, upper: 3.00, color: '#f5222d', label: '1.00 - 3.00', tag: null },
  { from: 3.00, to: null, upper: null, color: '#e838ff', label: '>= 3.00', tag: 'High' },
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

// Optional grade-proportional radii, opt-in via the "Scale thickness by grade"
// switch. Off by default: a constant diameter is the Leapfrog convention and
// keeps the hole reading as one continuous pipe. When on, the diameter step at
// each interval boundary is the second channel (with colour) carrying grade,
// which is what makes a high-grade run pop out at survey-scale zoom.
// Indexed by bucket, so index -1 (unsampled) must be handled by the caller.
export const DRILL_TUBE_RADIUS_BY_BUCKET = [0.30, 0.36, 0.44, 0.55, 0.72, 0.95];

// Unsampled intervals are not drawn by the tube builder at all, but the
// section view and any other consumer that needs a width for them should use
// the thinnest value so a gap never reads as a result.
export const DRILL_TUBE_RADIUS_UNSAMPLED = 0.22;

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
