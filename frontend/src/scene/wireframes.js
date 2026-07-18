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

export class WireframesRenderer {
  constructor(scene) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'vein-wireframes';
    this.scene.add(this.group);
  }

  async render(wireframes) {
    this.clear();
    if (!wireframes || wireframes.length === 0) return;

    const API_BASE_URL = (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') ? 'http://localhost:8000' : '';

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
          // Fallback to fetch and parse OBJ
          const response = await fetch(`${API_BASE_URL}/uploads/${w.file_ref}`);
          if (!response.ok) throw new Error(`Failed to load wireframe file: ${w.file_ref}`);
          
          const text = await response.text();
          const parsed = parseOBJ(text);
          vertices = parsed.vertices;
          indices = parsed.indices;
        }
        
        if (vertices.length === 0) continue;
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(vertices), 3));
        geometry.setIndex(indices);
        geometry.computeVertexNormals();

        // Premium translucent shaded vein solid material
        const material = new THREE.MeshStandardMaterial({
          color: 0xec4899, // Pink for ore veins
          transparent: true,
          opacity: 0.35,
          roughness: 0.2,
          metalness: 0.1,
          side: THREE.DoubleSide,
          depthWrite: false
        });

        const mesh = new THREE.Mesh(geometry, material);
        mesh.userData = {
          id: w.id,
          name: w.name,
          type: 'vein_solid'
        };

        // Add a wireframe helper overlay to make edges distinct
        const wireframeGeom = new THREE.WireframeGeometry(geometry);
        const wireframeMat = new THREE.LineBasicMaterial({
          color: 0xf472b6,
          transparent: true,
          opacity: 0.5
        });
        const line = new THREE.LineSegments(wireframeGeom, wireframeMat);
        mesh.add(line);

        this.group.add(mesh);
      } catch (err) {
        console.error(`Failed to render wireframe ${w.name}:`, err);
      }
    }
  }

  clear() {
    this.group.traverse((child) => {
      if (child.isMesh) {
        if (child.geometry) child.geometry.dispose();
        if (child.material) child.material.dispose();
      }
    });
    while (this.group.children.length > 0) {
      this.group.remove(this.group.children[0]);
    }
  }
}
