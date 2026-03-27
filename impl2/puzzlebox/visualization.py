"""Maze visualization — ASCII rendering, solution path finding, machine-readable output."""

from __future__ import annotations

import copy
from io import StringIO
from typing import List, Optional, Tuple

from .maze import Maze, FLAGL, FLAGR, FLAGU, FLAGD, FLAGA, FLAGI


class MazeVisualization:
    """Generates all maze visualization outputs for a single maze."""

    def __init__(self, maze: Maze, cfg, inside: int, stl: bool):
        self.maze = maze
        self.cfg = cfg
        self.inside = inside
        self.stl = stl
        self.W = maze.W
        self.H = maze.H
        self.helix = maze.helix
        self.abs_helix = abs(maze.helix)
        self.nubs = maze.nubs
        self.maxx = maze.entry_x
        self.maxy_exit = maze.exit_y

        # Computed during render
        self.minY = 0
        self.maxY = self.H - 1
        self.entrance_x = 0
        self.entrance_y = 0
        self._exit_x = -1
        self.solution = [[0] * self.H for _ in range(self.W)]
        self.reachable = [[False] * self.H for _ in range(self.W)]

    def render(self, out: StringIO, mazedata_buf: Optional[StringIO] = None):
        """Render all visualizations to the output stream."""
        maze = self.maze
        W, H = self.W, self.H

        # Build visualization copy (with nub replication)
        maze_viz = self._replicate_for_nubs()

        # Find valid row range
        self._find_valid_range(maze)

        # Find solution path
        self._find_solution(maze)

        # Write header
        side = "INSIDE" if self.inside else "OUTSIDE"
        self._write_header(out, mazedata_buf, side)

        # Render plain maze
        self._render_ascii(out, mazedata_buf, maze_viz, with_solution=False)

        # Render maze with solution
        self._render_solution_header(out, mazedata_buf)
        self._render_ascii(out, mazedata_buf, maze_viz, with_solution=True)

        # Machine-readable
        self._render_machine_readable(out, mazedata_buf, maze_viz)

    def _replicate_for_nubs(self) -> List[List[int]]:
        """BFS-replicate maze data for visualization when nubs > 1."""
        maze = self.maze
        W, H = self.W, self.H
        nubs = self.nubs
        helix = self.helix

        maze_viz = [row[:] for row in maze.grid]

        if nubs <= 1:
            return maze_viz

        seg = W // nubs
        visited = [[False] * H for _ in range(W)]
        queue = []

        viz_start_y = self.maxy_exit if self.maxy_exit >= 0 else self.maxY
        queue.append((self.maxx, viz_start_y))
        visited[self.maxx][viz_start_y] = True

        # Copy start cell to opposite side
        opp_x = (self.maxx + seg) % W
        opp_y = viz_start_y + helix * seg
        if 0 <= opp_y < H:
            maze_viz[opp_x][opp_y] = maze_viz[self.maxx][viz_start_y]

        head = 0
        while head < len(queue):
            cx, cy = queue[head]
            head += 1

            for flag, dx, dy in [(FLAGR, 1, 0), (FLAGL, -1, 0),
                                  (FLAGU, 0, 1), (FLAGD, 0, -1)]:
                if not (maze.grid[cx][cy] & flag):
                    continue
                nx = (cx + dx) % W
                ny = (cy + dy) % H
                if not visited[nx][ny]:
                    visited[nx][ny] = True
                    queue.append((nx, ny))
                    opp_x = (nx + seg) % W
                    opp_y = ny + helix * seg
                    if 0 <= opp_y < H:
                        maze_viz[opp_x][opp_y] = maze_viz[nx][ny]

        return maze_viz

    def _find_valid_range(self, maze: Maze):
        """Find min/max Y rows that contain valid (non-FLAGI) cells."""
        W, H = self.W, self.H
        self.minY = 0
        self.maxY = H - 1

        for Y in range(H):
            if any(not (maze.grid[X][Y] & FLAGI) for X in range(W)):
                self.minY = Y
                break

        for Y in range(H - 1, -1, -1):
            if any(not (maze.grid[X][Y] & FLAGI) for X in range(W)):
                self.maxY = Y
                break

    def _find_solution(self, maze: Maze):
        """BFS from entrance to exit, mark solution path with direction arrows."""
        W, H = self.W, self.H
        helix = self.helix
        abs_helix = self.abs_helix

        # Determine entrance
        self.entrance_x = (W // self.nubs - 1) if helix < 0 else 0
        self.entrance_y = abs_helix + (2 if helix < 0 else 1)

        if self.entrance_y < self.minY or self.entrance_y > self.maxY:
            return

        target_y = self.maxy_exit if self.maxy_exit >= 0 else self.maxY

        # BFS
        queue = [(self.entrance_x, self.entrance_y)]
        parentX = [[-1] * H for _ in range(W)]
        parentY = [[-1] * H for _ in range(W)]
        visited = [[False] * H for _ in range(W)]

        visited[self.entrance_x][self.entrance_y] = True
        parentX[self.entrance_x][self.entrance_y] = self.entrance_x
        parentY[self.entrance_x][self.entrance_y] = self.entrance_y

        found = False
        head = 0
        while head < len(queue) and not found:
            cx, cy = queue[head]
            head += 1

            if cx == self.maxx and cy == target_y:
                found = True
                break

            for flag, get_next in [
                (FLAGR, lambda cx, cy: ((cx + 1 - W, cy + helix) if cx + 1 >= W else (cx + 1, cy))),
                (FLAGL, lambda cx, cy: ((cx - 1 + W, cy - helix) if cx - 1 < 0 else (cx - 1, cy))),
                (FLAGU, lambda cx, cy: (cx, (cy + 1) % H)),
                (FLAGD, lambda cx, cy: (cx, (cy - 1 + H) % H)),
            ]:
                if not (maze.grid[cx][cy] & flag):
                    continue
                nx, ny = get_next(cx, cy)
                if 0 <= ny < H and not visited[nx][ny] and not (maze.grid[nx][ny] & FLAGI):
                    visited[nx][ny] = True
                    parentX[nx][ny] = cx
                    parentY[nx][ny] = cy
                    queue.append((nx, ny))

        if found:
            # Trace path back from exit to entrance
            path = []
            cx, cy = self.maxx, target_y
            while True:
                path.append((cx, cy))
                if cx == self.entrance_x and cy == self.entrance_y:
                    break
                px, py = parentX[cx][cy], parentY[cx][cy]
                cx, cy = px, py

            # path[-1] is entrance, path[0] is exit
            self.solution[path[-1][0]][path[-1][1]] = ord('S')
            self._exit_x = path[0][0]

            for i in range(len(path) - 2, 0, -1):
                curr_x, curr_y = path[i]
                next_x, next_y = path[i - 1]

                dx = (next_x - curr_x + W) % W
                dy = next_y - curr_y

                if dx == 0 and dy != 0:
                    self.solution[curr_x][curr_y] = ord('U') if dy > 0 else ord('D')
                elif dy == 0 and dx != 0:
                    if dx == 1:
                        self.solution[curr_x][curr_y] = ord('R')
                    elif dx == W - 1:
                        self.solution[curr_x][curr_y] = ord('L')
                    else:
                        self.solution[curr_x][curr_y] = ord('?')
                elif dx != 0 and dy != 0:
                    if dx == 1 or dx == W - 1:
                        self.solution[curr_x][curr_y] = ord('R') if dx == 1 else ord('L')
                    else:
                        self.solution[curr_x][curr_y] = ord('U') if dy > 0 else ord('D')
                else:
                    self.solution[curr_x][curr_y] = ord('?')

            # Exit cell leads up
            self.solution[path[0][0]][path[0][1]] = ord('U')

        # BFS to find all reachable cells
        queue2 = [(self.entrance_x, self.entrance_y)]
        self.reachable[self.entrance_x][self.entrance_y] = True
        head = 0
        while head < len(queue2):
            cx, cy = queue2[head]
            head += 1
            for flag, get_next in [
                (FLAGR, lambda cx, cy: ((cx + 1 - W, cy + helix) if cx + 1 >= W else (cx + 1, cy))),
                (FLAGL, lambda cx, cy: ((cx - 1 + W, cy - helix) if cx - 1 < 0 else (cx - 1, cy))),
                (FLAGU, lambda cx, cy: (cx, cy + 1)),
                (FLAGD, lambda cx, cy: (cx, cy - 1)),
            ]:
                if not (maze.grid[cx][cy] & flag):
                    continue
                nx, ny = get_next(cx, cy)
                if 0 <= ny < H and not self.reachable[nx][ny] and not (maze.grid[nx][ny] & FLAGI):
                    self.reachable[nx][ny] = True
                    queue2.append((nx, ny))

    def _write(self, out: StringIO, buf: Optional[StringIO], text: str,
               comment: bool = True, buf_text: Optional[str] = None):
        """Write to output (with // prefix) and optionally to mazedata buffer."""
        if comment:
            out.write(f"// {text}")
        else:
            out.write(text)
        if buf is not None:
            buf.write(buf_text if buf_text is not None else text)

    def _writeln(self, out: StringIO, buf: Optional[StringIO], text: str,
                 comment: bool = True, buf_text: Optional[str] = None):
        self._write(out, buf, text + "\n", comment, (buf_text or text) + "\n")

    def _write_header(self, out: StringIO, buf: Optional[StringIO], side: str):
        W, H = self.W, self.H
        helix = self.helix
        abs_helix = self.abs_helix
        nubs = self.nubs

        out.write("//\n")
        out.write(f"// ============ MAZE VISUALIZATION ({side}, {W}x{H}, helix={helix}) ============\n")
        out.write("//\n")
        out.write("// Human-readable maze (viewed from outside, unwrapped):\n")
        out.write("// Legend: + = corner, - = horizontal wall, | = vertical wall, # = invalid, E = exit, space = passage\n")

        if buf:
            buf.write("\n")
            buf.write(f"============ MAZE VISUALIZATION ({side}, {W}x{H}, helix={helix}) ============\n")
            buf.write("\n")
            buf.write("Human-readable maze (viewed from outside, unwrapped):\n")
            buf.write("Legend: + = corner, - = horizontal wall, | = vertical wall, # = invalid, E = exit, space = passage\n")

        if helix > 0:
            msg = f"Note: Maze wraps helically - crossing the seam shifts up {abs_helix} row(s) (counter-clockwise)\n"
        elif helix < 0:
            msg = f"Note: Maze wraps helically - crossing the seam shifts down {abs_helix} row(s) (clockwise)\n"
        else:
            msg = "Note: Maze wraps horizontally (cylinder) - leftmost and rightmost edges connect\n"
        out.write(f"// {msg}")
        if buf:
            buf.write(msg)

        msg2 = f"Note: With {nubs} nubs, the maze pattern repeats every {W // nubs} cells around the circumference\n"
        out.write(f"// {msg2}")
        out.write("//\n")
        if buf:
            buf.write(msg2)
            buf.write("\n")

        out.write(f"// Showing rows {self.minY} to {self.maxY} (valid maze area, helix={helix})\n")
        if buf:
            buf.write(f"Showing rows {self.minY} to {self.maxY} (valid maze area, helix={helix})\n")

    def _render_solution_header(self, out: StringIO, buf: Optional[StringIO]):
        out.write("//\n")
        out.write("// ============ MAZE WITH SOLUTION ============\n")
        out.write("//\n")
        out.write("// Legend: S = start, arrows (\u2191\u2193\u2190\u2192) show path to exit\n")
        out.write("//\n")
        if buf:
            buf.write("\n")
            buf.write("============ MAZE WITH SOLUTION ============\n")
            buf.write("\n")
            buf.write("Legend: S = start, arrows (\u2191\u2193\u2190\u2192) show path to exit\n")
            buf.write("\n")

    def _render_ascii(self, out: StringIO, buf: Optional[StringIO],
                      maze_viz: List[List[int]], with_solution: bool):
        """Render ASCII maze art."""
        W = self.W
        minY, maxY = self.minY, self.maxY
        maxx = self.maxx
        nubs = self.nubs
        seg = W // nubs

        for Y in range(maxY + 1, minY - 1, -1):
            # Horizontal walls row
            line = "// "
            bline = " "
            for X in range(W):
                line += "+"
                bline += "+"
                if Y == maxY + 1:
                    is_exit = any(X == (maxx + n * seg) % W for n in range(nubs))
                    cell = " E " if is_exit else "---"
                elif Y == minY:
                    cell = "---"
                else:
                    cell = "   " if (maze_viz[X][Y - 1] & FLAGU) else "---"
                line += cell
                bline += cell
            line += "+\n"
            bline += "+\n"
            out.write(line)
            if buf:
                buf.write(bline)

            # Cell interiors row
            if Y > minY:
                line = "// "
                bline = " "
                for X in range(W):
                    # Left edge
                    if X == 0:
                        wall = " " if (maze_viz[W - 1][Y - 1] & FLAGR) else "|"
                    else:
                        wall = ""  # handled by previous cell's right edge

                    if X == 0:
                        line += wall
                        bline += wall

                    # Cell interior
                    if maze_viz[X][Y - 1] & FLAGI:
                        interior = "###"
                    elif with_solution:
                        sol = self.solution[X][Y - 1]
                        if sol == ord('S'):
                            interior = " S "
                        elif sol == ord('U'):
                            interior = " \u2191 "
                        elif sol == ord('D'):
                            interior = " \u2193 "
                        elif sol == ord('L'):
                            interior = " \u2190 "
                        elif sol == ord('R'):
                            interior = " \u2192 "
                        elif not self.reachable[X][Y - 1]:
                            interior = "###"
                        else:
                            interior = "   "
                    else:
                        interior = "   "

                    line += interior
                    bline += interior

                    # Right edge
                    right = " " if (maze_viz[X][Y - 1] & FLAGR) else "|"
                    line += right
                    bline += right

                line += "\n"
                bline += "\n"
                out.write(line)
                if buf:
                    buf.write(bline)

        out.write("//\n")
        if buf:
            buf.write("\n")

    def _render_machine_readable(self, out: StringIO, buf: Optional[StringIO],
                                 maze_viz: List[List[int]]):
        """Render MAZE_START/MAZE_ROW/MAZE_END block."""
        W = self.W
        minY, maxY = self.minY, self.maxY
        maxx = self.maxx
        helix = self.helix
        maxy_exit = self.maxy_exit
        target_y = maxy_exit if maxy_exit >= 0 else maxY

        side = "INSIDE" if self.inside else "OUTSIDE"

        out.write("// Machine-readable maze data:\n")
        header = (f"// MAZE_START {side} {W} {maxY - minY + 1} {maxx} {helix} "
                  f"{minY} {maxY} {self.entrance_x} {self._exit_x} {target_y}\n")
        out.write(header)

        if buf:
            buf.write("Machine-readable maze data:\n")
            buf.write(header.replace("// ", ""))

        for Y in range(minY, maxY + 1):
            row_hex = " ".join(f"{maze_viz[X][Y]:02X}" for X in range(W))
            out.write(f"// MAZE_ROW {Y} {row_hex}\n")
            if buf:
                buf.write(f"MAZE_ROW {Y} {row_hex}\n")

        out.write("// MAZE_END\n")
        out.write("//\n")
        if buf:
            buf.write("MAZE_END\n")
            buf.write("\n")
