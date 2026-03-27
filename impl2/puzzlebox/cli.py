"""Command-line argument parsing for puzzlebox — maps all C popt flags to argparse."""

from __future__ import annotations

import argparse
from typing import List, Optional

from .config import Config


def build_parser() -> argparse.ArgumentParser:
    """Build argparse parser matching all C optionsTable entries."""
    p = argparse.ArgumentParser(
        description="Puzzle box maker — generates OpenSCAD for 3D-printable cylindrical maze puzzle boxes."
    )

    # Boolean flags (POPT_ARG_NONE)
    p.add_argument("--stl", "-l", action="store_true", default=False,
                   help="Run output through openscad to make stl")
    p.add_argument("--resin", "-R", action="store_true", default=False,
                   help="Half all specified clearances for resin printing")
    p.add_argument("--inside", "-i", action="store_true", default=False,
                   help="Maze on inside (hard)")
    p.add_argument("--flip", "-f", action="store_true", default=False,
                   help="Alternating inside/outside maze")
    p.add_argument("--flip-stagger", action="store_true", default=False,
                   help="Mazes on even parts, nubs on odd parts (opposite of --flip)")
    p.add_argument("--core-solid", "-q", action="store_true", default=False,
                   help="Core solid (content is in part 2)")
    p.add_argument("--park-vertical", "-v", action="store_true", default=False,
                   help="Park vertically")
    p.add_argument("--base-wide", "-W", action="store_true", default=False,
                   help="Inside base full width")
    p.add_argument("--text-slow", "-d", action="store_true", default=False,
                   help="Text has diagonal edges")
    p.add_argument("--text-outset", "-O", action="store_true", default=False,
                   help="Text on sides is outset not embossed")
    p.add_argument("--symmetric-cut", "-V", action="store_true", default=False,
                   help="Symmetric maze cut")
    p.add_argument("--ajk-logo", "-A", action="store_true", default=False,
                   help="Include AJK logo in last lid")
    p.add_argument("--aa-logo", "-a", action="store_true", default=False,
                   help="Include A&A logo in last lid")
    p.add_argument("--test", "-Q", action="store_true", default=False,
                   help="Test pattern instead of maze")
    p.add_argument("--fix-nubs", action="store_true", default=False,
                   help="Fix nub position opposite maze exit")
    p.add_argument("--mime", action="store_true", default=None,
                   help="MIME Header")
    p.add_argument("--no-a", action="store_true", default=False,
                   help="No A in design")
    p.add_argument("--web-form", action="store_true", default=False,
                   help="Web form")

    # Integer flags (POPT_ARG_INT)
    p.add_argument("--parts", "-m", type=int, default=2,
                   help="Total parts (default: 2)")
    p.add_argument("--part", "-n", type=int, default=0,
                   help="Which part to make (0 for all)")
    p.add_argument("--nubs", "-N", type=int, default=None,
                   help="Nubs (default: helix)")
    p.add_argument("--helix", "-H", type=int, default=2,
                   help="Helix (default: 2, 0=non-helical, negative=reverse/clockwise)")
    p.add_argument("--outer-sides", "-s", type=int, default=7,
                   help="Number of outer sides (0=round, default: 7)")
    p.add_argument("--maze-complexity", "-X", type=int, default=5,
                   help="Maze complexity -10 to 10 (default: 5)")

    # Double flags (POPT_ARG_DOUBLE)
    p.add_argument("--core-diameter", "-c", type=float, default=30.0,
                   help="Core diameter (mm, default: 30)")
    p.add_argument("--core-height", type=float, default=50.0,
                   help="Core height (mm, default: 50)")
    p.add_argument("--core-gap", "-C", type=float, default=0.0,
                   help="Core gap (mm, default: 0)")
    p.add_argument("--base-height", "-b", type=float, default=10.0,
                   help="Base height (mm, default: 10)")
    p.add_argument("--base-thickness", "-B", type=float, default=1.6,
                   help="Base thickness (mm, default: 1.6)")
    p.add_argument("--base-gap", "-Z", type=float, default=0.4,
                   help="Base gap Z clearance (mm, default: 0.4)")
    p.add_argument("--part-thickness", "-w", type=float, default=1.2,
                   help="Wall thickness (mm, default: 1.2)")
    p.add_argument("--maze-thickness", "-t", type=float, default=2.0,
                   help="Maze thickness (mm, default: 2)")
    p.add_argument("--maze-step", "-z", type=float, default=3.0,
                   help="Maze spacing (mm, default: 3)")
    p.add_argument("--maze-margin", "-M", type=float, default=1.0,
                   help="Maze top margin (mm, default: 1)")
    p.add_argument("--top-space", "-T", type=float, default=0.0,
                   help="Extra space above maze top (mm, default: 0)")
    p.add_argument("--park-thickness", "-p", type=float, default=0.7,
                   help="Park ridge thickness (mm, default: 0.7)")
    p.add_argument("--clearance", "-g", type=float, default=0.4,
                   help="General X/Y clearance (mm, default: 0.4)")
    p.add_argument("--nub-r-clearance", "-y", type=float, default=0.1,
                   help="Extra radius clearance for nub (mm, default: 0.1)")
    p.add_argument("--nub-z-clearance", type=float, default=0.2,
                   help="Extra Z clearance for nub (mm, default: 0.2)")
    p.add_argument("--nub-horizontal", type=float, default=1.0,
                   help="Nub horizontal size multiplier (default: 1.0)")
    p.add_argument("--nub-vertical", type=float, default=1.0,
                   help="Nub vertical size multiplier (default: 1.0)")
    p.add_argument("--nub-normal", type=float, default=1.0,
                   help="Nub normal (radial depth) multiplier (default: 1.0)")
    p.add_argument("--nub-distance", type=float, default=0.0,
                   help="Distance from end to place nubs (mm, default: 0)")
    p.add_argument("--outer-round", "-r", type=float, default=2.0,
                   help="Outer rounding on ends (mm, default: 2)")
    p.add_argument("--grip-depth", "-G", type=float, default=1.5,
                   help="Grip depth (mm, default: 1.5)")
    p.add_argument("--text-depth", "-D", type=float, default=0.5,
                   help="Text depth (mm, default: 0.5)")
    p.add_argument("--text-side-scale", type=float, default=100.0,
                   help="Scale side text percent (default: 100)")
    p.add_argument("--logo-depth", "-L", type=float, default=0.6,
                   help="Logo cut depth (mm, default: 0.6)")

    # String flags (POPT_ARG_STRING)
    p.add_argument("--text-end", "-E", type=str, default=None,
                   help="Text (initials) on end")
    p.add_argument("--text-inside", "-I", type=str, default=None,
                   help="Text (initials) inside end")
    p.add_argument("--text-side", "-S", type=str, default=None,
                   help="Text on sides")
    p.add_argument("--text-font", "-F", type=str, default=None,
                   help="Text font")
    p.add_argument("--text-font-end", "-e", type=str, default=None,
                   help="Font for end text")
    p.add_argument("--out-file", type=str, default=None,
                   help="Output to file")
    p.add_argument("--load-maze-inside", type=str, default=None,
                   help="Load pre-generated inside maze from file")
    p.add_argument("--load-maze-outside", type=str, default=None,
                   help="Load pre-generated outside maze from file")
    p.add_argument("--save-maze-inside", type=str, default=None,
                   help="Save generated inside maze to file")
    p.add_argument("--save-maze-outside", type=str, default=None,
                   help="Save generated outside maze to file")

    # Python-only
    p.add_argument("--seed", type=int, default=None,
                   help="Random seed for deterministic maze generation (Python-only)")

    return p


