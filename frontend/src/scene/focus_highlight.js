import * as THREE from 'three';

// Shared "look here" animation for the 3D view.
//
// Moving the camera is not, by itself, feedback: when the search bar flies to
// a hole or a log row selects a sample, the view changes but nothing says
// *which* thing was found -- on a site with thirty holes the user is left
// comparing the before and after. This draws attention to the target instead:
// a ring that expands and fades a few times, plus a steady marker that stays
// until something else is selected, so the answer is still on screen after the
// animation ends.
//
// Everything here is unlit (MeshBasicMaterial) and depth-write-free, so the
// highlight reads the same whether the target is above ground or buried inside
// the topography surface.

const PULSE_COUNT = 3;
const PULSE_SECONDS = 0.85;
// How far the ring grows, as a multiple of its base radius.
const PULSE_GROWTH = 2.6;

const HIGHLIGHT_COLOR = 0xffd21e;

export class FocusHighlight {
  constructor(scene) {
    this.scene = scene;

    this.group = new THREE.Group();
    this.group.name = 'focus-highlight';
    // Decoration that follows the data -- must never influence the camera fit.
    this.group.userData.excludeFromFit = true;
    this.scene.add(this.group);

    this.rings = [];      // active pulses
    this.marker = null;   // steady marker held after the pulses finish
    this.clock = 0;
  }

  /**
   * Pulses at a world position and leaves a steady marker there.
   * `radius` is the base size in metres -- callers scale it to the thing being
   * pointed at, so a 1 m sample and a 40 m trench both read sensibly.
   */
  focusOn(position, radius = 4) {
    this.clear();

    const base = Math.max(radius, 0.5);

    for (let i = 0; i < PULSE_COUNT; i++) {
      const geometry = new THREE.RingGeometry(base * 0.92, base, 48);
      const material = new THREE.MeshBasicMaterial({
        color: HIGHLIGHT_COLOR,
        transparent: true,
        opacity: 0,
        side: THREE.DoubleSide,
        depthWrite: false,
        depthTest: false,
      });
      const ring = new THREE.Mesh(geometry, material);
      ring.position.copy(position);
      ring.renderOrder = 20;
      // Staggered starts, so the pulses read as a repeating beat rather than
      // one thick ring.
      ring.userData.delay = i * (PULSE_SECONDS * 0.45);
      ring.userData.base = base;
      this.group.add(ring);
      this.rings.push(ring);
    }

    // The steady marker: a small billboarded disc that outlives the pulses, so
    // "which one was it" is still answerable a minute later.
    const markerGeometry = new THREE.RingGeometry(base * 0.55, base * 0.72, 40);
    const markerMaterial = new THREE.MeshBasicMaterial({
      color: HIGHLIGHT_COLOR,
      transparent: true,
      opacity: 0.85,
      side: THREE.DoubleSide,
      depthWrite: false,
      depthTest: false,
    });
    this.marker = new THREE.Mesh(markerGeometry, markerMaterial);
    this.marker.position.copy(position);
    this.marker.renderOrder = 21;
    this.group.add(this.marker);

    this.clock = 0;
  }

  /** Called from the render loop. `delta` is in seconds. */
  update(delta, camera) {
    if (!this.rings.length && !this.marker) return;
    this.clock += delta;

    for (const ring of this.rings) {
      const t = (this.clock - ring.userData.delay) / PULSE_SECONDS;
      if (t < 0 || t > 1) {
        ring.visible = false;
      } else {
        ring.visible = true;
        const scale = 1 + t * (PULSE_GROWTH - 1);
        ring.scale.setScalar(scale);
        // Fade out over the second half, so the ring is solid as it leaves the
        // marker and gone by the time it stops.
        ring.material.opacity = 0.9 * (1 - t) * (1 - t);
      }
      // Rings and marker always face the camera; a flat ring seen edge-on in
      // an orbiting view would vanish exactly when the user looks for it.
      if (camera) ring.quaternion.copy(camera.quaternion);
    }

    if (this.marker && camera) this.marker.quaternion.copy(camera.quaternion);
  }

  clear() {
    for (const child of [...this.group.children]) {
      child.geometry.dispose();
      child.material.dispose();
      this.group.remove(child);
    }
    this.rings = [];
    this.marker = null;
  }

  dispose() {
    this.clear();
    if (this.group.parent) this.group.parent.remove(this.group);
  }
}
