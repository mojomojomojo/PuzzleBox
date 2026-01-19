#!/usr/bin/env python3
"""Parse machine-readable maze data from an OpenSCAD file produced by PuzzleBox.

Usage: tools/parse_maze_comments.py <file.scad> [--weights key=val,...]

Outputs summary to stdout and JSON to stdout when --json is given.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import deque
from typing import Dict, List, Tuple, Optional

# Flags used by PuzzleBox (see puzzlebox.c / puzzlebox.py)
FLAGL = 0x01
FLAGR = 0x02
FLAGU = 0x04
FLAGD = 0x08
FLAGI = 0x80


class Maze:
    def __init__(self, width: int, height: int, orientation: str, miny: int, maxy: int, part: Optional[int] = None, part_text: Optional[str] = None):
        """Create a Maze container.

        Args:
            width: number of columns (W) in the maze.
            height: number of rows (H) in the maze.
            orientation: 'INSIDE' or 'OUTSIDE' marker from the source.
            miny: the minimum Y row number used in MAZE_ROW lines.
            maxy: the maximum Y row number used in MAZE_ROW lines.
            part: optional part number parsed from the preceding comment.
            part_text: optional textual description of the part line.

        The internal grid is stored as `grid[row][col]` with rows indexed 0..H-1
        corresponding to MAZE_ROW numbers `miny..maxy`.
        Each cell stores the byte flags produced by PuzzleBox (FLAGL/FLAGR/FLAGU/FLAGD/FLAGI).
        """
        self.W = width
        self.H = height
        self.orientation = orientation
        self.miny = miny
        self.maxy = maxy
        self.part = part
        self.part_text = part_text
        # grid[y][x]
        self.grid: List[List[int]] = [[0] * self.W for _ in range(self.H)]

    def set_row(self, row_number: int, values: List[int]):
        """Set a maze row by the original MAZE_ROW number.

        Args:
            row_number: the MAZE_ROW Y value found in the file (may be negative).
            values: list of integer flag values (parsed from hex) of length `self.W`.

        Raises IndexError if the row_number falls outside the expected range, and
        ValueError if the provided row width does not match the maze width.
        """
        idx = row_number - self.miny
        if idx < 0 or idx >= self.H:
            raise IndexError("Row number out of range")
        if len(values) != self.W:
            raise ValueError("Row width mismatch: expected %d got %d" % (self.W, len(values)))
        self.grid[idx] = values

    def degree(self, x: int, y: int) -> int:
        """Return the number of open passages (degree) for cell (x, y).

        Counts the direction flags (left/right/up/down) and returns a value
        in the range 0..4. The invalid bit (FLAGI) is ignored by this method.
        """
        v = self.grid[y][x]
        return bin(v & 0x0F).count("1")

    def is_invalid(self, x: int, y: int) -> bool:
        """Return True when the `FLAGI` (invalid) bit is set for the cell.

        Invalid cells are not considered usable for connectivity or scoring.
        """
        return bool(self.grid[y][x] & FLAGI)

    def neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Return reachable neighbor coordinates from cell (x, y).

        The returned list contains (nx, ny) tuples for each direction flag set
        on the source cell. Horizontal movement wraps around the X axis (cylinder),
        so left/right use modular arithmetic. Vertical moves are bounded to 0..H-1.
        Invalid neighbor cells are not filtered here — caller should check `is_invalid`.
        """
        nbrs = []
        v = self.grid[y][x]
        # Right
        if v & FLAGR:
            nx = (x + 1) % self.W
            nbrs.append((nx, y))
        # Left
        if v & FLAGL:
            nx = (x - 1) % self.W
            nbrs.append((nx, y))
        # Up (decreasing row index)
        if v & FLAGU:
            ny = y - 1
            if 0 <= ny < self.H:
                nbrs.append((x, ny))
        # Down
        if v & FLAGD:
            ny = y + 1
            if 0 <= ny < self.H:
                nbrs.append((x, ny))
        return nbrs


