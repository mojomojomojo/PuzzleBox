#!/usr/bin/env python3
"""
Lightweight Python port of core maze generation and SCAD comment output
(from puzzlebox.c). This focuses on `test_cell`, `generate_maze`, and
`build_scad_file` behavior to produce the maze visual and machine-readable
comments found in the original C program.

Usage (basic):
  python3 puzzlebox.py --r 20 --part 1 --out sample.scad

This is a starting point for a full conversion; it intentionally keeps
features small and readable so you can iterate.
"""

import argparse
import math
import random
import sys
import os
import tempfile
import subprocess

FLAGL = 0x01
FLAGR = 0x02
FLAGU = 0x04
FLAGD = 0x08
FLAGI = 0x80

BIASL = 2
BIASR = 1
BIASU = 1
BIASD = 4

# Buffer for optional STL/comment output (mirrors C appendmazedata)
comments_buffer = []

def appendmazedata(fmt, *args):
    if args:
        s = fmt % args
    else:
        s = fmt
    comments_buffer.append(s)


def normalise(t):
    """Normalize text by replacing double quotes with single quotes.
    Returns None if input is empty or None (mirrors C behaviour).
    """
    if not t:
        return None
    s = t.replace('"', "'")
    if s == '':
        return None
    return s


def test_cell(maze, W, H, helix, nubs, x, y):
    """Match C's `test()` semantics: wrap X into [0,W) adjusting Y by helix,
    OR across nub repeats, and handle the helix==nubs special-case.
    """
    n = nubs
    v = 0
    xx = x
    yy = y
    while n:
        # wrap xx into [0,W) adjusting yy like C
        while xx < 0:
            xx += W
            yy -= helix
        while xx >= W:
            xx -= W
            yy += helix
        if yy < 0 or yy >= H:
            v |= FLAGI
        else:
            v |= maze[xx + yy * W]
        n -= 1
        if n == 0:
            break
        xx += W // nubs
        while xx >= W:
            xx -= W
            yy += helix
        # special case from C: if helix == nubs then decrement y
        if helix == nubs:
            yy -= 1
    return v


class MazeResult:
    def __init__(self, W, H, helix, nubs):
        self.W = W
        self.H = H
        self.helix = helix
        self.nubs = nubs
        self.maze = bytearray(W * H)
        self.maze_viz = bytearray(W * H)
        self.solution = bytearray(b' ' * (W * H))
        self.reachable = bytearray(W * H)
        self.minY = 0
        self.maxY = H - 1
        self.maxx = 0
        self.entrya = 0.0
        self.mazeexit = 0.0
        self.entrance_x = -1


