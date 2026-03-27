"""OpenSCAD output orchestrator — assembles all geometry into .scad output."""

from __future__ import annotations

import math
import os
import random
import time
from io import StringIO
from typing import Optional

from .config import Config
from .geometry import MazePolyhedronBuilder, scaled
from .maze import Maze, FLAGA, FLAGI, create_rng
from .maze_io import save_maze, load_maze
from .nub import write_nub
from .text import (
    write_cuttext_module, write_ajk_logo_module, write_aa_logo_module,
    write_outer_module, write_text_end, write_text_sides,
    write_logo, write_mark,
)
from .visualization import MazeVisualization


def generate(cfg: Config, out: StringIO):
    """Main entry point — generate complete OpenSCAD output."""
    err = cfg.validate()
    if err:
        out.write(f"// ** {err} **\n")
        return

    cfg.basethickness += cfg.logodepth

    _write_header(out, cfg)
    _write_modules(out, cfg)

    out.write(f"scale(0.001){{\n")

    if cfg.part:
        _box(out, cfg, cfg.part, 0.0, 0.0)
    else:
        sq = int(math.sqrt(cfg.parts) + 0.5)
        n = sq * sq - cfg.parts
        layout_x = 0.0
        layout_y = 0.0
        for p in range(1, cfg.parts + 1):
            _box(out, cfg, p, layout_x, layout_y)
            outersides = cfg.outersides if cfg.outersides else 100
            pr3 = cfg.part_r3s[p]
            pr2 = cfg.part_r2s[p]
            layout_x += (pr3 if outersides & 1 else pr2) + pr2 + 5
            n += 1
            if n >= sq:
                n = 0
                layout_x = 0.0
                layout_y += (pr3 if outersides & 1 else pr2) * 2 + 5

    out.write("}\n")


def _write_header(out: StringIO, cfg: Config):
    """Write attribution and parameter header comments."""
    out.write("// Puzzlebox by RevK, @TheRealRevK www.me.uk\n")
    out.write("// Thingiverse examples and instructions https://www.thingiverse.com/thing:2410748\n")
    out.write("// GitHub source https://github.com/revk/PuzzleBox\n")
    out.write("// Get new random custom maze gift boxes from https://www.me.uk/puzzlebox\n")

    t = time.gmtime()
    out.write(f"// Created {t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
              f"T{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}Z"
              f" {os.environ.get('REMOTE_ADDR', '')}\n")

    # Document active parameters
    _write_param_comments(out, cfg)


def _write_param_comments(out: StringIO, cfg: Config):
    """Write parameter documentation comments matching the C output."""
    # Integer flags
    for name, val in [
        ("STL", cfg.stl), ("Resin mode", cfg.resin),
        ("Mirror inside", cfg.mirrorinside), ("AJK logo", cfg.ajklogo),
        ("A&A logo", cfg.aalogo), ("Flip", cfg.flip),
        ("Flip stagger", cfg.flip_stagger), ("Core solid", cfg.coresolid),
        ("Park vertical", cfg.parkvertical), ("No A", cfg.noa),
        ("Fix nubs", cfg.fixnubs), ("Base wide", cfg.basewide),
        ("Symmetric cut", cfg.symmetriccut), ("Text slow", cfg.textslow),
        ("Text outset", cfg.textoutset), ("Test maze", cfg.testmaze),
    ]:
        if val:
            out.write(f"// {name}\n")

    # Integer values
    for name, val in [
        ("Parts", cfg.parts), ("Part", cfg.part),
        ("Outer sides", cfg.outersides),
        ("Helix", cfg.helix), ("Nubs", cfg.nubs),
        ("Maze complexity", cfg.mazecomplexity),
    ]:
        if val:
            out.write(f"// {name}: {val}\n")

    # Float values
    for name, val in [
        ("Core diameter", cfg.corediameter), ("Core height", cfg.coreheight),
        ("Base thickness", cfg.basethickness - cfg.logodepth),  # Undo adjust
        ("Base gap", cfg.basegap), ("Base height", cfg.baseheight),
        ("Wall thickness", cfg.wallthickness), ("Maze thickness", cfg.mazethickness),
        ("Maze step", cfg.mazestep), ("Clearance", cfg.clearance),
        ("Outer round", cfg.outerround), ("Maze margin", cfg.mazemargin),
        ("Top space", cfg.topspace), ("Grip depth", cfg.gripdepth),
        ("Park thickness", cfg.parkthickness), ("Core gap", cfg.coregap),
        ("Nub distance", cfg.nubdistance),
        ("Nub R clearance", cfg.nubrclearance), ("Nub Z clearance", cfg.nubzclearance),
        ("Nub horizontal", cfg.nubhorizontal), ("Nub vertical", cfg.nubvertical),
        ("Nub normal", cfg.nubnormal),
        ("Text depth", cfg.textdepth), ("Logo depth", cfg.logodepth),
        ("Text side scale", cfg.textsidescale),
    ]:
        if val:
            out.write(f"// {name}: {val}\n")

    # String values
    for name, val in [
        ("Text end", cfg.textend), ("Text sides", cfg.textsides),
        ("Text inside", cfg.textinside), ("Font", cfg.textfont),
        ("Font end", cfg.textfontend),
    ]:
        if val:
            out.write(f"// {name}: {val}\n")


