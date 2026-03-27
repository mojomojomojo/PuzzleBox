"""Text, logo, and alignment mark generation for OpenSCAD output."""

from __future__ import annotations

from io import StringIO

from .config import Config
from .geometry import scaled


def write_cuttext_module(out: StringIO, cfg: Config):
    """Write the cuttext() OpenSCAD module definition."""
    if cfg.textslow:
        out.write(
            f"module cuttext(){{translate([0,0,-{scaled(1)}])minkowski(){{rotate([0,0,22.5])"
            f"cylinder(h={scaled(cfg.textdepth)},d1={scaled(cfg.textdepth)},d2=0,$fn=8);"
            f"linear_extrude(height={scaled(1)},convexity=10)mirror([1,0,0])children();}}}}\n"
        )
    else:
        out.write(
            f"module cuttext(){{linear_extrude(height={scaled(cfg.textdepth)},"
            f"convexity=10,center=true)mirror([1,0,0])children();}}\n"
        )


def write_ajk_logo_module(out: StringIO):
    """Write the AJK logo OpenSCAD module."""
    out.write(
        "module logo(w=100,$fn=120){scale(w/25)translate([0,0,0.5]){ "
        "hull(){translate([-10,-7])sphere(0.5);translate([0,7])sphere(0.5);} "
        "hull(){translate([0,7])sphere(0.5);translate([0,-7])sphere(0.5);} "
        "hull(){translate([0,0])sphere(0.5);translate([6,7])sphere(0.5);} "
        "hull(){translate([0,0])sphere(0.5);translate([6,-7])sphere(0.5);} "
        "hull(){translate([0,0])sphere(0.5);translate([-5,0])sphere(0.5);} "
        "translate([-2.5,-7])rotate_extrude(angle=180,start=180)"
        "translate([2.5,0])rotate(180/$fn)circle(0.5); "
        "translate([-5,-7])sphere(0.5); translate([0,-7])sphere(0.5);}}"
    )


def write_aa_logo_module(out: StringIO):
    """Write the A&A logo OpenSCAD module."""
    out.write(
        "module logo(w=100,white=0,$fn=100){scale(w/100){"
        "if(!white)difference(){circle(d=100.5);circle(d=99.5);}"
        "difference(){if(white)circle(d=100);"
        "difference(){circle(d=92);for(m=[0,1])mirror([m,0,0]){"
        "difference(){translate([24,0,0])circle(r=22.5);"
        "translate([24,0,0])circle(r=15);}"
        "polygon([[1.5,22],[9,22],[9,-18.5],[1.5,-22]]);"
        "}}}}} // A&A Logo is copyright (c) 2013 and trademark Andrews & Arnold Ltd\n"
    )


def write_outer_module(out: StringIO, cfg: Config, W4: int):
    """Write the outer() OpenSCAD module for rounded-edge cylinders."""
    outersides = cfg.outersides if cfg.outersides else 100
    out.write(
        f"module outer(h,r){{e={scaled(cfg.outerround)};minkowski(){{"
        f"cylinder(r1=0,r2=e,h=e,$fn=24);"
        f"cylinder(h=h-e,r=r,$fn={outersides});}}}}\n"
    )


def _cuttext(out: StringIO, s: float, t: str, f: str, outset: int):
    """Generate a cuttext() call with text parameters."""
    if outset:
        out.write("mirror([0,0,1])")
    out.write(f"cuttext()scale({scaled(1)})text(\"{t}\"")
    out.write(",halign=\"center\"")
    out.write(",valign=\"center\"")
    out.write(f",size={s:f}")
    if t and ord(t[0]) > 127:
        out.write(",font=\"Noto Emoji\"")
    elif f:
        out.write(f",font=\"{f}\"")
    out.write(");\n")


