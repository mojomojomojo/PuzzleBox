# AGENTS.md — PuzzleBox (fork) + impl2 Python port

Persistent context for AI agents. Read this first every session; keep it up to date when
you learn something durable (and update `.ai/fork_and_port_analysis.md` for detail).

## What this is

PuzzleBox generates OpenSCAD (and optionally STL) for 3D-printable nested cylindrical
maze puzzle boxes. Three codebases are relevant:

| Path (relative to `3d-cylinder/`) | What |
|---|---|
| `orig/PuzzleBox/` | Pristine upstream (RevK / Adrian Kennard), frozen at commit `15d01f7` (2019). Reference only — never edit. |
| `PuzzleBox/` | **This repo.** Todd's fork (github `mojomojomojo/PuzzleBox`). Contains later upstream work through `38778dd` (2026-01-08), then Todd's changes from `8b832b0` onward. |
| `PuzzleBox/impl2/puzzlebox/` | Python port + extension of *this fork's* `puzzlebox.c` (not of `orig`). |

Detailed diff analysis (upstream vs fork, C vs Python, with line refs):
`.ai/fork_and_port_analysis.md`.

## Layout

- `puzzlebox.c` — single-file C program (~2900 lines, popt CLI, GNU indent style, 3-space indent).
  All geometry is emitted as integer polyhedra in 0.001 mm units inside `scale(0.001){...}`.
- `impl2/puzzlebox/` — Python package (`__main__`, `cli`, `config`, `maze`, `maze_io`,
  `visualization`, `geometry`, `nub`, `text`, `scad`). `generate(cfg, out)` is the library API.
- `impl2/tests/` — pytest suite; fixtures are C-saved `.maze` files + C reference output.
- `puzzlebox.1.py` — older, abandoned single-file partial port (no geometry). Superseded by impl2.
- `tools/` — Python helpers around the **C binary**:
  - `gen_good.py` — runs `../puzzlebox` N times per part, scores mazes, keeps the best, writes
    `part-N.MM.scad` + `.meta`, renders STL with `openscad`. Writes `gen_good.log` in CWD.
  - `parse_maze_comments.py` — parses `// MAZE_START/ROW/END` comments from a .scad and scores difficulty.
  - `maze_visualizer.py` — maze file ⇄ human-readable/SVG.
  - `extract_mazes.py`, `check_svg_adjacent_duplicates.py`, `analyze_polyhedron.py`, `visualize_polyhedron.py`, `gen_many.py`.
- `.ai/` — AI-written notes (`MAZE_SEPARATION.md` describes maze load/save; `scoring.txt`).
- `good.NN/`, `inside.01/`, `explore_parameters/` — results of real print projects / parameter
  exploration. `good.06/notes.md` records chosen mazes for a 6-part build. Treat as data, don't clean up.
- `Makefile`, `Dockerfile`, `PuzzleBox.def`, `entrypoint.sh`, `.gitpod.yml`, `webform.cgi`,
  `makesamples*` — upstream build/container/CGI bits. Todd has not changed these.

## Building / running

- C: `make puzzlebox` (needs `libpopt-dev`, `-D_GNU_SOURCE` for `strdupa`/`asprintf`; Linux-oriented —
  uses `/dev/urandom`, `mkstemps`, `fork`, `flock /var/lock/puzzlebox` for `--stl`).
  `openscad.exe` copies are scattered in several subdirectories for local rendering.
- Python: from `PuzzleBox/impl2`: `python -m puzzlebox [options] > out.scad` (or `--out-file`).
  `--seed N` gives reproducible mazes (Python-only).
- Tests: from `PuzzleBox/`: `python -m pytest impl2/tests -q` (tests import `impl2.puzzlebox`, so
  `PuzzleBox/` must be on `sys.path`; `python -m` from that directory does this). 52 tests passed as of 2026-11-12.
