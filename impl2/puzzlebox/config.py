"""Configuration dataclass and parameter validation for puzzlebox."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Config:
    """All puzzle box parameters — mirrors the C variable declarations."""

    # Dimensions
    basethickness: float = 1.6
    basegap: float = 0.4
    baseheight: float = 10.0
    corediameter: float = 30.0
    coreheight: float = 50.0
    wallthickness: float = 1.2
    mazethickness: float = 2.0
    mazestep: float = 3.0
    topspace: float = 0.0
    clearance: float = 0.4
    nubrclearance: float = 0.1
    nubzclearance: float = 0.2
    nubhorizontal: float = 1.0
    nubvertical: float = 1.0
    nubnormal: float = 1.0
    nubdistance: float = 0.0
    parkthickness: float = 0.7
    coregap: float = 0.0
    outerround: float = 2.0
    mazemargin: float = 1.0
    textdepth: float = 0.5
    logodepth: float = 0.6
    gripdepth: float = 1.5
    textsidescale: float = 100.0

    # Text / logo
    textinside: Optional[str] = None
    textend: Optional[str] = None
    textsides: Optional[str] = None
    textfont: Optional[str] = None
    textfontend: Optional[str] = None

    # Integer params
    parts: int = 2
    part: int = 0
    inside: int = 0
    flip: int = 0
    flip_stagger: int = 0
    outersides: int = 7
    testmaze: int = 0
    helix: int = 2
    nubs: int = -1  # sentinel; will be set to helix in validate()
    aalogo: int = 0
    ajklogo: int = 0
    textslow: int = 0
    textoutset: int = 0
    symmetriccut: int = 0
    coresolid: int = 0
    parkvertical: int = 0
    mazecomplexity: int = 5
    mirrorinside: int = 0
    fixnubs: int = 0
    noa: int = 0
    basewide: int = 0
    stl: int = 0
    resin: int = 0

    # Output / IO
    mime: int = field(default_factory=lambda: 1 if os.environ.get("HTTP_HOST") else 0)
    webform: int = 0
    outfile: Optional[str] = None
    loadmazeinside: Optional[str] = None
    loadmazeoutside: Optional[str] = None
    savemazeinside: Optional[str] = None
    savemazeoutside: Optional[str] = None

    # Python-only: deterministic seed
    seed: Optional[int] = None

    # Python-only: thicker walls / end cap from a target part onward.
    # thickpart: first part to thicken (0 = last part). thickwall / thickbase:
    # wall and end-cap thickness (mm) for parts >= thickpart (None = unchanged).
    thickpart: int = 0
    thickwall: Optional[float] = None
    thickbase: Optional[float] = None
    # Multiple stages: (part, wall|None, base|None). Each applies from that part
    # onward until a later stage overrides it; None inherits the earlier value.
    thickstages: List[Tuple[int, Optional[float], Optional[float]]] = field(default_factory=list)

    # Set by generate() when basethickness is bumped by logodepth.
    logo_adjust: float = field(init=False, default=0.0)
    # Merged, sorted stages (populated by validate()).
    stages: List[Tuple[int, Optional[float], Optional[float]]] = field(init=False, default_factory=list)

    # Computed values (populated by validate())
    abs_helix: int = field(init=False, default=0)
    globalexit: float = field(init=False, default=0.0)
    markpos0: int = field(init=False, default=0)
    nubskew: float = field(init=False, default=0.0)
    part_r0s: List[float] = field(init=False, default_factory=list)
    part_r1s: List[float] = field(init=False, default_factory=list)
    part_r2s: List[float] = field(init=False, default_factory=list)
    part_r3s: List[float] = field(init=False, default_factory=list)

    def validate(self) -> Optional[str]:
        """Validate and adjust parameters. Returns error string or None."""
        # Default nubs to abs(helix) — in C, nubs is initialized to helix's
        # default (2), not its runtime value, so nubs is always positive.
        if self.nubs == -1:
            self.nubs = abs(self.helix) if self.helix else 2

        # Resin adjustments
        if self.resin:
            self.basegap /= 2
            self.clearance /= 2
            self.nubrclearance /= 2
            self.nubzclearance /= 2

        # Normalise text
        self.textend = _normalise(self.textend)
        self.textsides = _normalise(self.textsides)
        self.textinside = _normalise(self.textinside)

        if not self.outersides:
            self.textsides = None
        if self.textfont and not self.textfont.strip():
            self.textfont = None
        if self.textfont and not self.textfontend:
            self.textfontend = self.textfont
        if self.textend and not self.textend.strip():
            self.textend = None
        if self.textinside and not self.textinside.strip():
            self.textinside = None
        if self.textsides and not self.textsides.strip():
            self.textsidescale = 0
            self.textsides = None

        self.abs_helix = abs(self.helix)

        # Nub/helix constraints
        if self.helix and self.nubs > 1 and self.nubs < self.abs_helix:
            if not (self.abs_helix % 2) and self.nubs <= self.abs_helix // 2:
                self.nubs = self.abs_helix // 2
            else:
                self.nubs = self.abs_helix
        if self.helix and self.nubs > self.abs_helix:
            self.nubs = self.abs_helix

        # Grip depth clamping
        if self.gripdepth > (self.baseheight - self.outerround) / 5:
            self.gripdepth = (self.baseheight - self.outerround) / 5
        if self.gripdepth > self.mazethickness:
            self.gripdepth = self.mazethickness

        if not self.aalogo and not self.ajklogo and not self.textinside:
            self.logodepth = 0
        if not self.textsides and not self.textend and not self.textinside:
            self.textdepth = 0
        if self.coresolid and self.coregap < self.mazestep * 2:
            self.coregap = self.mazestep * 2

        if self.thickpart < 0 or self.thickpart > self.parts:
            return f"--thick-part must be between 1 and {self.parts} (0 = last part)"
        stages = list(self.thickstages)
        if self.thickwall is not None or self.thickbase is not None:
            stages.append((self.thickpart or self.parts, self.thickwall, self.thickbase))
        seen = set()
        for sp, sw, sb in stages:
            if sp < 1 or sp > self.parts:
                return f"--thick part must be between 1 and {self.parts} (got {sp})"
            if sp in seen:
                return f"--thick part {sp} given more than once"
            seen.add(sp)
            if sw is None and sb is None:
                return f"--thick {sp}: give a wall and/or base thickness"
            if (sw is not None and sw <= 0) or (sb is not None and sb <= 0):
                return f"--thick {sp}: thicknesses must be positive"
        self.stages = sorted(stages)

        # Pre-calculate part radii
        self._calc_part_radii()

        self.markpos0 = int(
            self.outersides
            and (self.outersides // self.nubs * self.nubs != self.outersides)
        )
        self.nubskew = 0.0 if self.symmetriccut else self.mazestep / 8

        return None

    def _calc_part_radii(self):
        """Pre-calculate r0/r1/r2/r3 for each part (1-indexed)."""
        self.part_r0s = [0.0] * (self.parts + 1)
        self.part_r1s = [0.0] * (self.parts + 1)
        self.part_r2s = [0.0] * (self.parts + 1)
        self.part_r3s = [0.0] * (self.parts + 1)

        for p in range(1, self.parts + 1):
            mazeinside = self.inside
            mazeoutside = 1 - self.inside
            nextinside = self.inside
            nextoutside = 1 - self.inside

            if self.flip:
                if p & 1:
                    mazeinside = 1 - mazeinside
                    nextoutside = 1 - nextoutside
                else:
                    mazeoutside = 1 - mazeoutside
                    nextinside = 1 - nextinside

            if self.flip_stagger:
                if p & 1:
                    mazeoutside = 1 - mazeoutside
                    nextinside = 1 - nextinside
                else:
                    mazeinside = 1 - mazeinside
                    nextoutside = 1 - nextoutside

            if p == 1:
                mazeinside = 0
            if p == self.parts:
                mazeoutside = 0
            if p + 1 >= self.parts:
                nextoutside = 0
            if p == self.parts:
                nextinside = 0

            wall = self.wall_t(p)
            r1 = (
                self.corediameter / 2
                + self.wallthickness
                + (p - 1) * (self.wallthickness + self.mazethickness + self.clearance)
            )
            # Extra wall thickness on parts 1..p pushes this part outward.
            # (Added separately so default output stays bit-identical.)
            extra = sum(self.wall_t(q) - self.wallthickness for q in range(1, p + 1))
            if extra:
                r1 += extra
            if self.coresolid:
                r1 -= (
                    self.wall_t(1)
                    + self.mazethickness
                    + self.clearance
                    - (self.mazethickness if self.inside else 0)
                )

            r0 = r1 - wall
            if mazeinside and p > 1:
                r0 -= self.mazethickness
            if mazeoutside and p < self.parts:
                r1 += self.mazethickness

            r2 = r1
            if p < self.parts:
                r2 += self.clearance
            if p + 1 >= self.parts and self.textsides and not self.textoutset:
                r2 += self.textdepth
            if nextinside:
                r2 += self.mazethickness
            # The base sits flush with the NEXT part's outside, so it uses
            # that part's wall thickness.
            if nextoutside or p + 1 == self.parts:
                r2 += self.wall_t(p + 1)
            if self.basewide and p + 1 < self.parts:
                r2 += self.mazethickness if nextoutside else self.wall_t(p + 1)

            r3 = r2
            if self.outersides and p + 1 >= self.parts:
                r3 /= math.cos(math.pi / self.outersides)

            self.part_r0s[p] = r0
            self.part_r1s[p] = r1
            self.part_r2s[p] = r2
            self.part_r3s[p] = r3

    def wall_t(self, part: int) -> float:
        """Wall thickness (mm) for a part: the latest stage at or below it."""
        wall = self.wallthickness
        for sp, sw, _sb in self.stages:
            if sp <= part and sw is not None:
                wall = sw
        return wall

    def base_t(self, part: int) -> float:
        """End-cap (base) thickness (mm) for a part: the latest stage at or below it.

        Includes the logodepth adjustment once generate() has applied it.
        """
        base = self.basethickness
        for sp, _sw, sb in self.stages:
            if sp <= part and sb is not None:
                base = sb + self.logo_adjust
        return base

    def part_height(self, part: int) -> float:
        """Overall height (mm) of a part, from the bottom of its base to its rim."""
        height = ((self.coregap + self.baseheight if self.coresolid else 0) +
                  self.coreheight + self.basethickness +
                  (self.basethickness + self.basegap) * (part - 1))
        if part == 1:
            height -= self.coreheight if self.coresolid else self.coregap
        if part > 1:
            height -= self.baseheight
        # A thicker end cap on part q raises the height of part q and of every
        # part enclosing it; inside heights of parts <= q are unchanged.
        for q in range(1, part + 1):
            extra = self.base_t(q) - self.basethickness
            if extra:
                height += extra
        return height

    def part_dimensions(self, part: int) -> dict:
        """Key dimensions (mm) of a part.

        inner_radius:  innermost surface (wall, or inside-maze ridges).
        outer_radius:  outermost surface of the wall (or outside-maze ridges).
        base_radius:   outer radius of the base (flat-to-centre for polygons).
        inside_height: from the inside floor (top of the end cap) to the rim.
        """
        return {
            "inner_radius": self.part_r0s[part],
            "outer_radius": self.part_r1s[part],
            "base_radius": self.part_r2s[part],
            "inside_height": self.part_height(part) - self.base_t(part),
        }

    def get_maze_flags(self, part: int):
        """Return (mazeinside, mazeoutside, nextinside, nextoutside) for a part."""
        mazeinside = self.inside
        mazeoutside = 1 - self.inside
        nextinside = self.inside
        nextoutside = 1 - self.inside

        if self.flip:
            if part & 1:
                mazeinside = 1 - mazeinside
                nextoutside = 1 - nextoutside
            else:
                mazeoutside = 1 - mazeoutside
                nextinside = 1 - nextinside

        if self.flip_stagger:
            if part & 1:
                mazeoutside = 1 - mazeoutside
                nextinside = 1 - nextinside
            else:
                mazeinside = 1 - mazeinside
                nextoutside = 1 - nextoutside

        if part == 1:
            mazeinside = 0
        if part == self.parts:
            mazeoutside = 0
        if part + 1 >= self.parts:
            nextoutside = 0
        if part == self.parts:
            nextinside = 0

        return mazeinside, mazeoutside, nextinside, nextoutside


def _normalise(t: Optional[str]) -> Optional[str]:
    """Replace double quotes with single quotes; return None if empty."""
    if not t:
        return None
    return t.replace('"', "'")
