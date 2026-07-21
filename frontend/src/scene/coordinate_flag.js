import * as THREE from 'three';

// A QGIS-style "flash geometry" marker: pinpoints a coordinate with a
// small point plus two expanding, fading rings (like QGIS's map canvas
// flash on "Zoom to coordinate"). Everything -- point and rings -- fades
// out and is removed once the flash finishes; nothing is left behind.
export class CoordinateFlag {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'coordinate-flag';
    this.group.visible = false;
    this.scene.add(this.group);

    this.transientObjects = [];
    this._animId = null;
  }

  // Places a temporary marker at (x, y, z) and flashes twice, then the
  // whole marker disappears -- mirrors QGIS's "flash" feedback on Zoom to
  // Coordinate, which doesn't leave a permanent pin behind.
  flashAt(x, y, z) {
    this.group.position.set(x, y, z);
    this.group.visible = true;

    this._clearTransient();

    // Center point
    const pointGeom = new THREE.SphereGeometry(0.6, 16, 16);
    const pointMat = new THREE.MeshBasicMaterial({ color: 0xff3b30, transparent: true, opacity: 1 });
    const point = new THREE.Mesh(pointGeom, pointMat);
    point.userData = { kind: 'point', elapsed: 0, duration: 1300 };
    this.group.add(point);
    this.transientObjects.push(point);

    // Two expanding, fading rings (flash #1 and flash #2)
    const ringGeom = new THREE.RingGeometry(1, 1.35, 32);
    for (let i = 0; i < 2; i++) {
      const material = new THREE.MeshBasicMaterial({
        color: 0xff3b30,
        transparent: true,
        opacity: 1,
        side: THREE.DoubleSide,
        depthWrite: false
      });
      const ring = new THREE.Mesh(ringGeom, material);
      ring.rotation.x = -Math.PI / 2; // lie flat on the ground plane
      ring.userData = { kind: 'ring', elapsed: -i * 350, duration: 800 };
      ring.scale.setScalar(0.01);
      this.group.add(ring);
      this.transientObjects.push(ring);
    }

    if (this._animId) cancelAnimationFrame(this._animId);
    this._lastTime = performance.now();
    this._animate();
  }

  _animate() {
    const now = performance.now();
    const dt = now - this._lastTime;
    this._lastTime = now;
    let anyActive = false;

    for (const obj of this.transientObjects) {
      obj.userData.elapsed += dt;
      if (obj.userData.elapsed < 0) { anyActive = true; continue; }
      const t = Math.min(obj.userData.elapsed / obj.userData.duration, 1);

      if (obj.userData.kind === 'ring') {
        obj.scale.setScalar(1 + t * 22);
        obj.material.opacity = 1 - t;
      } else {
        // Point: brief hold then fade out entirely.
        obj.material.opacity = t < 0.6 ? 1 : 1 - (t - 0.6) / 0.4;
      }
      if (t < 1) anyActive = true;
    }

    if (anyActive) {
      this._animId = requestAnimationFrame(() => this._animate());
    } else {
      this._clearTransient();
      this.group.visible = false;
      this._animId = null;
    }
  }

  _clearTransient() {
    this.transientObjects.forEach(o => {
      this.group.remove(o);
      o.geometry.dispose();
      o.material.dispose();
    });
    this.transientObjects = [];
  }

  clear() {
    if (this._animId) cancelAnimationFrame(this._animId);
    this._clearTransient();
    this.group.visible = false;
  }

  dispose() {
    this.clear();
    this.scene.remove(this.group);
  }
}
