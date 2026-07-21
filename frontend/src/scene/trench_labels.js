import * as THREE from 'three';
import { makeLabelSprite, updateBillboardScale } from './label_sprite.js';

// Renders one trench_id label per trench line, positioned at its first
// sample point. Off by default (see LayerTogglePanel) -- like borehole
// labels, useful on demand rather than always-on clutter.
export class TrenchLabels {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'trench-labels';
    this.scene.add(this.group);
  }

  render(trenches, drillholes) {
    this.clear();
    if (!trenches || trenches.length === 0) return;

    let baselineElevation = 0.0;
    if (drillholes && drillholes.length > 0) {
      const sum = drillholes.reduce((s, dh) => s + dh.elevation, 0);
      baselineElevation = sum / drillholes.length;
    }

    const seen = new Set();
    for (const t of trenches) {
      if (seen.has(t.trench_id) || t.easting == null || t.northing == null) continue;
      seen.add(t.trench_id);

      const sprite = makeLabelSprite(t.trench_id, 'rgba(247, 40, 9, 0.8)', '#fca5a5');
      const elevation = t.elevation != null ? t.elevation : baselineElevation;
      sprite.position.set(t.easting, elevation + 4, t.northing);
      sprite.userData.type = 'trench_label';
      sprite.userData.trench_id = t.trench_id;
      this.group.add(sprite);
    }
  }

  update(camera) {
    updateBillboardScale(this.group, camera);
  }

  clear() {
    this.group.traverse((child) => {
      if (child.isSprite) {
        child.material.map.dispose();
        child.material.dispose();
      }
    });
    while (this.group.children.length > 0) {
      this.group.remove(this.group.children[0]);
    }
  }
}
