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
});

test('fitCameraToData frames the data and records a home pose', () => {
  const { camera, controls, loader, scene } = makeLoader();

  const traces = new DrillholeTraces(scene);
  traces.render([plannedHole()]);
  scene.add(new THREE.GridHelper(5000, 100));

  loader.fitCameraToData();

  assert.ok(controls.home, 'a home pose must be stored for Reset Camera');

  // Every corner of the data must land inside the frustum, and the fit must be
  // tight enough that the data actually fills it -- the previous fit left the
  // model at roughly half the frame.
  camera.updateMatrixWorld(true);
  const bounds = loader.visibleBounds();
  let maxAbs = 0;
  for (const x of [bounds.min.x, bounds.max.x]) {
    for (const y of [bounds.min.y, bounds.max.y]) {
      for (const z of [bounds.min.z, bounds.max.z]) {
        const ndc = new THREE.Vector3(x, y, z).project(camera);
        assert.ok(
          Math.abs(ndc.x) <= 1 && Math.abs(ndc.y) <= 1,
          `corner (${x}, ${y}, ${z}) falls outside the viewport`
        );
        maxAbs = Math.max(maxAbs, Math.abs(ndc.x), Math.abs(ndc.y));
      }
    }
  }
  assert.ok(maxAbs > 0.8, `data should fill the frame (widest corner at ${maxAbs.toFixed(2)})`);
});
