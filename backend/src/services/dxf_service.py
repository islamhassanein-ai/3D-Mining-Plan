import io
import ezdxf
from typing import List, Tuple, Dict, Any

def parse_dxf_wireframe(file_bytes: bytes) -> Tuple[List[List[float]], List[List[int]], List[str]]:
    """
    Parses a DXF file from bytes and extracts 3D vertices and triangular/quad face indices.
    Returns (vertices, faces, errors).
    """
    vertices = []
    faces = []
    errors = []
    
    try:
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(suffix='.dxf', delete=False)
        tmp.write(file_bytes)
        tmp.close()
        try:
            doc = ezdxf.readfile(tmp.name)
        finally:
            os.unlink(tmp.name)
        msp = doc.modelspace()
    except Exception as e:
        errors.append(f"Failed to parse DXF structure: {str(e)}")
        return [], [], errors

    vtx_map = {}

    def add_vertex(pt) -> int:
        # Round coordinates slightly to merge very close vertices
        key = (round(pt[0], 6), round(pt[1], 6), round(pt[2], 6))
        if key not in vtx_map:
            idx = len(vertices)
            vertices.append([pt[0], pt[1], pt[2]])
            vtx_map[key] = idx
            return idx
        return vtx_map[key]

    # 1. Parse 3DFACE entities
    try:
        faces_3d = msp.query('3DFACE')
        for face in faces_3d:
            try:
                pts = [face.dxf.vtx0, face.dxf.vtx1, face.dxf.vtx2, face.dxf.vtx3]
                indices = [add_vertex(pt) for pt in pts]
                
                # Check if it's a triangle (3rd and 4th vertices match)
                if pts[2] == pts[3]:
                    faces.append([indices[0], indices[1], indices[2]])
                else:
                    # Quad: split into two triangles
                    faces.append([indices[0], indices[1], indices[2]])
                    faces.append([indices[0], indices[2], indices[3]])
            except Exception as e:
                errors.append(f"Error parsing 3DFACE entity: {str(e)}")
    except Exception as e:
        errors.append(f"Failed to query 3DFACE entities: {str(e)}")

    # 2. Parse MESH entities
    try:
        meshes = msp.query('MESH')
        for mesh in meshes:
            try:
                mesh_vtx_indices = []
                for v in mesh.vertices:
                    mesh_vtx_indices.append(add_vertex(v))
                for f in mesh.faces:
                    if len(f) == 3:
                        faces.append([mesh_vtx_indices[f[0]], mesh_vtx_indices[f[1]], mesh_vtx_indices[f[2]]])
                    elif len(f) == 4:
                        faces.append([mesh_vtx_indices[f[0]], mesh_vtx_indices[f[1]], mesh_vtx_indices[f[2]]])
                        faces.append([mesh_vtx_indices[f[0]], mesh_vtx_indices[f[2]], mesh_vtx_indices[f[3]]])
                    elif len(f) > 4:
                        # Triangle fan for polygon
                        for k in range(1, len(f) - 1):
                            faces.append([mesh_vtx_indices[f[0]], mesh_vtx_indices[f[k]], mesh_vtx_indices[f[k+1]]])
            except Exception as e:
                errors.append(f"Error parsing MESH entity: {str(e)}")
    except Exception as e:
        errors.append(f"Failed to query MESH entities: {str(e)}")

    # 3. Parse POLYFACE / POLYLINE meshes
    try:
        polylines = msp.query('POLYLINE')
        for poly in polylines:
            try:
                if poly.is_polyface_mesh:
                    poly_vtxs = list(poly.vertices)
                    coords = []
                    for v in poly_vtxs:
                        if not v.is_face_record:
                            coords.append(add_vertex(v.dxf.location))
                    
                    for v in poly_vtxs:
                        if v.is_face_record:
                            indices = []
                            for idx_val in (v.dxf.vtx1, v.dxf.vtx2, v.dxf.vtx3, v.dxf.vtx4):
                                if idx_val:
                                    idx = abs(idx_val) - 1
                                    if idx < len(coords):
                                        indices.append(coords[idx])
                            if len(indices) == 3:
                                faces.append(indices)
                            elif len(indices) == 4:
                                faces.append([indices[0], indices[1], indices[2]])
                                faces.append([indices[0], indices[2], indices[3]])
            except Exception as e:
                errors.append(f"Error parsing POLYFACE entity: {str(e)}")
    except Exception as e:
        errors.append(f"Failed to query POLYLINE entities: {str(e)}")

    if not vertices and not errors:
        errors.append("No 3D geometry (3DFACE, MESH, or POLYFACE) found in DXF file.")
        
    return vertices, faces, errors

def export_wireframes_to_dxf(wireframes_data: List[Dict[str, Any]]) -> bytes:
    """
    Generates a 3D DXF file representing the vein solids using 3DFACE entities.
    """
    doc = ezdxf.new('R2000')
    msp = doc.modelspace()
    
    for w in wireframes_data:
        name = w.get("name", "Vein_Solid")
        vertices = w.get("vertices", [])
        faces = w.get("faces", [])
        
        # Group faces into different DXF layers by name
        layer_name = "".join([c if c.isalnum() or c == "_" else "_" for c in name])
        try:
            doc.layers.new(name=layer_name)
        except Exception:
            pass
            
        for f in faces:
            if len(f) >= 3:
                p0 = vertices[f[0]]
                p1 = vertices[f[1]]
                p2 = vertices[f[2]]
                p3 = p2
                msp.add_3dface([p0, p1, p2, p3], dxfattribs={'layer': layer_name})
                
    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode('utf-8')
