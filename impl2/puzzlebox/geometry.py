"""Polyhedron geometry builders — maze walls, slice logic, point/face tracking."""

from __future__ import annotations

import math
from io import StringIO
from typing import List, Optional

from .config import Config
from .maze import Maze, FLAGL, FLAGR, FLAGU, FLAGD, FLAGA, FLAGI

SCALE = 1000


def scaled(x: float) -> int:
    """Scale and round a value, matching C's scaled() macro."""
    return int(round(x * SCALE))


class SliceData:
    """Per-slice tracking data for the manifold polyhedron builder."""
    __slots__ = ('x', 'y', 'l', 'r', 'n', 'p')

    def __init__(self):
        self.x = [0.0, 0.0, 0.0]  # back, recess, front
        self.y = [0.0, 0.0, 0.0]
        self.l = 0  # left point (signed)
        self.r = 0  # right point (signed)
        self.n = 0  # count of points in p
        self.p: List[int] = []  # signed point indices


class MazePolyhedronBuilder:
    """Builds the OpenSCAD polyhedron for one maze (inside or outside)."""

    def __init__(self, out: StringIO, maze: Maze, cfg: Config,
                 r: float, inside: int, part: int, height: float,
                 margin: float, y0: float):
        self.out = out
        self.maze = maze
        self.cfg = cfg
        self.r = r
        self.inside = inside
        self.part = part
        self.height = height
        self.margin = margin
        self.y0 = y0
        self.W = maze.W
        self.H = maze.H

        # Initialize slice data
        self.slices = [SliceData() for _ in range(self.W * 4)]
        self._init_slice_positions()

        # Point index tracking
        self.P = 0  # next point index
        self.cell_points = [[0] * maze.H for _ in range(self.W)]

        self.bottom = 0
        self.top = 0

    def _init_slice_positions(self):
        """Pre-calculate x/y positions for each slice."""
        W = self.W
        r = self.r
        inside = self.inside
        cfg = self.cfg

        for S in range(W * 4):
            a = math.pi * 2 * (S - 1.5) / W / 4
            if not inside:
                a = math.pi * 2 - a
            sa = math.sin(a)
            ca = math.cos(a)

            if inside:
                back_r = r + cfg.mazethickness + (cfg.wallthickness if self.part < cfg.parts else cfg.clearance + 0.01)
                recess_r = r + cfg.mazethickness
                front_r = r
            else:
                back_r = r - cfg.mazethickness - cfg.wallthickness
                recess_r = r - cfg.mazethickness
                front_r = r

            self.slices[S].x[0] = back_r * sa
            self.slices[S].y[0] = back_r * ca
            self.slices[S].x[1] = recess_r * sa
            self.slices[S].y[1] = recess_r * ca
            self.slices[S].x[2] = front_r * sa
            self.slices[S].y[2] = front_r * ca

    def _addpoint(self, S: int, x: float, y: float, z: float):
        """Add a point with positive index."""
        self.out.write(f"[{scaled(x)},{scaled(y)},{scaled(z)}],")
        sl = self.slices[S]
        sl.p.append(self.P)
        sl.n += 1
        self.P += 1

    def _addpointr(self, S: int, x: float, y: float, z: float):
        """Add a point with negative (recess) index."""
        self.out.write(f"[{scaled(x)},{scaled(y)},{scaled(z)}],")
        sl = self.slices[S]
        sl.p.append(-(self.P))
        sl.n += 1
        self.P += 1

    def _slice(self, S: int, l: int, r: int):
        """Advance slice S to new L and R points, generating faces."""
        W4 = self.W * 4
        sl = self.slices[S]
        out = self.out

        if sl.l == 0:
            # New slice — connect to bottom
            sl.l = (-1 if l < 0 else 1) * (self.bottom + S + W4 + (0 if l < 0 else W4))
            sl.r = (-1 if r < 0 else 1) * (self.bottom + (S + 1) % W4 + W4 + (0 if r < 0 else W4))
            out.write(f"[{abs(sl.l)},{abs(sl.r)},{(S + 1) % W4},{S}],")

        if l == sl.l and r == sl.r:
            return

        SR = (S + 1) % W4
        sl_r = self.slices[SR]

        out.write("[")
        p_count = 0

        # Find n1, n2 in left slice
        n1 = 0
        while n1 < sl.n and abs(sl.p[n1]) != abs(sl.l):
            n1 += 1
        n2 = n1
        while n2 < sl.n and abs(sl.p[n2]) != abs(l):
            n2 += 1

        if n1 == sl.n or n2 == sl.n:
            raise RuntimeError(f"Bad render {sl.l}->{l}")

        while n1 < n2:
            if _sgn(sl.p[n1]) == _sgn(sl.l):
                out.write(f"{abs(sl.p[n1])},")
                p_count += 1
            n1 += 1

        out.write(f"{abs(l)},")
        if p_count:
            out.write(f"{abs(r)}],")

        # Find n1, n2 in right slice
        n1 = 0
        while n1 < sl_r.n and abs(sl_r.p[n1]) != abs(sl.r):
            n1 += 1
        n2 = n1
        while n2 < sl_r.n and abs(sl_r.p[n2]) != abs(r):
            n2 += 1

        if n1 == sl_r.n or n2 == sl_r.n:
            raise RuntimeError(f"Bad render {r}->{sl.r}")

        if not p_count or n1 < n2:
            n2 -= 1
            if p_count:
                out.write("[")
            out.write(f"{abs(r)}")
            while n1 <= n2:
                if _sgn(sl_r.p[n2]) == _sgn(sl.r):
                    out.write(f",{abs(sl_r.p[n2])}")
                n2 -= 1
            if p_count:
                out.write(f",{abs(sl.l)}")
            out.write("],")

        sl.l = l
        sl.r = r

    def build(self):
        """Build the complete polyhedron and write to output."""
        out = self.out
        maze = self.maze
        cfg = self.cfg
        W, H = self.W, self.H
        W4 = W * 4
        nubskew = cfg.nubskew

        if self.inside and cfg.mirrorinside:
            out.write("mirror([1,0,0])")
        out.write("polyhedron(")

        # === POINTS ===
        out.write("points=[")

        self.bottom = self.P
        # Base points: 3 rings
        for S in range(W4):
            self._addpoint(S, self.slices[S].x[0], self.slices[S].y[0],
                           cfg.basethickness - cfg.clearance)
        for S in range(W4):
            self._addpointr(S, self.slices[S].x[1], self.slices[S].y[1],
                            cfg.basethickness - cfg.clearance)
        for S in range(W4):
            self._addpoint(S, self.slices[S].x[2], self.slices[S].y[2],
                           cfg.basethickness - cfg.clearance)

        # Maze cell points (16 per cell)
        dy_per_S = cfg.mazestep * maze.helix / W / 4
        my = cfg.mazestep / 8
        y_base = self.y0 - dy_per_S * 1.5

        for Y in range(H):
            for X in range(W):
                v = maze.test(X, Y)
                if not (v & FLAGA) or (v & FLAGI):
                    continue
                self.cell_points[X][Y] = self.P

                for S in range(X * 4, X * 4 + 4):
                    z = y_base + Y * cfg.mazestep + dy_per_S * S - my * 3
                    self._addpoint(S, self.slices[S].x[2], self.slices[S].y[2], z)
                for S in range(X * 4, X * 4 + 4):
                    z = y_base + Y * cfg.mazestep + dy_per_S * S - my - nubskew
                    self._addpointr(S, self.slices[S].x[1], self.slices[S].y[1], z)
                for S in range(X * 4, X * 4 + 4):
                    z = y_base + Y * cfg.mazestep + dy_per_S * S + my - nubskew
                    self._addpointr(S, self.slices[S].x[1], self.slices[S].y[1], z)
                for S in range(X * 4, X * 4 + 4):
                    z = y_base + Y * cfg.mazestep + dy_per_S * S + my * 3
                    self._addpoint(S, self.slices[S].x[2], self.slices[S].y[2], z)

        # Top points: 3 rings
        self.top = self.P
        for S in range(W4):
            top_z = self.height - (0 if (cfg.basewide and not self.inside and self.part > 1) else self.margin)
            self._addpoint(S, self.slices[S].x[2], self.slices[S].y[2], top_z)
        for S in range(W4):
            self._addpoint(S, self.slices[S].x[1], self.slices[S].y[1], self.height)
        for S in range(W4):
            self._addpoint(S, self.slices[S].x[0], self.slices[S].y[0], self.height)

        # Wrap-around: add first point index to each slice
        for S in range(W4):
            self.slices[S].p.append(S)
            self.slices[S].n += 1

        out.write("]")

        # === FACES ===
        out.write(",\nfaces=[")

        # Maze faces
        for Y in range(H):
            for X in range(W):
                v = maze.test(X, Y)
                if not (v & FLAGA) or (v & FLAGI):
                    continue
                S = X * 4
                P = self.cell_points[X][Y]

                # Left sub-slice
                if not (v & FLAGD):
                    self._slice(S + 0, P + 0, P + 1)
                self._slice(S + 0, P + 0, -(P + 5))
                if v & FLAGL:
                    self._slice(S + 0, -(P + 4), -(P + 5))
                    self._slice(S + 0, -(P + 8), -(P + 9))
                self._slice(S + 0, P + 12, -(P + 9))
                if not (v & FLAGU):
                    self._slice(S + 0, P + 12, P + 13)

                # Middle sub-slice
                if not (v & FLAGD):
                    self._slice(S + 1, P + 1, P + 2)
                self._slice(S + 1, -(P + 5), -(P + 6))
                self._slice(S + 1, -(P + 9), -(P + 10))
                if not (v & FLAGU):
                    self._slice(S + 1, P + 13, P + 14)

                # Right sub-slice
                if not (v & FLAGD):
                    self._slice(S + 2, P + 2, P + 3)
                self._slice(S + 2, -(P + 6), P + 3)
                if v & FLAGR:
                    self._slice(S + 2, -(P + 6), -(P + 7))
                    self._slice(S + 2, -(P + 10), -(P + 11))
                self._slice(S + 2, -(P + 10), P + 15)
                if not (v & FLAGU):
                    self._slice(S + 2, P + 14, P + 15)

                # Join to right neighbor
                x2 = X + 1
                y2 = Y
                if x2 >= W:
                    x2 -= W
                    y2 += maze.helix
                if 0 <= y2 < H:
                    PR = self.cell_points[x2][y2]
                    if PR:
                        self._slice(S + 3, P + 3, PR + 0)
                        if v & FLAGR:
                            self._slice(S + 3, -(P + 7), -(PR + 4))
                            self._slice(S + 3, -(P + 11), -(PR + 8))
                        self._slice(S + 3, P + 15, PR + 12)

        # Top cap
        for S in range(W4):
            sl = self.slices[S]
            self._slice(S, self.top + S + (W4 if sl.l < 0 else 0),
                        self.top + (S + 1) % W4 + (W4 if sl.r < 0 else 0))
            self._slice(S, self.top + S + W4, self.top + (S + 1) % W4 + W4)
            self._slice(S, self.top + S + 2 * W4, self.top + (S + 1) % W4 + 2 * W4)
            self._slice(S, self.bottom + S, self.bottom + (S + 1) % W4)

        out.write("]")
        out.write(",convexity=10")
        out.write(");\n")

        # Park ridge
        if cfg.parkthickness:
            self._build_park_ridge(dy_per_S)

    def _build_park_ridge(self, dy_per_S: float):
        """Build the park ridge polyhedron (click-stop bumps)."""
        out = self.out
        cfg = self.cfg
        maze = self.maze
        W = self.W
        W4 = W * 4
        helix = maze.helix
        abs_helix = abs(helix)
        nubs = cfg.nubs
        dy_outer = dy_per_S * 4  # mazestep * helix / W

        park_S_shift = ((W // nubs - 2) * 4) if (helix < 0 and not cfg.parkvertical) else 0

        if self.inside and cfg.mirrorinside:
            out.write("mirror([1,0,0])")
        out.write("polyhedron(points=[")

        for N in range(0, W, W // nubs):
            for Y in range(4):
                for X in range(4):
                    S = (N * 4 + X + park_S_shift + (0 if cfg.parkvertical else 2) + W4) % W4
                    z = (self.y0 - dy_per_S * 1.5 +
                         (abs_helix + 1) * cfg.mazestep +
                         Y * cfg.mazestep / 4 +
                         dy_per_S * X +
                         (cfg.mazestep / 8 if cfg.parkvertical else dy_outer / 2 - cfg.mazestep * 3 / 8) +
                         ((cfg.mazestep + dy_outer * (W // nubs - 2)) if (helix < 0 and not cfg.parkvertical) else 0))
                    sx = self.slices[S].x[1]
                    sy = self.slices[S].y[1]
                    if (cfg.parkvertical and (Y == 1 or Y == 2)) or (not cfg.parkvertical and (X == 1 or X == 2)):
                        # Ridge height
                        sx = (self.slices[S].x[1] * (cfg.mazethickness - cfg.parkthickness) +
                              self.slices[S].x[2] * cfg.parkthickness) / cfg.mazethickness
                        sy = (self.slices[S].y[1] * (cfg.mazethickness - cfg.parkthickness) +
                              self.slices[S].y[2] * cfg.parkthickness) / cfg.mazethickness
                    elif cfg.parkvertical:
                        z -= cfg.nubskew

                    out.write(f"[{scaled(self.slices[S].x[0])},{scaled(self.slices[S].y[0])},{scaled(z)}],")
                    out.write(f"[{scaled(sx)},{scaled(sy)},{scaled(z)}],")

        out.write("],faces=[")

        for N_idx in range(nubs):
            P = N_idx * 32

            for X in range(0, 6, 2):
                self._park_add(P, X + 0, X + 1, X + 3, X + 2, helix, cfg.parkvertical)
                for Y in range(0, 24, 8):
                    self._park_add(P, X + 0 + Y, X + 2 + Y, X + 10 + Y, X + 8 + Y, helix, cfg.parkvertical)
                    self._park_add(P, X + 1 + Y, X + 9 + Y, X + 11 + Y, X + 3 + Y, helix, cfg.parkvertical)
                self._park_add(P, X + 25, X + 24, X + 26, X + 27, helix, cfg.parkvertical)

            for Y in range(0, 24, 8):
                self._park_add(P, Y + 0, Y + 8, Y + 9, Y + 1, helix, cfg.parkvertical)
                self._park_add(P, Y + 6, Y + 7, Y + 15, Y + 14, helix, cfg.parkvertical)

        out.write("],convexity=10);\n")

    def _park_add(self, P: int, a: int, b: int, c: int, d: int, helix: int, parkvertical: bool):
        """Write two triangular faces for park ridge (with winding flip for negative helix)."""
        if helix < 0 and not parkvertical:
            self.out.write(f"[{P+a},{P+c},{P+b}],[{P+a},{P+d},{P+c}],")
        else:
            self.out.write(f"[{P+a},{P+b},{P+c}],[{P+a},{P+c},{P+d}],")


def _sgn(x: int) -> int:
    if x < 0:
        return -1
    if x > 0:
        return 1
    return 0
