#!/usr/bin/env python3

import sys, os, os.path, subprocess, datetime, argparse, multiprocessing, itertools

def gen_puzzle( args ):
    index, complexity = args

    for part in range(1,6):
        outfile = f'{out_dir}/maze.part-{part:02d}.cplx-{complexity:02d}.{index:03d}.scad'
        command = [
            './puzzlebox',

            '--parts', 6,            # 5 parts, 4 mazes
            '--part', part,          # which part? (0:all, 1:innermost, ..., <n>:outer)
            '--core-diameter', 15,   # size of empty space in smallest
            '--core-height', 75,     # height of the innermost piece
            '--nubs', 2,             # count of nubs (2,3)
            '--base-height', 8,      # "base height" (mm); the height of the base of the part

            '--clearance', 0.4,      # clearance between parts, radius (default: 0.4)

            '--fix-nubs',
            '--nub-horizontal', 1.0, # scale the size of the nubs
            '--nub-vertical',   1.0,
            '--nub-normal',     0.8,

            '--helix', 0,            # non-helical (no slope to maze path?)
            '--part-thickness', 2,   # wall thickness (mm) (wall of the cylinder, not the maze)
            '--park-thickness', 1,   # thickness of park ridge to click closed (mm)
            '--maze-thickness', 2,   # maze thickness (mm); the height of the maze walls
            '--maze-complexity', complexity, # [-10, +10]
            '--maze-step', 5,        # maze spacing (mm); the (centerline) distance between one cell and the next
            '--maze-margin', 1,      # maze top margin (mm)
            '--outer-sides', 0,      # side count (0: round)

            #'--stl',
            '--out-file', outfile,
        ]        

        print(f'{outfile}')
        sys.stdout.flush()
        started = datetime.datetime.now()
        subprocess.run(list(map(str,command)))
        elapsed = datetime.datetime.now() - started
        info = os.stat(outfile)
        print(f'{outfile}: {info.st_size/1024/1024:.2f} MiB\n    {elapsed}')



if __name__ == '__main__':

    out_dir = 'output'
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    count = 50
    complexities = [ 7, 10 ]

    with multiprocessing.Pool(11) as pool:
        pool.map(gen_puzzle, itertools.product(list(range(50)),complexities))
