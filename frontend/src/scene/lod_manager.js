import * as THREE from 'three';

export class LodManager {
  constructor(camera, tracesRenderer, assaysRenderer, lithologiesRenderer) {
    this.camera = camera;
    this.tracesRenderer = tracesRenderer;
    this.assaysRenderer = assaysRenderer;
    this.lithologiesRenderer = lithologiesRenderer;
    // LOD only activates once the combined assay+lithology interval count
    // exceeds this threshold (research.md Decision 4) -- below it, rendering
    // must be identical to feature 003 (no distance-based toggling at all).
    this.activationThreshold = 20000;
    this.enabled = false;
    this.threshold = 400; // meters threshold for high detail (3D cylinders)
    this.drillholes = [];
    this.lastUpdateTime = 0;
  }

  setDrillholes(drillholes) {
    if (!drillholes) {
      this.drillholes = [];
      this.enabled = false;
      return;
    }
    this.drillholes = drillholes.map(dh => ({
      collar_id: dh.collar_id,
      center: new THREE.Vector3(dh.easting, dh.elevation, dh.northing)
    }));

    const intervalCount = drillholes.reduce(
      (sum, dh) => sum + (dh.assays ? dh.assays.length : 0) + (dh.lithologies ? dh.lithologies.length : 0),
      0
    );
    this.enabled = intervalCount > this.activationThreshold;

    if (!this.enabled) {
      // Below threshold: force everything back to full detail (in case a
      // previous, larger project had LOD engaged) and skip toggling entirely.
      if (this.tracesRenderer) {
        for (const line of this.tracesRenderer.tracesMap.values()) {
          line.visible = true;
        }
      }
      if (this.assaysRenderer && typeof this.assaysRenderer.setLodStates === 'function') {
        this.assaysRenderer.setLodStates(null);
      }
      if (this.lithologiesRenderer && typeof this.lithologiesRenderer.setLodStates === 'function') {
        this.lithologiesRenderer.setLodStates(null);
      }
    }
  }

  update() {
    if (!this.enabled || this.drillholes.length === 0) return;
    
    const now = performance.now();
    if (now - this.lastUpdateTime < 150) return; // throttle updates to ~7 FPS for performance
    this.lastUpdateTime = now;

    const camPos = this.camera.position;
    const lodStates = new Map();

    for (const dh of this.drillholes) {
      const dist = camPos.distanceTo(dh.center);
      const isClose = dist <= this.threshold;
      lodStates.set(dh.collar_id, isClose);

      // Show low-detail trace lines if far away, hide if close
      if (this.tracesRenderer) {
        const line = this.tracesRenderer.tracesMap.get(dh.collar_id);
        if (line) {
          line.visible = !isClose;
        }
      }
    }

    // Toggle 3D cylinder instances based on proximity
    if (this.assaysRenderer && typeof this.assaysRenderer.setLodStates === 'function') {
      this.assaysRenderer.setLodStates(lodStates);
    }
    if (this.lithologiesRenderer && typeof this.lithologiesRenderer.setLodStates === 'function') {
      this.lithologiesRenderer.setLodStates(lodStates);
    }
  }

  setThreshold(val) {
    this.threshold = Number(val);
    this.lastUpdateTime = 0; // force update next frame
  }
}
