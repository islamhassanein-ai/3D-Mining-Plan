import * as THREE from 'three';

export class SceneSelection {
  constructor(viewportInstance, onSelectCallback) {
    this.viewport = viewportInstance; // init3DViewport result
    this.onSelect = onSelectCallback;
    
    this.raycaster = new THREE.Raycaster();
    // Add collision threshold for lines so they are easy to click
    this.raycaster.params.Line.threshold = 10.0; 
    this.pointer = new THREE.Vector2();

    this.onPointerDown = this.onPointerDown.bind(this);
    this.viewport.renderer.domElement.addEventListener('pointerdown', this.onPointerDown);
  }

  onPointerDown(event) {
    // Only select on left click (button 0)
    if (event.button !== 0) return;

    const rect = this.viewport.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.pointer, this.viewport.camera);

    // Intersect objects in scene
    const intersects = this.raycaster.intersectObjects(this.viewport.scene.children, true);

    if (intersects.length > 0) {
      // Two passes over the hits, for the same reason as hover.js: the trace
      // line is picked with a 10 m threshold so a 1px line stays clickable,
      // which routinely makes it report a nearer hit than the tube drawn over
      // it. Taking hits in plain distance order would therefore open the
      // whole-hole view when the user clicked squarely on one sample.
      // Interval hits win; the bare trace is the fallback.
      for (const hit of intersects) {
        const obj = hit.object;

        // 1a. Continuous assay tube: one mesh per hole, so the interval is
        //     resolved from the hit triangle's first vertex.
        if (obj.userData && obj.userData.intervalRefs && hit.face) {
          const interval = obj.userData.intervalRefs[hit.face.a];
          if (interval) {
            this.onSelect('interval', {
              collarId: interval.collar_id,
              holeId: interval.hole_id,
              intervalId: interval.id,
              intervalType: 'assay',
              fromDepth: interval.from_depth,
              toDepth: interval.to_depth,
              gradeValue: interval.grade_value,
              point: hit.point
            });
            return;
          }
        }

        // 1b. Lithologies are still an InstancedMesh.
        if (obj.isInstancedMesh && obj.userData && obj.userData.intervals) {
          const instanceId = hit.instanceId;
          const interval = obj.userData.intervals[instanceId];

          if (interval) {
            this.onSelect('interval', {
              collarId: interval.collar_id,
              holeId: interval.hole_id,
              intervalId: interval.id,
              intervalType: obj.userData.type === 'assay_intervals' ? 'assay' : 'lithology',
              fromDepth: interval.from_depth,
              toDepth: interval.to_depth,
              gradeValue: interval.grade_value,
              lithCode: interval.lith_code,
              point: hit.point
            });
            return; // Selected!
          }
        }
      }

      // 2. Fallback: the bare trace line, or a planned hole's collar marker.
      //    Both carry type 'drillhole_trace'.
      for (const hit of intersects) {
        const ud = hit.object.userData;
        if (ud && ud.type === 'drillhole_trace' && ud.collar_id) {
          this.onSelect('trace', {
            collarId: ud.collar_id,
            holeId: ud.hole_id,
            point: hit.point
          });
          return; // Selected!
        }
      }
    }
  }

  dispose() {
    this.viewport.renderer.domElement.removeEventListener('pointerdown', this.onPointerDown);
  }
}
