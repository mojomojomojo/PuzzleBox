"""Nub (interlocking bump) polyhedron generation."""

from __future__ import annotations

import math
from io import StringIO

from .config import Config
from .geometry import scaled

SCALE = 1000


def write_nub(out: StringIO, cfg: Config, r: float, inside: int,
              height: float, part_entrya: float):
    """Generate the interlocking nub polyhedron.

    Creates nubs around the circumference that connect puzzle box parts.
    32-point polyhedron (two 4x4 grids) with fixed face indices.
    """
    helix = cfg.helix
    nubs = cfg.nubs

    ri = r + (-cfg.mazethickness if inside else cfg.mazethickness) * cfg.nubnormal
    W_nub = int((ri + (-cfg.clearance if inside else cfg.clearance)) * 2 * math.pi / cfg.mazestep) // nubs * nubs
    da = 2 * math.pi / W_nub / 4 * cfg.nubhorizontal
    dz = (cfg.mazestep / 4 - cfg.nubzclearance) * cfg.nubvertical
    my = cfg.mazestep * da * 4 * helix / (r * 2 * math.pi)

    if inside:
        da = -da
    elif cfg.mirrorinside:
        my = -my

    a = -da * 1.5  # Centre angle
    z = height - cfg.mazestep / 2 - (0 if cfg.parkvertical else cfg.mazestep / 8) - dz * 1.5 - my * 1.5 - cfg.nubdistance

    out.write(f"// NUB ({r:.6f}) inside?({inside})\n")
    out.write(f"rotate([0,0,{part_entrya:f}])for(a=[0:{360.0 / nubs:f}:359])rotate([0,0,a])polyhedron(points=[")

    # Front face points (with nub protrusion)
    r_front = r + (cfg.nubrclearance if inside else -cfg.nubrclearance)
    ri_front = ri + (cfg.nubrclearance if inside else -cfg.nubrclearance)

    for Z in range(4):
        for X in range(4):
            use_ri = (X == 1 or X == 2) and (Z == 1 or Z == 2)
            rr = ri_front if use_ri else r_front
            out.write(f"[{scaled(rr * math.sin(a + da * X))},"
                      f"{scaled(rr * math.cos(a + da * X))},"
                      f"{scaled(z + Z * dz + X * my + (cfg.nubskew if (Z == 1 or Z == 2) else 0))}],")

    # Back face points (at wall surface)
    r_back = r_front + (cfg.clearance - cfg.nubrclearance if inside else -cfg.clearance + cfg.nubrclearance)

    for Z in range(4):
        for X in range(4):
            out.write(f"[{scaled(r_back * math.sin(a + da * X))},"
                      f"{scaled(r_back * math.cos(a + da * X))},"
                      f"{scaled(z + Z * dz + X * my + (cfg.nubskew if (Z == 1 or Z == 2) else 0))}],")

    out.write("],faces=[")

    # Back face grid
    for Z in range(3):
        for X in range(3):
            out.write(f"[{Z*4+X+20},{Z*4+X+21},{Z*4+X+17}],"
                      f"[{Z*4+X+20},{Z*4+X+17},{Z*4+X+16}],")

    # Side faces (left/right)
    for Z in range(3):
        out.write(f"[{Z*4+4},{Z*4+20},{Z*4+16}],"
                  f"[{Z*4+4},{Z*4+16},{Z*4+0}],"
                  f"[{Z*4+23},{Z*4+7},{Z*4+3}],"
                  f"[{Z*4+23},{Z*4+3},{Z*4+19}],")

    # Top/bottom faces
    for X in range(3):
        out.write(f"[{X+28},{X+12},{X+13}],"
                  f"[{X+28},{X+13},{X+29}],"
                  f"[{X+0},{X+16},{X+17}],"
                  f"[{X+0},{X+17},{X+1}],")

    # Front face grid
    out.write("[0,1,5],[0,5,4],[4,5,9],[4,9,8],[8,9,12],[9,13,12],")
    out.write("[1,2,6],[1,6,5],[5,6,10],[5,10,9],[9,10,14],[9,14,13],")
    out.write("[2,3,6],[3,7,6],[6,7,11],[6,11,10],[10,11,15],[10,15,14],")
    out.write("]);\n")
