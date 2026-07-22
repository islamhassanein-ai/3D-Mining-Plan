import * as THREE from 'three';

// 3D hover feedback for drillholes: hovering any part of a hole (its trace
// line or an assay/lithology interval) fades in a translucent gold "glow
// sleeve" along that hole's full trace and shows a cursor tooltip with the
// hole ID and its peak Au grade. This previews what a click will inspect --
// reducing misclicks and letting a geologist scan holes without opening the
// inspector for each one.
export class SceneHover {
  constructor(viewport) {
    this.viewport = viewport;
    this.dom = viewport.renderer.domElement;

    this.raycaster = new THREE.Raycaster();
    this.raycaster.params.Line.threshold = 10.0;
    this.pointer = new THREE.Vector2();

    // collar_id -> { holeId, peak, points: THREE.Vector3[] }
    this.holes = new Map();

    this.hoveredCollar = null;
    this.currentOpacity = 0.0;
    this.targetOpacity = 0.0;

    this.group = new THREE.Group();
    this.group.name = 'hover-highlight';
    this.viewport.scene.add(this.group);
    this.sleeve = null;

    this._buildTooltip();

    this.onMove = this.onMove.bind(this);
    this.onLeave = this.onLeave.bind(this);
    this.dom.addEventListener('pointermove', this.onMove);
    this.dom.addEventListener('pointerleave', this.onLeave);
  }

  _buildTooltip() {
    const el = document.createElement('div');
    el.className = 'hover-tooltip';
    el.style.cssText = [
      'position:absolute', 'pointer-events:none', 'z-index:6',
      'background:rgba(13,21,36,0.94)', 'border:1px solid rgba(212,175,55,0.55)',
      'border-radius:7px', 'padding:7px 10px', 'font-size:11.5px',
      'color:#e8edf5', 'white-space:nowrap', 'opacity:0',
      'transition:opacity 0.12s ease', 'box-shadow:0 6px 18px rgba(0,0,0,0.45)',
      'transform:translate(14px, 14px)'
    ].join(';');
    // The 3D canvas sits in a position:relative container (#viewport-3d).
    (this.dom.parentElement || document.body).appendChild(el);
    this.tooltip = el;
  }

  // Feeds per-hole trace geometry + peak grade. Call on each scene load.
  setData(drillholes) {
    this.holes.clear();
    for (const dh of (drillholes || [])) {
      let peak = 0;
      for (const a of dh.assays) if (a.grade_value > peak) peak = a.grade_value;
      // Map to Three.js Y-up (Easting -> X, Elevation -> Y, Northing -> Z),
      // matching drillhole_traces.js.
      const points = (dh.trace || []).map(p => new THREE.Vector3(p.x, p.z, p.y));
      this.holes.set(dh.collar_id, { holeId: dh.hole_id, peak, points });
    }
    this._clearHover();
  }

  onLeave() { this._clearHover(); }

  _clearHover() {
    this.hoveredCollar = null;
    this.targetOpacity = 0.0;
    if (this.tooltip) this.tooltip.style.opacity = '0';
    this.dom.style.cursor = '';
  }

  onMove(event) {
    // Skip while the user is dragging (orbiting/panning) to avoid flicker.
    if (event.buttons !== 0) { this._clearHover(); return; }

    const rect = this.dom.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.viewport.camera);

    const hits = this.raycaster.intersectObjects(this.viewport.scene.children, true);
    let collarId = null;
    for (const hit of hits) {
      const obj = hit.object;
      if (obj.parent === this.group) continue; // ignore our own highlight
      if (obj.isInstancedMesh && obj.userData && obj.userData.intervals) {
        const iv = obj.userData.intervals[hit.instanceId];
        if (iv) { collarId = iv.collar_id; break; }
      }
      if (obj.isLine && obj.userData && obj.userData.type === 'drillhole_trace') {
        collarId = obj.userData.collar_id; break;
      }
    }

    if (collarId && this.holes.has(collarId)) {
      if (collarId !== this.hoveredCollar) {
        this.hoveredCollar = collarId;
        this._buildSleeve(this.holes.get(collarId));
      }
      this.targetOpacity = 0.55;
      this.dom.style.cursor = 'pointer';
      this._showTooltip(event, this.holes.get(collarId));
    } else {
      this._clearHover();
    }
  }

  _buildSleeve(hole) {
    this._disposeSleeve();
    if (!hole.points || hole.points.length < 2) return;
    const curve = new THREE.CatmullRomCurve3(hole.points);
    const geometry = new THREE.TubeGeometry(
      curve, Math.max(hole.points.length * 2, 8), 1.15, 10, false
    );
    const material = new THREE.MeshBasicMaterial({
      color: 0xd4af37,
      transparent: true,
      opacity: 0.0,
      depthWrite: false,
      side: THREE.DoubleSide
    });
    this.sleeve = new THREE.Mesh(geometry, material);
    this.sleeve.renderOrder = 5;
    this.group.add(this.sleeve);
    this.currentOpacity = 0.0;
  }

  _disposeSleeve() {
    if (this.sleeve) {
      this.group.remove(this.sleeve);
      this.sleeve.geometry.dispose();
      this.sleeve.material.dispose();
      this.sleeve = null;
    }
  }

  _showTooltip(event, hole) {
    if (!this.tooltip) return;
    const rect = this.dom.getBoundingClientRect();
    this.tooltip.style.left = (event.clientX - rect.left) + 'px';
    this.tooltip.style.top = (event.clientY - rect.top) + 'px';
    this.tooltip.innerHTML =
      `<b style="color:#e8c76b">${hole.holeId}</b>` +
      `<span style="color:#93a2ba"> &middot; peak </span>` +
      `<b>${hole.peak.toFixed(2)} g/t</b>`;
    this.tooltip.style.opacity = '1';
  }

  // Called from the render loop: eases the sleeve opacity toward its target
  // so highlights fade in/out smoothly instead of popping.
  update() {
    this.currentOpacity += (this.targetOpacity - this.currentOpacity) * 0.18;
    if (this.sleeve) {
      this.sleeve.material.opacity = this.currentOpacity;
      if (this.currentOpacity < 0.01 && this.targetOpacity === 0.0) {
        this._disposeSleeve();
      }
    }
  }

  dispose() {
    this.dom.removeEventListener('pointermove', this.onMove);
    this.dom.removeEventListener('pointerleave', this.onLeave);
    this._disposeSleeve();
    if (this.tooltip && this.tooltip.parentElement) this.tooltip.parentElement.removeChild(this.tooltip);
    if (this.group.parent) this.group.parent.remove(this.group);
  }
}
