"""Tests for --thick-part / --thick-wall / --thick-base and part dimension output."""

import io
import re

import pytest

from impl2.puzzlebox.cli import parse_args
from impl2.puzzlebox.scad import generate

# Mirrors the Ennes build (ennes/gen_good.py defaults), 7 parts, round outside.
BASE_ARGS = [
    "--parts", "7", "--core-diameter", "30", "--core-height", "90",
    "--nubs", "3", "--base-height", "8", "--base-gap", "1", "--clearance", "0.4",
    "--helix", "0", "--part-thickness", "3", "--park-thickness", "0.7",
    "--maze-thickness", "2", "--maze-complexity", "7", "--maze-step", "5",
    "--maze-margin", "1", "--outer-sides", "0", "--base-wide", "--fix-nubs",
]
WALL = 3.0
BASE = 1.6  # default --base-thickness
THICK_WALL = 4.5
THICK_BASE = 3.0
DW = THICK_WALL - WALL
DB = THICK_BASE - BASE
TOL = 1e-9


def _cfg(extra=()):
    cfg = parse_args(BASE_ARGS + list(extra))
    assert cfg.validate() is None
    return cfg


def _thick_args(target):
    return ["--thick-part", str(target),
            "--thick-wall", str(THICK_WALL), "--thick-base", str(THICK_BASE)]


def _all_dims(cfg):
    return {p: dict(cfg.part_dimensions(p), height=cfg.part_height(p))
            for p in range(1, cfg.parts + 1)}


def _run(argv):
    cfg = parse_args(argv)
    buf = io.StringIO()
    generate(cfg, buf)
    return buf.getvalue()


def _geometry_lines(text):
    """Non-comment, non-dimension-variable lines."""
    return [l for l in text.splitlines()
            if l.strip() and not l.strip().startswith("//") and not l.startswith("part_")]


# ---------------------------------------------------------------------------
# Dimension-level checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("target", [7, 5, 3])
class TestThickDimensions:

    def test_parts_below_target_unchanged(self, target):
        ref = _all_dims(_cfg())
        thick = _all_dims(_cfg(_thick_args(target)))
        for p in range(1, target - 1):
            assert thick[p] == ref[p], f"part {p} changed"
        # Part target-1: only its base widens, to stay flush with the thicker part.
        p = target - 1
        for k in ("inner_radius", "outer_radius", "inside_height", "height"):
            assert thick[p][k] == ref[p][k], f"part {p} {k} changed"
        assert thick[p]["base_radius"] == pytest.approx(ref[p]["base_radius"] + DW)

    def test_parts_at_and_above_target_change(self, target):
        ref = _all_dims(_cfg())
        thick = _all_dims(_cfg(_thick_args(target)))
        for p in range(target, 8):
            n = p - target + 1  # number of thickened parts from target to p
            assert thick[p]["outer_radius"] == pytest.approx(ref[p]["outer_radius"] + n * DW)
            assert thick[p]["base_radius"] > ref[p]["base_radius"]
            assert thick[p]["height"] == pytest.approx(ref[p]["height"] + n * DB)
            # Inner surface grows only by the thickening of the parts inside it.
            assert thick[p]["inner_radius"] == pytest.approx(ref[p]["inner_radius"] + (n - 1) * DW)
            assert thick[p]["inside_height"] == pytest.approx(ref[p]["inside_height"] + (n - 1) * DB)

    def test_target_still_fits_previous_part(self, target):
        ref = _all_dims(_cfg())
        thick = _all_dims(_cfg(_thick_args(target)))
        assert thick[target]["inner_radius"] == ref[target]["inner_radius"]
        assert thick[target]["inside_height"] == ref[target]["inside_height"]

    def test_wall_and_end_cap_thickness(self, target):
        cfg = _cfg(_thick_args(target))
        for p in range(1, 8):
            d = cfg.part_dimensions(p)
            mi, mo, _ni, _no = cfg.get_maze_flags(p)
            wall = d["outer_radius"] - d["inner_radius"] - cfg.mazethickness * (mi + mo)
            cap = cfg.part_height(p) - d["inside_height"]
            if p >= target:
                assert wall == pytest.approx(THICK_WALL)
                assert cap == pytest.approx(THICK_BASE)
            else:
                assert wall == pytest.approx(WALL)
                assert cap == pytest.approx(BASE)


