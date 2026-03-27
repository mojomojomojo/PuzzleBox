"""Tests for impl2.puzzlebox — verifies Python output matches C reference."""

import os
import io
import pytest

from impl2.puzzlebox.cli import parse_args
from impl2.puzzlebox.scad import generate
from impl2.puzzlebox.config import Config
from impl2.puzzlebox.maze import Maze, FLAGL, FLAGR, FLAGU, FLAGD, FLAGA, FLAGI, create_rng
from impl2.puzzlebox.maze_io import save_maze, load_maze

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name):
    return os.path.join(FIXTURE_DIR, name)


def _clean_lines(text):
    """Return non-comment, non-empty lines (stripped) for structural comparison."""
    return [l.rstrip() for l in text.splitlines()
            if l.strip() and not l.strip().startswith("//")]


def _run_python(argv):
    """Run puzzlebox Python with given args, return output string."""
    cfg = parse_args(argv)
    buf = io.StringIO()
    generate(cfg, buf)
    return buf.getvalue()


def _load_c_ref(name):
    """Load C reference .scad file."""
    with open(_fixture(name), encoding="utf-8", errors="replace") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Structural comparison tests: load a maze saved by C, generate with Python,
# compare all non-comment lines.
# ---------------------------------------------------------------------------

class TestStructuralMatch:
    """Compare Python output structure against C reference output."""

    def test_2part_helix2_outside(self):
        """2 parts, helix=2, outside maze."""
        py = _run_python([
            "--parts", "2", "--helix", "2",
            "--load-maze-outside", _fixture("t1_outside.maze"),
        ])
        c_ref = _load_c_ref("t1_c.scad")
        assert _clean_lines(py) == _clean_lines(c_ref)

    def test_2part_helix_neg2_outside(self):
        """2 parts, helix=-2 (clockwise), outside maze."""
        py = _run_python([
            "--parts", "2", "--helix", "-2",
            "--load-maze-outside", _fixture("t2_outside.maze"),
        ])
        c_ref = _load_c_ref("t2_c.scad")
        assert _clean_lines(py) == _clean_lines(c_ref)

    def test_2part_helix2_inside(self):
        """2 parts, helix=2, inside maze."""
        py = _run_python([
            "--parts", "2", "--helix", "2", "--inside",
            "--load-maze-inside", _fixture("t3_inside.maze"),
        ])
        c_ref = _load_c_ref("t3_c.scad")
        assert _clean_lines(py) == _clean_lines(c_ref)


# ---------------------------------------------------------------------------
# Config validation tests
# ---------------------------------------------------------------------------

class TestConfig:
    """Test parameter validation and defaults."""

    def test_defaults(self):
        cfg = parse_args([])
        cfg.validate()
        assert cfg.parts == 2
        assert cfg.helix == 2
        assert cfg.nubs == 2
        assert cfg.basethickness == 1.6
        assert cfg.mazestep == 3.0
        assert cfg.corediameter == 30.0

    def test_nubs_defaults_to_abs_helix(self):
        cfg = parse_args(["--helix", "-3"])
        cfg.validate()
        assert cfg.nubs == 3  # abs(-3), not -3

    def test_nubs_defaults_positive_helix(self):
        cfg = parse_args(["--helix", "4"])
        cfg.validate()
        assert cfg.nubs == 4

    def test_nubs_explicit_override(self):
        cfg = parse_args(["--helix", "4", "--nubs", "2"])
        cfg.validate()
        assert cfg.nubs == 2

    def test_resin_halves_clearances(self):
        cfg = parse_args(["--resin"])
        cfg.validate()
        assert cfg.clearance == 0.2  # 0.4 / 2
        assert cfg.basegap == 0.2  # 0.4 / 2

    def test_part_radii_computed(self):
        cfg = parse_args(["--parts", "2"])
        cfg.validate()
        assert len(cfg.part_r0s) > 1
        assert cfg.part_r0s[1] > 0
        assert cfg.part_r1s[1] > cfg.part_r0s[1]

    def test_outersides_default(self):
        cfg = parse_args([])
        cfg.validate()
        assert cfg.outersides == 7  # default


# ---------------------------------------------------------------------------
# Maze generation tests
# ---------------------------------------------------------------------------

