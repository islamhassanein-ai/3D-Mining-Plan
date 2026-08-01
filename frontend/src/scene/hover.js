import * as THREE from 'three';

// 3D hover feedback for drillholes: hovering any part of a hole (its trace
// line or an assay/lithology interval) fades in a translucent gold "glow
// sleeve" along that hole's full trace and shows a cursor tooltip with the
// hole ID and its peak Au grade. This previews what a click will inspect --
// reducing misclicks and letting a geologist scan holes without opening the
// inspector for each one.
// Peak opacity of the gold glow sleeve. Deliberately faint: the sleeve's job
// is to say "this is the hole you're pointing at", and at the previous 0.55 it
// washed out the grade colours underneath -- which are the thing the geologist
// is actually reading while they scan.
const HIGHLIGHT_OPACITY = 0.22;

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
    if (!document.getElementById('hover-tooltip-styles')) {
      const style = document.createElement('style');
      style.id = 'hover-tooltip-styles';
      style.textContent = `
        .hover-tooltip .ht-title {
          font-weight: 800; font-size: 12.5px; letter-spacing: 0.2px;
          margin-bottom: 5px; padding-bottom: 4px;
          border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .hover-tooltip .ht-tag {
          font-size: 8.5px; font-weight: 700; letter-spacing: 0.6px;
          vertical-align: middle; padding: 1px 4px; border-radius: 3px;
          background: rgba(103,232,249,0.16); border: 1px solid rgba(103,232,249,0.4);
        }
        .hover-tooltip .ht-row {
          display: flex; justify-content: space-between; gap: 16px; padding: 1.5px 0;
        }
        .hover-tooltip .ht-l { color: var(--text-muted, #93a2ba); }
        .hover-tooltip .ht-v { font-weight: 600; font-variant-numeric: tabular-nums; }
      `;
      document.head.appendChild(style);
    }

    const el = document.createElement('div');
    el.className = 'hover-tooltip';
    el.style.cssText = [
      'position:absolute', 'pointer-events:none', 'z-index:6',
      'background:rgba(13,21,36,0.96)', 'border:1px solid rgba(212,175,55,0.55)',
      'border-radius:8px', 'padding:8px 11px', 'font-size:11.5px',
      'color:#e8edf5', 'white-space:nowrap', 'opacity:0', 'min-width:170px',
      'transition:opacity 0.12s ease', 'box-shadow:0 8px 22px rgba(0,0,0,0.5)',
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
      // Unsampled intervals have a null grade -- excluded so they never
      // contribute to (or zero out) the peak.
      let peak = null;
      for (const a of dh.assays) {
        const g = Number(a.grade_value);
        if (Number.isFinite(g) && (peak === null || g > peak)) peak = g;
      }
      // Map to Three.js Y-up (Easting -> X, Elevation -> Y, Northing -> Z),
      // matching drillhole_traces.js.
      const points = (dh.trace || []).map(p => new THREE.Vector3(p.x, p.z, p.y));
      this.holes.set(dh.collar_id, {
        holeId: dh.hole_id,
        peak,
        points,
        // Downhole depth of each trace point, so a 3D hit position can be
        // turned back into a depth (see _depthAtPoint).
        depths: (dh.trace || []).map(p => p.depth),
        // Sorted once here so the per-frame lookup is a scan of an already
        // ordered list rather than a sort on every pointer move.
        intervals: [...(dh.assays || [])].sort((a, b) => a.from_depth - b.from_depth),
        isPlanned: dh.hole_status === 'planned',
        totalDepth: dh.total_depth ?? null,
        collar: { easting: dh.easting, northing: dh.northing, elevation: dh.elevation },
      });
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
    let interval = null;
    let depthAtCursor = null;

    // Two passes, because the drillhole trace line is picked with a 10 m
    // threshold (below) so that a 1px line stays grabbable. That fat radius
    // means the line frequently reports a *nearer* hit than the tube drawn
    // over it -- so taking the first hit in distance order would report
    // "somewhere on this hole" even when the cursor is squarely on a sample.
    // Resolving a specific interval always wins; the line is the fallback.
    for (const hit of hits) {
      const obj = hit.object;
      if (obj.parent === this.group) continue; // ignore our own highlight
      // Continuous assay tube: the hole owns the mesh, so its id is right
      // there -- and `intervalRefs` is indexed by vertex, so any corner of the
      // hit triangle identifies the exact sample the cursor is over.
      if (obj.userData && obj.userData.intervalRefs && hit.face) {
        const iv = obj.userData.intervalRefs[hit.face.a];
        if (iv) { collarId = obj.userData.collar_id; interval = iv; break; }
      }
      if (obj.isInstancedMesh && obj.userData && obj.userData.intervals) {
        const iv = obj.userData.intervals[hit.instanceId];
        if (iv) { collarId = iv.collar_id; interval = iv; break; }
      }
    }

    if (!collarId) {
      for (const hit of hits) {
        const obj = hit.object;
        if (obj.parent === this.group) continue;
        const ud = obj.userData;
        const isTrace = ud && ud.type === 'drillhole_trace' && ud.collar_id;
        if (!isTrace && !(ud && ud.intervalRefs)) continue;
        collarId = ud.collar_id;
        // The tube is only ~0.8 m across, which is a handful of pixels at
        // survey framing, while the trace line is picked with a 10 m
        // threshold -- so at anything but close zoom the pick lands on the
        // line. Rather than degrade to "somewhere on this hole", convert the
        // 3D hit position back to a downhole depth and look up the sample
        // covering it. The user gets Hole / Depth / Assay at every zoom.
        const hole = this.holes.get(collarId);
        if (hole && hit.point) {
          depthAtCursor = this._depthAtPoint(hole, hit.point);
          if (depthAtCursor !== null) {
            interval = this._intervalAtDepth(hole, depthAtCursor);
          }
        }
        break;
      }
    }

    if (collarId && this.holes.has(collarId)) {
      if (collarId !== this.hoveredCollar) {
        this.hoveredCollar = collarId;
        this._buildSleeve(this.holes.get(collarId));
      }
      this.targetOpacity = HIGHLIGHT_OPACITY;
      this.dom.style.cursor = 'pointer';
      this._showTooltip(event, this.holes.get(collarId), interval, depthAtCursor);
    } else {
      this._clearHover();
    }
  }

  /**
   * Downhole depth of the trace point closest to `point`, by projecting onto
   * each polyline segment and keeping the nearest. Returns null for a hole
   * with no usable trace.
   *
   * Walking every segment is fine here: traces are tens of stations, and this
   * only runs on pointer move over a hole that was already hit.
   */
  _depthAtPoint(hole, point) {
    const pts = hole.points;
    const depths = hole.depths;
    if (!pts || pts.length < 2 || !depths || depths.length !== pts.length) return null;

    let bestDistSq = Infinity;
    let bestDepth = null;
    const seg = new THREE.Vector3();
    const rel = new THREE.Vector3();
    const proj = new THREE.Vector3();

    for (let i = 0; i < pts.length - 1; i++) {
      seg.subVectors(pts[i + 1], pts[i]);
      const lenSq = seg.lengthSq();
      if (lenSq < 1e-9) continue;
      rel.subVectors(point, pts[i]);
      const t = Math.min(1, Math.max(0, rel.dot(seg) / lenSq));
      proj.copy(pts[i]).addScaledVector(seg, t);
      const distSq = proj.distanceToSquared(point);
      if (distSq < bestDistSq) {
        bestDistSq = distSq;
        bestDepth = depths[i] + t * (depths[i + 1] - depths[i]);
      }
    }

    return bestDepth;
  }

  /**
   * The sample covering `depth`, or null where the hole was not assayed --
   * an unsampled stretch has to report as such, never as the nearest result.
   */
  _intervalAtDepth(hole, depth) {
    for (const iv of (hole.intervals || [])) {
      if (depth >= iv.from_depth && depth <= iv.to_depth) return iv;
    }
    return null;
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

  // Rows read Hole / Coords / Depth / Assay, matching the reference viewer's
  // hover card. When the cursor is over a specific sampled interval its own
  // From-To and grade are shown; over bare trace line it falls back to
  // whole-hole facts (peak grade, end of hole), since there is no one sample
  // to report there.
  _showTooltip(event, hole, interval, depthAtCursor) {
    if (!this.tooltip) return;
    const rect = this.dom.getBoundingClientRect();
    this.tooltip.style.left = (event.clientX - rect.left) + 'px';
    this.tooltip.style.top = (event.clientY - rect.top) + 'px';

    const row = (label, value, color) =>
      `<div class="ht-row"><span class="ht-l">${label}</span>` +
      `<span class="ht-v"${color ? ` style="color:${color}"` : ''}>${value}</span></div>`;

    const titleColor = hole.isPlanned ? '#67e8f9' : '#e8c76b';
    let html =
      `<div class="ht-title" style="color:${titleColor}">${hole.holeId}` +
      (hole.isPlanned ? ' <span class="ht-tag">PLANNED</span>' : '') +
      `</div>`;

    if (hole.collar) {
      html += row('Coords',
        `${hole.collar.easting.toFixed(0)}, ${hole.collar.northing.toFixed(0)}`);
    }

    if (interval) {
      html += row('Depth',
        `${Number(interval.from_depth).toFixed(1)} &ndash; ${Number(interval.to_depth).toFixed(1)} m`);
      const grade = Number(interval.grade_value);
      html += Number.isFinite(grade)
        ? row('Assay', `${grade.toFixed(2)} ${interval.grade_unit || 'g/t'} Au`, interval.color)
        : row('Assay', 'No sample', '#93a2ba');
      if (interval.sample_id) html += row('Sample', interval.sample_id);
    } else if (depthAtCursor !== null && depthAtCursor !== undefined) {
      // On the hole, but at a depth with no assay row -- say so rather than
      // reporting the nearest result, which would be a false statement about
      // rock that was never sampled.
      html += row('Depth', `${depthAtCursor.toFixed(1)} m`);
      html += row('Assay', 'Not sampled', '#93a2ba');
    } else {
      html += row('Peak',
        hole.peak === null ? 'no assays' : `${hole.peak.toFixed(2)} g/t Au`,
        hole.peak === null ? '#93a2ba' : undefined);
      if (hole.totalDepth != null) {
        html += row('End of hole', `${hole.totalDepth.toFixed(1)} m`);
      }
    }

    this.tooltip.innerHTML = html;
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