def generate_maze(r, inside, mazethickness, basethickness, baseheight, basegap,
                  mazestep, helix, nubs, testmaze, mazecomplexity, flip, noa,
                  parkvertical, mazemargin, height, part=1, coresolid=0, coreheight=0,
                  seed=None):
    # compute W exactly like C: use integer truncation then make divisible by nubs
    W = int(((r + (mazethickness if inside else -mazethickness)) * 2 * math.pi / mazestep))
    W = (W // nubs) * nubs
    # base calculation follows C's makemaze
    base = basethickness if inside else baseheight
    if inside and part > 2:
        base += baseheight
    if coresolid:
        base += coreheight
    if inside:
        base += basegap
    # vertical span calculation matching C (parkvertical influences subtraction)
    h = height - base - mazemargin - (mazestep / 4 if parkvertical else 0) - (mazestep / 8)
    H = int(h / mazestep)
    H += 2 + helix
    if W < 3 or H < 1:
        raise ValueError("Too small")

    mr = MazeResult(W, H, helix, nubs)
    maze = mr.maze

    # RNG used to emulate C's reads from /dev/urandom (deterministic if seed provided)
    # Provide helpers to emulate signed 32-bit int and C's remainder semantics
    if seed is None:
        rng = random.Random()
    else:
        rng = random.Random(seed)

    def c_rand32(rng):
        u = rng.getrandbits(32)
        # interpret as signed 32-bit like C `int`
        if u & 0x80000000:
            return u - 0x100000000
        return u


    def c_mod(signed_val, m):
        # emulate C remainder: quotient truncates toward zero
        if m == 0:
            return 0
        q = int(signed_val / m)
        return signed_val - q * m

    # Debug logging support
    maze_debug = os.getenv('MAZE_DEBUG') is not None
    rand_log = []
    carve_log = []
    test_log = []
    py_df = None
    if maze_debug:
        try:
            py_df = open('py_debug.log', 'w', encoding='utf-8')
        except Exception:
            py_df = None

    # Clear too high/low marked as invalid (match C's y0 and dy)
    y0 = base + mazestep / 2 - mazestep * (helix + 1) + mazestep / 8
    dy = 0.0
    if helix:
        dy = mazestep * helix / W
    for Y in range(H):
        for X in range(W):
            yval = mazestep * Y + y0 + dy * X
            if yval < base + mazestep / 2 + mazestep / 8 or yval > height - mazestep / 2 - mazemargin - mazestep / 8:
                maze[X + Y * W] |= FLAGI

    # simple park vertical handling
    if parkvertical:
        for N in range(helix + 2):
            if 0 + N * W < len(maze):
                maze[0 + N * W] |= FLAGU | FLAGD
            if N + 1 < H:
                maze[0 + (N + 1) * W] |= FLAGD
    else:
        # Left-to-final park handling (mirror C's PARK_LEFT_FINAL)
        px = 0
        py = helix + 1 if helix + 1 < H else 0
        if 0 <= px < W and 0 <= py < H:
            idx = px + py * W
            old = maze[idx]
            maze[idx] |= FLAGR
            if maze_debug and py_df:
                try:
                    py_df.write(f"SET X={px} Y={py} old={old:02X} new={maze[idx]:02X} reason=PARK_LEFT_FINAL\n")
                except Exception:
                    pass
        px2 = 1 if W > 1 else 0
        py2 = helix + 1 if helix + 1 < H else 0
        if 0 <= px2 < W and 0 <= py2 < H:
            idx2 = px2 + py2 * W
            old2 = maze[idx2]
            maze[idx2] |= FLAGL
            if maze_debug and py_df:
                try:
                    py_df.write(f"SET X={px2} Y={py2} old={old2:02X} new={maze[idx2]:02X} reason=PARK_LEFT_FINAL2\n")
                except Exception:
                    pass
        # Optional 'A' glyph at finish - mirror C's conditions
        if (not inside) and (not noa) and (W // nubs > 3) and (H > helix + 3):
            # Apply same pattern as C (guard indices)
            # SET X,Y (px2,py2) |= FLAGL | FLAGR | FLAGU
            if 0 <= px2 < W and 0 <= py2 < H:
                old3 = maze[px2 + py2 * W]
                maze[px2 + py2 * W] |= (FLAGL | FLAGR | FLAGU)
                if maze_debug and py_df:
                    try:
                        py_df.write(f"SET X={px2} Y={py2} old={old3:02X} new={maze[px2+py2*W]:02X} reason=PARK_A_L1\n")
                    except Exception:
                        pass
            if 0 <= px2 + 1 < W and 0 <= py2 < H:
                old4 = maze[(px2 + 1) + py2 * W]
                maze[(px2 + 1) + py2 * W] |= (FLAGL | FLAGU)
                if maze_debug and py_df:
                    try:
                        py_df.write(f"SET X={px2+1} Y={py2} old={old4:02X} new={maze[(px2+1)+py2*W]:02X} reason=PARK_A_L2\n")
                    except Exception:
                        pass
            if 0 <= px2 + 1 < W and 0 <= py2 + 1 < H:
                old5 = maze[(px2 + 1) + (py2 + 1) * W]
                maze[(px2 + 1) + (py2 + 1) * W] |= (FLAGL | FLAGD)
                if maze_debug and py_df:
                    try:
                        py_df.write(f"SET X={px2+1} Y={py2+1} old={old5:02X} new={maze[(px2+1)+(py2+1)*W]:02X} reason=PARK_A_L3\n")
                    except Exception:
                        pass
            if 0 <= px2 < W and 0 <= py2 + 1 < H:
                old6 = maze[px2 + (py2 + 1) * W]
                maze[px2 + (py2 + 1) * W] |= (FLAGL | FLAGR | FLAGD)
                if maze_debug and py_df:
                    try:
                        py_df.write(f"SET X={px2} Y={py2+1} old={old6:02X} new={maze[px2+(py2+1)*W]:02X} reason=PARK_A_L4\n")
                    except Exception:
                        pass
            if 0 <= px2 - 1 < W and 0 <= py2 + 1 < H:
                old7 = maze[(px2 - 1) + (py2 + 1) * W]
                maze[(px2 - 1) + (py2 + 1) * W] |= FLAGR
                if maze_debug and py_df:
                    try:
                        py_df.write(f"SET X={px2-1} Y={py2+1} old={old7:02X} new={maze[(px2-1)+(py2+1)*W]:02X} reason=PARK_A_L5\n")
                    except Exception:
                        pass

    maxx = 0
    if testmaze:
        for Y in range(H):
            for X in range(W):
                t0 = test_cell(maze, W, H, helix, nubs, X, Y)
                t1 = test_cell(maze, W, H, helix, nubs, X + 1, Y)
                if maze_debug:
                    # write each TEST_CELL line like the C debug log for easy comparison
                    if py_df:
                        try:
                            py_df.write(f"TEST_CELL X={X} Y={Y} t0={t0:02X} t1={t1:02X}\n")
                        except Exception:
                            pass
                    if len(test_log) < 200:
                        test_log.append((X, Y, t0, t1))
                if not (t0 & FLAGI) and not (t1 & FLAGI):
                    maze[X + Y * W] |= FLAGR
                    if maze_debug and py_df and (X % (W) < 4 or Y <= 4):
                        try:
                            py_df.write(f"SET X={X} Y={Y} old={(maze[X+Y*W]-FLAGR):02X} new={maze[X+Y*W]:02X} reason=TEST_FLAGR\n")
                        except Exception:
                            pass
                    x2 = X + 1
                    y2 = Y
                    if x2 >= W:
                        x2 -= W
                        y2 += helix
                    if 0 <= x2 < W and 0 <= y2 < H:
                        maze[x2 + y2 * W] |= FLAGL
                        if maze_debug and py_df and (x2 < 4 or y2 <= 4):
                            try:
                                py_df.write(f"SET X={x2} Y={y2} old={0:02X} new={maze[x2+y2*W]:02X} reason=TEST_FLAGL\n")
                            except Exception:
                                pass
        # Match C: extend maxx to the right while the cell at H-2 is valid
        if (not flip) or inside:
            while maxx + 1 < W and not (test_cell(maze, W, H, helix, nubs, maxx + 1, H - 2) & FLAGI):
                if maze_debug:
                    tval = test_cell(maze, W, H, helix, nubs, maxx + 1, H - 2)
                    if len(test_log) < 200:
                        test_log.append((maxx + 1, H - 2, tval))
                    if py_df:
                        try:
                            py_df.write(f"EXTEND_TEST X={maxx+1} Y={H-2} tv={tval:02X}\n")
                        except Exception:
                            pass
                maxx += 1
    else:
        # Full C-style recursive-backtracking carving with biased choices
        maxlen = 0
        # pos linked-list emulation: use Python objects with next pointer
        class Pos:
            __slots__ = ('x', 'y', 'n', 'next')
            def __init__(self, x, y, n=0):
                self.x = x; self.y = y; self.n = n; self.next = None

        # Establish starting X,Y consistent with C's park handling
        if parkvertical:
            X = 0
            Y = helix + 1 if helix + 1 < H else 0
        else:
            X = 1 if W > 1 else 0
            Y = helix + 1 if helix + 1 < H else 0
        # If A glyph is drawn for finish in C, it may adjust X/Y; attempt to mirror that
        if (not inside) and (not noa) and (W // nubs > 3) and (H > helix + 3) and (not parkvertical):
            # mirror C pattern that moves X--/Y++ before carving; approximate
            # (C does several assignments; this keeps starting point consistent)
            X = max(0, X - 1)
            Y = min(H - 1, Y + 1)

        pos = Pos(X, Y, 0)
        last = pos
        # main loop
        while pos:
            p = pos
            pos = p.next
            p.next = None
            if not pos:
                last = None
            X = p.x; Y = p.y
            # compute available directions with bias
            n = 0
            if not test_cell(maze, W, H, helix, nubs, X + 1, Y):
                n += BIASR
            if not test_cell(maze, W, H, helix, nubs, X - 1, Y):
                n += BIASL
            if not test_cell(maze, W, H, helix, nubs, X, Y - 1):
                n += BIASD
            if not test_cell(maze, W, H, helix, nubs, X, Y + 1):
                n += BIASU
            if n == 0:
                continue
            # v = read 32-bit (emulate C signed 32-bit then C remainder)
            raw = c_rand32(rng)
            if maze_debug and len(rand_log) < 400:
                rand_log.append(('R', len(rand_log), raw, n))
            v = c_mod(raw, n)
            # pick direction
            if (not test_cell(maze, W, H, helix, nubs, X + 1, Y)) and (v - BIASR) < 0:
                maze[X + Y * W] |= FLAGR
                X += 1
                if X >= W:
                    X -= W; Y += helix
                maze[X + Y * W] |= FLAGL
            elif (not test_cell(maze, W, H, helix, nubs, X - 1, Y)) and (v - BIASR - BIASL) < 0:
                maze[X + Y * W] |= FLAGL
                X -= 1
                if X < 0:
                    X += W; Y -= helix
                maze[X + Y * W] |= FLAGR
            elif (not test_cell(maze, W, H, helix, nubs, X, Y - 1)) and (v - BIASR - BIASL - BIASD) < 0:
                maze[X + Y * W] |= FLAGD
                Y -= 1
                maze[X + Y * W] |= FLAGU
            elif (not test_cell(maze, W, H, helix, nubs, X, Y + 1)) and (v - BIASR - BIASL - BIASD - BIASU) < 0:
                maze[X + Y * W] |= FLAGU
                Y += 1
                maze[X + Y * W] |= FLAGD
            else:
                # fallback (shouldn't happen)
                continue
            # update maxx like C
            if p.n > maxlen and (test_cell(maze, W, H, helix, nubs, X, Y + 1) & FLAGI) and (not flip or inside or not (X % (W // nubs))):
                maxlen = p.n; maxx = X
            # create next
            nextp = Pos(X, Y, p.n + 1)
            # second random for queue placement (C-style signed 32-bit & remainder)
            raw2 = c_rand32(rng)
            if maze_debug and len(rand_log) < 400:
                rand_log.append(('S', len(rand_log), raw2, 10))
            v = c_mod(raw2, 10)
            if maze_debug and len(carve_log) < 1000:
                carve_log.append((p.n, p.x if hasattr(p,'x') else None, p.y if hasattr(p,'y') else None, X, Y, raw, raw2, v))
            if v < ( -mazecomplexity if mazecomplexity < 0 else mazecomplexity ):
                # add at start
                if not pos:
                    last = nextp
                nextp.next = pos
                pos = nextp
            else:
                if last:
                    last.next = nextp
                else:
                    pos = nextp
                last = nextp
            if mazecomplexity <= 0 and v < -mazecomplexity:
                # current p to start
                if not pos:
                    last = p
                p.next = pos
                pos = p
            else:
                if last:
                    last.next = p
                else:
                    pos = p
                last = p
        # end carving
        # (optional) log path length
        # mr.pathlen = maxlen
        # end else

    mr.maxx = maxx

    # Dump debug logs if requested
    if maze_debug:
        try:
            if py_df is None:
                py_df = open('py_debug.log', 'w', encoding='utf-8')
            # Append other logs after TEST_CELL entries
            py_df.write(f'W={W} H={H} helix={helix} nubs={nubs} maxx={maxx}\n')
            py_df.write('RAND_LOG:\n')
            for entry in rand_log:
                py_df.write(str(entry) + '\n')
            py_df.write('CARVE_LOG:\n')
            for entry in carve_log:
                py_df.write(str(entry) + '\n')
        except Exception:
            pass
        finally:
            try:
                if py_df:
                    py_df.close()
            except Exception:
                pass

    # Entry angle and positions
    mr.entrya = 360.0 * maxx / W
    mr.mazeexit = mr.entrya

    # mark entry positions
    for X in range(maxx % (W // nubs), W, W // nubs):
        Y = H - 1
        while Y and (maze[X + Y * W] & FLAGI):
            maze[X + (Y) * W] |= FLAGU | FLAGD
            Y -= 1
        maze[X + Y * W] |= FLAGU

    # determine minY/maxY
    minY = 0
    maxY = H - 1
    for Y in range(H):
        all_invalid = True
        for X in range(W):
            if not (maze[X + Y * W] & FLAGI):
                all_invalid = False
                break
        if not all_invalid:
            minY = Y
            break
    for Y in range(H-1, -1, -1):
        all_invalid = True
        for X in range(W):
            if not (maze[X + Y * W] & FLAGI):
                all_invalid = False
                break
        if not all_invalid:
            maxY = Y
            break
    mr.minY = minY
    mr.maxY = maxY

    # copy to maze_viz
    mr.maze_viz[:] = mr.maze[:]

    # Replicate maze data by BFS copying to opposite sector when nubs > 1 (match C behavior)
    if nubs > 1:
        from collections import deque
        visited = [[False] * H for _ in range(W)]
        dq = deque()
        sx = mr.maxx
        sy = mr.maxY
        if 0 <= sx < W and 0 <= sy < H:
            dq.append((sx, sy))
            visited[sx][sy] = True
            opp_x = (sx + W // nubs) % W
            opp_y = sy
            mr.maze_viz[opp_x + opp_y * W] = mr.maze_viz[sx + sy * W]

        while dq:
            cx, cy = dq.popleft()
            # Right
            if mr.maze[cx + cy * W] & FLAGR:
                nx = cx + 1; ny = cy
                if nx >= W:
                    nx -= W; ny += helix
                if 0 <= nx < W and 0 <= ny < H and not visited[nx][ny]:
                    visited[nx][ny] = True
                    dq.append((nx, ny))
                    opp_x = (nx + W // nubs) % W
                    opp_y = ny
                    mr.maze_viz[opp_x + opp_y * W] = mr.maze_viz[nx + ny * W]
            # Left
            if mr.maze[cx + cy * W] & FLAGL:
                nx = cx - 1; ny = cy
                if nx < 0:
                    nx += W; ny -= helix
                if 0 <= nx < W and 0 <= ny < H and not visited[nx][ny]:
                    visited[nx][ny] = True
                    dq.append((nx, ny))
                    opp_x = (nx + W // nubs) % W
                    opp_y = ny
                    mr.maze_viz[opp_x + opp_y * W] = mr.maze_viz[nx + ny * W]
            # Up
            if mr.maze[cx + cy * W] & FLAGU:
                nx = cx; ny = (cy + 1) % H
                if 0 <= nx < W and 0 <= ny < H and not visited[nx][ny]:
                    visited[nx][ny] = True
                    dq.append((nx, ny))
                    opp_x = (nx + W // nubs) % W
                    opp_y = ny
                    mr.maze_viz[opp_x + opp_y * W] = mr.maze_viz[nx + ny * W]
            # Down
            if mr.maze[cx + cy * W] & FLAGD:
                nx = cx; ny = (cy - 1 + H) % H
                if 0 <= nx < W and 0 <= ny < H and not visited[nx][ny]:
                    visited[nx][ny] = True
                    dq.append((nx, ny))
                    opp_x = (nx + W // nubs) % W
                    opp_y = ny
                    mr.maze_viz[opp_x + opp_y * W] = mr.maze_viz[nx + ny * W]

    # entrance_x
    entrance_x = -1
    for X in range(W // nubs):
        if not (maze[X + minY * W] & FLAGI):
            entrance_x = X
            break
    mr.entrance_x = entrance_x

    # BFS for path to exit (simplified)
    if entrance_x >= 0:
        from collections import deque
        q = deque()
        parent = { (entrance_x, minY): None }
        q.append((entrance_x, minY))
        found = False
        while q and not found:
            cx, cy = q.popleft()
            if cx == mr.maxx and cy == mr.maxY:
                found = True
                break
            # neighbors
            # right
            if mr.maze[cx + cy * W] & FLAGR:
                nx = cx + 1; ny = cy
                if nx >= W: nx -= W; ny += helix
                if 0 <= ny < H and not (mr.maze[nx + ny * W] & FLAGI) and (nx, ny) not in parent:
                    parent[(nx, ny)] = (cx, cy); q.append((nx, ny))
            if mr.maze[cx + cy * W] & FLAGL:
                nx = cx - 1; ny = cy
                if nx < 0: nx += W; ny -= helix
                if 0 <= ny < H and not (mr.maze[nx + ny * W] & FLAGI) and (nx, ny) not in parent:
                    parent[(nx, ny)] = (cx, cy); q.append((nx, ny))
            if mr.maze[cx + cy * W] & FLAGU:
                nx = cx; ny = cy + 1
                if 0 <= ny < H and not (mr.maze[nx + ny * W] & FLAGI) and (nx, ny) not in parent:
                    parent[(nx, ny)] = (cx, cy); q.append((nx, ny))
            if mr.maze[cx + cy * W] & FLAGD:
                nx = cx; ny = cy - 1
                if 0 <= ny < H and not (mr.maze[nx + ny * W] & FLAGI) and (nx, ny) not in parent:
                    parent[(nx, ny)] = (cx, cy); q.append((nx, ny))
        if found:
            # reconstruct path
            path = []
            node = (mr.maxx, mr.maxY)
            while node is not None:
                path.append(node)
                node = parent.get(node)
            # mark solution arrows
            for i in range(len(path)-1, 0, -1):
                cx, cy = path[i]
                nx, ny = path[i-1]
                dx = (nx - cx + W) % W
                dy = ny - cy
                if dx == 0 and dy != 0:
                    mr.solution[cx + cy*W] = ord('U' if dy>0 else 'D')
                elif dy == 0 and dx != 0:
                    mr.solution[cx + cy*W] = ord('R' if dx==1 else 'L')
            if path:
                sx, sy = path[-1]
                mr.solution[sx + sy * W] = ord('S')

    # reachable BFS
    from collections import deque
    if mr.entrance_x >= 0:
        q = deque()
        q.append((mr.entrance_x, mr.minY))
        mr.reachable[mr.entrance_x + mr.minY * W] = 1
        while q:
            cx, cy = q.popleft()
            if mr.maze[cx + cy * W] & FLAGR:
                nx = cx+1; ny = cy
                if nx>=W: nx-=W; ny+=helix
                if 0<=ny< H and not mr.reachable[nx + ny*W] and not (mr.maze[nx + ny*W] & FLAGI):
                    mr.reachable[nx + ny*W]=1; q.append((nx, ny))
            if mr.maze[cx + cy * W] & FLAGL:
                nx = cx-1; ny = cy
                if nx<0: nx+=W; ny-=helix
                if 0<=ny< H and not mr.reachable[nx + ny*W] and not (mr.maze[nx + ny*W] & FLAGI):
                    mr.reachable[nx + ny*W]=1; q.append((nx, ny))
            if mr.maze[cx + cy * W] & FLAGU:
                nx=cx; ny=cy+1
                if 0<=ny< H and not mr.reachable[nx + ny*W] and not (mr.maze[nx + ny*W] & FLAGI):
                    mr.reachable[nx + ny*W]=1; q.append((nx, ny))
            if mr.maze[cx + cy * W] & FLAGD:
                nx=cx; ny=cy-1
                if 0<=ny< H and not mr.reachable[nx + ny*W] and not (mr.maze[nx + ny*W] & FLAGI):
                    mr.reachable[nx + ny*W]=1; q.append((nx, ny))

    return mr


def build_scad_file(out, inside, part, mazethickness, basethickness, baseheight,
                    mazestep, helix, nubs, mr):
    W = mr.W
    H = mr.H
    minY = mr.minY
    maxY = mr.maxY
    maze_viz = mr.maze_viz
    solution = mr.solution
    reachable = mr.reachable

    def wprint(s):
        out.write(s + "\n")
        # mirror comment lines into comments buffer (strip leading // and optional space)
        if s.startswith("//"):
            appendmazedata(s)

    # Emit some small SCAD module definitions that the C version writes
    def write_scad_modules():
        # Simple cuttext module (non-textslow version)
        out.write("module cuttext(){linear_extrude(height=1000,convexity=10,center=true)mirror([1,0,0])children();}\n")
        # Minimal logo placeholders (AJK / A&A logos are optional in C)
        out.write("module logo(w=100,$fn=120){}\n")
        out.write("module outer(h,r){}\n")

    write_scad_modules()

    # Human-readable visualization
    wprint("//")
    wprint(f"// ============ MAZE VISUALIZATION ({'INSIDE' if inside else 'OUTSIDE'}, {W}x{H}) ============")
    wprint("//")
    wprint("// Human-readable maze (viewed from outside, unwrapped):")
    wprint("// Legend: + = corner, - = horizontal wall, | = vertical wall, # = invalid, E = exit, space = passage")
    wprint("// Note: Maze wraps horizontally (cylinder) - leftmost and rightmost edges connect")
    wprint("//")

    wprint(f"// Showing rows {minY} to {maxY} (valid maze area)")

    for Y in range(maxY + 1, minY - 1, -1):
        line = "// "
        # top border / row
        for X in range(W):
            line += "+"
            if Y == maxY + 1:
                is_exit = any((X == (mr.maxx + n * (W // nubs)) % W) for n in range(nubs))
                line += " E " if is_exit else "---"
            elif Y == minY:
                line += "---"
            else:
                if maze_viz[X + (Y-1) * W] & FLAGU:
                    line += "   "
                else:
                    line += "---"
        line += "+"
        wprint(line)
        if Y > minY:
            line = "// "
            for X in range(W):
                if X == 0:
                    line += " " if (maze_viz[W-1 + (Y-1)*W] & FLAGR) else "|"
                if maze_viz[X + (Y-1)*W] & FLAGI:
                    line += "###"
                else:
                    line += "   "
                line += " " if (maze_viz[X + (Y-1)*W] & FLAGR) else "|"
            wprint(line)

    wprint("//")

    # Maze with solution
    wprint("//")
    wprint("// ============ MAZE WITH SOLUTION ============")
    wprint("//")
    wprint("// Legend: S = start, arrows (↑↓←→) show path to exit")
    wprint("//")

    for Y in range(maxY + 1, minY - 1, -1):
        line = "// "
        for X in range(W):
            line += "+"
            if Y == maxY + 1:
                is_exit = any((X == (mr.maxx + n * (W // nubs)) % W) for n in range(nubs))
                line += " E " if is_exit else "---"
            elif Y == minY:
                line += "---"
            else:
                if maze_viz[X + (Y-1) * W] & FLAGU:
                    line += "   "
                else:
                    line += "---"
        line += "+"
        wprint(line)
        if Y > minY:
            line = "// "
            for X in range(W):
                if X == 0:
                    line += " " if (maze_viz[W-1 + (Y-1)*W] & FLAGR) else "|"
                if maze_viz[X + (Y-1)*W] & FLAGI:
                    line += "###"
                else:
                    sol = solution[X + (Y-1)*W]
                    if sol == ord('S'):
                        line += " S "
                    elif sol == ord('U'):
                        line += " ↑ "
                    elif sol == ord('D'):
                        line += " ↓ "
                    elif sol == ord('L'):
                        line += " ← "
                    elif sol == ord('R'):
                        line += " → "
                    elif not reachable[X + (Y-1)*W]:
                        line += "###"
                    else:
                        line += "   "
                line += " " if (maze_viz[X + (Y-1)*W] & FLAGR) else "|"
            wprint(line)

    wprint("//")
    # Machine-readable
    wprint("// Machine-readable maze data:")
    wprint(f"// MAZE_START {'INSIDE' if inside else 'OUTSIDE'} {W} {maxY - minY + 1} {mr.maxx} {mr.helix} {minY} {maxY}")
    for Y in range(minY, maxY + 1):
        row = "// MAZE_ROW %d " % Y
        row += " ".join(f"{maze_viz[X + Y * W]:02X}" for X in range(W))
        wprint(row)
    wprint("// MAZE_END")


def main(argv):
    p = argparse.ArgumentParser()
    p.add_argument('--r', type=float, default=20.0)
    p.add_argument('--core-diameter', '--core_diameter', dest='core_diameter', type=float, default=30.0, help='Core diameter (compute r from this like C)')
    p.add_argument('--wall-thickness', '--wallthickness', dest='wallthickness', type=float, default=1.2)
    p.add_argument('--clearance', type=float, default=0.4)
    p.add_argument('--stl', action='store_true', help='Run output through openscad to make stl (best-effort)')
    p.add_argument('--resin', action='store_true', help='Half all specified clearances for resin printing')
    p.add_argument('--parts', type=int, default=2, help='Total parts')
    p.add_argument('--part', type=int, default=1)
    p.add_argument('--out', type=str, default=None)
    p.add_argument('--comments', type=str, default=None, help='Write optional comments/STL text to this file')
    p.add_argument('--seed', type=int, default=None, help='Deterministic RNG seed')
    p.add_argument('--nubs', type=int, default=2)
    p.add_argument('--helix', type=int, default=2)
    # Defaults aligned to `puzzlebox.c`
    p.add_argument('--maze-step', '--mazestep', dest='mazestep', type=float, default=3.0)
    p.add_argument('--height', type=float, default=50.0)
    p.add_argument('--maze-thickness', '--mazethickness', dest='mazethickness', type=float, default=2.0)
    p.add_argument('--base-thickness', '--basethickness', dest='basethickness', type=float, default=1.6)
    p.add_argument('--base-height', '--baseheight', dest='baseheight', type=float, default=10.0)
    p.add_argument('--core-height', dest='core_height', type=float, default=50.0, help='Core height for part 1')
    p.add_argument('--base-gap', '--basegap', dest='basegap', type=float, default=0.4)
    p.add_argument('--maze-complexity', '--mazecomplexity', dest='mazecomplexity', type=int, default=5)
    p.add_argument('--parkvertical', action='store_true')
    p.add_argument('--park-thickness', dest='park_thickness', type=float, default=0.7)
    p.add_argument('--park-vertical', action='store_true')
    p.add_argument('--maze-margin', '--mazemargin', dest='mazemargin', type=float, default=1.0)
    p.add_argument('--inside', action='store_true')
    p.add_argument('--text-end', dest='text_end', type=str, default=None)
    p.add_argument('--text-inside', dest='text_inside', type=str, default=None)
    p.add_argument('--text-side', dest='text_side', type=str, default=None)
    p.add_argument('--text-font', dest='text_font', type=str, default=None)
    p.add_argument('--text-font-end', dest='text_font_end', type=str, default=None)
    p.add_argument('--text-slow', action='store_true')
    p.add_argument('--text-side-scale', dest='text_side_scale', type=float, default=100.0)
    p.add_argument('--text-outset', action='store_true')
    p.add_argument('--logo-depth', dest='logo_depth', type=float, default=0.6)
    p.add_argument('--ajk-logo', action='store_true')
    p.add_argument('--aa-logo', action='store_true')
    p.add_argument('--core-solid', dest='core_solid', action='store_true')
    p.add_argument('--core-gap', dest='core_gap', type=float, default=0.0)
    p.add_argument('--part-thickness', dest='wall_thickness', type=float, default=1.2)
    p.add_argument('--base-wide', dest='base_wide', action='store_true')
    p.add_argument('--nub-r-clearance', dest='nub_r_clearance', type=float, default=0.1)
    p.add_argument('--nub-z-clearance', dest='nub_z_clearance', type=float, default=0.2)
    p.add_argument('--nub-horizontal', dest='nub_horizontal', type=float, default=1.0)
    p.add_argument('--nub-vertical', dest='nub_vertical', type=float, default=1.0)
    p.add_argument('--nub-normal', dest='nub_normal', type=float, default=1.0)
    p.add_argument('--fix-nubs', dest='fix_nubs', action='store_true')
    p.add_argument('--outer-sides', dest='outer_sides', type=int, default=7)
    p.add_argument('--outer-round', dest='outer_round', type=float, default=2.0)
    p.add_argument('--grip-depth', dest='grip_depth', type=float, default=1.5)
    p.add_argument('--text-depth', dest='text_depth', type=float, default=0.5)
    p.add_argument('--symmetric-cut', dest='symmetric_cut', action='store_true')
    p.add_argument('--test', dest='test', action='store_true', help='Test pattern instead of maze')
    p.add_argument('--mime', dest='mime', action='store_true')
    p.add_argument('--no-a', dest='no_a', action='store_true')
    p.add_argument('--web-form', dest='web_form', action='store_true')
    p.add_argument('--out-file', dest='out_file', type=str, default=None, help='Output to file (alias)')
    p.add_argument('--testmaze', action='store_true')
    args = p.parse_args(argv)

    # parameters (mapped from CLI)
    # determine basic params
    part = args.part
    mazethickness = args.mazethickness
    inside = args.inside
    # Mimic C's r0/r1 computation so we pass the same radius into makemaze
    if args.core_diameter is not None:
        r1 = args.core_diameter / 2.0 + args.wallthickness + (part - 1) * (args.wallthickness + mazethickness + args.clearance)
    else:
        r1 = args.r
    # r0 is inner
    r0 = r1 - args.wallthickness
    # mazeinside/mazeoutside like C defaults
    mazeinside = inside
    mazeoutside = not inside
    if part == 1:
        mazeinside = False
    if part == args.part:  # keep parity with C; parts default 2 so leave mazeoutside unless part==parts
        pass
    # if mazeoutside and part < parts then outside radius includes mazethickness
    parts_total = args.parts if hasattr(args, 'parts') else 2
    if mazeoutside and part < parts_total:
        r1 += mazethickness
    # choose radius to generate maze at
    r = r0 if inside else r1
    mazethickness = args.mazethickness
    basethickness = args.basethickness
    baseheight = args.baseheight
    basegap = args.basegap
    mazestep = args.mazestep
    helix = args.helix
    nubs = args.nubs
    # Accept either --testmaze or --test (C uses --test)
    testmaze = 1 if (getattr(args, 'testmaze', False) or getattr(args, 'test', False)) else 0
    mazecomplexity = args.mazecomplexity
    flip = 0
    noa = 0
    parkvertical = 1 if args.parkvertical else 0
    mazemargin = args.mazemargin
    # Wire coresolid/coregap from CLI and compute height like C
    coresolid = 1 if getattr(args, 'core_solid', False) else 0
    coregap = getattr(args, 'core_gap', 0.0)
    coreheight = args.core_height if hasattr(args, 'core_height') else 0.0
    height = (coregap + baseheight) if coresolid else 0.0
    height += coreheight + basethickness + (basethickness + basegap) * (part - 1)
    if part == 1:
        height -= (coreheight if coresolid else coregap)
    if part > 1:
        height -= baseheight
    coreheight = args.core_height if hasattr(args, 'core_height') else 0
    if args.seed is not None:
        random.seed(args.seed)

    # Match C adjustments: constrain `nubs` relative to `helix`
    if helix and nubs > 1 and nubs < helix:
        if (helix % 2 == 0) and (nubs <= helix // 2):
            nubs = helix // 2
        else:
            nubs = helix
    if helix and nubs > helix:
        nubs = helix

    # Apply resin adjustments (same effect as C)
    if getattr(args, 'resin', False):
        basegap /= 2.0
        args.clearance /= 2.0
        # nub clearances may be present
        if hasattr(args, 'nub_r_clearance'):
            args.nub_r_clearance /= 2.0
        if hasattr(args, 'nub_z_clearance'):
            args.nub_z_clearance /= 2.0

    # If out-file alias provided, map to --out
    if getattr(args, 'out_file', None):
        if not args.out:
            args.out = args.out_file

    mr = generate_maze(r, inside, mazethickness, basethickness, baseheight, basegap,
                       mazestep, helix, nubs, testmaze, mazecomplexity, flip, noa,
                       parkvertical, mazemargin, height, part=part, coresolid=coresolid, coreheight=coreheight, seed=args.seed)

    # Output: either SCAD or STL conversion via OpenSCAD
    if getattr(args, 'stl', False):
        # Write SCAD to a temporary file
        fd, scad_path = tempfile.mkstemp(suffix='.scad')
        os.close(fd)
        try:
            with open(scad_path, 'w', encoding='utf-8') as f:
                build_scad_file(f, inside, part, mazethickness, basethickness, baseheight,
                                mazestep, helix, nubs, mr)
            # Determine output STL path
            if args.out:
                out_stl = args.out
            else:
                fd2, out_stl = tempfile.mkstemp(suffix='.stl')
                os.close(fd2)
            # Run openscad to convert
            try:
                res = subprocess.run(['openscad', '-q', scad_path, '-o', out_stl], check=False)
            except FileNotFoundError:
                os.remove(scad_path)
                if not args.out and os.path.exists(out_stl):
                    os.remove(out_stl)
                raise RuntimeError('openscad not found; please install OpenSCAD or run without --stl')
            finally:
                # remove temporary scad file
                if os.path.exists(scad_path):
                    os.remove(scad_path)
            if res.returncode != 0:
                if os.path.exists(out_stl):
                    os.remove(out_stl)
                raise RuntimeError('openscad failed to generate STL')
            # If no explicit outfile, stream STL to stdout
            if not args.out:
                with open(out_stl, 'rb') as sf:
                    sys.stdout.buffer.write(sf.read())
                os.remove(out_stl)
            else:
                # Write metadata if we have collected comments_buffer
                if comments_buffer:
                    try:
                        meta_path = args.out + '.meta'
                        with open(meta_path, 'w', encoding='utf-8') as mf:
                            mf.write('Puzzlebox Metadata\n')
                            mf.write('==================\n\n')
                            mf.write('Generated by: puzzlebox (Python port)\n')
                            mf.write('\n')
                            for line in comments_buffer:
                                mf.write(line)
                                if not line.endswith('\n'):
                                    mf.write('\n')
                    except Exception:
                        pass
        except Exception as e:
            print('Error creating STL:', e, file=sys.stderr)
            sys.exit(1)
    else:
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                build_scad_file(f, inside, part, mazethickness, basethickness, baseheight,
                                mazestep, helix, nubs, mr)
        else:
            build_scad_file(sys.stdout, inside, part, mazethickness, basethickness, baseheight,
                            mazestep, helix, nubs, mr)

    # optionally write collected comments (for STL-comments or comparison files)
    if args.comments:
        with open(args.comments, 'w', encoding='utf-8') as cf:
            for line in comments_buffer:
                cf.write(line)
                if not line.endswith('\n'):
                    cf.write('\n')


if __name__ == '__main__':
    main(sys.argv[1:])
