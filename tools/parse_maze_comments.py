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


class SolutionCell:
    def __init__(self, location: Tuple[int,int], exit_count: int, enter_direction: Optional[str], exit_direction: Optional[str], options: Dict[str, Dict], has_options: bool, straight: bool):
        self.location = location
        self.exit_count = exit_count
        self.enter_direction = enter_direction
        self.exit_direction = exit_direction
        self.options = options
        self.has_options = has_options
        self.straight = straight

    def __str__(self):
        return f'{self.location}  exit_count({self.exit_count}) Enter({self.enter_direction}) Exit({self.exit_direction}) options(?{self.has_options})({self.options}) straight({self.straight})'


class Maze:
    def __init__(self, width: int, height: int, orientation: str, miny: int, maxy: int, entrance_x: int, exit_x:int, part: Optional[int] = None, part_text: Optional[str] = None):
        """Create a Maze container.

        Args:
            width: number of columns (W) in the maze.
            height: number of rows (H) in the maze.
            orientation: 'INSIDE' or 'OUTSIDE' marker from the source.
            miny: the minimum Y row number used in MAZE_ROW lines.
            maxy: the maximum Y row number used in MAZE_ROW lines.
            entrance_x: the X position of the first entrance to the maze
            exit_x: the X position of the corresponding exit to the maze
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
        self.starts = [ (entrance_x,0), ((entrance_x + self.W//2) % self.W,0) ]
        self.exits = [ (exit_x,self.H-1), ((exit_x + self.W//2) % self.W, self.H-1) ]
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

        #print(f'  [IS_INVALID] ({x},{y}): {self.grid[y][x]} & {FLAGI}: {self.grid[y][x] & FLAGI}')

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
        #print(f'[NEIGHBORS] ({x},{y}): 0x{v:x}')
        # Right
        if v & FLAGR:
            #print('    [RIGHT]')
            nx = (x + 1) % self.W
            if not self.is_invalid(nx, y):
                nbrs.append(('right', nx, y))
        # Left
        if v & FLAGL:
            #print('    [LEFT]')
            nx = (x - 1) % self.W
            if not self.is_invalid(nx, y):
                nbrs.append(('left', nx, y))
        # Up (decreasing row index)
        if v & FLAGU:
            ny = y + 1 # up is the _next_ row (in the data)
            #print(f'    [UP] ({x},{ny}) in [0, {self.H})')
            if 0 <= ny < self.H and not self.is_invalid(x, ny):
                nbrs.append(('up', x, ny))
        # Down
        if v & FLAGD:
            #print('    [DOWN]')
            ny = y - 1 # down is the _previous_ row (in the data)
            if 0 <= ny < self.H and not self.is_invalid(x, ny):
                nbrs.append(('down', x, ny))
        return nbrs

    def get_direction(self, x1, y1, x2, y2):
        # AI gets these confused because right: x2>x1 and up: y2>y1, but the arrays are
        #   conceived of differently.
        if x2 == (x1 + 1) % self.W and y2 == y1:
            return 'right'
        if x2 == (x1 - 1) % self.W and y2 == y1:
            return 'left'
        if x2 == x1 and y2 == y1 - 1:
            return 'down'
        if x2 == x1 and y2 == y1 + 1:
            return 'up'
        return None

    def get_opposite(self, dir):
        opposites = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
        return opposites.get(dir)

    def get_component_size(self, start_x, start_y, from_dir):
        if self.is_invalid(start_x, start_y):
            return 0
        q = deque([(start_x, start_y)])
        seen = {(start_x, start_y)}
        # Don't include the cell that led to here.
        for ndir,nx,ny in self.neighbors(start_x,start_y):
            if ndir == from_dir:
                seen.add((nx,ny))
        count = 1
        while q:
            x, y = q.popleft()
            for ndir, nx, ny in self.neighbors(x, y):
                if (nx, ny) in seen:
                    continue
                seen.add((nx, ny))
                q.append((nx, ny))
                count += 1
        return count

    def find_solution(self):
        """
        Find the shortest path solution from the left-most start to the accessible exit in the maze.

        This method identifies the starts and exits from the human-readable maze,
        selects the left-most start, and uses BFS to find the path to the exit reachable from it.
        It then reconstructs the path and creates a detailed solution dictionary.

        Returns:
            dict: A dictionary mapping (x, y) coordinates to SolutionCell objects
                  containing path information, directions, and alternative choices.
                  Empty dict if no solution found.
        """
        if not hasattr(self, 'starts') or not self.starts:
            print("No starts found")
            return {}
        if not hasattr(self, 'exits') or not self.exits:
            print("No exits found")
            return {}
        
        print(f"Starts: {self.starts}, Exits: {self.exits}")
        
        # Find the left-most start (smallest col, then smallest row)
        start = min(self.starts, key=lambda p: (p[0], p[1]))  # x, then y
        #print(f"Selected start: {start}")
        
        # BFS from start to find the accessible exit
        dist = {}  # Distance from start to each cell
        parent = {}  # Parent cell for path reconstruction
        q = deque([start])
        dist[start] = 0
        parent[start] = None
        found_end = None
        
        #print(self.grid)  # Debug: print the maze grid
        
        while q:
            #print(f'QUEUE: {q}')  # Debug: show current queue
            x, y = q.popleft()
            #print(f'  Processing cell ({x},{y})')  # Debug: current cell
            
            # Check if this is an exit
            if (x, y) in self.exits:
                found_end = (x, y)
                #print(f'[SOLUTION] Found exit at ({x},{y})')
                break  # Stop at the first (only) accessible exit
            
            # Explore neighbors
            for ndir, nx, ny in self.neighbors(x, y):
                #print(f'[SOLUTION] Checking neighbor ({nx},{ny})')  # Debug
                if (nx, ny) in dist:
                    #print(f'[SOLUTION] Neighbor ({nx},{ny}) already visited')  # Debug
                    continue
                # Mark distance and parent, add to queue
                dist[(nx, ny)] = dist[(x, y)] + 1
                parent[(nx, ny)] = (x, y)
                q.append((nx, ny))
        
        if not found_end:
            return {}
        
        #print(f'[SOLUTION] Distance map: {dist}')   # Debug
        #print(f'[SOLUTION] Parent map: {parent}')   # Debug
        
        # Reconstruct the path from end to start using parent pointers
        path = []
        current = found_end
        while current:
            path.append(current)
            current = parent.get(current)
        path.reverse()  # Reverse to get start-to-end order
        
        #print(f'[SOLUTION] Reconstructed path: {path}')  # Debug
        
        # Create detailed solution dictionary with SolutionCell objects
        solution = {}
        for i, (x, y) in enumerate(path):
            # Determine entry and exit directions
            enter_dir = None
            exit_dir = None
            if i > 0:
                prev = path[i-1]
                enter_dir = self.get_direction(x, y, prev[0], prev[1]) # WRT this cell, which exit did we enter from?
                #print(f'[ENTER_DIR] {prev} -> ({x}, {y}): {enter_dir}')
            if i < len(path) - 1:
                next_ = path[i+1]
                exit_dir = self.get_direction(x, y, next_[0], next_[1])
                #print(f'[EXIT_DIR]  ({x}, {y}) -> {next_}: {exit_dir}')
            
            # Analyze possible directions from this cell (excluding entry)
            possible_dirs = {}
            for ndir, nx, ny in self.neighbors(x, y):
                dir_ = self.get_direction(x, y, nx, ny)
                if dir_ != enter_dir:  # Don't consider the direction we came from
                    cell_count = self.get_component_size(nx, ny, self.get_opposite(dir_))  # Size of connected component
                    print(f'  ({x},{y}) -> {dir_} ({nx},{ny}): count({cell_count})')
                    in_solution = (i < len(path)-1 and (nx, ny) == path[i+1])  # Is this the solution path?
                    possible_dirs[dir_] = {
                        'location': (nx, ny),
                        'cell_count': cell_count,
                        'in_solution': in_solution
                    }
            
            # Cell properties
            has_options = len(possible_dirs) > 1  # Multiple choices available?
            straight = enter_dir and exit_dir and self.get_opposite(enter_dir) == exit_dir  # Straight path?
            exit_count = self.degree(x, y)  # Number of exits from this cell
            
            solution[(x, y)] = SolutionCell((x,y), exit_count, enter_dir, exit_dir, possible_dirs, has_options, straight)
        
        return solution


def evaluate_turn(cell: SolutionCell) -> float:
    print(f'\n[EVAL_TURN] {cell}')
    score = 0.0
    if cell.exit_direction == 'down':
        score += 0.25
        print(f'  [EVAL_TURN] exit_down')
    # If corner, return current score
    if not cell.has_options:
        print(f'  [EVAL_TURN] [SCORE] {cell.location}: {score}')
        return score
    # evaluate each option
    for dir_, attrs in cell.options.items():
        if dir_ == cell.enter_direction:
            # Don't evaluate the "option" where we came from.
            continue

        cell_count = attrs['cell_count']
        if dir_ == 'down':
            if cell.exit_direction == 'down':
                score += 0.25
                print(f'  [EVAL_TURN] down is in solution')
            else:
                score -= 0.1 * cell_count
                print(f'  [EVAL_TURN] down is not in solution ({cell_count})')
        elif dir_ == 'up':
            if cell.exit_direction != 'up':
                print(f'  [EVAL_TURN] up is not in solution')
                score += 0.5
                if cell_count > 4:
                    print(f'  [EVAL_TURN] up/trap ({cell_count}) has > 4')
                    score += 0.5
                if cell_count > 8:
                    score += 0.5
                    print(f'  [EVAL_TURN] up/trap ({cell_count}) has > 8')
            else:
                # Is this a turn from horiz to vertical and NOT at a corner?
                if cell.has_options and cell.enter_direction in ('left','right'):
                    score += 1.0
                    print(f'  [EVAL_TURN] up/soln is in the middle of L/R move')
                    
        elif dir_ in ('left', 'right'):
            if cell.exit_direction in ('up', 'down'):
                print(f'  [EVAL_TURN] opt_dir({dir_}) has likely unexplored L/R options')
                continue
            if 'up' in cell.options:
                if dir_ == cell.exit_direction:
                    print(f'  [EVAL_TURN] L/R({dir_}) is in solution when U is available')
                    score += 0.5
    print(f'  [EVAL_TURN] [SCORE] {cell.location}: {score}')
    return score


def evaluate_all_turns(solution: Dict[Tuple[int, int], SolutionCell]) -> float:
    cells_with_options = [cell for cell in solution.values() if cell.has_options]
    # skip first two
    relevant_cells = cells_with_options[2:]
    total_score = sum(evaluate_turn(cell) for cell in relevant_cells)
    return total_score


def parse_machine_readable(lines: List[str]) -> Maze:
    start_re = re.compile(r"MAZE_START\s+(INSIDE|OUTSIDE)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)", re.I)
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
            entrance_x = int(m.group(8))
            exit_x = int(m.group(9))
            maze = Maze(W, H, orientation, miny, maxy, entrance_x=entrance_x, exit_x=exit_x, part=part, part_text=part_text)
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

    # Extract human-readable data if available
    hr = None
    try:
        mr_idx = next((i for i, l in enumerate(lines) if 'machine-readable maze data:' in l.lower()), None)
    except StopIteration:
        mr_idx = None
    if mr_idx is not None:
        hr = extract_human_readable(lines, mr_idx)

    maze.solution = maze.find_solution()

    if maze is None:
        raise RuntimeError("No MAZE_START found in machine-readable block")
    return maze


# def extract_human_readable(lines: List[str], mr_idx: int) -> Dict[str, Optional[object]]:
#     """Search backwards from mr_idx for human-readable maze visualization and solution blocks.
#
#     Returns dict with keys 'visualization' and 'solution' (each a list of strings or None),
#     and parsed 'starts', 'exits', and 'arrows' for the solution block.
#     """
#     viz = None
#     sol = None
#     arrows = []
#
#     def collect_block(start_i: int) -> List[str]:
#         out = []
#         i = start_i + 1
#         while i < len(lines):
#             s = lines[i].rstrip('\n')
#             if not s.strip():
#                 break
#             # stop if next marker
#             low = s.lower()
#             if 'machine-readable maze data' in low or '=========== maze' in low or 'maze with solution' in low:
#                 break
#             # accept commented lines starting with // or raw lines
#             if s.strip().startswith('//'):
#                 out.append(s.strip()[2:].rstrip())
#             else:
#                 out.append(s.rstrip())
#             i += 1
#         return out
#
#     # search backwards for visualization and solution markers within 1000 lines
#     viz = None
#     # collect backwards from mr_idx
#     out = []
#     i = mr_idx - 1
#     while i >= 0:
#         s = lines[i].rstrip('\n')
#         if not s.strip():
#             break
#         if s.strip().startswith('//'):
#             out.append(s.strip()[2:].rstrip())
#         else:
#             out.append(s.rstrip())
#         i -= 1
#     if out:
#         viz = list(reversed(out))
#     sol = None
#
#     # If solution block present, find starts 'S', exits 'E' (cell below), and arrows positions
#     starts = []
#     exits = []
#     if sol:
#         for row_idx, raw in enumerate(sol):
#             for col_idx, ch in enumerate(raw):
#                 if ch == 'S':
#                     x = col_idx // 4
#                     y = row_idx
#                     starts.append((x, y))
#                 elif ch == 'E':
#                     x = col_idx // 4
#                     y = row_idx + 1
#                     exits.append((x, y))
#                 if ch in ('↑', '↓', '←', '→', '^', 'v', '<', '>'):
#                     arrows.append({'pos': (row_idx, col_idx), 'char': ch})
#     elif viz:
#         for row_idx, raw in enumerate(viz):
#             for col_idx, ch in enumerate(raw):
#                 if ch == 'S':
#                     x = col_idx // 4
#                     y = row_idx
#                     starts.append((x, y))
#                 elif ch == 'E':
#                     x = col_idx // 4
#                     y = row_idx + 1
#                     exits.append((x, y))
#                 if ch in ('↑', '↓', '←', '→', '^', 'v', '<', '>'):
#                     arrows.append({'pos': (row_idx, col_idx), 'char': ch})
#
#     return {'visualization': viz, 'solution': sol, 'starts': starts, 'exits': exits, 'arrows': arrows}


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
            for ndir, nx, ny in m.neighbors(x, y):
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
    viz = []
    sol = []
    # collect backwards from mr_idx
    out = []
    i = mr_idx - 1
    #print(f'[XHR] mr_idx({mr_idx})')
    
    while i >= 0:
        s = lines[i].rstrip('\n')
        #print(f'[XHR] #{i} "{s}"')
        if s.strip().startswith('//'):
            s = s.strip()[2:]
        #if not s.strip():
        #    break
        out.append(s)

        if 'MAZE WITH SOLUTION' in s:
            sol = list(reversed(out))
            out = []
        elif 'MAZE VISUALIZATION' in s:
            viz = list(reversed(out))
            out = []

        i -= 1

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
            for ndir, nx, ny in m.neighbors(x, y):
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

    print('\n'.join(map(lambda item: f'  {item[0]}: {item[1]}',maze.solution.items())))
    print('\n'.join(hr['solution']))

    print('Score: ',evaluate_all_turns(maze.solution))


if __name__ == '__main__':
    main()
