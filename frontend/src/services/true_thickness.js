// Port of backend/src/api/collars.py:178–249.
// Kept structurally identical so the two stay diffable.

export function interpolateSurveyOrientation(surveys, midDepth) {
  if (!surveys || surveys.length === 0) return { dip: -90.0, azimuth: 0.0 };
  if (surveys.length === 1) return { dip: surveys[0].dip, azimuth: surveys[0].azimuth };

  const s1 = surveys[0];
  const s2 = surveys[surveys.length - 1];

  if (midDepth <= s1.depth) return { dip: s1.dip, azimuth: s1.azimuth };
  if (midDepth >= s2.depth) return { dip: s2.dip, azimuth: s2.azimuth };

  for (let i = 1; i < surveys.length; i++) {
    const prev = surveys[i - 1];
    const curr = surveys[i];
    if (prev.depth <= midDepth && midDepth <= curr.depth) {
      const d1 = prev.depth, d2 = curr.depth;
      const t = Math.abs(d2 - d1) > 1e-9 ? (midDepth - d1) / (d2 - d1) : 0.0;

      const dip = prev.dip + t * (curr.dip - prev.dip);

      const a1 = prev.azimuth * Math.PI / 180;
      const a2 = curr.azimuth * Math.PI / 180;
      const x = (1 - t) * Math.cos(a1) + t * Math.cos(a2);
      const y = (1 - t) * Math.sin(a1) + t * Math.sin(a2);
      const azimuth = (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;

      return { dip, azimuth };
    }
  }
  return { dip: s2.dip, azimuth: s2.azimuth };
}

export function computeTrueThickness({ surveys, fromDepth, toDepth, dipDirection, dip, collarId = null, intervalId = null }) {
  const apparentThickness = toDepth - fromDepth;
  const midDepth = (fromDepth + toDepth) / 2.0;

  const { dip: holeDip, azimuth: holeAz } = interpolateSurveyOrientation(surveys, midDepth);

  const hdRad = holeDip * Math.PI / 180;
  const haRad = holeAz * Math.PI / 180;

  const dx = Math.cos(hdRad) * Math.sin(haRad);
  const dy = Math.cos(hdRad) * Math.cos(haRad);
  const dz = Math.sin(hdRad);

  const alpha = dipDirection * Math.PI / 180;
  const delta = dip * Math.PI / 180;

  const nx = Math.sin(delta) * Math.sin(alpha);
  const ny = Math.sin(delta) * Math.cos(alpha);
  const nz = -Math.cos(delta);

  const cosTheta = dx * nx + dy * ny + dz * nz;
  const trueThickness = apparentThickness * Math.abs(cosTheta);
  const intersectionAngleDeg = Math.acos(Math.min(1.0, Math.max(-1.0, Math.abs(cosTheta)))) * 180 / Math.PI;

  return {
    collar_id: collarId,
    interval_id: intervalId,
    apparent_thickness: apparentThickness,
    true_thickness: trueThickness,
    hole_dip: holeDip,
    hole_azimuth: holeAz,
    vein_dip_direction: dipDirection,
    vein_dip: dip,
    intersection_angle_deg: intersectionAngleDeg
  };
}
