// Six-bucket Au grade scale, copied verbatim from the Abo Elmagd Hill 3D
// Design Pro reference viewer, and kept in sync with the backend's
// canonical version at backend/src/services/grade_coloring.py.
// Bucket 0 = background/waste (thinnest), bucket 5 = high grade (thickest).
export const GRADE_BUCKETS = [
  { upper: 0.01, color: '#7d8b8f', label: '0 - 0.01', tag: 'Waste' },
  { upper: 0.05, color: '#2b24eb', label: '0.01 - 0.05', tag: null },
  { upper: 0.1, color: '#27ea5b', label: '0.05 - 0.1', tag: null },
  { upper: 0.5, color: '#fef600', label: '0.1 - 0.5', tag: null },
  { upper: 1.0, color: '#f72809', label: '0.5 - 1.0', tag: null },
  { upper: null, color: '#ff00ff', label: '> 1.0', tag: 'High' },
];

// Cylinder radius (m) per grade bucket -- higher-grade intervals render
// visibly thicker along the drill core / trench trace, matching the
// reference viewer's "thickness as a grade cue" convention.
export const DRILL_RADIUS_BY_BUCKET = [0.15, 0.22, 0.28, 0.35, 0.45, 0.6];
export const TRENCH_RADIUS_BY_BUCKET = [0.5, 0.7, 0.9, 1.1, 1.4, 1.8];

export function getGradeBucketIndex(gradeValue, gradeUnit = 'ppm') {
  let val = Number(gradeValue);
  if (gradeUnit === '%') val *= 10000.0; // 1% = 10,000 ppm

  for (let i = 0; i < GRADE_BUCKETS.length; i++) {
    const upper = GRADE_BUCKETS[i].upper;
    if (upper === null || val < upper) return i;
  }
  return GRADE_BUCKETS.length - 1;
}