def test_wall_only_and_base_only():
    ref = _all_dims(_cfg())
    wall_only = _all_dims(_cfg(["--thick-wall", str(THICK_WALL)]))
    base_only = _all_dims(_cfg(["--thick-base", str(THICK_BASE)]))
    assert wall_only[7]["height"] == ref[7]["height"]
    assert wall_only[7]["outer_radius"] == pytest.approx(ref[7]["outer_radius"] + DW)
    assert base_only[7]["outer_radius"] == ref[7]["outer_radius"]
    assert base_only[7]["height"] == pytest.approx(ref[7]["height"] + DB)


def test_thick_part_defaults_to_last():
    assert _all_dims(_cfg(["--thick-wall", str(THICK_WALL), "--thick-base", str(THICK_BASE)])) \
        == _all_dims(_cfg(_thick_args(7)))


@pytest.mark.parametrize("extra", [["--inside"], ["--flip"], ["--flip-stagger"], ["--core-solid"]])
def test_other_layouts_below_target_unchanged(extra):
    ref = _all_dims(_cfg(extra))
    thick = _all_dims(_cfg(extra + _thick_args(5)))
    for p in range(1, 4):
        assert thick[p] == ref[p]
    for k in ("inner_radius", "outer_radius", "inside_height", "height"):
        assert thick[4][k] == ref[4][k]
    for p in range(5, 8):
        assert thick[p]["outer_radius"] > ref[p]["outer_radius"]
        assert thick[p]["height"] > ref[p]["height"]


# ---------------------------------------------------------------------------
# Multiple stages (--thick PART:WALL[:BASE], repeatable)
# ---------------------------------------------------------------------------

ARGS_15 = [a if a != "7" else "15" for a in BASE_ARGS[:2]] + BASE_ARGS[2:]
STAGE1 = (6, 4.5, 3.0)
STAGE2 = (12, 6.0, 4.0)


def _cfg15(extra=()):
    cfg = parse_args(ARGS_15 + list(extra))
    assert cfg.validate() is None
    return cfg


def _stage_args(*stages):
    out = []
    for p, w, b in stages:
        out += ["--thick", f"{p}:{'' if w is None else w}:{'' if b is None else b}"]
    return out


def test_two_stages_wall_and_cap_per_part():
    cfg = _cfg15(_stage_args(STAGE1, STAGE2))
    for p in range(1, 16):
        expect_w, expect_b = (WALL, BASE) if p < 6 else STAGE1[1:] if p < 12 else STAGE2[1:]
        assert cfg.wall_t(p) == expect_w
        assert cfg.base_t(p) == expect_b
        d = cfg.part_dimensions(p)
        mi, mo, _ni, _no = cfg.get_maze_flags(p)
        wall = d["outer_radius"] - d["inner_radius"] - cfg.mazethickness * (mi + mo)
        assert wall == pytest.approx(expect_w)
        assert cfg.part_height(p) - d["inside_height"] == pytest.approx(expect_b)


def test_second_stage_builds_on_first():
    ref = _all_dims(_cfg15())
    one = _all_dims(_cfg15(_stage_args(STAGE1)))
    two = _all_dims(_cfg15(_stage_args(STAGE1, STAGE2)))
    # Parts below the first target are untouched by either stage.
    for p in range(1, 5):
        assert one[p] == ref[p] and two[p] == ref[p]
    # Below the second target, adding stage 2 changes nothing but part 11's flush base.
    for p in range(1, 11):
        assert two[p] == one[p], f"part {p} changed"
    for k in ("inner_radius", "outer_radius", "inside_height", "height"):
        assert two[11][k] == one[11][k]
    assert two[11]["base_radius"] == pytest.approx(one[11]["base_radius"] + STAGE2[1] - STAGE1[1])
    # Part 12 still fits part 11 (whose size includes stage 1's thickening).
    assert two[12]["inner_radius"] == pytest.approx(one[12]["inner_radius"])
    assert two[12]["inside_height"] == pytest.approx(one[12]["inside_height"])
    # From part 12 on, each part grows by the extra thickening of 12..p.
    for p in range(12, 16):
        n = p - 12 + 1
        assert two[p]["outer_radius"] == pytest.approx(
            one[p]["outer_radius"] + n * (STAGE2[1] - STAGE1[1]))
        assert two[p]["height"] == pytest.approx(one[p]["height"] + n * (STAGE2[2] - STAGE1[2]))


def test_stage_inherits_missing_values():
    cfg = _cfg15(_stage_args(STAGE1, (12, None, 4.0), (14, 7.0, None)))
    assert [cfg.wall_t(p) for p in (5, 6, 12, 13, 14)] == [WALL, 4.5, 4.5, 4.5, 7.0]
    assert [cfg.base_t(p) for p in (5, 6, 12, 13, 14)] == [BASE, 3.0, 4.0, 4.0, 4.0]


