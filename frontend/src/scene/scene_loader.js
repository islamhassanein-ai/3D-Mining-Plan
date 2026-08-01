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

// Breathing room so nothing sits flush against the viewport edge.
const FIT_PADDING = 1.06;

// Re-centre / re-solve rounds. Centring and distance interact, so a couple of
// rounds settle it; the distance search inside each is exact, not iterative.
const FIT_ROUNDS = 3;

// Bisection steps per round. 40 halvings take any starting bracket to far
// below single-pixel precision, and each step is a few multiplies per point.
const BISECTION_STEPS = 40;

// Closest a sampled point may sit to the camera, in metres. Keeps the
// bisection off the singularity where a point crosses the camera plane.
const MIN_CAMERA_DEPTH = 0.5;

// Floor for the camera distance, for a scene that is effectively a point.
const MIN_CAMERA_DISTANCE = 15;

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
      let box;

      if (obj.isInstancedMesh) {
        // An InstancedMesh's geometry is one unit primitive at the local
        // origin; where the copies actually are lives in the per-instance
        // matrices. Reading geometry.boundingBox therefore places the whole
        // layer at (0,0,0), which on a UTM site drags the bounds out by
        // millions of metres. InstancedMesh.computeBoundingBox walks the
        // instance matrices, which is the only correct source here.
        if (!obj.boundingBox) obj.computeBoundingBox();
        if (!obj.boundingBox) return;
        box = obj.boundingBox.clone().applyMatrix4(obj.matrixWorld);
      } else {
        if (!obj.geometry.boundingBox) obj.geometry.computeBoundingBox();
        if (!obj.geometry.boundingBox) return;
        box = obj.geometry.boundingBox.clone().applyMatrix4(obj.matrixWorld);
      }

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
      // Instanced layers (lithology) carry their real positions in the
      // per-instance matrices, not in the geometry -- see visibleBounds. The
      // translation of each instance matrix is a good representative sample:
      // one point per interval, which is exactly the granularity wanted.
      if (obj.isInstancedMesh) {
        const matrix = new THREE.Matrix4();
        const stride = Math.max(1, Math.ceil(obj.count / SAMPLES_PER_OBJECT));
        for (let i = 0; i < obj.count; i += stride) {
          obj.getMatrixAt(i, matrix);
          vertex.setFromMatrixPosition(matrix).applyMatrix4(obj.matrixWorld);
          if (Number.isFinite(vertex.x)) points.push(vertex.clone());
        }
        return;
      }

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
   * Two things make this harder than it looks.
   *
   * First, the model is not its bounding box. Framing the box's eight corners
   * centres an empty box: the lower corners span the whole horizontal
   * footprint at the depth of the deepest hole, so they project below anything
   * real and push the visible geometry up the screen (measured at NDC Y
   * centred on +0.32). So it frames a sample of the actual vertices instead.
   *
   * Second, the obvious iteration -- project, measure how much of the frame is
   * filled, multiply the distance by that -- does not converge. Halving the
   * distance more than doubles the projected size, because the points nearest
   * the camera dominate, so the correction overshoots and the estimate
   * oscillates: on one project it ran 337 -> 234 -> 310 -> 241 -> 311 -> 233,
   * and the framing you got depended on which pass it stopped at. That is why
   * some projects looked well framed and others sat at 40% of the viewport.
   *
   * Bisection is used instead. "Does everything fit at distance d" is
   * monotonic -- if it fits at d it fits at anything larger -- so the smallest
   * fitting distance can be found by bisection, which always converges. The
   * aim point is re-centred between rounds, since centring and distance
   * interact.
   */
  fitCameraToData() {
    const points = this.visiblePoints();
    if (!points.length) return;

    const camera = this.controls.camera;
    const eye = SceneLoader.ISO_EYE;
    // Frustum half-angles. camera.fov is the vertical one.
    const tanY = Math.tan((camera.fov * Math.PI / 180) / 2);
    const tanX = tanY * camera.aspect;

    // Screen-space basis orthogonal to the view direction. World up is +Y
    // (elevation), and eye is never parallel to it at the isometric angle.
    const right = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), eye).normalize();
    const up = new THREE.Vector3().crossVectors(eye, right).normalize();

    // Start aiming at the centroid of the sample.
    const target = new THREE.Vector3();
    for (const point of points) target.add(point);
    target.divideScalar(points.length);

    // Per-point offsets in camera axes, recomputed whenever the aim moves.
    // With these, projecting at a distance d is pure arithmetic -- no matrix
    // per point per bisection step, which is what keeps this cheap enough to
    // run on every layer toggle.
    const count = points.length;
    const along = new Float64Array(count);
    const across = new Float64Array(count);
    const vertical = new Float64Array(count);
    const offset = new THREE.Vector3();

    const projectOffsets = () => {
      for (let i = 0; i < count; i++) {
        offset.subVectors(points[i], target);
        along[i] = offset.dot(eye);
        across[i] = offset.dot(right);
        vertical[i] = offset.dot(up);
      }
    };

    // Largest |NDC| over all points at distance d, plus the NDC bounds needed
    // to re-centre. A point at or behind the camera returns Infinity, which
    // simply tells the bisection that d is too small.
    const measure = (distance) => {
      let maxAbs = 0;
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      for (let i = 0; i < count; i++) {
        const depth = distance - along[i];
        if (depth <= MIN_CAMERA_DEPTH) return { maxAbs: Infinity };
        const x = across[i] / (depth * tanX);
        const y = vertical[i] / (depth * tanY);
        if (x < minX) minX = x;
        if (x > maxX) maxX = x;
        if (y < minY) minY = y;
        if (y > maxY) maxY = y;
        const abs = Math.max(Math.abs(x), Math.abs(y));
        if (abs > maxAbs) maxAbs = abs;
      }
      return { maxAbs, centreX: (minX + maxX) / 2, centreY: (minY + maxY) / 2 };
    };

    let distance = 0;
    for (let round = 0; round < FIT_ROUNDS; round++) {
      projectOffsets();

      // An upper bound that is guaranteed to fit: the distance at which every
      // point fits under a *parallel* projection, which always overshoots a
      // perspective one. Doubled defensively so `hi` is never marginal.
      let maxAlong = -Infinity;
      let hi = 0;
      for (let i = 0; i < count; i++) {
        if (along[i] > maxAlong) maxAlong = along[i];
        hi = Math.max(
          hi,
          along[i] + Math.abs(across[i]) / tanX,
          along[i] + Math.abs(vertical[i]) / tanY
        );
      }
      hi = Math.max(hi * 2, maxAlong + 1);
      if (!Number.isFinite(hi) || hi <= 0) hi = MIN_CAMERA_DISTANCE;

      // Anything at or nearer than the frontmost point cannot fit.
      let lo = maxAlong + MIN_CAMERA_DEPTH;

      for (let step = 0; step < BISECTION_STEPS; step++) {
        const mid = (lo + hi) / 2;
        if (measure(mid).maxAbs > 1) lo = mid; else hi = mid;
      }
      distance = hi;

      // Re-centre the aim on the projected midpoint. One NDC unit spans
      // distance*tan(halfAngle) in world units at the aim's depth.
      const { centreX, centreY } = measure(distance);
      if (Number.isFinite(centreX)) {
        target.addScaledVector(right, centreX * distance * tanX)
              .addScaledVector(up, centreY * distance * tanY);
      }
    }

    distance *= FIT_PADDING;
    if (!Number.isFinite(distance) || distance < MIN_CAMERA_DISTANCE) {
      distance = MIN_CAMERA_DISTANCE;
    }

    // Final centring at the padded distance, so the framing the user sees is
    // the one that was centred.
    projectOffsets();
    const final = measure(distance);
    if (Number.isFinite(final.centreX)) {
      target.addScaledVector(right, final.centreX * distance * tanX)
            .addScaledVector(up, final.centreY * distance * tanY);
    }

    camera.position.copy(target).addScaledVector(eye, distance);
    this.controls.setTarget(target);
    this.controls.update();

    this.controls.storeHome();
  }
}
