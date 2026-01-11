#!/usr/bin/env python3

import subprocess, datetime, os

is_stl = True

if is_stl:
    outfile = 'lk.stl'
else:
    outfile = 'lk.scad'

## `russiandollmaze.scad`
# p=2*1;	    // Paths
# s=5*1;	    // Spacing (unit)
# bh=8*1;	    // Base height
# wt=3*1;	    // Wall thickness
# iw=2*1;	    // Inside wall thickness
# base=1*1;	// Print base
# k=0*1;	    // Skew
# i=0*1;	    // Inside (maze inside lid)
# inner = (part=="inner")?1:0;
# center = (part=="center")?1:0;
# outer = (part=="outer")?1:0;
# h=(outer==1)?14:13;	                // Height in units
# w=(outer==1)?26:(center==1)?20:14;	// Width in units
# bs=(outer==1)?10:(center==1)?8:4;	// Base sides
# bd=(outer==1)?48:(center==1)?42:33;	// Base diameter
# ih=(outer==1)?78:75;	            // Inside height
# eh=(inner==1)?5:8;	                // Extra height
# id=(outer==1)?33:(center==1)?24:15;	// Inside diameter
# lid=(outer==1)?1:0;	                // Print lid
# is=(outer==1)?2:(center==1)?1:0;	// Inside Russian
# os=(outer==1)?0:(center==1)?1:2;	// Outside Russian

# Dimensions
#   part#1: inside wall - top of outside wall
#     0.162 in ≅ 4.1148 mm
#   part#1: inside wall - outside path
#     0.082 in ≅ 2.0828 mm
#   13 cells tall

# Needed features
#   base: larger radius, slot for exit
#   chamfer on inside, top

command = [
    './puzzlebox',
    '--parts', 4,            # 5 parts, 4 mazes
    '--part', 1,             # which part? (0:all, 1:innermost, ..., <n>:outer)
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
    '--park-thickness', 2,   # thickness of park ridge to click closed (mm)
    '--maze-thickness', 2,   # maze thickness (mm); the height of the maze walls
    '--maze-step', 5,        # maze spacing (mm); the (centerline) distance between one cell and the next
    '--maze-margin', 1,      # maze top margin (mm)
    '--maze-complexity', 10, # [-10, +10]
    '--outer-sides', 0,      # side count (0: round)
    '--out-file', outfile,
]
if is_stl:
    command.append('--stl')

started = datetime.datetime.now()
subprocess.run(list(map(str,command)))
elapsed = datetime.datetime.now() - started
info = os.stat(outfile)
print(f'{outfile}: {info.st_size/1024/1024:.2f} MiB\n    {elapsed}')


# Info
'''
Nub Scaling

z(0.8): ok
y(2) z(0.8): can't move laterally
y(1.5) z(0.8): can't move laterally

y(1.25) z(0.8): ok ***

there's too much space between the parts

y(1.25) z(0.8) clearance(0.2): I have to push hard to move laterally. clearance seems good


## Smooth Maze

### part-thickness

2 mm

# wall thickness (mm) (wall of the cylinder, not the maze)

This p

### maze-thickness
maze thickness (mm)

3

### maze-step
maze spacing (mm)

3



'''
