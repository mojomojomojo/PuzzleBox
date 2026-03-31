"""Maze generation for puzzlebox — DFS with biased random direction selection."""

from __future__ import annotations

import os
import random
import struct
from dataclasses import dataclass, field
from typing import Optional, Tuple

from .config import Config

# Direction flags (must match C exactly)
FLAGL = 0x01  # Left
FLAGR = 0x02  # Right
FLAGU = 0x04  # Up
FLAGD = 0x08  # Down
FLAGA = 0x0F  # All directions
FLAGI = 0x80  # Invalid

# Direction bias for random choices (must match C exactly)
BIASL = 2
BIASR = 1
BIASU = 1
BIASD = 4


class Maze:
    """A cylindrical maze grid with generation capabilities."""

    def __init__(self, W: int, H: int, helix: int, nubs: int):
        self.W = W
        self.H = H
        self.helix = helix
        self.abs_helix = abs(helix)
        self.nubs = nubs
        # Column-major: maze[x][y], matching C's maze[W][H]
        self.grid = [[0] * H for _ in range(W)]
        self.entry_x = 0  # X position of maze exit/entry at top
        self.exit_y = -1  # Y position where DFS reached top

    def __getitem__(self, xy):
        x, y = xy
        return self.grid[x][y]

    def __setitem__(self, xy, val):
        x, y = xy
        self.grid[x][y] = val

    def test(self, x: int, y: int) -> int:
        """Test if cell is in use / invalid — handles wrapping and nub symmetry."""
        W, H = self.W, self.H
        helix = self.helix
        abs_helix = self.abs_helix
        nubs = self.nubs

        while x < 0:
            x += W
            y -= helix
        while x >= W:
            x -= W
            y += helix

        n = nubs
        v = 0
        while True:
            if y < 0 or y >= H:
                v |= FLAGI
            else:
                v |= self.grid[x][y]
            n -= 1
            if n == 0:
                break
            x += W // nubs
            while x >= W:
                x -= W
                y += helix
            if abs_helix == nubs:
                y -= (1 if helix > 0 else -1)
        return v

    def mark_boundaries(self, cfg: Config, base: float, height: float,
                        maze_margin: float, inside: int, part: int):
        """Mark cells that are too high or too low as FLAGI."""
        y0 = base + cfg.mazestep / 2 - cfg.mazestep * (self.abs_helix + 1) + cfg.mazestep / 8
        dy = cfg.mazestep * self.helix / self.W if self.helix else 0

        for Y in range(self.H):
            for X in range(self.W):
                cell_z = cfg.mazestep * Y + y0 + dy * X
                if (cell_z < base + cfg.mazestep / 2 + cfg.mazestep / 8 or
                        cell_z > height - cfg.mazestep / 2 - maze_margin - cfg.mazestep / 8):
                    self.grid[X][Y] |= FLAGI

    def create_park(self, cfg: Config, inside: int):
        """Create the park point (dead-end for puzzle solution closure).

        Returns (X, Y) of the last cell set by park creation — used as DFS start.
        """
        W = self.W
        abs_helix = self.abs_helix
        nubs = self.nubs
        seg = W // nubs

        if cfg.parkvertical:
            for N in range(abs_helix + 2):
                self.grid[0][N] |= FLAGU + FLAGD
                X, Y = 0, N + 1
                self.grid[X][Y] |= FLAGD
            if not inside and not cfg.noa and seg > 2 and self.H > abs_helix + 4:
                # "A" at finish
                self.grid[X][Y] |= FLAGD | FLAGU | FLAGR
                self.grid[X][Y + 1] |= FLAGD | FLAGR
                self.grid[X + 1][Y] |= FLAGD | FLAGU | FLAGL
                self.grid[X + 1][Y + 1] |= FLAGD | FLAGL
                self.grid[X + 1][Y - 1] |= FLAGU
                X += 1
                Y -= 1
        else:
            if self.helix < 0:
                # Negative helix
                self.grid[0][abs_helix + 1] |= FLAGI
                self.grid[seg - 1][abs_helix + 2] |= FLAGL
                X = seg - 2
                Y = abs_helix + 2
                self.grid[X][Y] |= FLAGR
                if not inside and not cfg.noa and seg > 3 and self.H > abs_helix + 4:
                    # "A" at finish (horizontally mirrored)
                    self.grid[X][Y] |= FLAGR | FLAGL | FLAGU
                    self.grid[X - 1][Y] |= FLAGR | FLAGU
                    self.grid[X - 1][Y + 1] |= FLAGR | FLAGD
                    self.grid[X][Y + 1] |= FLAGR | FLAGL | FLAGD
                    self.grid[X + 1][Y + 1] |= FLAGL
                    X += 1
                    Y += 1
            else:
                # Positive / zero helix
                self.grid[0][abs_helix + 1] |= FLAGR
                X = 1
                Y = abs_helix + 1
                self.grid[X][Y] |= FLAGL
                if not inside and not cfg.noa and seg > 3 and self.H > abs_helix + 3:
                    # "A" at finish
                    self.grid[X][Y] |= FLAGL | FLAGR | FLAGU
                    self.grid[X + 1][Y] |= FLAGL | FLAGU
                    self.grid[X + 1][Y + 1] |= FLAGL | FLAGD
                    self.grid[X][Y + 1] |= FLAGL | FLAGR | FLAGD
                    self.grid[X - 1][Y + 1] |= FLAGR
                    X -= 1
                    Y += 1

        return X, Y

    def generate_test_pattern(self, cfg: Config, inside: int):
        """Simple test pattern — horizontal connections only."""
        for Y in range(self.H):
            for X in range(self.W):
                if not (self.test(X, Y) & FLAGI) and not (self.test(X + 1, Y) & FLAGI):
                    self.grid[X][Y] |= FLAGR
                    x, y = X + 1, Y
                    if x >= self.W:
                        x -= self.W
                        y += self.helix
                    self.grid[x][y] |= FLAGL

        flip = cfg.flip
        flip_stagger = cfg.flip_stagger
        nubs = self.nubs

        maxx = 0
        if (not flip or inside) and (not flip_stagger or not inside):
            while maxx + 1 < self.W and not (self.test(maxx + 1, self.H - 2) & FLAGI):
                maxx += 1

        self.entry_x = maxx

    def generate(self, cfg: Config, rng: random.Random, inside: int):
        """Generate maze using DFS with biased random direction selection."""
        W, H = self.W, self.H
        helix = self.helix
        flip = cfg.flip
        flip_stagger = cfg.flip_stagger
        nubs = self.nubs

        # Create park point and get DFS start position
        start_X, start_Y = self.create_park(cfg, inside)

        # DFS with linked list (simulated via list of dicts)
        max_depth = 0
        maxx = 0
        maxy_exit = -1

        # Queue: list of (x, y, n) tuples
        # Using deque-like operations on list for front/back insertion
        pos_list = [(start_X, start_Y, 0)]

        while pos_list:
            p = pos_list.pop(0)
            px, py, pn = p

            X, Y = px, py

            # Count available directions with bias
            n = 0
            if not self.test(X + 1, Y):
                n += BIASR
            if not self.test(X - 1, Y):
                n += BIASL
            if not self.test(X, Y - 1):
                n += BIASD
            if not self.test(X, Y + 1):
                n += BIASU

            if n == 0:
                continue

            # Pick random direction
            v = rng.randint(0, 0x7FFFFFFF) % n

            # Move in chosen direction
            if not self.test(X + 1, Y) and (v := v - BIASR) < 0:
                # Right
                self.grid[X][Y] |= FLAGR
                X += 1
                if X >= W:
                    X -= W
                    Y += helix
                self.grid[X][Y] |= FLAGL
            elif not self.test(X - 1, Y) and (v := v - BIASL) < 0:
                # Left
                self.grid[X][Y] |= FLAGL
                X -= 1
                if X < 0:
                    X += W
                    Y -= helix
                self.grid[X][Y] |= FLAGR
            elif not self.test(X, Y - 1) and (v := v - BIASD) < 0:
                # Down
                self.grid[X][Y] |= FLAGD
                Y -= 1
                self.grid[X][Y] |= FLAGU
            elif not self.test(X, Y + 1) and (v := v - BIASU) < 0:
                # Up
                self.grid[X][Y] |= FLAGU
                Y += 1
                self.grid[X][Y] |= FLAGD
            else:
                raise RuntimeError("WTF — should have picked a valid direction")

            # Check for entry point (longest path reaching top)
            if (pn > max_depth and (self.test(X, Y + 1) & FLAGI)
                    and (not flip or inside or not (X % (W // nubs)))
                    and (not flip_stagger or not inside or not (X % (W // nubs)))):
                max_depth = pn
                maxx = X
                maxy_exit = Y

            # Create next work item
            next_item = (X, Y, pn + 1)

            # Randomly decide queue insertion order (complexity control)
            v2 = rng.randint(0, 0x7FFFFFFF) % 10
            complexity = cfg.mazecomplexity
            abs_complexity = abs(complexity)

            if v2 < abs_complexity:
                # Add next at front (longer single path)
                pos_list.insert(0, next_item)
            else:
                # Add next at end (more branching)
                pos_list.append(next_item)

            if complexity <= 0 and v2 < -complexity:
                # Current point to front
                pos_list.insert(0, (px, py, pn))
            else:
                # Current point to end
                pos_list.append((px, py, pn))

        # With nub symmetry all segment offsets have identical maze structure.
        # Pick the segment offset that places the exit at the highest physical z.
        # helix>0: dy>0, highest z at offset seg-1; helix<0: dy<0, highest z at offset 0.
        seg = W // self.nubs
        if self.helix > 0:
            best_offset = seg - 1
        elif self.helix < 0:
            best_offset = 0
        else:
            best_offset = maxx % seg  # no helix, any offset is equally high
        self.entry_x = (maxx // seg) * seg + best_offset

        self.exit_y = maxy_exit
        return max_depth

    def create_entry_columns(self, cfg: Config):
        """Create entry points at top of maze for the exit columns."""
        W, H = self.W, self.H
        nubs = self.nubs
        seg = W // nubs

        for X in range(self.entry_x % seg, W, seg):
            Y = H - 1
            while Y and (self.grid[X][Y] & FLAGI):
                self.grid[X][Y] |= FLAGU + FLAGD
                Y -= 1
            self.grid[X][Y] += FLAGU


def create_rng(cfg: Config) -> random.Random:
    """Create a random.Random instance — seeded if cfg.seed is set, otherwise from urandom."""
    if cfg.seed is not None:
        return random.Random(cfg.seed)
    else:
        seed_bytes = os.urandom(8)
        seed_val = struct.unpack("<Q", seed_bytes)[0]
        return random.Random(seed_val)
