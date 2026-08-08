import * as THREE from 'three';

export function parseOBJ(text) {
  const vertices = [];
  const indices = [];
  const lines = text.split('\n');
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line || line.startsWith('#')) continue;
    
    if (line.startsWith('v ')) {
      const parts = line.split(/\s+/).slice(1).map(Number);
      if (parts.length >= 3) {
        // Raw OBJ coordinates are UTM: (Easting, Northing, Elevation)
        // Map to Three.js Y-up: X = Easting, Y = Elevation, Z = Northing
        const easting = parts[0];
        const northing = parts[1];
        const elevation = parts[2];
        vertices.push(easting, elevation, northing);
      }
    } else if (line.startsWith('f ')) {
      const parts = line.split(/\s+/).slice(1).map(p => {
        const vIndex = p.split('/')[0];
        return parseInt(vIndex, 10) - 1; // Convert 1-indexed to 0-indexed
      });
      
      // Handle triangles and quads
      if (parts.length === 3) {
        indices.push(parts[0], parts[1], parts[2]);
      } else if (parts.length === 4) {
        // Triangle 1
        indices.push(parts[0], parts[1], parts[2]);
        // Triangle 2
        indices.push(parts[0], parts[2], parts[3]);
      }
    }
  }
  return { vertices, indices };
}

// Generated grade-domain shells are a different kind of object from an
// imported vein solid -- one is an interpretation this tool produced, the other
// is geometry someone else drew -- so they get their own group, their own
// colour, and their own layer toggle. Rendering them into the vein group would
// make an interpretation indistinguishable from imported data.
const GRADE_SHELL_SOLID_TYPE = 'grade_shell';

const STYLES = {
  vein_solid: { fill: 0xec4899, edge: 0xf472b6, opacity: 0.35 },
  grade_shell: { fill: 0x38bdf8, edge: 0x7dd3fc, opacity: 0.45 },
};

export class WireframesRenderer {
  constructor(scene, resolveGeometry = null) {
    this.scene = scene;
    this.resolveGeometry = resolveGeometry;
    this.group = new THREE.Group();
    this.group.name = 'vein-wireframes';
    this.scene.add(this.group);

    this.gradeShellGroup = new THREE.Group();
    this.gradeShellGroup.name = 'grade-shells';
    this.scene.add(this.gradeShellGroup);
  }

  async render(wireframes) {
    this.clear();
    if (!wireframes || wireframes.length === 0) return;

    for (const w of wireframes) {
      // Topography is handled separately by TopographyRenderer
      if (w.solid_type === 'topography') continue;

      try {
        let vertices, indices;
        
        if (w.vertices && w.faces) {
          // Pre-parsed DXF geometry!
          // Map raw coordinates to Three.js Y-up: X = Easting, Y = Elevation, Z = Northing
          vertices = [];
          for (const pt of w.vertices) {
            vertices.push(pt[0], pt[2], pt[1]);
          }
          // Flatten faces (list of lists of indices)
          indices = [];
          for (const f of w.faces) {
            indices.push(f[0], f[1], f[2]);
          }
        } else {
          if (!this.resolveGeometry) { continue; }
          const resolved = await this.resolveGeometry(w);
          if (resolved === null) {
            console.warn(`Wireframe ${w.name}: geometry could not be resolved, skipping`);
            continue;
          }
          vertices = resolved.vertices;
          indices = resolved.indices;
        }
        
        if (vertices.length === 0) continue;
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(vertices), 3));
        geometry.setIndex(indices);
        geometry.computeVertexNormals();

        const isGradeShell = w.solid_type === GRADE_SHELL_SOLID_TYPE;
        const style = isGradeShell ? STYLES.grade_shell : STYLES.vein_solid;

        // Translucent, and depthWrite off, so the drillholes the shell was
        // built from stay visible through it. An opaque shell hides the very
        // data a reviewer needs to check it against.
        const material = new THREE.MeshStandardMaterial({
          color: style.fill,
          transparent: true,
          opacity: style.opacity,
          roughness: 0.2,
          metalness: 0.1,
          side: THREE.DoubleSide,
          depthWrite: false
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.userData = {
          id: w.id,
          name: w.name,
          type: isGradeShell ? GRADE_SHELL_SOLID_TYPE : 'vein_solid',
          parameters: w.parameters || null
        };

        // Add a wireframe helper overlay to make edges distinct
        const wireframeGeom = new THREE.WireframeGeometry(geometry);
        const wireframeMat = new THREE.LineBasicMaterial({
          color: style.edge,
          transparent: true,
          opacity: 0.5
        });
        const line = new THREE.LineSegments(wireframeGeom, wireframeMat);
        mesh.add(line);

        (isGradeShell ? this.gradeShellGroup : this.group).add(mesh);
      } catch (err) {
        console.error(`Failed to render wireframe ${w.name}:`, err);
      }
    }
  }

  clear() {
    for (const group of [this.group, this.gradeShellGroup]) {
      group.traverse((child) => {
        if (child.isMesh) {
          if (child.geometry) child.geometry.dispose();
          if (child.material) child.material.dispose();
        }
      });
      while (group.children.length > 0) {
        group.remove(group.children[0]);
      }
    }
  }
}
