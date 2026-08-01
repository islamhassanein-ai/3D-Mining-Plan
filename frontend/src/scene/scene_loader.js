import * as THREE from 'three';

// Two control points closer together than this (in metres, plan view) are
// treated as the same location. Delaunator degenerates on coincident inputs,
// and trench channel samples are often logged a fraction of a metre apart,
// which would otherwise produce slivers instead of triangles.
const SURFACE_POINT_MERGE_TOLERANCE = 2.0;

/**
 * Every point in the project whose elevation was actually surveyed on the
 * ground: drill collars, trench channel samples, and structural stations.
 * These are the control points a derived topography surface is fitted to.
 *
 * Only surface data qualifies -- downhole trace points are below ground, so
 * including them would drag the interpolated surface down into the rock.
 */
function collectSurfaceControlPoints(data) {
  const merged = new Map();

  const add = (e, n, el) => {
    if (!Number.isFinite(e) || !Number.isFinite(n) || !Number.isFinite(el)) return;
    // Snap to a grid at the merge tolerance; first point in a cell wins.
    const key = `${Math.round(e / SURFACE_POINT_MERGE_TOLERANCE)}:` +
                `${Math.round(n / SURFACE_POINT_MERGE_TOLERANCE)}`;
    if (!merged.has(key)) merged.set(key, { e, n, el });
  };

  for (const dh of (data.drillholes || [])) {
    add(dh.easting, dh.northing, dh.elevation);
  }
  // `trenches` is a flat list of channel-sample points (one row per sample,
  // grouped by trench_id downstream), not a list of trench objects.
  for (const pt of (data.trenches || [])) {
    add(pt.easting, pt.northing, pt.elevation);
  }
  for (const sr of (data.structural_readings || [])) {
    add(sr.easting, sr.northing, sr.elevation);
  }

  return [...merged.values()];
}

export class SceneLoader {
  constructor(scene, controls, tracesRenderer, assaysRenderer, lithologiesRenderer, topographyRenderer, trenchesRenderer, wireframesRenderer, structuralRenderer, lodManager, boreholeLabelsRenderer, trenchLabelsRenderer) {
    this.scene = scene;
    this.controls = controls;
    this.tracesRenderer = tracesRenderer;
    this.assaysRenderer = assaysRenderer;
    this.lithologiesRenderer = lithologiesRenderer;
    this.topographyRenderer = topographyRenderer;
    this.trenchesRenderer = trenchesRenderer;
    this.wireframesRenderer = wireframesRenderer;
    this.structuralRenderer = structuralRenderer;
    this.lodManager = lodManager;
    this.boreholeLabelsRenderer = boreholeLabelsRenderer;
    this.trenchLabelsRenderer = trenchLabelsRenderer;
    this.loading = false;
  }

  async load(dataSource) {
    if (this.loading) return;
    this.loading = true;

    try {
      const data = await dataSource.getScene();

      // Inject wireframe resolver for this load
      if (this.wireframesRenderer) {
        this.wireframesRenderer.resolveGeometry = w => dataSource.getWireframeGeometry(w);
      }

      // Topography: resolve via data source, render via renderPoints. With no
      // uploaded survey, fall back to a surface interpolated from the
      // project's own surveyed points so the scene still has ground.
      this.surfaceDerived = false;
      if (this.topographyRenderer) {
        this.topographyRenderer.clear();
        const points = await dataSource.getTopographyPoints(data.topography_ref || null);
        if (points && points.length > 0) {
          this.topographyRenderer.renderPoints(points);
        } else {
          const derived = collectSurfaceControlPoints(data);
          this.surfaceDerived = this.topographyRenderer.renderDerived(derived);
        }
        // Null out the ref so renderScene's loadAndRender is skipped
        data.topography_ref = null;
      }

      await this.renderScene(data);
      this.loading = false;
      return data;
    } catch (err) {
      this.loading = false;
      console.error('Failed to load scene:', err);
      throw err;
    }
  }

  async renderScene(data) {
    // 1. Render elements
    this.tracesRenderer.render(data.drillholes);
    this.assaysRenderer.render(data.drillholes);
    this.lithologiesRenderer.render(data.drillholes);

    // Only when a file ref actually survived load(). loadAndRender() clears
    // the group before it looks at its argument, so calling it with null
    // wipes the surface that load() just built -- which silently deleted the
    // topography on every scene load, uploaded or derived.
    if (this.topographyRenderer && data.topography_ref) {
      await this.topographyRenderer.loadAndRender(data.topography_ref);
    }
    if (this.trenchesRenderer) this.trenchesRenderer.render(data.trenches, data.drillholes);
    if (this.wireframesRenderer) await this.wireframesRenderer.render(data.wireframes);
    if (this.structuralRenderer) this.structuralRenderer.render(data.structural_readings);
    if (this.boreholeLabelsRenderer) this.boreholeLabelsRenderer.render(data.drillholes);
    if (this.trenchLabelsRenderer) this.trenchLabelsRenderer.render(data.trenches, data.drillholes);

    // 2. Feed LOD manager with drillhole collar positions
    if (this.lodManager) this.lodManager.setDrillholes(data.drillholes);

    // 3. Adjust camera to fit data
    this.fitCameraToData();
  }

