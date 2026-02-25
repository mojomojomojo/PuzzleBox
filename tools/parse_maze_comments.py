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
    def __init__(self, width: int, height: int, orientation: str, miny: int, maxy: int, maxx: int, helix: int = 0, part: Optional[int] = None, part_text: Optional[str] = None):
        """Create a Maze container.

        Args:
            width: number of columns (W) in the maze.
            height: number of rows (H) in the maze.
            orientation: 'INSIDE' or 'OUTSIDE' marker from the source.
            miny: the minimum Y row number used in MAZE_ROW lines.
            maxy: the maximum Y row number used in MAZE_ROW lines.
            maxx: the X position of the exit at the top
            helix: helix value (vertical shift per horizontal wrap)
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
        self.maxx = maxx
        self.helix = helix
        self.part = part
        self.part_text = part_text
        # grid[y][x]
        self.grid: List[List[int]] = [[0] * self.W for _ in range(self.H)]
        # Will be set after grid is populated
        self.starts: List[Tuple[int, int]] = []
        self.exits: List[Tuple[int, int]] = []
    
    def find_entry_exit_points(self):
        """Find actual entry and exit points by scanning the maze grid.
        
        Uses entrance_x/maxy_exit from MAZE_START if available (set by parse_machine_readable).
        Falls back to scanning for the first non-invalid cell at the bottom and top rows.
        """
        self.starts = []
        self.exits = []
        
        # Use entrance_x from MAZE_START if available and valid
        entr_x = getattr(self, 'entrance_x', -1)
        if entr_x >= 0:
            # entrance_x is in absolute C-space X; entry Y is always minY (grid[0])
            if not (self.grid[0][entr_x] & FLAGI):
                self.starts.append((entr_x, 0))
        
        if not self.starts:
            # Fallback: scan bottom row for first non-invalid cell
            for x in range(self.W):
                if not self.is_invalid(x, 0):
                    self.starts.append((x, 0))
                    break
        
        # Use maxy_exit from MAZE_START for the exit (may differ from H-1 for helix mazes)
        exit_y_c = getattr(self, 'maxy_exit', self.maxy)  # C-space row of exit
        exit_y = exit_y_c - self.miny  # Python-space y index
        exit_x_val = getattr(self, 'exit_x_val', -1)
        
        if exit_x_val >= 0 and 0 <= exit_y < self.H:
            # Use the known exit from MAZE_START
            self.exits.append((exit_x_val, exit_y))
        else:
            # Fallback: find exits at top (y=H-1) - any non-invalid cell
            for x in range(self.W):
                if not self.is_invalid(x, self.H - 1):
                    self.exits.append((x, self.H - 1))
            # Also check exit_y row if different from H-1
            if exit_y != self.H - 1 and 0 <= exit_y < self.H:
                for x in range(self.W):
                    if not self.is_invalid(x, exit_y):
                        self.exits.append((x, exit_y))

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
        """Return True when the `FLAGI` (invalid) bit is set or the cell has no connections.

        Invalid cells are not considered usable for connectivity or scoring.
        Cells with no direction flags (all zeros) are also treated as invalid
        since they are isolated and unreachable.
        """

        #print(f'  [IS_INVALID] ({x},{y}): {self.grid[y][x]} & {FLAGI}: {self.grid[y][x] & FLAGI}')

        v = self.grid[y][x]
        return bool(v & FLAGI) or (v & 0x0F) == 0

    def neighbors(self, x: int, y: int) -> List[Tuple[int, int]]:
        """Return reachable neighbor coordinates from cell (x, y).

        The returned list contains (nx, ny) tuples for each direction flag set
        on the source cell. Horizontal movement wraps around the X axis (cylinder),
        so left/right use modular arithmetic. When helix is non-zero, horizontal
        wrapping also shifts vertically. Vertical moves are bounded to 0..H-1.
        Invalid neighbor cells are not filtered here — caller should check `is_invalid`.
        """
        nbrs = []
        v = self.grid[y][x]
        #print(f'[NEIGHBORS] ({x},{y}): 0x{v:x}')
        # Right
        if v & FLAGR:
            #print('    [RIGHT]')
            nx = x + 1
            ny = y
            if nx >= self.W:
                nx -= self.W
                ny += self.helix
            if 0 <= ny < self.H and not self.is_invalid(nx, ny):
                nbrs.append(('right', nx, ny))
        # Left
        if v & FLAGL:
            #print('    [LEFT]')
            nx = x - 1
            ny = y
            if nx < 0:
                nx += self.W
                ny -= self.helix
            if 0 <= ny < self.H and not self.is_invalid(nx, ny):
                nbrs.append(('left', nx, ny))
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
        
        #print(f"Starts: {self.starts}, Exits: {self.exits}")
        
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
                    #print(f'  ({x},{y}) -> {dir_} ({nx},{ny}): count({cell_count})')
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
    #print(f'\n[EVAL_TURN] {cell}')
    score = 0.0
    if cell.exit_direction == 'down':
        score += 0.25
        #print(f'  [EVAL_TURN] exit_down')
    # If corner, return current score
    if not cell.has_options:
        #print(f'  [EVAL_TURN] [SCORE] {cell.location}: {score}')
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
                #print(f'  [EVAL_TURN] down is in solution')
            else:
                score -= 0.05 * cell_count
                #print(f'  [EVAL_TURN] down is not in solution ({cell_count})')
        elif dir_ == 'up':
            if cell.exit_direction != 'up':
                #print(f'  [EVAL_TURN] up is not in solution')
                score += 0.5
                if cell_count > 4:
                    #print(f'  [EVAL_TURN] up/trap ({cell_count}) has > 4')
                    score += 0.5
                if cell_count > 8:
                    score += 0.5
                    #print(f'  [EVAL_TURN] up/trap ({cell_count}) has > 8')
            else:
                # Is this a turn from horiz to vertical and NOT at a corner?
                if cell.has_options and cell.enter_direction in ('left','right'):
                    score += 1.0
                    #print(f'  [EVAL_TURN] up/soln is in the middle of L/R move')
                    
        elif dir_ in ('left', 'right'):
            if cell.exit_direction in ('up', 'down'):
                #print(f'  [EVAL_TURN] opt_dir({dir_}) has likely unexplored L/R options')
                continue
            if 'up' in cell.options:
                if dir_ == cell.exit_direction:
                    #print(f'  [EVAL_TURN] L/R({dir_}) is in solution when U is available')
                    score += 0.5
    #print(f'  [EVAL_TURN] [SCORE] {cell.location}: {score}')
    return score


def evaluate_all_turns(solution: Dict[Tuple[int, int], SolutionCell]) -> float:
    cells_with_options = [cell for cell in solution.values() if cell.has_options]
    # Skip first two: they're always the same.
    relevant_cells = cells_with_options[2:]
    total_score = sum(evaluate_turn(cell) for cell in relevant_cells)
    return total_score

def score_maze( maze: Maze ) -> float:
    score = evaluate_all_turns(maze.solution)
    score += len(maze.solution) * .05
    return score

def parse_machine_readable(lines: List[str]) -> Maze:
    start_re = re.compile(r"MAZE_START\s+(INSIDE|OUTSIDE)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+))?)?", re.I)
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
            maxx = int(m.group(4))
            helix = int(m.group(5))
            miny = int(m.group(6))
            maxy = int(m.group(7))
            # entrance_x and exit_x at positions 8,9; maxy_exit at position 10
            entrance_x = int(m.group(8)) if m.group(8) is not None else -1
            exit_x = int(m.group(9)) if m.group(9) is not None else -1
            maxy_exit = int(m.group(10)) if m.group(10) is not None else maxy
            maze = Maze(W, H, orientation, miny, maxy, maxx=maxx, helix=helix, part=part, part_text=part_text)
            maze.entrance_x = entrance_x
            maze.exit_x_val = exit_x
            maze.maxy_exit = maxy_exit
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

    # Find entry/exit points after maze grid is loaded
    if maze:
        maze.find_entry_exit_points()
        maze.solution = maze.find_solution()

    if maze is None:
        raise RuntimeError("No MAZE_START found in machine-readable block")
    return maze


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

    # Connectivity: BFS from actual start point if available, otherwise first non-invalid cell with degree > 0
    start = None
    if m.starts:
        start = m.starts[0]
    else:
        for y in range(H):
            for x in range(W):
                if not m.is_invalid(x, y) and m.degree(x, y) > 0:
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


def extract_human_readable(lines: List[str], mr_idx: int) -> Dict[str, Optional[object]]:
    """Search backwards from mr_idx for human-readable maze visualization and solution blocks.

    Returns dict with keys 'visualization' and 'solution' (each a list of strings or None),
    and parsed 'start' and 'arrows' for the solution block.
    """
    viz = []
    sol = []
    start_pos = None
    arrows = []

    # collect backwards from mr_idx
    out = []
    i = mr_idx - 1
    
    while i >= 0:
        s = lines[i].rstrip('\n')
        if s.strip().startswith('//'):
            s = s.strip()[2:]  # Strip //
            if s.startswith(' '):
                s = s[1:]  # Strip exactly one optional space (the comment separator)
        
        if 'MAZE WITH SOLUTION' in s:
            # Don't include the marker line itself
            sol = list(reversed(out))
            out = []
        elif 'MAZE VISUALIZATION' in s:
            # Don't include the marker line itself
            viz = list(reversed(out))
            out = []
        else:
            out.append(s)

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

    # Print solution if available
    if hr and 'solution' in hr:
        try:
            print('\n'.join(hr['solution']))
        except UnicodeEncodeError:
            print("(Solution contains special characters that cannot be displayed)")


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


def score_file(mpath, weights):
    """Score a maze file using custom scoring logic.
    
    Args:
        mpath: Path to the maze file
        weights: Weight string for scoring
        
    Returns:
        Tuple of (score, maze, metrics)
    """
    with open(mpath, 'r', encoding='utf-8', errors='ignore') as fh:
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
    override = parse_weights(weights)
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

    score = evaluate_all_turns(maze.solution)

    return (score, maze, metrics)


if __name__ == '__main__':
    main()
