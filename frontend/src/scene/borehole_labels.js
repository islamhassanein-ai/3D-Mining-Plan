import * as THREE from 'three';

function makeLabelSprite(text) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const fontSize = 42;
  ctx.font = `700 ${fontSize}px Inter, sans-serif`;
  const textWidth = ctx.measureText(text).width;

  canvas.width = textWidth + 24;
  canvas.height = fontSize + 20;

  ctx.font = `700 ${fontSize}px Inter, sans-serif`;
  ctx.fillStyle = 'rgba(11, 18, 32, 0.75)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.strokeStyle = 'rgba(212, 175, 55, 0.8)';
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
  ctx.fillStyle = '#e8c76b';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 12, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const material = new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true });
  const sprite = new THREE.Sprite(material);

  // World-space size proportional to the canvas's pixel aspect, tuned so
  // hole_id labels read clearly at typical site-scale zoom without
  // dominating the scene.
  const scale = 4.5;
  sprite.scale.set((canvas.width / canvas.height) * scale, scale, 1);
  return sprite;
}

// Renders a hole_id text label floating above each collar. Toggleable
// separately from Drillhole Traces since labels can get visually busy on
// dense sites -- see LayerTogglePanel.
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
      const sprite = makeLabelSprite(dh.hole_id);
      sprite.position.set(dh.easting, dh.elevation + 6, dh.northing);
      sprite.userData = { type: 'borehole_label', collar_id: dh.collar_id };
      this.group.add(sprite);
    }
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
