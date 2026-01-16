#!/usr/bin/env python3
"""
analyze_polyhedron.py

Usage:
    python analyze_polyhedron.py             # uses the embedded points (from the user's polyhedron)
    python analyze_polyhedron.py path/to/file.scad
        # attempts to extract the points=[...] block from the first polyhedron(...) found

Output:
    - number of vertices
    - bounding box min and max (x, y, z)
    - dimensions (width, depth, height)
    - bounding-box center
"""

import ast
import sys
import argparse
from typing import List, Tuple

# Default points taken from the user's polyhedron (embedded for convenience)
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


def compute_bounding_box(points: List[List[float]]) -> Tuple[Tuple[float,float,float], Tuple[float,float,float]]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    minpt = (min(xs), min(ys), min(zs))
    maxpt = (max(xs), max(ys), max(zs))
    return minpt, maxpt

def dimensions(minpt: Tuple[float,float,float], maxpt: Tuple[float,float,float]) -> Tuple[float,float,float]:
    return (maxpt[0] - minpt[0], maxpt[1] - minpt[1], maxpt[2] - minpt[2])

def center(minpt: Tuple[float,float,float], maxpt: Tuple[float,float,float]) -> Tuple[float,float,float]:
    return ((minpt[0] + maxpt[0]) / 2.0, (minpt[1] + maxpt[1]) / 2.0, (minpt[2] + maxpt[2]) / 2.0)

def extract_points_from_scad(text: str) -> List[List[float]]:
    """
    Extracts the first points=[...] block found after 'polyhedron' in an OpenSCAD file string.
    Returns a Python list-of-lists via ast.literal_eval.
    """
    poly_idx = text.find('polyhedron')
    if poly_idx == -1:
        raise ValueError("No 'polyhedron' keyword found")
    pts_idx = text.find('points', poly_idx)
    if pts_idx == -1:
        raise ValueError("No 'points' found inside polyhedron")
    bracket_idx = text.find('[', pts_idx)
    if bracket_idx == -1:
        raise ValueError("No '[' after points=")
    # Find matching closing bracket for the points list
    i = bracket_idx
    depth = 0
    while i < len(text):
        if text[i] == '[':
            depth += 1
        elif text[i] == ']':
            depth -= 1
            if depth == 0:
                # slice from bracket_idx to i (inclusive)
                pts_text = text[bracket_idx:i+1]
                # Use ast.literal_eval to safely parse into Python list
                try:
                    pts = ast.literal_eval(pts_text)
                except Exception as e:
                    raise ValueError(f"Failed to parse points list: {e}")
                return pts
        i += 1
    raise ValueError("Unbalanced brackets while parsing points list")

def main():
    parser = argparse.ArgumentParser(description="Analyze OpenSCAD polyhedron points for bounding box/dimensions.")
    parser.add_argument('file', nargs='?', help="Optional OpenSCAD file to parse. If omitted, uses embedded points.")
    args = parser.parse_args()

    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
            points = extract_points_from_scad(text)
        except Exception as e:
            print(f"Error extracting points from file: {e}", file=sys.stderr)
            sys.exit(2)
    else:
        points = POINTS

    if not points:
        print("No points to analyze.", file=sys.stderr)
        sys.exit(1)

    # Validate each point has 3 coordinates
    for i, p in enumerate(points):
        if not (isinstance(p, (list, tuple)) and len(p) == 3):
            raise ValueError(f"Point at index {i} is not a 3-element sequence: {p}")

    n_vertices = len(points)
    minpt, maxpt = compute_bounding_box(points)
    dims = dimensions(minpt, maxpt)
    ctr = center(minpt, maxpt)

    print("Summary")
    print(f"- Number of vertices: {n_vertices}")
    print(f"- Bounding box min: ({minpt[0]}, {minpt[1]}, {minpt[2]})")
    print(f"- Bounding box max: ({maxpt[0]}, {maxpt[1]}, {maxpt[2]})")
    print()
    print("Dimensions (max - min)")
    print(f"- X (width): {maxpt[0]} - ({minpt[0]}) = {dims[0]}")
    print(f"- Y (depth/length): {maxpt[1]} - ({minpt[1]}) = {dims[1]}")
    print(f"- Z (height): {maxpt[2]} - ({minpt[2]}) = {dims[2]}")
    print()
    print(f"Bounding-box center: ({ctr[0]}, {ctr[1]}, {ctr[2]})")
    print("\n(Units are the same as the coordinates in the polyhedron.)")

if __name__ == "__main__":
    main()