- Python-only options (no C equivalent): `--thick-part N` (0 = last part), `--thick-wall MM`, `--thick-base MM`
  thicken walls / end cap of parts >= N; `--thick PART:WALL[:BASE]` (repeatable, empty field = inherit)
  adds more stages, merged into `cfg.stages` by `validate()`. Use `cfg.wall_t(p)` / `cfg.base_t(p)` / `cfg.part_height(p)`,
  never raw `cfg.wallthickness` / `cfg.basethickness`, for per-part geometry. Part N-1's base widens to stay
  flush (r2 uses the next part's wall); nothing else on parts < N changes (`tests/test_thick.py`).
- Python output also emits `// PART_DIMENSIONS part=N inner_radius= outer_radius= base_radius= inside_height=`
  plus top-level OpenSCAD variables (`part_inner_radius`, ... and `part_*_radii` lists), all in mm.
  `tools/parse_maze_comments.find_part_dimensions()` parses them; `ennes/gen_good.py` writes them to `.meta`.

## Key domain concepts

- Parts are nested cylinders; each part's maze (inside or outside) mates with the next part's nubs.
  `--inside`, `--flip`, `--flip-stagger` choose which parts get mazes on which surface.
- Maze grid `maze[x][y]`, W columns around the circumference (multiple of `nubs`), H rows.
  Cell flags: `FLAGL=1 FLAGR=2 FLAGU=4 FLAGD=8` passages, `FLAGA=0x10` (used/"A"), `FLAGI=0x80` invalid.
  Maze is replicated `nubs` times around the cylinder; `test()` enforces nub symmetry and helix wrap.
- `--helix` slopes the maze rows; **negative helix = reverse (clockwise)**, a Todd addition with special
  park/"A"/park-ridge handling (`abs_helix`, mirrored columns, flipped face winding).
- Park point + "A" loop at the maze start; the exit is at the top. `--fix-nubs` puts nubs opposite the exit.
- Machine-readable output: `// MAZE_START <IN|OUT> W rows maxx helix minY maxY entrance_x exit_x exit_y`,
  `// MAZE_ROW y hex...`, `// MAZE_END`, plus ASCII maze and BFS-solution drawings in comments.
  Tools depend on this format — keep it stable (or update `tools/parse_maze_comments.py` too).
- Maze file format `PUZZLEBOX_MAZE v1.1` (WIDTH, HEIGHT, HELIX, EXIT_X, DATA hex rows, END);
  loader also accepts v1.0 / `ENTRY_X`. Dimensions must match the computed W×H.

## Known pitfalls (verified 2026-11-09 — re-verify before relying on line numbers)

C (`puzzlebox.c`):
- `-T` is registered twice (`--top-space` and `--text-side-scale`); popt picks `--top-space`.
  `-Z` likewise (`--base-gap` wins over `--nub-z-clearance`, upstream bug).
- Exit-column override after DFS (`~1348-1354`) forces the exit to the segment's end column for any
  nonzero helix, including defaults. It can conflict with `--flip`/`--flip-stagger` exit constraints and
  with the solution search (`maxy_exit` belongs to the pre-override column).
- `base += (coresolid ? coreheight : 0)` (`~1032`) is unconditional due to an upstream reindent that
  swallowed an `if` into a comment.
- RNG: `int v` read from `/dev/urandom`, then `v %= n` — negative half the time, which biases direction
  choice (inherited upstream behavior; Python does NOT reproduce it).
- `--fix-nubs` uses `globalexit == 0` as "unset".
- Maze save/load handles one maze per side; multi-part runs overwrite/mismatch.
- `.meta` file is only written with both `--stl` and `--out-file`. Long-only options are not recorded
  in header comments or `.meta`.
- `part_entryas[]` / `part_mazeexits[]` are filled but unused (groundwork for "base options").

Python (impl2) vs C — non-intentional divergences:
- Default `--nubs` = `abs(helix)` in Python vs effectively 2 in C (differs for helix ≥ 4); a test asserts the Python value.
- RNG distribution differs (see above); `--seed` reseeds identically for every part.
- `--test` mode skips park/"A" and the exit-column adjustment.
- `--part N` alone: Python omits the layout translate (part at origin).
- Side text step uses `360.0/outersides` (C uses integer division).
- `--stl`, `--mime`, `--web-form`, CGI `PATH_INFO`/`QUERY_STRING` are parsed but not implemented. No `.meta`.
- Header comment format differs from C; `-h` is help (C: core-height).
- Writing ↑↓←→ to a cp1252 stdout on Windows may raise `UnicodeEncodeError`; prefer `--out-file`.

When asked to make Python match C (or vice versa), confirm with Todd which side is "correct" —
several C behaviors are bugs that Python silently fixed.

## Working conventions

- Todd's global shell rules apply (no `cd`, no chained commands, literal `C:/...` paths, no
  inline `python -c`/awk blocks; use Read/Grep/Glob; scripts go in the scratchpad). Repeat them to subagents.
- Use `git -C C:/data/todd/thproj/hackshop/3d_print/puzzles/3d-cylinder/PuzzleBox ...` for git.
- The working tree has many untracked experiment files (`good.*`, `reverse_helix/`, `t_maze_sep/`,
  `*.maze`, `openscad.exe`). Don't delete or commit them unless asked.
- Commits only when asked. Todd's history labels AI-generated changes (e.g. "ai-auto-doc", "revert broken
  ai slop") — keep changes small, reviewable, and don't reformat `puzzlebox.c` wholesale.
- When changing C geometry/maze code, mirror the change in impl2 (or note the divergence here) and
  keep `MAZE_*` comment output compatible with `tools/`.
