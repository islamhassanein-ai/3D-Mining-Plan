import * as THREE from 'three';

// Shared canvas-text-sprite builder + billboard-size updater used by both
// BoreholeLabels and TrenchLabels, so hole/trench tags share one look and
// one sizing behavior.
//
// The pill is rendered at the device pixel ratio (crisp, not blurry when
// magnified) with a rounded, semi-transparent background and a small accent
// dot, so labels read as clean map-style tags rather than raw text boxes.
export function makeLabelSprite(text, accentColor = '#d4af37', textColor = '#f1f5f9') {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const fontSize = 30;
  const padX = 14;
  const padY = 8;
  const dotR = 5;
  const dotGap = 8;

  const measure = document.createElement('canvas').getContext('2d');
  measure.font = `600 ${fontSize}px Inter, "Segoe UI", sans-serif`;
  const textW = measure.measureText(text).width;

  const cssW = Math.ceil(textW + padX * 2 + dotR * 2 + dotGap);
  const cssH = Math.ceil(fontSize + padY * 2);

  const canvas = document.createElement('canvas');
  canvas.width = Math.ceil(cssW * dpr);
  canvas.height = Math.ceil(cssH * dpr);
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  // Rounded pill background
  const r = cssH / 2;
  ctx.beginPath();
  ctx.moveTo(r, 0);
  ctx.arcTo(cssW, 0, cssW, cssH, r);
  ctx.arcTo(cssW, cssH, 0, cssH, r);
  ctx.arcTo(0, cssH, 0, 0, r);
  ctx.arcTo(0, 0, cssW, 0, r);
  ctx.closePath();
  ctx.fillStyle = 'rgba(13, 21, 36, 0.86)';
  ctx.fill();
  ctx.lineWidth = 1.25;
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.14)';
  ctx.stroke();

  // Accent dot
  ctx.beginPath();
  ctx.arc(padX + dotR, cssH / 2, dotR, 0, Math.PI * 2);
  ctx.fillStyle = accentColor;
  ctx.fill();

  // Text
  ctx.font = `600 ${fontSize}px Inter, "Segoe UI", sans-serif`;
  ctx.fillStyle = textColor;
  ctx.textBaseline = 'middle';
  ctx.fillText(text, padX + dotR * 2 + dotGap, cssH / 2 + 1);

  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.anisotropy = 4;

  const material = new THREE.SpriteMaterial({
    map: texture,
    depthTest: true,
    depthWrite: false,
    transparent: true
  });
  const sprite = new THREE.Sprite(material);
  sprite.renderOrder = 10;
  sprite.userData.aspect = cssW / cssH;
  return sprite;
}

// Billboard sizing: labels read at a near-constant on-screen size (like map
// pins) rather than shrinking to nothing far away or swelling to cover the
// scene up close. Height is proportional to camera distance (canceling
// perspective attenuation), then clamped so extreme zoom in/out keeps labels
// within a sane world-size band. `pixelScale` controls apparent screen size.
export function updateBillboardScale(group, camera, pixelScale = 0.026) {
  for (const sprite of group.children) {
    if (!sprite.isSprite) continue;
    const distance = camera.position.distanceTo(sprite.position);
    let height = distance * pixelScale;
    height = Math.max(2.5, Math.min(height, 22)); // world-unit clamp
    const aspect = sprite.userData.aspect || 3;
    sprite.scale.set(height * aspect, height, 1);
  }
}