class TestMaze:
    """Test maze generation and properties."""

    def _make_cfg(self, **kwargs):
        """Create a Config suitable for maze generation."""
        base = ["--parts", "2", "--helix", "2"]
        cfg = parse_args(base)
        cfg.validate()
        return cfg

    def test_maze_dimensions(self):
        m = Maze(16, 10, 2, 2)
        assert m.W == 16
        assert m.H == 10

    def test_maze_generate_fills_grid(self):
        import random
        cfg = self._make_cfg()
        m = Maze(16, 10, 2, 2)
        rng = random.Random(42)
        m.generate(cfg, rng, inside=0)
        # At least some cells should have flags set
        has_flags = sum(1 for x in range(16) for y in range(10)
                        if m.grid[x][y] & FLAGA)
        assert has_flags > 0

    def test_maze_deterministic_with_seed(self):
        import random
        cfg = self._make_cfg()
        m1 = Maze(16, 10, 2, 2)
        m1.generate(cfg, random.Random(42), inside=0)
        m2 = Maze(16, 10, 2, 2)
        m2.generate(cfg, random.Random(42), inside=0)
        for x in range(16):
            for y in range(10):
                assert m1.grid[x][y] == m2.grid[x][y]

    def test_maze_different_seeds_differ(self):
        import random
        cfg = self._make_cfg()
        m1 = Maze(16, 10, 2, 2)
        m1.generate(cfg, random.Random(42), inside=0)
        m2 = Maze(16, 10, 2, 2)
        m2.generate(cfg, random.Random(99), inside=0)
        differs = any(m1.grid[x][y] != m2.grid[x][y]
                      for x in range(16) for y in range(10))
        assert differs


# ---------------------------------------------------------------------------
# Maze I/O tests
# ---------------------------------------------------------------------------

class TestMazeIO:
    """Test maze save/load round-trip."""

    def test_round_trip(self, tmp_path):
        import random
        cfg = parse_args(["--parts", "2", "--helix", "2"])
        cfg.validate()
        m = Maze(16, 10, 2, 2)
        m.generate(cfg, random.Random(42), inside=0)
        m.entry_x = 5

        path = str(tmp_path / "test.maze")
        save_maze(path, m, 5, 2)
        loaded, entry_x, helix_val = load_maze(path, 16, 10)

        assert entry_x == 5
        assert helix_val == 2
        for x in range(16):
            for y in range(10):
                assert loaded[x, y] == m[x, y]

    def test_load_dimension_mismatch(self, tmp_path):
        import random
        cfg = parse_args(["--parts", "2", "--helix", "2"])
        cfg.validate()
        m = Maze(16, 10, 2, 2)
        m.generate(cfg, random.Random(42), inside=0)
        path = str(tmp_path / "test.maze")
        save_maze(path, m, 5, 2)

        with pytest.raises(RuntimeError, match="Width mismatch"):
            load_maze(path, 20, 10)


# ---------------------------------------------------------------------------
# Output structure tests (no C reference needed)
# ---------------------------------------------------------------------------

class TestOutputStructure:
    """Verify output structural properties."""

    def test_braces_balanced(self):
        """All generated output should have balanced braces."""
        py = _run_python(["--parts", "2", "--helix", "2", "--seed", "42"])
        depth = 0
        for ch in py:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            assert depth >= 0, "Brace depth went negative"
        assert depth == 0, f"Unclosed braces: depth={depth}"

    def test_scale_block_present(self):
        py = _run_python(["--parts", "2", "--helix", "2", "--seed", "42"])
        assert "scale(0.001){" in py

    def test_polyhedron_present(self):
        py = _run_python(["--parts", "2", "--helix", "2", "--seed", "42"])
        assert "polyhedron(points=" in py

    def test_module_definitions_present(self):
        py = _run_python(["--parts", "2", "--helix", "2", "--seed", "42"])
        assert "module cuttext()" in py
        assert "module outer(h,r)" in py

    def test_part_comments(self):
        py = _run_python(["--parts", "3", "--helix", "2", "--seed", "42"])
        assert "// Part 1" in py
        assert "// Part 2" in py
        assert "// Part 3" in py

    def test_single_part_output(self):
        py = _run_python(["--parts", "2", "--helix", "2", "--part", "2", "--seed", "42"])
        assert "// Part 2" in py
        assert "// Part 1" not in py

    def test_negative_helix_clockwise(self):
        py = _run_python(["--parts", "2", "--helix", "-2", "--seed", "42"])
        assert "(clockwise)" in py

    def test_positive_helix_counterclockwise(self):
        py = _run_python(["--parts", "2", "--helix", "2", "--seed", "42"])
        assert "(counter-clockwise)" in py
