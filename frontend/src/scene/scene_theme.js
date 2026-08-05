import * as THREE from 'three';

// Scene-side half of the theme switch. The DOM half is pure CSS variables on
// <html data-theme>, but the WebGL viewport has no cascade -- background, fill
// light and grid have to be set explicitly. Grade colours are deliberately
// untouched: they encode data and must not shift with the theme.
//
// This lives in its own module because two entry points need it and they may
// not import each other: scene.js bootstraps the live app, while the
// standalone export builds its scene inline in export/viewer_main.js and must
// never pull scene.js in (that would drag ApiClient into a bundle whose whole
// point is that it makes no network calls). Copying the palette into both
// would let the two drift, and a reader comparing an export against the app
// would be looking at two different scenes.
export const SCENE_THEMES = {
  dark:     { bg: 0x0b0f19, ambient: 0.60, fill: 0x3b82f6, fillIntensity: 0.30, grid: [0x374151, 0x1f2937] },
  light:    { bg: 0xe6ecf4, ambient: 0.85, fill: 0x3b82f6, fillIntensity: 0.12, grid: [0x94a3b8, 0xcbd5e1] },
  // Neutral charcoal with a white fill light instead of a blue one: any
  // tint in the fill lands on every grade colour at once and shifts how it
  // reads, which defeats the point of a reference-grade view.
  graphite: { bg: 0x17171a, ambient: 0.66, fill: 0xffffff, fillIntensity: 0.14, grid: [0x3f4046, 0x2a2b2f] },
};

export const THEMES = Object.keys(SCENE_THEMES);

export function isTheme(name) {
  return Object.prototype.hasOwnProperty.call(SCENE_THEMES, name);
}

/**
 * Applies `theme` to a scene's background, lights and grid.
 *
 * The grid can't be recoloured in place -- GridHelper bakes its two colours
 * into vertex colours at construction -- so it is rebuilt, and the caller must
 * store the returned helper in place of the one it passed in.
 *
 * Returns the new grid helper (or null when no grid was supplied).
 */
export function applySceneTheme(theme, { scene, ambientLight, fillLight, gridHelper }) {
  const cfg = SCENE_THEMES[theme] || SCENE_THEMES.dark;

  scene.background = new THREE.Color(cfg.bg);
  // On a pale background the cool fill light muddies the surface, and the
  // ambient has to come down or everything flattens out.
  if (ambientLight) ambientLight.intensity = cfg.ambient;
  if (fillLight) {
    fillLight.color.setHex(cfg.fill);
    fillLight.intensity = cfg.fillIntensity;
  }

  if (!gridHelper) return null;

  const wasVisible = gridHelper.visible;
  scene.remove(gridHelper);
  gridHelper.geometry.dispose();
  gridHelper.material.dispose();

  const next = new THREE.GridHelper(5000, 100, cfg.grid[0], cfg.grid[1]);
  next.position.y = 0;
  next.visible = wasVisible;
  next.userData.excludeFromFit = true;
  scene.add(next);
  return next;
}
