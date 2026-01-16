#!/usr/bin/env python3
"""
visualize_polyhedron.py

Quick viewer for an OpenSCAD-style polyhedron(points=[...], faces=[...]) using matplotlib.

Usage:
    python visualize_polyhedron.py            # uses embedded example points/faces
    python visualize_polyhedron.py file.scad   # extracts first polyhedron(...) and shows it

Requirements:
    - Python 3.7+
    - matplotlib

The viewer draws each face as a filled polygon, uses simple lighting (shading by face normal),
and makes the 3D axes equal so the shape is not distorted.
"""
import ast
import sys
from math import sqrt
from typing import List, Tuple

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# --- Embedded example (from your polyhedron) ---
POINTS = [
    [-584,11886,9250],[-682,13883,9250],[-1746,11771,9250],[-2113,14244,9250],[-2891,11543,9250],[-3499,13968,9250],[-4009,11204,9250],[-4683,13087,9250],
    [-584,11886,10500],[-682,13883,10500],[-1746,11771,10500],[-2113,14244,10500],[-2891,11543,10500],[-3499,13968,10500],[-4009,11204,10500],[-4683,13087,10500],
    [-584,11886,11750],[-682,13883,11750],[-1746,11771,11750],[-2113,14244,11750],[-2891,11543,11750],[-3499,13968,11750],[-4009,11204,11750],[-4683,13087,11750],
    [-584,11886,13000],[-682,13883,13000],[-1746,11771,13000],[-2113,14244,13000],[-2891,11543,13000],[-3499,13968,13000],[-4009,11204,13000],[-4683,13087,13000],
    [584,-11886,9250],[682,-13883,9250],[1746,-11771,9250],[2113,-14244,9250],[2891,-11543,9250],[3499,-13968,9250],[4009,-11204,9250],[4683,-13087,9250],
    [584,-11886,10500],[682,-13883,10500],[1746,-11771,10500],[2113,-14244,10500],[2891,-11543,10500],[3499,-13968,10500],[4009,-11204,10500],[4683,-13087,10500],
    [584,-11886,11750],[682,-13883,11750],[1746,-11771,11750],[2113,-14244,11750],[2891,-11543,11750],[3499,-13968,11750],[4009,-11204,11750],[4683,-13087,11750],
    [584,-11886,13000],[682,-13883,13000],[1746,-11771,13000],[2113,-14244,13000],[2891,-11543,13000],[3499,-13968,13000],[4009,-11204,13000],[4683,-13087,13000],
]
FACES = [
    [0,1,3],[0,3,2],[0,2,10],[0,10,8],[1,9,11],[1,11,3],[8,10,18],[8,18,16],[9,17,19],[9,19,11],[16,18,26],[16,26,24],[17,25,27],[17,27,19],[25,24,26],[25,26,27],
    [2,3,5],[2,5,4],[2,4,12],[2,12,10],[3,11,13],[3,13,5],[10,12,20],[10,20,18],[11,19,21],[11,21,13],[18,20,28],[18,28,26],[19,27,29],[19,29,21],[27,26,28],[27,28,29],
    [4,5,7],[4,7,6],[4,6,14],[4,14,12],[5,13,15],[5,15,7],[12,14,22],[12,22,20],[13,21,23],[13,23,15],[20,22,30],[20,30,28],[21,29,31],[21,31,23],[29,28,30],[29,30,31],
    [0,8,9],[0,9,1],[6,7,15],[6,15,14],[8,16,17],[8,17,9],[14,15,23],[14,23,22],[16,24,25],[16,25,17],[22,23,31],[22,31,30],
    [32,33,35],[32,35,34],[32,34,42],[32,42,40],[33,41,43],[33,43,35],[40,42,50],[40,50,48],[41,49,51],[41,51,43],[48,50,58],[48,58,56],[49,57,59],[49,59,51],[57,56,58],[57,58,59],
    [34,35,37],[34,37,36],[34,36,44],[34,44,42],[35,43,45],[35,45,37],[42,44,52],[42,52,50],[43,51,53],[43,53,45],[50,52,60],[50,60,58],[51,59,61],[51,61,53],[59,58,60],[59,60,61],
    [36,37,39],[36,39,38],[36,38,46],[36,46,44],[37,45,47],[37,47,39],[44,46,54],[44,54,52],[45,53,55],[45,55,47],[52,54,62],[52,62,60],[53,61,63],[53,63,55],[61,60,62],[61,62,63],
    [32,40,41],[32,41,33],[38,39,47],[38,47,46],[40,48,49],[40,49,41],[46,47,55],[46,55,54],[48,56,57],[48,57,49],[54,55,63],[54,63,62],
]