def parse_args(argv: Optional[List[str]] = None) -> Config:
    """Parse command-line args and return a populated Config."""
    parser = build_parser()
    args = parser.parse_args(argv)

    cfg = Config(
        basethickness=args.base_thickness,
        basegap=args.base_gap,
        baseheight=args.base_height,
        corediameter=args.core_diameter,
        coreheight=args.core_height,
        wallthickness=args.part_thickness,
        mazethickness=args.maze_thickness,
        mazestep=args.maze_step,
        topspace=args.top_space,
        clearance=args.clearance,
        nubrclearance=args.nub_r_clearance,
        nubzclearance=args.nub_z_clearance,
        nubhorizontal=args.nub_horizontal,
        nubvertical=args.nub_vertical,
        nubnormal=args.nub_normal,
        nubdistance=args.nub_distance,
        parkthickness=args.park_thickness,
        coregap=args.core_gap,
        outerround=args.outer_round,
        mazemargin=args.maze_margin,
        textdepth=args.text_depth,
        logodepth=args.logo_depth,
        gripdepth=args.grip_depth,
        textsidescale=args.text_side_scale,
        textinside=args.text_inside,
        textend=args.text_end,
        textsides=args.text_side,
        textfont=args.text_font,
        textfontend=args.text_font_end,
        parts=args.parts,
        part=args.part,
        inside=int(args.inside),
        flip=int(args.flip),
        flip_stagger=int(args.flip_stagger),
        outersides=args.outer_sides,
        testmaze=int(args.test),
        helix=args.helix,
        nubs=args.nubs if args.nubs is not None else -1,
        aalogo=int(args.aa_logo),
        ajklogo=int(args.ajk_logo),
        textslow=int(args.text_slow),
        textoutset=int(args.text_outset),
        symmetriccut=int(args.symmetric_cut),
        coresolid=int(args.core_solid),
        parkvertical=int(args.park_vertical),
        mazecomplexity=args.maze_complexity,
        fixnubs=int(args.fix_nubs),
        noa=int(args.no_a),
        basewide=int(args.base_wide),
        stl=int(args.stl),
        resin=int(args.resin),
        webform=int(args.web_form),
        outfile=args.out_file,
        loadmazeinside=args.load_maze_inside,
        loadmazeoutside=args.load_maze_outside,
        savemazeinside=args.save_maze_inside,
        savemazeoutside=args.save_maze_outside,
        seed=args.seed,
    )

    if args.mime is not None:
        cfg.mime = int(args.mime)

    return cfg