  // Isometric eye direction, normalised. Matches the reference viewer's
  // (1.15, -1.15, 0.65) in Easting/Northing/Elevation, remapped to Three.js
  // Y-up: X = Easting, Y = Elevation, Z = Northing.
  static get ISO_EYE() {
    return new THREE.Vector3(1.15, 0.65, -1.15).normalize();
  }

  /**
   * Bounding box of everything currently VISIBLE in the scene. Layers the
   * user has switched off are excluded, so hiding topography (usually the
   * widest layer by far) tightens the framing onto what's left rather than
   * leaving the camera parked around empty ground.
   *
   * Walking the live scene graph -- instead of the raw API payload -- is what
   * makes that possible, and it also picks up trenches, veins and the derived
   * surface, none of which the old drillhole-only fit accounted for.
   */
  visibleBounds() {
    const bbox = new THREE.Box3();
    let hasPoints = false;

    this.scene.traverse((obj) => {
      if (!obj.isMesh && !obj.isLine && !obj.isPoints) return;
      // visible=false anywhere up the chain removes the whole subtree.
      for (let node = obj; node; node = node.parent) {
        if (node.visible === false) return;
      }
      // Sprites (labels) and the hover sleeve are decoration that follows the
      // data; including them would bias the fit.
      if (obj.userData && obj.userData.excludeFromFit) return;
      if (!obj.geometry) return;
      if (!obj.geometry.boundingBox) obj.geometry.computeBoundingBox();
      if (!obj.geometry.boundingBox) return;

      const box = obj.geometry.boundingBox.clone().applyMatrix4(obj.matrixWorld);
      if (!Number.isFinite(box.min.x) || !Number.isFinite(box.max.x)) return;
      bbox.union(box);
      hasPoints = true;
    });

    return hasPoints ? bbox : null;
  }

  /**
   * Frames the visible scene and records the result as the "home" camera, so
   * Reset Camera returns here rather than to a fixed angle.
   *
   * The old fit was roughly 1.8x too far out: it padded the largest single
   * axis by 1.5x, then placed the camera at (0.7, 0.7, 0.7) x that distance,
   * whose length is another 1.21x again. This solves for the exact distance
   * instead.
   *
   * Projecting each of the eight bbox corners: with the camera at
   * `center + eye * t` looking back down `eye`, a corner's offset q from the
   * centre sits at depth (t - q.eye) with screen offsets q.right and q.up.
   * Keeping it inside the frustum needs
   *
   *     t >= q.eye + |q.right| / tan(fovX/2)
   *     t >= q.eye + |q.up|    / tan(fovY/2)
   *
   * and the fit is the largest such t over all corners. Solving per corner
   * (rather than per axis, or against a circumscribed bounding sphere) is
   * what makes the framing tight from the isometric angle -- an axis-aligned
   * estimate is wrong the moment the view direction isn't axis-aligned, and a
   * bounding sphere always overshoots on a site that is wide and shallow.
   */
  fitCameraToData() {
    const bbox = this.visibleBounds();
    if (!bbox) return;

    const center = new THREE.Vector3();
    bbox.getCenter(center);

    const camera = this.controls.camera;
    const eye = SceneLoader.ISO_EYE;
    // Frustum half-angles. camera.fov is the vertical one.
    const tanY = Math.tan((camera.fov * Math.PI / 180) / 2);
    const tanX = tanY * camera.aspect;

    // Screen-space basis orthogonal to the view direction. World up is +Y
    // (elevation), and eye is never parallel to it at the isometric angle.
    const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), eye).normalize();
    const up = new THREE.Vector3().crossVectors(eye, right).normalize();

    const q = new THREE.Vector3();
    let distance = 0;
    for (const x of [bbox.min.x, bbox.max.x]) {
      for (const y of [bbox.min.y, bbox.max.y]) {
        for (const z of [bbox.min.z, bbox.max.z]) {
          q.set(x, y, z).sub(center);
          const along = q.dot(eye);
          distance = Math.max(
            distance,
            along + Math.abs(q.dot(right)) / tanX,
            along + Math.abs(q.dot(up)) / tanY
          );
        }
      }
    }

    // Small breathing room so nothing sits flush against the viewport edge.
    distance *= 1.08;
    if (!Number.isFinite(distance) || distance < 40) distance = 40;

    camera.position.copy(center).addScaledVector(eye, distance);
    this.controls.setTarget(center);
    this.controls.update();

    this.controls.storeHome();
  }
}
