#!/usr/bin/env python3
"""Extract human-readable mazes with solutions from .scad files.

Scans an input directory (default: output/) for .scad files, finds
consecutive comment blocks (lines starting with //) that contain
the marker "MAZE WITH SOLUTION", determines the corresponding Part
(from a nearby "// Part N" marker), and writes combined per-part
files containing the relative path and the maze text.
"""
from __future__ import annotations
import argparse
import os
import re
from collections import defaultdict
from typing import List, Tuple


def extract_blocks(lines: List[str]) -> List[Tuple[int, int, str]]:
    """Return list of (start_idx, end_idx, block_text) for consecutive comment blocks."""
    blocks = []
    i = 0
    n = len(lines)
    while i < n:
        if lines[i].lstrip().startswith('//'):
            start = i
            while i < n and lines[i].lstrip().startswith('//'):
                i += 1
            end = i
            block = ''.join(lines[start:end])
            blocks.append((start, end, block))
        else:
            i += 1
    return blocks


def find_part_for_block(lines: List[str], start_idx: int, block_text: str) -> int:
    """Determine the part number for a block.

    First check inside the block for a "// Part N" marker, otherwise
    scan backwards from start_idx-1 to find the nearest marker. If none
    is found, return 0.
    """
    m = re.search(r'//\s*Part\s*(\d+)\b', block_text)
    if m:
        return int(m.group(1))
    j = start_idx - 1
    while j >= 0:
        m2 = re.search(r'//\s*Part\s*(\d+)\b', lines[j])
        if m2:
            return int(m2.group(1))
        j -= 1
    return 0


def clean_comment_block(block_text: str) -> str:
    """Strip leading // and one optional space from each comment line."""
    cleaned_lines = []
    for raw in block_text.splitlines():
        s = raw.lstrip()
        if s.startswith('//'):
            content = s[2:]
            if content.startswith(' '):
                content = content[1:]
            cleaned_lines.append(content.rstrip())
        else:
            cleaned_lines.append(raw.rstrip())
    return '\n'.join(cleaned_lines).strip()


def extract_from_file(path: str, cwd: str) -> List[Tuple[int, str, str]]:
    """Return list of tuples (part, relpath, maze_text) found in file."""
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        lines = fh.readlines()
    results = []
    blocks = extract_blocks(lines)
    for start, end, block in blocks:
        if not re.search(r'MAZE\s+WITH\s+SOLUTION', block, re.I):
            continue
        part = find_part_for_block(lines, start, block)
        maze = clean_comment_block(block)
        maze_lines = maze.splitlines()
        # Remove region between 'MAZE VISUALIZATION' and 'MAZE WITH SOLUTION'
        try:
            viz_idx = next((i for i, l in enumerate(maze_lines) if 'maze visualization' in l.lower()), None)
        except StopIteration:
            viz_idx = None
        try:
            sol_idx = next((i for i, l in enumerate(maze_lines) if 'maze with solution' in l.lower()), None)
        except StopIteration:
            sol_idx = None
        if viz_idx is not None and sol_idx is not None and viz_idx < sol_idx:
            del maze_lines[viz_idx:sol_idx]

        # Truncate everything after 'Machine-readable maze data:' (exclusive)
        mr_idx = next((i for i, l in enumerate(maze_lines) if 'machine-readable maze data:' in l.lower()), None)
        if mr_idx is not None:
            maze_lines = maze_lines[:mr_idx]

        # Remove numeric-only lines (likely raw maze data arrays)
        filtered_lines = [l for l in maze_lines if not re.match(r'^[\s\[\]\d,;()\-]+$', l)]
        maze_filtered = '\n'.join(filtered_lines).strip()
        if not maze_filtered:
            continue
        rel = os.path.relpath(path, cwd)
        results.append((part, rel, maze_filtered))
    return results


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Extract mazes with solutions from .scad files')
    p.add_argument('--input', '-i', default='output', help='Input directory to scan (default: output)')
    p.add_argument('--output-dir', '-o', default='output/mazes', help='Directory to write per-part files')
    args = p.parse_args(argv)

    input_dir = args.input
    out_dir = args.output_dir
    cwd = os.getcwd()

    parts = defaultdict(list)  # part -> list of (relpath, maze)

    for root, _, files in os.walk(input_dir):
        for fname in files:
            if not fname.lower().endswith('.scad'):
                continue
            path = os.path.join(root, fname)
            try:
                found = extract_from_file(path, cwd)
            except Exception as e:
                print(f'Warning: failed to read {path}: {e}')
                continue
            for part, rel, maze in found:
                parts[part].append((rel, maze))

    if not parts:
        print('No mazes with solutions found.')
        return 0

    os.makedirs(out_dir, exist_ok=True)
    for part in sorted(parts.keys()):
        fname = os.path.join(out_dir, f'part_{part}_mazes.txt')
        with open(fname, 'w', encoding='utf-8') as out:
            for rel, maze in parts[part]:
                out.write(f'FILE: {rel}\n')
                out.write(maze)
                out.write('\n\n' + ('-' * 60) + '\n\n')
        print(f'Wrote {fname} ({len(parts[part])} entries)')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
