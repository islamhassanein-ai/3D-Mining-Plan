import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

import { computeTrueThickness } from '../src/services/true_thickness.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(__dirname, '../../specs/006-standalone-html-export/fixtures/true_thickness_vectors.json');
const fixture = JSON.parse(readFileSync(fixturePath, 'utf8'));
const { tolerance } = fixture;

for (const c of fixture.cases) {
  test(c.name, () => {
    const result = computeTrueThickness({
      surveys: c.surveys,
      fromDepth: c.from_depth,
      toDepth: c.to_depth,
      dipDirection: c.dip_direction,
      dip: c.vein_dip,
    });
    const exp = c.expected;
    assert.ok(
      Math.abs(result.apparent_thickness - exp.apparent_thickness) <= tolerance,
      `apparent_thickness: got ${result.apparent_thickness}, expected ${exp.apparent_thickness}`
    );
    assert.ok(
      Math.abs(result.true_thickness - exp.true_thickness) <= tolerance,
      `true_thickness: got ${result.true_thickness}, expected ${exp.true_thickness}`
    );
    assert.ok(
      Math.abs(result.hole_dip - exp.hole_dip) <= tolerance,
      `hole_dip: got ${result.hole_dip}, expected ${exp.hole_dip}`
    );
    assert.ok(
      Math.abs(result.hole_azimuth - exp.hole_azimuth) <= tolerance,
      `hole_azimuth: got ${result.hole_azimuth}, expected ${exp.hole_azimuth}`
    );
  });
}