def _write_modules(out: StringIO, cfg: Config):
    """Write OpenSCAD module definitions."""
    write_cuttext_module(out, cfg)
    if cfg.ajklogo:
        write_ajk_logo_module(out)
    elif cfg.aalogo:
        write_aa_logo_module(out)

    # outer() module — used by box
    outersides = cfg.outersides if cfg.outersides else 100
    out.write(
        f"module outer(h,r){{e={scaled(cfg.outerround)};minkowski(){{"
        f"cylinder(r1=0,r2=e,h=e,$fn=24);"
        f"cylinder(h=h-e,r=r,$fn={outersides});}}}}\n"
    )


def _box(out: StringIO, cfg: Config, part: int, layout_x: float = 0.0, layout_y: float = 0.0):
    """Generate one part of the puzzle box."""
    rng = create_rng(cfg)  # Per-part RNG (C uses /dev/urandom per read)

    part_r0 = cfg.part_r0s[part]
    part_r1 = cfg.part_r1s[part]
    part_r2 = cfg.part_r2s[part]
    part_r3 = cfg.part_r3s[part]
    mazeinside, mazeoutside, nextinside, nextoutside = cfg.get_maze_flags(part)
    W = int(part_r1 * 2 * math.pi / cfg.mazestep) // cfg.nubs * cfg.nubs
    W4 = W * 4

    height = ((cfg.coregap + cfg.baseheight if cfg.coresolid else 0) +
              cfg.coreheight + cfg.basethickness +
              (cfg.basethickness + cfg.basegap) * (part - 1))
    if part == 1:
        height -= cfg.coreheight if cfg.coresolid else cfg.coregap
    if part > 1:
        height -= cfg.baseheight

    out.write(f"// Part {part} ({part_r0:.2f}mm to {part_r1:.2f}mm and {part_r2:.2f}mm/{part_r3:.2f}mm base)\n")

    part_entrya = 0.0
    part_mazeexit = 0.0

    # Generate mazes (updates W like C's nested function)
    if mazeinside:
        part_entrya, part_mazeexit, W = _makemaze(
            out, cfg, rng, part, part_r0, 1, height)
    if mazeoutside:
        part_entrya, part_mazeexit, W = _makemaze(
            out, cfg, rng, part, part_r1, 0, height)
    W4 = W * 4

    # Part positioning
    outersides = cfg.outersides if cfg.outersides else 100
    x_off = layout_x + ((part_r3 if cfg.outersides & 1 else part_r2) if cfg.part == 0 else 0)
    y_off = layout_y + ((part_r3 if cfg.outersides & 1 else part_r2) if cfg.part == 0 else 0)

    out.write(f"translate([{scaled(x_off)},{scaled(y_off)},0])\n")
    if cfg.outersides:
        rot = 180.0 / cfg.outersides + (180 if part + 1 == cfg.parts else 0)
        out.write(f"rotate([0,0,{rot:f}])")
    out.write("{\n")

    # Maze geometry
    out.write("// Maze\ndifference(){union(){")
    if mazeinside:
        _write_maze_polyhedron(out, cfg, part, part_r0, 1, height)
    if mazeoutside:
        _write_maze_polyhedron(out, cfg, part, part_r1, 0, height)
    if not mazeinside and not mazeoutside and part < cfg.parts:
        # Non-maze thin wall
        out.write("difference(){\n")
        out.write(f"translate([0,0,{scaled(cfg.basethickness / 2 - cfg.clearance)}])"
                  f"cylinder(r={scaled(part_r1)},h={scaled(height - cfg.basethickness / 2 + cfg.clearance)},$fn={W4});"
                  f"translate([0,0,{scaled(cfg.basethickness)}])"
                  f"cylinder(r={scaled(part_r0)},h={scaled(height)},$fn={W4});\n")
        out.write("}\n")

    # Base
    out.write("// BASE\ndifference(){\n")
    cos_val = math.cos(math.pi / outersides)
    if part == cfg.parts:
        out.write(f"outer({scaled(height)},{scaled((part_r2 - cfg.outerround) / cos_val)});\n")
    elif part + 1 >= cfg.parts:
        out.write(f"mirror([1,0,0])outer({scaled(cfg.baseheight)},{scaled((part_r2 - cfg.outerround) / cos_val)});\n")
    else:
        out.write(f"hull(){{cylinder(r={scaled(part_r2 - cfg.mazethickness)},"
                  f"h={scaled(cfg.baseheight)},$fn={W4});"
                  f"translate([0,0,{scaled(cfg.mazemargin)}])"
                  f"cylinder(r={scaled(part_r2)},h={scaled(cfg.baseheight - cfg.mazemargin)},$fn={W4});}}\n")

    hole_r = (part_r0 +
              (cfg.mazethickness + cfg.clearance if part > 1 and mazeinside else 0) +
              (cfg.clearance if not mazeinside and part < cfg.parts else 0))
    out.write(f"translate([0,0,{scaled(cfg.basethickness)}])"
              f"cylinder(r={scaled(hole_r)},h={scaled(height)},$fn={W4});\n")
    out.write("}\n")  # close BASE difference
    out.write("}\n")  # close union

    # --- Inside difference, outside union (subtracted from geometry) ---

    # Grip cutouts
    if cfg.gripdepth:
        if part + 1 < cfg.parts:
            out.write(f"rotate([0,0,{360.0 / W4 / 2:f}])"
                      f"translate([0,0,{scaled(cfg.mazemargin + (cfg.baseheight - cfg.mazemargin) / 2)}])"
                      f"rotate_extrude(start=180,angle=360,convexity=10,$fn={W4})"
                      f"translate([{scaled(part_r2 + cfg.gripdepth)},0,0])"
                      f"circle(r={scaled(cfg.gripdepth * 2)},$fn=9);\n")
        elif part + 1 == cfg.parts:
            out.write(f"translate([0,0,{scaled(cfg.outerround + (cfg.baseheight - cfg.outerround) / 2)}])"
                      f"rotate_extrude(start=180,angle=360,convexity=10,$fn={outersides})"
                      f"translate([{scaled(part_r3 + cfg.gripdepth)},0,0])"
                      f"circle(r={scaled(cfg.gripdepth * 2)},$fn=9);\n")

    # Basewide connectors
    if cfg.basewide and nextoutside and part + 1 < cfg.parts:
        Wbw = int((part_r2 - cfg.mazethickness) * 2 * math.pi / cfg.mazestep) // cfg.nubs * cfg.nubs
        wi = 2 * (part_r2 - cfg.mazethickness) * 2 * math.pi / Wbw / 4
        wo = 2 * part_r2 * 2 * math.pi * 3 / Wbw / 4
        out.write(f"for(a=[0:{360.0 / cfg.nubs:f}:359])rotate([0,0,a])"
                  f"translate([0,{scaled(part_r2)},0])hull(){{"
                  f"cube([{scaled(wi)},{scaled(cfg.mazethickness * 2)},{scaled(cfg.baseheight * 2 + cfg.clearance)}],center=true);"
                  f"cube([{scaled(wo)},0.01,{scaled(cfg.baseheight * 2 + cfg.clearance)}],center=true);}}\n")

    # Text (embossed/cut — subtracted)
    write_text_end(out, cfg, part, part_r2)

    if cfg.textsides and part == cfg.parts and cfg.outersides and not cfg.textoutset:
        write_text_sides(out, cfg, part, part_r2, part_r3, height, 0)

    write_logo(out, cfg, part, part_r0)

    if cfg.markpos0 and part + 1 >= cfg.parts:
        write_mark(out, cfg, part, part_r0, part_r1, height,
                   part_entrya, mazeinside, mazeoutside, W4)

    out.write("}\n")  # close outer difference

    # --- Outside difference, inside translate/rotate (added geometry) ---

    # Text outset (raised, outside the difference block)
    if cfg.textsides and part == cfg.parts and cfg.outersides and cfg.textoutset:
        write_text_sides(out, cfg, part, part_r2, part_r3, height, 1)

    # Solid core
    if cfg.coresolid and part == 1:
        core_r = (part_r0 + cfg.clearance +
                  (cfg.clearance if not mazeinside and part < cfg.parts else 0))
        out.write(f"translate([0,0,{scaled(cfg.basethickness)}])"
                  f"cylinder(r={scaled(core_r)},h={scaled(height - cfg.basethickness)},$fn={W4});\n")

    # Nub entry angle
    if ((mazeoutside and not cfg.flip and not cfg.flip_stagger and part == cfg.parts)
            or (not mazeoutside and part + 1 == cfg.parts)):
        part_entrya = 0.0
    elif cfg.fixnubs:
        part_entrya = cfg.globalexit + 180.0
        if part_entrya >= 360.0:
            part_entrya -= 360.0
    elif part < cfg.parts and not cfg.basewide:
        part_entrya = rng.randint(0, 0x7FFFFFFF) % 360

    # Nubs (added outside difference)
    if not mazeinside and part > 1:
        write_nub(out, cfg, part_r0, 1, height, part_entrya)
    if not mazeoutside and part < cfg.parts:
        write_nub(out, cfg, part_r1, 0, height, part_entrya)

    out.write("}\n")  # close translate/rotate block