#!/usr/bin/env python3
"""Extract "MAZE WITH SOLUTION" comment blocks from .scad files.

Creates files `part1-maze-comparison.txt` .. `part5-maze-comparison.txt` in the
specified output directory (current directory by default). For each .scad file,
each occurrence of "MAZE WITH SOLUTION" (in comment lines) is treated as one
part in order; the first occurrence goes to part1, second to part2, etc.
"""
import argparse
import os
import sys


def find_scad_files(root):
    for dirpath, dirs, files in os.walk(root):
        for fn in files:
            if fn.lower().endswith('.scad'):
                yield os.path.join(dirpath, fn)


def extract_blocks(path):
    blocks = []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
    except Exception:
        return blocks

    i = 0
    while i < len(lines):
        line = lines[i]
        if 'MAZE WITH SOLUTION' in line.upper():
            # collect following consecutive comment lines (// ...)
            i += 1
            block_lines = []
            while i < len(lines):
                l = lines[i]
                stripped = l.lstrip()
                if stripped.startswith('//'):
                    # drop leading // and one optional space
                    content = stripped[2:]
                    if content.startswith(' '):
                        content = content[1:]
                    block_lines.append(content.rstrip('\n'))
                    i += 1
                    continue
                # stop on any non-comment line
                break
            blocks.append('\n'.join(block_lines).rstrip())
        else:
            i += 1
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('root', nargs='?', default='.', help='root directory to search for .scad files')
    ap.add_argument('--outdir', '-o', default='.', help='where to write part<n>-maze-comparison.txt files')
    args = ap.parse_args()

    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    # prepare output files (overwrite)
    part_files = []
    for n in range(1, 6):
        p = os.path.join(outdir, f'part{n}-maze-comparison.txt')
        part_files.append(p)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(f'Part {n} maze comparison file. Extracted MAZE WITH SOLUTION blocks.\n\n')

    counts = [0]*5

    scad_count = 0
    for scad in find_scad_files(args.root):
        scad_count += 1
        blocks = extract_blocks(scad)
        for idx, block in enumerate(blocks[:5]):
            outpath = part_files[idx]
            counts[idx] += 1
            with open(outpath, 'a', encoding='utf-8') as f:
                f.write('File: ' + scad + '\n')
                f.write(block + '\n')
                f.write('\n' + ('-'*72) + '\n\n')

    # summary
    print(f'Searched root: {args.root}')
    print(f'Found {scad_count} .scad files')
    for i, c in enumerate(counts, start=1):
        print(f'part{i}-maze-comparison.txt: appended {c} blocks')


if __name__ == '__main__':
    main()