def test_stage_order_on_command_line_does_not_matter():
    assert _all_dims(_cfg15(_stage_args(STAGE2, STAGE1))) == \
        _all_dims(_cfg15(_stage_args(STAGE1, STAGE2)))


def test_single_target_options_equal_one_stage():
    assert _all_dims(_cfg(_thick_args(5))) == \
        _all_dims(_cfg(_stage_args((5, THICK_WALL, THICK_BASE))))


def test_scad_two_stages_below_second_target_identical():
    for p in (5, 10):
        one = _run(ARGS_15 + _stage_args(STAGE1) + ["--part", str(p), "--seed", "7"])
        two = _run(ARGS_15 + _stage_args(STAGE1, STAGE2) + ["--part", str(p), "--seed", "7"])
        assert _geometry_lines(two) == _geometry_lines(one), f"part {p} geometry changed"


@pytest.mark.parametrize("bad", [["--thick", "6:4.5", "--thick", "6:5"],   # duplicate part
                                 ["--thick", "16:4.5"],                     # out of range
                                 ["--thick", "6::"],                        # nothing set
                                 ["--thick", "6:0"],                        # non-positive
                                 ["--thick-wall", "4", "--thick", "15:5"]])  # dup via old opts
def test_stage_validation(bad):
    cfg = parse_args(ARGS_15 + bad)
    assert cfg.validate() is not None


@pytest.mark.parametrize("bad", ["6", "6:a", "6:1:2:3"])
def test_stage_parse_errors(bad):
    with pytest.raises(SystemExit):
        parse_args(ARGS_15 + ["--thick", bad])


@pytest.mark.parametrize("bad", [["--thick-part", "8"], ["--thick-part", "-1"],
                                 ["--thick-wall", "0"], ["--thick-base", "-1"]])
def test_validation(bad):
    cfg = parse_args(BASE_ARGS + bad)
    assert cfg.validate() is not None


# ---------------------------------------------------------------------------
# Generated OpenSCAD checks
# ---------------------------------------------------------------------------

def test_scad_parts_below_target_identical():
    target = 5
    for p in range(1, target - 1):
        ref = _run(BASE_ARGS + ["--part", str(p), "--seed", "7"])
        thick = _run(BASE_ARGS + _thick_args(target) + ["--part", str(p), "--seed", "7"])
        assert _geometry_lines(thick) == _geometry_lines(ref), f"part {p} geometry changed"


@pytest.mark.parametrize("p", [5, 6, 7])
def test_scad_parts_at_or_above_target_differ(p):
    ref = _run(BASE_ARGS + ["--part", str(p), "--seed", "7"])
    thick = _run(BASE_ARGS + _thick_args(5) + ["--part", str(p), "--seed", "7"])
    assert _geometry_lines(thick) != _geometry_lines(ref)


def _scad_vars(text):
    return {m.group(1): m.group(2)
            for m in re.finditer(r"^(part_\w+) = (.*);$", text, re.M)}


def test_scad_dimension_variables_single_part():
    text = _run(BASE_ARGS + _thick_args(7) + ["--part", "7", "--seed", "7"])
    cfg = _cfg(_thick_args(7))
    d = cfg.part_dimensions(7)
    v = _scad_vars(text)
    assert v["part_number"] == "7"
    for k in ("inner_radius", "outer_radius", "base_radius", "inside_height"):
        assert float(v[f"part_{k}"]) == pytest.approx(d[k], abs=1e-3)
    assert v["part_inner_radii"].split(",")[0] == "[undef"
    m = re.search(r"^// PART_DIMENSIONS part=7 (.*)$", text, re.M)
    assert m
    fields = dict(f.split("=") for f in m.group(1).split())
    assert float(fields["inside_height"]) == pytest.approx(d["inside_height"], abs=1e-3)
    # Assignments must be top-level (before the scale block) to be visible.
    assert text.index("part_inner_radius =") < text.index("scale(0.001){")


def test_scad_dimension_lists_all_parts():
    text = _run(["--parts", "3", "--helix", "2", "--seed", "1"])
    v = _scad_vars(text)
    assert "part_number" not in v
    radii = v["part_outer_radii"].strip("[]").split(",")
    assert radii[0] == "undef" and len(radii) == 4
    assert len(re.findall(r"^// PART_DIMENSIONS ", text, re.M)) == 3