def _compute_maze_params(cfg: Config, r: float, inside: int, part: int, height: float):
    """Compute W, H, base, y0, dy, margin for a maze surface."""
    nubs = cfg.nubs
    helix = cfg.helix
    abs_helix = abs(helix)
    mazestep = cfg.mazestep

    W = int((r + (cfg.mazethickness if inside else -cfg.mazethickness)) * 2 * math.pi / mazestep) // nubs * nubs
    base = cfg.basethickness if inside else cfg.baseheight
    if (inside and part > 1) or (not inside and part < cfg.parts):
        base += cfg.nubdistance
    base += cfg.coreheight if cfg.coresolid else 0
    if inside:
        base += cfg.basegap

    h = height - base - cfg.mazemargin - cfg.topspace - (mazestep / 4 if cfg.parkvertical else 0) - mazestep / 8
    H_raw = int(h / mazestep)
    H = H_raw + 2 + abs_helix

    y0 = base + mazestep / 2 - mazestep * (abs_helix + 1) + mazestep / 8
    dy = mazestep * helix / W if helix else 0
    margin = cfg.mazemargin

    if W < 3 or H < 1:
        raise RuntimeError("Too small")

    return W, H, H_raw, base, y0, dy, margin


def _makemaze(out: StringIO, cfg: Config, rng: random.Random,
              part: int, r: float, inside: int, height: float):
    """Generate a maze. Returns (part_entrya, part_mazeexit, W).

    Defers visualization to _write_maze_polyhedron so output order matches C.
    """
    W, H, H_raw, base, y0, dy, margin = _compute_maze_params(cfg, r, inside, part, height)
    helix = cfg.helix
    abs_helix = abs(helix)
    nubs = cfg.nubs

    # Buffer for comments/viz that should appear before the polyhedron
    pre_buf = StringIO()

    pre_buf.write(f"// Maze {'inside' if inside else 'outside'} {W}/{H_raw} helix={helix}"
                  f" ({'counter-clockwise' if helix > 0 else 'clockwise' if helix < 0 else 'none'})\n")

    maze = Maze(W, H, helix, nubs)

    # Load or generate
    loadfile = cfg.loadmazeinside if inside else cfg.loadmazeoutside
    savefile = cfg.savemazeinside if inside else cfg.savemazeoutside

    if loadfile:
        loaded_maze, loaded_maxx, loaded_helix = load_maze(loadfile, W, H)
        # Copy loaded data into our maze
        maze = Maze(W, H, helix, nubs)
        for y in range(H):
            for x in range(W):
                maze.grid[x][y] = loaded_maze.grid[x][y]
        maze.entry_x = loaded_maxx
        if loaded_helix != helix:
            import sys
            print(f"Warning: Loaded maze helix ({loaded_helix}) doesn't match current helix ({helix})",
                  file=sys.stderr)
        pre_buf.write(f"// Loaded {'inside' if inside else 'outside'} maze from {loadfile} "
                      f"(exit_x={loaded_maxx}, helix={loaded_helix})\n")
    else:
        if cfg.testmaze:
            maze.generate_test_pattern(cfg, inside)
        else:
            max_path = maze.generate(cfg, rng, inside)
            pre_buf.write(f"// Path length {max_path}\n")
        maze.create_entry_columns(cfg)

    if savefile:
        save_maze(savefile, maze, maze.entry_x, helix)
        pre_buf.write(f"// Saved {'inside' if inside else 'outside'} maze to {savefile} "
                      f"(exit_x={maze.entry_x}, helix={helix})\n")

    part_entrya = 360.0 * maze.entry_x / W
    part_mazeexit = part_entrya

    if cfg.fixnubs and cfg.globalexit == 0:
        cfg.globalexit = part_entrya

    # Visualization (to buffer)
    vis = MazeVisualization(maze, cfg, inside, stl=bool(cfg.stl))
    vis.render(pre_buf)

    # Store maze and buffered output for later polyhedron building
    if inside:
        cfg._maze_inside = maze
        cfg._maze_inside_params = (W, H, base, y0, dy, margin)
        cfg._maze_inside_pre = pre_buf.getvalue()
    else:
        cfg._maze_outside = maze
        cfg._maze_outside_params = (W, H, base, y0, dy, margin)
        cfg._maze_outside_pre = pre_buf.getvalue()

    return part_entrya, part_mazeexit, W


def _write_maze_polyhedron(out: StringIO, cfg: Config, part: int,
                           r: float, inside: int, height: float):
    """Write the maze polyhedron for a surface."""
    if inside:
        maze = cfg._maze_inside
        W, H, base, y0, dy, margin = cfg._maze_inside_params
        out.write(cfg._maze_inside_pre)
    else:
        maze = cfg._maze_outside
        W, H, base, y0, dy, margin = cfg._maze_outside_params
        out.write(cfg._maze_outside_pre)

    builder = MazePolyhedronBuilder(
        out=out, maze=maze, cfg=cfg, r=r, inside=inside,
        part=part, height=height, margin=margin, y0=y0
    )
    builder.build()