def write_text_end(out: StringIO, cfg: Config, part: int,
                   part_r2: float):
    """Write end text for a part."""
    if not cfg.textend:
        return
    out.write("// Text End\n")
    n = 0
    for segment in cfg.textend.split("\\"):
        if segment and n == (cfg.parts - part):
            outersides = cfg.outersides if cfg.outersides else 100
            angle = (1 if part == cfg.parts else -1) * (90 + 180.0 / outersides)
            out.write(f"rotate([0,0,{angle:f}])")
            _cuttext(out, part_r2 - cfg.outerround, segment, cfg.textfontend, 0)
        n += 1


def write_text_sides(out: StringIO, cfg: Config, part: int,
                     part_r2: float, part_r3: float, height: float,
                     outset: int):
    """Write text on outer sides of the polygon."""
    if not cfg.textsides or part != cfg.parts or not cfg.outersides:
        return
    a = 90.0 + 180.0 / cfg.outersides
    h = part_r3 * __import__('math').sin(__import__('math').pi / cfg.outersides) * cfg.textsidescale / 100
    for segment in cfg.textsides.split("\\"):
        if segment:
            out.write(f"rotate([0,0,{a:f}])translate([0,-{scaled(part_r2)},{scaled(cfg.outerround + (height - cfg.outerround) / 2)}])"
                      f"rotate([-90,-90,0])")
            _cuttext(out, h, segment, cfg.textfont, outset)
        a -= 360.0 / cfg.outersides


def write_logo(out: StringIO, cfg: Config, part: int,
               part_r0: float):
    """Write logo or inside text at the base of a part."""
    if cfg.ajklogo and part == cfg.parts:
        out.write(f"translate([0,0,{scaled(cfg.basethickness - cfg.logodepth)}])"
                  f"logo({scaled(part_r0 * 1.8)});\n")
    elif cfg.aalogo and part == cfg.parts:
        out.write(f"translate([0,0,{scaled(cfg.basethickness - cfg.logodepth)}])"
                  f"linear_extrude(height={scaled(cfg.logodepth * 2)},convexity=10)"
                  f"logo({scaled(part_r0 * 1.8)},white=true);\n")
    elif cfg.textinside:
        out.write(
            f"translate([0,0,{scaled(cfg.basethickness - cfg.logodepth)}])"
            f"linear_extrude(height={scaled(cfg.logodepth * 2)},convexity=10)"
            f"text(\"{cfg.textinside}\",font=\"{cfg.textfontend}\","
            f"size={scaled(part_r0)},halign=\"center\",valign=\"center\");\n"
        )


def write_mark(out: StringIO, cfg: Config, part: int,
               part_r0: float, part_r1: float, height: float,
               part_entrya: float, mazeinside: int, mazeoutside: int,
               W4: int):
    """Write alignment mark at position 0."""
    markpos0 = cfg.outersides and (cfg.outersides // cfg.nubs * cfg.nubs != cfg.outersides)
    if not markpos0 or part + 1 < cfg.parts:
        return
    r = part_r0 + cfg.wallthickness / 2
    t = cfg.wallthickness * 2
    if mazeinside:
        r = part_r0 + cfg.mazethickness + cfg.wallthickness / 2
    elif mazeoutside:
        r = part_r1 - cfg.mazethickness - cfg.wallthickness / 2
    if not mazeoutside:
        r -= cfg.wallthickness / 2
        t = cfg.wallthickness * 3 / 2
    a = 0.0
    if part == cfg.parts and mazeinside:
        a = (-1 if cfg.mirrorinside else 1) * part_entrya  # Flipped sign from C since mirror
        # Actually C has: a = (mirrorinside ? 1 : -1) * part_entrya
        a = (1 if cfg.mirrorinside else -1) * part_entrya
    if part + 1 == cfg.parts and mazeoutside:
        a = part_entrya
    out.write(
        f"rotate([0,0,{a:f}])translate([0,{scaled(r)},{scaled(height)}])"
        f"cylinder(d={scaled(t)},h={scaled(cfg.mazestep / 2)},center=true,$fn=4);\n"
    )
