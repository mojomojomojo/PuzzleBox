# Maze Generation and Loading

This document describes the new features for separating maze generation from OpenSCAD geometry generation in the PuzzleBox program.

## Overview

The maze generation has been separated from the geometry generation, allowing you to:

1. Generate a maze once and reuse it multiple times
2. Pre-generate mazes with specific parameters
3. Share maze designs with others
4. Create collections of known-good maze designs
5. Reproduce exact puzzle designs

## New Command-Line Options

### Saving Generated Mazes

- `--save-maze-inside <filename>` - Save the generated inside maze to a text file
- `--save-maze-outside <filename>` - Save the generated outside maze to a text file

### Loading Pre-Generated Mazes

- `--load-maze-inside <filename>` - Load a pre-generated inside maze from a text file
- `--load-maze-outside <filename>` - Load a pre-generated outside maze from a text file

## Usage Examples

### Example 1: Generate and save a maze

Generate a puzzle and save both mazes for later reuse:

```bash
./puzzlebox --parts 3 --inside \
  --save-maze-inside maze_inside.txt \
  --save-maze-outside maze_outside.txt \
  > output.scad
```

This will:
- Generate a 3-part puzzle with inside maze
- Save the inside maze to `maze_inside.txt`
- Save the outside maze to `maze_outside.txt`
- Output the OpenSCAD code to `output.scad`

### Example 2: Reuse a saved maze

Generate a new puzzle using the previously saved mazes:

```bash
./puzzlebox --parts 3 --inside \
  --load-maze-inside maze_inside.txt \
  --load-maze-outside maze_outside.txt \
  > output2.scad
```

This will generate a puzzle with identical mazes but can use different parameters for other aspects (colors, sizes, etc.).

### Example 3: Create a collection of mazes

Generate multiple maze variants and save them:

```bash
# Simple maze
./puzzlebox --maze-complexity -5 --save-maze-outside simple_maze.txt > /dev/null

# Medium complexity
./puzzlebox --maze-complexity 0 --save-maze-outside medium_maze.txt > /dev/null

# Complex maze
./puzzlebox --maze-complexity 8 --save-maze-outside complex_maze.txt > /dev/null
```

Then use them in different puzzle designs:

```bash
# Create puzzles with different sizes but the same complexity
./puzzlebox --core-diameter 40 --load-maze-outside complex_maze.txt > large_complex.scad
./puzzlebox --core-diameter 30 --load-maze-outside complex_maze.txt > medium_complex.scad
```

**Note:** The maze dimensions must match! If the core diameter changes significantly, it will affect the calculated maze dimensions (W×H) and the load will fail. Use saved mazes with identical dimensional parameters.

### Example 4: Generate only maze files

To generate maze files without creating OpenSCAD output:

```bash
./puzzlebox --parts 2 \
  --save-maze-outside my_maze.txt \
  --out-file /dev/null
```

Or redirect stdout to null:

```bash
./puzzlebox --parts 2 --save-maze-outside my_maze.txt > /dev/null
```

### Example 5: Load and modify

Load a maze but save a modified version:

```bash
# Load an existing maze, use different geometric parameters, save the result
./puzzlebox --load-maze-outside original.txt \
  --save-maze-outside modified.txt \
  --maze-thickness 2.5 \
  > modified_output.scad
```

## Maze File Format

The maze files are stored in a human-readable text format:

```
PUZZLEBOX_MAZE v1.0
WIDTH <width>
HEIGHT <height>
ENTRY_X <entry_position>
DATA
<hex values row 0>
<hex values row 1>
...
<hex values row height-1>
END
```

Example:
```
PUZZLEBOX_MAZE v1.0
WIDTH 32
HEIGHT 17
ENTRY_X 23
DATA
80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80
80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80 80
00 00 00 04 06 03 03 01 06 03 07 03 03 03 07 07 02 07 05 00 00 00 00 00 00 00 00 00 00 00 00 00
...
END
```

### Format Details

- Each row of hex values represents one vertical slice of the maze (Y=0 to Y=H-1)
- Each hex value represents one cell in the maze
- Values are space-separated for readability
- ENTRY_X specifies the position (0 to W-1) where the maze entry is located
  - This preserves the exact geometry when loading the maze

Each cell contains bit flags indicating which directions have passages:
- Bit 0 (0x01): Left passage
- Bit 1 (0x02): Right passage
- Bit 2 (0x04): Up passage
- Bit 3 (0x08): Down passage
- Bit 7 (0x80): Invalid cell (out of bounds)

Examples:
- `00` = No walls (open cell)
- `0F` = All four walls
- `03` = Passages left and right
- `0C` = Passages up and down
- `80` = Invalid cell (outside maze area)

## Important Notes

### Dimension Matching

When loading a maze, the dimensions must match exactly with what the program calculates for the current parameters. The maze dimensions depend on:

- Radius (core-diameter + wall-thickness + maze-thickness)
- maze-step (spacing between maze cells)
- nubs (number of nub segments)
- helix value
- Whether it's an inside or outside maze

If dimensions don't match, you'll get an error like:
```
Maze width mismatch: expected 84, got 72 from maze.txt
```

### Random vs. Loaded Mazes

- **Without** `--load-maze-*`: A new random maze is generated each time
- **With** `--load-maze-*`: The exact same maze is used each time
- You can combine: load one maze and generate the other (e.g., `--load-maze-inside` but generate outside)

### STL Comments

When generating STL files (with `--stl`), the maze visualization is still included in the STL comments, whether the maze was generated or loaded.

## Troubleshooting

### "Failed to load maze from file"

- Check that the file exists and is readable
- Ensure you're using the correct filename/path

### "Maze dimensions don't match"

- The maze was generated with different parameters
- Ensure radius, maze-step, nubs, and helix parameters match the saved maze
- Generate a new maze with current parameters or adjust parameters to match the saved maze

### "Cannot open maze file for writing"

- Check directory permissions
- Ensure the directory exists
- Check disk space

## Integration with Existing Workflow

The new options are completely optional and backward-compatible:

- **Old workflow** (no changes needed):
  ```bash
  ./puzzlebox --parts 3 > output.scad
  ```

- **New workflow** (save mazes):
  ```bash
  ./puzzlebox --parts 3 --save-maze-outside maze.txt > output.scad
  ```

- **New workflow** (load mazes):
  ```bash
  ./puzzlebox --parts 3 --load-maze-outside maze.txt > output.scad
  ```

All existing command-line options work exactly as before.
