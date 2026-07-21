import * as THREE from 'three';
import { makeLabelSprite, updateBillboardScale } from './label_sprite.js';

// Renders a hole_id text label floating above each collar. Toggleable
// separately from Drillhole Traces since labels can get visually busy on
// dense sites -- see LayerTogglePanel. Sized in screen-space (billboard),
// not world-space, so labels stay readable at any zoom level.
export class BoreholeLabels {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'borehole-labels';
    this.scene.add(this.group);
  }

  render(drillholes) {
    this.clear();
    for (const dh of drillholes) {
      const sprite = makeLabelSprite(dh.hole_id, 'rgba(212, 175, 55, 0.8)', '#e8c76b');
      sprite.position.set(dh.easting, dh.elevation + 6, dh.northing);
      sprite.userData.type = 'borehole_label';
      sprite.userData.collar_id = dh.collar_id;
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
