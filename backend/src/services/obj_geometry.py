"""
OBJ geometry parser for wireframe embedding in standalone HTML exports.

Mirrors frontend/src/scene/wireframes.js:3-40 (parseOBJ), with one deliberate
difference: vertices are returned in raw UTM order (easting, northing, elevation)
WITHOUT the Y-up swap.  The swap is applied by the renderer at wireframes.js:68
when it processes the embedded vertices/faces arrays, so applying it here too
would mirror the model.  Return empty lists rather than raising on malformed input.
"""


def parse_obj(text: str) -> dict:
    """Parse OBJ text -> {"vertices": [[e, n, el], ...], "faces": [[i, j, k], ...]}."""
    vertices = []
    faces = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue

        if line.startswith('v '):
            parts = line.split()
            if len(parts) >= 4:
                try:
                    easting = float(parts[1])
                    northing = float(parts[2])
                    elevation = float(parts[3])
                    vertices.append([easting, northing, elevation])
                except ValueError:
                    continue

        elif line.startswith('f '):
            parts = line.split()[1:]
            # Each token may be "v", "v/vt", or "v/vt/vn"; take only the vertex index
            indices = []
            for token in parts:
                try:
                    indices.append(int(token.split('/')[0]) - 1)  # 1-indexed -> 0-indexed
                except ValueError:
                    break

            if len(indices) == 3:
                faces.append(indices)
            elif len(indices) == 4:
                # Triangulate quad: (0,1,2) + (0,2,3)
                faces.append([indices[0], indices[1], indices[2]])
                faces.append([indices[0], indices[2], indices[3]])

    return {"vertices": vertices, "faces": faces}
