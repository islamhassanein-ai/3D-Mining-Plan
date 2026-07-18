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
      // Find the first valid drillhole trace or instanced mesh hit
      for (const hit of intersects) {
        const obj = hit.object;
        
        // 1. Check if it's an InstancedMesh (Assays or Lithologies)
        if (obj.isInstancedMesh && obj.userData && obj.userData.intervals) {
          const instanceId = hit.instanceId;
          const interval = obj.userData.intervals[instanceId];
          
          if (interval) {
            this.onSelect({
              type: obj.userData.type === 'assay_intervals' ? 'assay' : 'lithology',
              collar_id: interval.collar_id,
              hole_id: interval.hole_id,
              interval_id: interval.id,
              from_depth: interval.from_depth,
              to_depth: interval.to_depth,
              grade_value: interval.grade_value,
              lith_code: interval.lith_code,
              point: hit.point
            });
            return; // Selected!
          }
        }
        
        // 2. Check if it's a Line (Drillhole Trace)
        if (obj.isLine && obj.userData && obj.userData.type === 'drillhole_trace') {
          this.onSelect({
            type: 'trace',
            collar_id: obj.userData.collar_id,
            hole_id: obj.userData.hole_id,
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
