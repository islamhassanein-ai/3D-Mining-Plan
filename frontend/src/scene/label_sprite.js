import * as THREE from 'three';

// Shared canvas-text-sprite builder + billboard-size updater used by both
// BoreholeLabels and TrenchLabels, so hole/trench tags share one look and
// one sizing behavior.
export function makeLabelSprite(text, accentColor = '#d4af37', textColor = '#e8c76b') {
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
  ctx.strokeStyle = accentColor;
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, canvas.width - 2, canvas.height - 2);
  ctx.fillStyle = textColor;
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 12, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const material = new THREE.SpriteMaterial({ map: texture, depthTest: false, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.userData.aspect = canvas.width / canvas.height;
  return sprite;
}

// Billboard sizing: labels should read as a constant on-screen size (like
// map pins), not shrink to nothing far away or swell to cover the scene up
// close the way a fixed world-space scale does. Each frame, size every
// sprite in `group` proportional to its distance from the camera --
// canceling out perspective attenuation so the apparent screen size stays
// constant. `pixelSize` roughly controls how large labels read on screen.
export function updateBillboardScale(group, camera, pixelSize = 0.045) {
  for (const sprite of group.children) {
    if (!sprite.isSprite) continue;
    const distance = camera.position.distanceTo(sprite.position);
    const height = distance * pixelSize;
    const aspect = sprite.userData.aspect || 3;
    sprite.scale.set(height * aspect, height, 1);
  }
}