# --- utilities ---
def parse_scad_polyhedron(text: str):
    """Find first 'polyhedron' and extract points=[...] and faces=[...] using ast.literal_eval."""
    idx = text.find('polyhedron')
    if idx == -1:
        raise ValueError("No 'polyhedron' found")
    # crude but effective: find 'points' and 'faces' and extract bracket content
    def extract_array(keyword: str):
        kidx = text.find(keyword, idx)
        if kidx == -1:
            return None
        bidx = text.find('[', kidx)
        if bidx == -1:
            return None
        i = bidx
        depth = 0
        while i < len(text):
            if text[i] == '[':
                depth += 1
            elif text[i] == ']':
                depth -= 1
                if depth == 0:
                    slice_ = text[bidx:i+1]
                    return ast.literal_eval(slice_)
            i += 1
        return None
    pts = extract_array('points')
    fcs = extract_array('faces')
    return pts, fcs

def face_normal(face_coords: List[Tuple[float,float,float]]) -> Tuple[float,float,float]:
    """Compute a simple normal from the first three vertices (not normalized)."""
    (x0,y0,z0), (x1,y1,z1), (x2,y2,z2) = face_coords[:3]
    ux,uy,uz = x1 - x0, y1 - y0, z1 - z0
    vx,vy,vz = x2 - x0, y2 - y0, z2 - z0
    # cross product u x v
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    # normalize
    norm = sqrt(nx*nx + ny*ny + nz*nz) or 1.0
    return (nx / norm, ny / norm, nz / norm)

def set_axes_equal(ax):
    """Set 3D plot axes to equal scale.

    This tries to use set_box_aspect if available (matplotlib >= 3.3). Otherwise falls back to
    manual scaling by adjusting the limits to a centered cube.
    """
    try:
        # newer matplotlib
        ax.set_box_aspect((1,1,1))
    except Exception:
        # fallback
        x_limits = ax.get_xlim3d()
        y_limits = ax.get_ylim3d()
        z_limits = ax.get_zlim3d()
        x_range = abs(x_limits[1] - x_limits[0])
        x_mid = sum(x_limits) * 0.5
        y_range = abs(y_limits[1] - y_limits[0])
        y_mid = sum(y_limits) * 0.5
        z_range = abs(z_limits[1] - z_limits[0])
        z_mid = sum(z_limits) * 0.5
        max_range = max(x_range, y_range, z_range) / 2.0
        ax.set_xlim3d(x_mid - max_range, x_mid + max_range)
        ax.set_ylim3d(y_mid - max_range, y_mid + max_range)
        ax.set_zlim3d(z_mid - max_range, z_mid + max_range)

# --- main plotting ---
def plot_polyhedron(points: List[List[float]], faces: List[List[int]]):
    # map faces to coordinates
    polys = []
    normals = []
    for f in faces:
        try:
            poly = [tuple(points[idx]) for idx in f]
        except Exception:
            # skip malformed face
            continue
        polys.append(poly)
        normals.append(face_normal(poly))

    # simple lighting: light direction and compute brightness per face
    light_dir = (0.3, 0.5, 1.0)
    lnorm = sqrt(sum(c*c for c in light_dir))
    light_dir = tuple(c / lnorm for c in light_dir)

    face_colors = []
    for n in normals:
        dot = max(0.0, n[0]*light_dir[0] + n[1]*light_dir[1] + n[2]*light_dir[2])
        # mix base color with brightness
        base = (0.2, 0.6, 0.9)  # bluish
        shaded = tuple(min(1.0, 0.15 + 0.85 * (0.3 + 0.7*dot)) * c for c in base)
        face_colors.append(shaded)

    fig = plt.figure(figsize=(10,8))
    ax = fig.add_subplot(111, projection='3d')
    poly_collection = Poly3DCollection(polys, facecolors=face_colors, edgecolors=(0.05,0.05,0.05), linewidths=0.4, alpha=1.0)
    ax.add_collection3d(poly_collection)

    # set limits from points
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    ax.set_xlim(min(xs), max(xs))
    ax.set_ylim(min(ys), max(ys))
    ax.set_zlim(min(zs), max(zs))

    set_axes_equal(ax)
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Z')
    ax.set_title('Polyhedron faces (rotate with mouse)')
    plt.tight_layout()
    plt.show()

def main():
    if len(sys.argv) > 1:
        path = sys.argv[1]
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
            pts, fcs = parse_scad_polyhedron(text)
            if not pts or not fcs:
                raise ValueError("Could not find both points and faces in file.")
            points = pts
            faces = fcs
        except Exception as e:
            print("Failed to parse SCAD file:", e, file=sys.stderr)
            sys.exit(2)
    else:
        points = POINTS
        faces = FACES

    if not points or not faces:
        print("No points or faces to display.", file=sys.stderr)
        sys.exit(1)

    plot_polyhedron(points, faces)

if __name__ == "__main__":
    main()
