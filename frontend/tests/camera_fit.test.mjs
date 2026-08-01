// Camera framing checks for SceneLoader.visibleBounds / fitCameraToData.
// Three.js builds its scene graph without a WebGL context, so these run
// headless against a real scene.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import * as THREE from 'three';

import { SceneLoader } from '../src/scene/scene_loader.js';
import { DrillholeTraces } from '../src/scene/drillhole_traces.js';
import { DampedCameraControls } from '../src/scene/camera_controls.js';

// Real sites sit at UTM coordinates in the hundreds of thousands / millions,
// which is what makes an object mistakenly read at the world origin so
// destructive: the bounds stretch from the data all the way back to (0,0,0).
const EASTING = 208300;
const NORTHING = 2467900;
const ELEVATION = 300;

function plannedHole() {
  return {
    collar_id: 'c-planned',
    hole_id: 'AAPL001',
    easting: EASTING, northing: NORTHING, elevation: ELEVATION,
    hole_status: 'planned',
    total_depth: 60,
    trace: [
      { depth: 0, x: EASTING, y: NORTHING, z: ELEVATION },
      { depth: 60, x: EASTING + 20, y: NORTHING + 20, z: ELEVATION - 55 },
    ],
    assays: [],
    lithologies: [],
    unsampled_gaps: [],
  };
}

// Minimal stand-in for the DOM element the controls listen on.
function fakeDomElement() {
  return {
    clientWidth: 1200,
    clientHeight: 800,
    addEventListener() {},
    removeEventListener() {},
    getBoundingClientRect() { return { left: 0, top: 0, width: 1200, height: 800 }; },
    setPointerCapture() {},
    releasePointerCapture() {},
    style: {},
  };
}

function makeLoader() {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1200 / 800, 1, 100000);
  camera.position.set(200, 200, 200);
  const controls = new DampedCameraControls(camera, fakeDomElement(), scene);
  const loader = new SceneLoader(scene, controls);
  return { scene, camera, controls, loader };
}

test('grid and axes helpers are excluded from the camera fit', () => {
  const { scene, loader } = makeLoader();

  const traces = new DrillholeTraces(scene);
  traces.render([plannedHole()]);

  // The grid spans 5 km. Letting it into the bounds frames the grid instead
  // of the drilling and shrinks the site to a few pixels -- which is exactly
  // what the standalone export viewer did, because it adds its helpers
  // without the excludeFromFit flag.
  scene.add(new THREE.GridHelper(5000, 100));
  scene.add(new THREE.AxesHelper(100));

  const bounds = loader.visibleBounds();
  assert.ok(bounds, 'bounds must be found');

  const size = new THREE.Vector3();
  bounds.getSize(size);
  assert.ok(size.x < 500, `bounds must not include the 5 km grid (got ${size.x} m across)`);
});

test('bounds use up-to-date world matrices, not stale ones', () => {
  const { scene, loader } = makeLoader();

  // The planned-hole collar marker is positioned via .position rather than
  // baked into its vertices. World matrices are normally refreshed by the
  // renderer, so before the first frame it still carries an identity matrix
  // -- reading it then puts it at (0,0,0), and on a UTM site that inflates
  // the bounds to millions of metres. fitCameraToData runs during the initial
  // load, before any frame has rendered, so this is the live case.
  const traces = new DrillholeTraces(scene);
  traces.render([plannedHole()]);

  const bounds = loader.visibleBounds();
  const size = new THREE.Vector3();
  bounds.getSize(size);

  assert.ok(
    size.z < 1000,
    `bounds must not stretch back to the world origin (got ${Math.round(size.z)} m)`
  );
  assert.ok(bounds.min.x > 1000, 'bounds must sit at the site, not near zero');

  // The sampled point cloud feeds the fit, so it has to be safe on the same
  // count -- a refactor once moved the matrix refresh onto the bounds path
  // only, and the fit went back to parking the camera millions of metres out.
  for (const point of loader.visiblePoints()) {
    assert.ok(
      Math.abs(point.x) > 1000 && Math.abs(point.z) > 1000,
      'no sampled point may sit at the world origin'
    );
  }
});

test('fitCameraToData frames the data and records a home pose', () => {
  const { camera, controls, loader, scene } = makeLoader();

  const traces = new DrillholeTraces(scene);
  traces.render([plannedHole()]);
  scene.add(new THREE.GridHelper(5000, 100));

  loader.fitCameraToData();

  assert.ok(controls.home, 'a home pose must be stored for Reset Camera');

  // No geometry may be clipped, and the fit must be tight enough that the data
  // actually fills the frame -- the old fit left the model at about half of it.
  //
  // This checks the sampled geometry, not the bounding box: a box corner can
  // sit in empty space, and requiring those on screen is what kept the camera
  // too far out in the first place. What must never be clipped is something
  // the user can see.
  camera.updateMatrixWorld(true);
  let maxAbs = 0;
  for (const point of loader.visiblePoints()) {
    const ndc = point.clone().project(camera);
    assert.ok(
      Math.abs(ndc.x) <= 1 && Math.abs(ndc.y) <= 1,
      `geometry at (${Math.round(point.x)}, ${Math.round(point.y)}, ${Math.round(point.z)}) is clipped`
    );
    maxAbs = Math.max(maxAbs, Math.abs(ndc.x), Math.abs(ndc.y));
  }
  assert.ok(maxAbs > 0.8, `data should fill the frame (widest point at ${maxAbs.toFixed(2)})`);
});

test('the fit centres the geometry, not its bounding box', () => {
  const { camera, loader, scene } = makeLoader();

  const traces = new DrillholeTraces(scene);
  traces.render([plannedHole()]);

  loader.fitCameraToData();
  camera.updateMatrixWorld(true);

  // Framing the box's eight corners centres an empty box: its lower corners
  // span the whole footprint at the depth of the deepest hole, so they project
  // below anything real and shove the visible geometry up the screen. Measured
  // in the app at NDC Y centred on +0.32 -- visibly high. The fit works from
  // sampled vertices now, so what's on screen is what gets centred.
  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (const point of loader.visiblePoints()) {
    const ndc = point.clone().project(camera);
    minX = Math.min(minX, ndc.x); maxX = Math.max(maxX, ndc.x);
    minY = Math.min(minY, ndc.y); maxY = Math.max(maxY, ndc.y);
  }

  const centreX = (minX + maxX) / 2;
  const centreY = (minY + maxY) / 2;
  assert.ok(Math.abs(centreX) < 0.1, `geometry should be centred horizontally (at ${centreX.toFixed(2)})`);
  assert.ok(Math.abs(centreY) < 0.1, `geometry should be centred vertically (at ${centreY.toFixed(2)})`);

  const fill = Math.max(maxX - minX, maxY - minY) / 2;
  assert.ok(fill > 0.8, `geometry should fill the frame (fills ${fill.toFixed(2)})`);
});
