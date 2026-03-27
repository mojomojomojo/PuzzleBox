"""Save and load maze files in PUZZLEBOX_MAZE v1.0/v1.1 format."""

from __future__ import annotations

import sys
from typing import Optional, Tuple

from .maze import Maze, FLAGI


def save_maze(filename: str, maze: Maze, entry_x: int, helix_val: int):
    """Save maze to file in v1.1 format."""
    with open(filename, "w") as f:
        f.write("PUZZLEBOX_MAZE v1.1\n")
        f.write(f"WIDTH {maze.W}\n")
        f.write(f"HEIGHT {maze.H}\n")
        f.write(f"HELIX {helix_val}\n")
        f.write(f"EXIT_X {entry_x}\n")
        f.write("DATA\n")
        for y in range(maze.H):
            row_parts = []
            for x in range(maze.W):
                row_parts.append(f"{maze.grid[x][y]:02X}")
            f.write(" ".join(row_parts) + "\n")
        f.write("END\n")


def load_maze(filename: str, expected_W: int = 0, expected_H: int = 0
              ) -> Tuple[Maze, int, int]:
    """Load maze from file. Returns (maze, entry_x, helix_val).

    Raises RuntimeError on format errors.
    """
    with open(filename, "r") as f:
        header = f.readline().strip()

        if header == "PUZZLEBOX_MAZE v1.1":
            file_version = 1
        elif header == "PUZZLEBOX_MAZE v1.0":
            file_version = 0
        else:
            raise RuntimeError(f"Invalid maze file header in {filename}")

        # Read WIDTH
        line = f.readline().strip()
        if not line.startswith("WIDTH "):
            raise RuntimeError(f"Invalid or missing WIDTH in {filename}")
        W = int(line.split()[1])

        # Read HEIGHT
        line = f.readline().strip()
        if not line.startswith("HEIGHT "):
            raise RuntimeError(f"Invalid or missing HEIGHT in {filename}")
        H = int(line.split()[1])

        # Read HELIX (v1.1 only)
        helix_val = 0
        if file_version >= 1:
            line = f.readline().strip()
            if not line.startswith("HELIX "):
                raise RuntimeError(f"Invalid or missing HELIX in {filename}")
            helix_val = int(line.split()[1])

        # Read EXIT_X or DATA
        entry_x = 0
        line = f.readline().strip()
        if line.startswith("EXIT_X ") or line.startswith("ENTRY_X "):
            entry_x = int(line.split()[1])
            line = f.readline().strip()
            if line != "DATA":
                raise RuntimeError(f"Missing DATA marker in {filename}")
        elif line == "DATA":
            entry_x = 0
        else:
            raise RuntimeError(f"Expected EXIT_X or DATA in {filename}")

        # Validate dimensions
        if expected_W > 0 and W != expected_W:
            raise RuntimeError(
                f"Width mismatch: expected {expected_W}, got {W} from {filename}")
        if expected_H > 0 and H != expected_H:
            raise RuntimeError(
                f"Height mismatch: expected {expected_H}, got {H} from {filename}")

        # Create maze and read data
        maze = Maze(W, H, helix_val, max(1, abs(helix_val)))
        for y in range(H):
            line = f.readline().strip()
            vals = line.split()
            if len(vals) != W:
                raise RuntimeError(
                    f"Wrong number of values at row {y}: expected {W}, got {len(vals)} in {filename}")
            for x in range(W):
                maze.grid[x][y] = int(vals[x], 16)

        # Read END
        line = f.readline().strip()
        if not line.startswith("END"):
            raise RuntimeError(f"Missing END marker in {filename}")

        maze.entry_x = entry_x
        return maze, entry_x, helix_val
