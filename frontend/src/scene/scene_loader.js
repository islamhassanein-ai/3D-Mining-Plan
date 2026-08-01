import * as THREE from 'three';

// Two control points closer together than this (in metres, plan view) are
// treated as the same location. Delaunator degenerates on coincident inputs,
// and trench channel samples are often logged a fraction of a metre apart,
// which would otherwise produce slivers instead of triangles.
const SURFACE_POINT_MERGE_TOLERANCE = 2.0;

// Three.js helper objects, excluded from the camera fit -- see visibleBounds.
const HELPER_TYPES = new Set(['GridHelper', 'AxesHelper', 'Box3Helper']);

// Vertices sampled per object when framing the camera. Enough to trace out a
// silhouette faithfully, few enough that a 100k-vertex terrain mesh doesn't
// make a layer toggle stutter.
const SAMPLES_PER_OBJECT = 240;

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

    this.eachFittableObject((obj) => {
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
   * Visits every object that should influence the camera fit.
   *
   * Reference geometry is excluded. The grid helper spans 5 km, so letting it
   * in frames the grid and shrinks an 80 m prospect to a few pixels -- which
   * is exactly what the static export viewer did, since it adds its helpers
   * without the excludeFromFit flag. Checking the type as well as the flag
   * means no scene can reintroduce this by forgetting to tag a helper.
   * (Three.js gives helpers no `isX` flag, but it does set `.type`.)
   */
  eachFittableObject(visit) {
    // World matrices are normally refreshed by the renderer, so an object
    // added since the last frame still carries an identity matrix. Most
    // renderers here bake world coordinates straight into their vertices and
    // don't notice, but anything placed via .position -- the planned-hole
    // collar marker -- would be read at the world origin. On a UTM site that
    // stretches the bounds from the data out to (0,0,0), millions of metres,
    // and the fit parks the camera so far away the scene looks empty.
    //
    // This lives here, in the one walk both visibleBounds and visiblePoints
    // share, precisely so neither can be refactored out from under it.
    this.scene.updateMatrixWorld(true);

    this.scene.traverse((obj) => {
      if (!obj.isMesh && !obj.isLine && !obj.isPoints) return;
      // visible=false anywhere up the chain removes the whole subtree.
      for (let node = obj; node; node = node.parent) {
        if (node.visible === false) return;
      }
      if (HELPER_TYPES.has(obj.type)) return;
      // Sprites (labels) and the hover sleeve are decoration that follows the
      // data; including them would bias the fit.
      if (obj.userData && obj.userData.excludeFromFit) return;
      if (!obj.geometry) return;
      visit(obj);
    });
  }

  /**
   * A sample of the actual vertices on screen, in world space.
   *
   * Framing against the bounding box's eight corners centres an empty box
   * rather than the model. The box's lower corners sit under the whole
   * horizontal footprint, but the deepest hole is only at one spot in it, so
   * those corners project below anything real and shove the visible geometry
   * up the screen -- measured at NDC Y -0.30..+0.93, centred at +0.32, when
   * the box itself was centred. Sampling real vertices frames what the user
   * can actually see.
   *
   * Strided per object so a dense terrain mesh can't drown out a drill trace,
   * and capped so this stays cheap enough to run on every layer toggle.
   */
  visiblePoints() {
    const points = [];
    const vertex = new THREE.Vector3();

    this.eachFittableObject((obj) => {
      const position = obj.geometry.getAttribute('position');
      if (!position || !position.count) return;

      const stride = Math.max(1, Math.ceil(position.count / SAMPLES_PER_OBJECT));
      for (let i = 0; i < position.count; i += stride) {
        vertex.fromBufferAttribute(position, i).applyMatrix4(obj.matrixWorld);
        if (!Number.isFinite(vertex.x) || !Number.isFinite(vertex.y) ||
            !Number.isFinite(vertex.z)) continue;
        points.push(vertex.clone());
      }
      // Always include the last vertex: a stride that doesn't divide the count
      // evenly would otherwise drop the end of a trace, which is often the
      // deepest point in the scene.
      vertex.fromBufferAttribute(position, position.count - 1).applyMatrix4(obj.matrixWorld);
      if (Number.isFinite(vertex.x)) points.push(vertex.clone());
    });

    return points;
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
   * It frames a sample of the real vertices (visiblePoints) rather than the
   * bounding box, because the box is not where the model is: its lower
   * corners span the full horizontal footprint at the depth of the deepest
   * hole, so they project below any actual geometry and push everything
   * visible up the screen.
   *
   * For each sampled point: with the camera at `aim + eye * t` looking back
   * down `eye`, a point's offset q from the aim sits at depth (t - q.eye)
   * with screen offsets q.right and q.up. Keeping it inside the frustum needs
   *
   *     t >= q.eye + |q.right| / tan(fovX/2)
   *     t >= q.eye + |q.up|    / tan(fovY/2)
   *
   * and the first estimate is the largest such t. Solving per point (rather
   * than per axis, or against a circumscribed bounding sphere) is what makes
   * the framing tight from the isometric angle -- an axis-aligned estimate is
   * wrong the moment the view direction isn't axis-aligned, and a bounding
   * sphere always overshoots on a site that is wide and shallow.
   */
  fitCameraToData() {
    const points = this.visiblePoints();
    if (!points.length) return;

    // Centroid of the sample, as the starting aim. The refine loop moves it
    // onto the projected centre from there.
    const center = new THREE.Vector3();
    for (const point of points) center.add(point);
    center.divideScalar(points.length);

    const camera = this.controls.camera;
    const eye = SceneLoader.ISO_EYE;
    // Frustum half-angles. camera.fov is the vertical one.
    const tanY = Math.tan((camera.fov * Math.PI / 180) / 2);
    const tanX = tanY * camera.aspect;

    // Screen-space basis orthogonal to the view direction. World up is +Y
    // (elevation), and eye is never parallel to it at the isometric angle.
    const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), eye).normalize();
    const up = new THREE.Vector3().crossVectors(eye, right).normalize();

    // First guess: the distance at which every sample fits under a *parallel*
    // projection. It always overshoots, which is what we want -- the refine
    // loop below only ever pulls in.
    const target = center.clone();
    const q = new THREE.Vector3();
    let distance = 0;
    for (const point of points) {
      q.subVectors(point, target);
      const along = q.dot(eye);
      distance = Math.max(
        distance,
        along + Math.abs(q.dot(right)) / tanX,
        along + Math.abs(q.dot(up)) / tanY
      );
    }
    if (!Number.isFinite(distance) || distance <= 0) distance = 40;

    // Refine against the real perspective projection. A parallel estimate is
    // wrong in two ways that both show on screen: near points project wider
    // than far ones, so the fit is looser than it needs to be, and the
    // silhouette's centre is not the world centre, so the model sits off to
    // one side. Each pass re-centres the aim on the projected midpoint and
    // rescales the distance by how much of the frame is actually filled.
    // Four passes converge to within a fraction of a percent.
    const projected = new THREE.Vector3();
    for (let pass = 0; pass < 4; pass++) {
      camera.position.copy(target).addScaledVector(eye, distance);
      camera.lookAt(target);
      camera.updateMatrixWorld(true);
      camera.updateProjectionMatrix();

      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      let behind = false;
      for (const point of points) {
        projected.copy(point).project(camera);
        // A point behind the near plane projects nonsensically; if that
        // happens the estimate is already inside the model, so stop refining
        // and keep the last good distance.
        if (projected.z > 1) { behind = true; break; }
        if (projected.x < minX) minX = projected.x;
        if (projected.x > maxX) maxX = projected.x;
        if (projected.y < minY) minY = projected.y;
        if (projected.y > maxY) maxY = projected.y;
      }
      if (behind) break;

      // Slide the aim point so the silhouette centres. At the target's depth
      // one NDC unit spans distance*tan(halfAngle) in world units.
      const dx = (minX + maxX) / 2;
      const dy = (minY + maxY) / 2;
      target.addScaledVector(right, dx * distance * tanX)
            .addScaledVector(up, dy * distance * tanY);

      // Then pull in (or push out) so the wider axis just fills the frame.
      const fill = Math.max((maxX - minX) / 2, (maxY - minY) / 2);
      if (fill > 1e-4) distance *= fill;
    }

    // Small breathing room so nothing sits flush against the viewport edge.
    distance *= 1.06;
    if (!Number.isFinite(distance) || distance < 15) distance = 15;

    camera.position.copy(target).addScaledVector(eye, distance);
    this.controls.setTarget(target);
    this.controls.update();

    this.controls.storeHome();
  }
}