def parse_machine_readable(lines: List[str]) -> Maze:
    start_re = re.compile(r"MAZE_START\s+(INSIDE|OUTSIDE)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+(-?\d+)", re.I)
    row_re = re.compile(r"MAZE_ROW\s+(-?\d+)\s+(.+)", re.I)

    # locate machine-readable block start
    mr_idx = next((i for i, l in enumerate(lines) if 'machine-readable maze data:' in l.lower()), None)
    if mr_idx is None:
        raise RuntimeError("No machine-readable maze data found")

    # look backwards for a Part comment near the block
    part = None
    part_text = None
    part_re = re.compile(r"//\s*Part\s+(\d+)\s*(.*)", re.I)
    for j in range(mr_idx - 1, max(-1, mr_idx - 200), -1):
        mpart = part_re.search(lines[j])
        if mpart:
            part = int(mpart.group(1))
            part_text = mpart.group(2).strip()
            break

    maze: Optional[Maze] = None
    # parse from the machine-readable block forward
    for raw in lines[mr_idx:]:
        line = raw.strip()
        m = start_re.search(line)
        if m:
            orientation = m.group(1).upper()
            W = int(m.group(2))
            H = int(m.group(3))
            # other fields currently unused: maxx, helix
            miny = int(m.group(6))
            maxy = int(m.group(7))
            maze = Maze(W, H, orientation, miny, maxy, part=part, part_text=part_text)
            continue

        m2 = row_re.search(line)
        if m2:
            if maze is None:
                raise RuntimeError("Found MAZE_ROW before MAZE_START")
            rownum = int(m2.group(1))
            hexvals = m2.group(2).strip()
            parts = [p for p in re.split(r"\s+", hexvals) if p]
            vals = [int(p, 16) for p in parts]
            maze.set_row(rownum, vals)
            continue

        if line.upper().startswith("// MAZE_END") or line.upper().startswith("MAZE_END"):
            break

    if maze is None:
        raise RuntimeError("No MAZE_START found in machine-readable block")
    return maze


def extract_human_readable(lines: List[str], mr_idx: int) -> Dict[str, Optional[object]]:
    """Search backwards from mr_idx for human-readable maze visualization and solution blocks.

    Returns dict with keys 'visualization' and 'solution' (each a list of strings or None),
    and parsed 'start' and 'arrows' for the solution block.
    """
    viz = None
    sol = None
    start_pos = None
    arrows = []

    def collect_block(start_i: int) -> List[str]:
        out = []
        i = start_i + 1
        while i < len(lines):
            s = lines[i].rstrip('\n')
            if not s.strip():
                break
            # stop if next marker
            low = s.lower()
            if 'machine-readable maze data' in low or '=========== maze' in low or 'maze with solution' in low:
                break
            # accept commented lines starting with // or raw lines
            if s.strip().startswith('//'):
                out.append(s.strip()[2:].rstrip())
            else:
                out.append(s.rstrip())
            i += 1
        return out

    # search backwards for visualization and solution markers within 1000 lines
    window = 1000
    for i in range(max(0, mr_idx - window), mr_idx):
        l = lines[i].lower()
        if 'maze visualization' in l or 'human-readable maze' in l:
            viz = collect_block(i)
        if 'maze with solution' in l or 'maze with solution' in l:
            sol = collect_block(i)

    # If solution block present, find start 'S' and arrows positions
    if sol:
        for row_idx, raw in enumerate(sol):
            for col_idx, ch in enumerate(raw):
                if ch == 'S':
                    start_pos = (row_idx, col_idx)
                if ch in ('↑', '↓', '←', '→', '^', 'v', '<', '>'):
                    arrows.append({'pos': (row_idx, col_idx), 'char': ch})

    return {'visualization': viz, 'solution': sol, 'start': start_pos, 'arrows': arrows}


