// Arithmetic extracted verbatim from index.html updateDdAndTrenchSummary.
// Convention: total metres come from each hole's deepest assay interval,
// not raw trace length (reflects sampled depth, not full drilled hole).

export function computeProjectSummary(sceneData) {
  const drillholes = sceneData.drillholes || [];
  let totalMeters = 0, ddGradeSum = 0, ddGradeCount = 0, ddPeak = 0;
  let drilledCount = 0, plannedCount = 0;

  for (const dh of drillholes) {
    const isPlanned = dh.hole_status === 'planned';
    if (isPlanned) { plannedCount++; } else { drilledCount++; }

    // A planned hole's intervals are TARGETS -- grades someone expects to
    // intersect, not results. Averaging them into the project's headline
    // figures reports an expectation as a measurement, which is the one thing
    // a grade summary must never do. On a project that is majority planned it
    // moves the numbers a long way. Metres are excluded for the same reason:
    // that ground has not been drilled yet.
    if (isPlanned) continue;

    let maxDepth = 0;
    for (const a of dh.assays) {
      if (a.to_depth > maxDepth) maxDepth = a.to_depth;
      if (a.grade_value == null) continue;
      ddGradeSum += a.grade_value;
      ddGradeCount++;
      if (a.grade_value > ddPeak) ddPeak = a.grade_value;
    }
    totalMeters += maxDepth;
  }

  const trenches = sceneData.trenches || [];
  const trenchIds = new Set(trenches.map(t => t.trench_id));
  let trGradeSum = 0, trGradeCount = 0, trPeak = 0;
  for (const t of trenches) {
    if (t.grade_value == null) continue;
    trGradeSum += t.grade_value;
    trGradeCount++;
    if (t.grade_value > trPeak) trPeak = t.grade_value;
  }

  return {
    drillholes: {
      holes: drillholes.length,
      drilled: drilledCount,
      planned: plannedCount,
      meters: totalMeters,
      avgGrade: ddGradeCount ? ddGradeSum / ddGradeCount : 0,
      peakGrade: ddPeak,
      sampleCount: ddGradeCount,
    },
    trenches: {
      count: trenchIds.size,
      samples: trenches.length,
      avgGrade: trGradeCount ? trGradeSum / trGradeCount : 0,
      peakGrade: trPeak,
      sampleCount: trGradeCount,
    },
  };
}