def analyze_maze(m: Maze) -> Dict:
    W, H = m.W, m.H
    total = W * H
    invalid = 0
    deg_counts = [0] * 5  # 0..4
    dead_ends = 0
    branch_cells = 0

    for y in range(H):
        for x in range(W):
            if m.is_invalid(x, y):
                invalid += 1
                continue
            d = m.degree(x, y)
            deg_counts[min(d, 4)] += 1
            if d <= 1:
                dead_ends += 1
            if d >= 3:
                branch_cells += 1

    # Connectivity: BFS from first non-invalid cell
    start = None
    for y in range(H):
        for x in range(W):
            if not m.is_invalid(x, y):
                start = (x, y)
                break
        if start:
            break

    reachable = 0
    if start:
        q = deque([start])
        seen = {start}
        while q:
            x, y = q.popleft()
            reachable += 1
            for nx, ny in m.neighbors(x, y):
                if m.is_invalid(nx, ny):
                    continue
                if (nx, ny) in seen:
                    continue
                # ensure reciprocal connection if present (robustness)
                q.append((nx, ny))
                seen.add((nx, ny))

    largest_component = reachable
    unreachable = total - invalid - largest_component

    avg_degree = 0.0
    counted = 0
    for y in range(H):
        for x in range(W):
            if m.is_invalid(x, y):
                continue
            avg_degree += m.degree(x, y)
            counted += 1
    avg_degree = avg_degree / counted if counted else 0.0

    metrics = {
        "width": W,
        "height": H,
        "total_cells": total,
        "invalid_cells": invalid,
        "usable_cells": total - invalid,
        "largest_component": largest_component,
        "unreachable_cells": unreachable,
        "dead_ends": dead_ends,
        "branching_cells": branch_cells,
        "avg_degree": avg_degree,
        "deg_counts": deg_counts,
    }
    return metrics


def compute_score(metrics: Dict, weights: Dict[str, float]) -> float:
    usable = metrics["usable_cells"] or 1
    largest_ratio = metrics["largest_component"] / usable
    unreachable_ratio = metrics["unreachable_cells"] / usable
    dead_end_ratio = metrics["dead_ends"] / usable
    branching_ratio = metrics["branching_cells"] / usable
    avg_degree = metrics["avg_degree"] / 4.0  # normalize (0..1)

    score = 0.0
    score += weights.get("connected", 2.0) * largest_ratio
    score += weights.get("unreachable", -5.0) * unreachable_ratio
    score += weights.get("dead_end", -1.0) * dead_end_ratio
    score += weights.get("branching", 1.0) * branching_ratio
    score += weights.get("avg_degree", 1.0) * avg_degree

    return float(score)


def parse_weights(s: Optional[str]) -> Dict[str, float]:
    if not s:
        return {}
    weights: Dict[str, float] = {}
    for part in s.split(','):
        if not part.strip():
            continue
        if '=' not in part:
            raise ValueError("Weight must be key=val")
        k, v = part.split('=', 1)
        weights[k.strip()] = float(v)
    return weights


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file', help='OpenSCAD file or exported comments file')
    ap.add_argument('--weights', help='Comma separated key=val weights (connected,unreachable,dead_end,branching,avg_degree)')
    ap.add_argument('--json', action='store_true', help='Output JSON metrics+score to stdout')
    args = ap.parse_args()

    with open(args.file, 'r', encoding='utf-8', errors='ignore') as fh:
        lines = fh.readlines()

    maze = parse_machine_readable(lines)
    # extract human-readable blocks near the machine-readable data
    try:
        mr_idx = next((i for i, l in enumerate(lines) if 'machine-readable maze data:' in l.lower()), None)
    except StopIteration:
        mr_idx = None
    hr = None
    if mr_idx is not None:
        hr = extract_human_readable(lines, mr_idx)

    metrics = analyze_maze(maze)
    default_weights = {"connected": 2.0, "unreachable": -5.0, "dead_end": -1.0, "branching": 1.0, "avg_degree": 1.0}
    override = parse_weights(args.weights)
    weights = {**default_weights, **override}
    score = compute_score(metrics, weights)
    metrics['score'] = score
    metrics['weights_used'] = weights
    # include part info when available
    if getattr(maze, 'part', None) is not None:
        metrics['part'] = maze.part
    if getattr(maze, 'part_text', None):
        metrics['part_text'] = maze.part_text
    if hr:
        metrics['human_readable'] = hr

    print('\n'.join(metrics['human_readable']['solution']))


    # Print concise human summary
    print(f"Parsed maze {maze.W}x{maze.H} orientation={maze.orientation}")
    print(f"Usable: {metrics['usable_cells']} invalid: {metrics['invalid_cells']} largest_component: {metrics['largest_component']} unreachable: {metrics['unreachable_cells']}")
    print(f"Dead-ends: {metrics['dead_ends']} branching: {metrics['branching_cells']} avg_degree: {metrics['avg_degree']:.2f}")
    print(f"Score: {metrics['score']:.3f}")

    if args.json:
        # Exclude heavy/human-only data from JSON output
        metrics_json = dict(metrics)
        metrics_json.pop('human_readable', None)
        print(json.dumps(metrics_json, indent=2))


if __name__ == '__main__':
    main()
