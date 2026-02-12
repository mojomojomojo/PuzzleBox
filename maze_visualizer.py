#!/usr/bin/env python3
"""
Maze Visualizer for PuzzleBox Maze Files

Parses and visualizes maze files in human-readable format, showing walls.
"""

import sys
import argparse


# Bit flags for maze cells
FLAG_LEFT = 0x01   # Left passage (no wall on left)
FLAG_RIGHT = 0x02  # Right passage (no wall on right)
FLAG_UP = 0x04     # Up passage (no wall above)
FLAG_DOWN = 0x08   # Down passage (no wall below)
FLAG_INVALID = 0x80  # Invalid cell (out of bounds)


def parse_maze_file(filename):
    """Parse a PuzzleBox maze file and return maze data."""
    with open(filename, 'r') as f:
        lines = f.readlines()
    
    # Parse header
    if not lines[0].strip().startswith('PUZZLEBOX_MAZE'):
        raise ValueError(f"Invalid maze file: {filename}")
    
    width = None
    height = None
    exit_x = None
    data_start = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('WIDTH'):
            width = int(line.split()[1])
        elif line.startswith('HEIGHT'):
            height = int(line.split()[1])
        elif line.startswith('EXIT_X') or line.startswith('ENTRY_X'):  # Accept both formats
            exit_x = int(line.split()[1])
        elif line.startswith('DATA'):
            data_start = i + 1
            break
    
    if width is None or height is None or data_start is None:
        raise ValueError("Missing WIDTH, HEIGHT, or DATA in maze file")
    
    # Parse maze data
    maze = [[0 for _ in range(height)] for _ in range(width)]
    
    for y in range(height):
        if data_start + y >= len(lines):
            raise ValueError(f"Unexpected end of file at row {y}")
        
        line = lines[data_start + y].strip()
        if line == 'END':
            raise ValueError(f"Premature END marker at row {y}")
        
        hex_values = line.split()
        if len(hex_values) != width:
            raise ValueError(f"Row {y} has {len(hex_values)} values, expected {width}")
        
        for x in range(width):
            maze[x][y] = int(hex_values[x], 16)
    
    return {
        'width': width,
        'height': height,
        'exit_x': exit_x,
        'maze': maze
    }


def visualize_maze_ascii(maze_data, show_invalid=False):
    """Visualize maze using ASCII characters, showing walls.
    
    Each cell is represented as:
    +---+
    |   |
    +---+
    """
    width = maze_data['width']
    height = maze_data['height']
    exit_x = maze_data['exit_x']
    maze = maze_data['maze']
    
    # Find first valid row (top of actual maze)
    first_valid_y = 0
    for y in range(height):
        has_valid = False
        for x in range(width):
            if not (maze[x][y] & FLAG_INVALID):
                has_valid = True
                break
        if has_valid:
            first_valid_y = y
            break
    
    # Start point is always at column 0, Y=1 (second row, first row is invalid)
    start_positions = [(0, 1)]
    
    # Exit point is at column exit_x, Y=height-1 (top of cylinder, top of display)
    exit_positions = [(exit_x, height - 1)] if exit_x is not None else []
    
    # Create a grid: each cell is 4 chars wide (+---) and 2 chars tall (top border + content)
    # Plus 1 extra row at bottom for final border
    grid_h = height * 2 + 1
    grid_w = width * 4 + 1
    grid = [[' ' for _ in range(grid_w)] for _ in range(grid_h)]
    
    # Draw the maze
    for y in range(height):
        for x in range(width):
            cell = maze[x][y]
            
            # Cell position in grid
            # Each cell starts at (x*4, y*2)
            base_x = x * 4
            base_y = y * 2
            
            # Check if this is start or exit
            is_start = ((x, y) in start_positions)
            is_exit = ((x, y) in exit_positions)
            
            # For exit cell, ignore INVALID flag when drawing passages
            cell_for_drawing = cell if not is_exit else (cell & ~FLAG_INVALID)
            
            # Always draw corner at top-left of this cell
            grid[base_y][base_x] = '+'
            
            # Draw top wall (if no DOWN passage or if invalid) - swapped due to display reversal
            if not (cell_for_drawing & FLAG_DOWN) or (cell_for_drawing & FLAG_INVALID):
                grid[base_y][base_x + 1] = '-'
                grid[base_y][base_x + 2] = '-'
                grid[base_y][base_x + 3] = '-'
            
            # Draw left wall (if no LEFT passage or if invalid)
            if not (cell_for_drawing & FLAG_LEFT) or (cell_for_drawing & FLAG_INVALID):
                grid[base_y + 1][base_x] = '|'
            
            # Draw cell content
            
            if cell & FLAG_INVALID and not is_exit:
                # Invalid cell (not exit)
                # Invalid cell
                if show_invalid:
                    if is_start:
                        grid[base_y + 1][base_x + 1] = '#'
                        grid[base_y + 1][base_x + 2] = 'S'
                        grid[base_y + 1][base_x + 3] = '#'
                    elif is_exit:
                        grid[base_y + 1][base_x + 1] = '#'
                        grid[base_y + 1][base_x + 2] = 'E'
                        grid[base_y + 1][base_x + 3] = '#'
                    else:
                        grid[base_y + 1][base_x + 1] = '#'
                        grid[base_y + 1][base_x + 2] = '#'
                        grid[base_y + 1][base_x + 3] = '#'
                elif is_start:
                    # Show start even in invalid cells
                    grid[base_y + 1][base_x + 1] = ' '
                    grid[base_y + 1][base_x + 2] = 'S'
                    grid[base_y + 1][base_x + 3] = ' '
                elif is_exit:
                    # Show exit even in invalid cells
                    grid[base_y + 1][base_x + 1] = ' '
                    grid[base_y + 1][base_x + 2] = 'E'
                    grid[base_y + 1][base_x + 3] = ' '
            else:
                # Valid cell - show as spaces or mark start/exit
                if is_start:
                    grid[base_y + 1][base_x + 1] = ' '
                    grid[base_y + 1][base_x + 2] = 'S'
                    grid[base_y + 1][base_x + 3] = ' '
                elif is_exit:
                    grid[base_y + 1][base_x + 1] = ' '
                    grid[base_y + 1][base_x + 2] = 'E'
                    grid[base_y + 1][base_x + 3] = ' '
                else:
                    grid[base_y + 1][base_x + 1] = ' '
                    grid[base_y + 1][base_x + 2] = ' '
                    grid[base_y + 1][base_x + 3] = ' '
            
            # If this is the last column, draw the right edge
            if x == width - 1:
                grid[base_y][base_x + 4] = '+'
                if not (cell_for_drawing & FLAG_RIGHT) or (cell_for_drawing & FLAG_INVALID):
                    grid[base_y + 1][base_x + 4] = '|'
            
            # If this is the last row, draw the bottom edge
            if y == height - 1:
                grid[base_y + 2][base_x] = '+'
                if not (cell_for_drawing & FLAG_UP) or (cell_for_drawing & FLAG_INVALID):
                    grid[base_y + 2][base_x + 1] = '-'
                    grid[base_y + 2][base_x + 2] = '-'
                    grid[base_y + 2][base_x + 3] = '-'
                if x == width - 1:
                    grid[base_y + 2][base_x + 4] = '+'
    
    # Convert grid to string (reversed so top of cylinder shows at top)
    output = []
    for row in grid:
        output.append(''.join(row))
    
    return '\n'.join(reversed(output))


def visualize_maze_unicode(maze_data, show_invalid=False):
    """Visualize maze using Unicode box-drawing characters, showing walls."""
    width = maze_data['width']
    height = maze_data['height']
    exit_x = maze_data['exit_x']
    maze = maze_data['maze']
    
    # Find first valid row (top of actual maze)
    first_valid_y = 0
    for y in range(height):
        has_valid = False
        for x in range(width):
            if not (maze[x][y] & FLAG_INVALID):
                has_valid = True
                break
        if has_valid:
            first_valid_y = y
            break
    
    # Start point is always at column 0, Y=1 (second row, first row is invalid)
    start_positions = [(0, 1)]
    
    # Exit point is at column exit_x, Y=height-1 (top of cylinder, top of display)
    exit_positions = [(exit_x, height - 1)] if exit_x is not None else []
    
    # Create a grid that's 2*height+1 by 2*width+1 for drawing
    grid_h = height * 2 + 1
    grid_w = width * 2 + 1
    grid = [[' ' for _ in range(grid_w)] for _ in range(grid_h)]
    
    # Track which grid positions have walls
    h_walls = [[False for _ in range(grid_w)] for _ in range(grid_h)]  # horizontal
    v_walls = [[False for _ in range(grid_w)] for _ in range(grid_h)]  # vertical
    
    # First pass: mark all walls
    for y in range(height):
        for x in range(width):
            cell = maze[x][y]
            cx = x * 2 + 1
            cy = y * 2 + 1
            
            # Mark start/exit
            is_start = ((x, y) in start_positions)
            is_exit = ((x, y) in exit_positions)
            
            # For exit cell, ignore INVALID flag
            cell_for_walls = cell if not is_exit else (cell & ~FLAG_INVALID)
            
            if cell & FLAG_INVALID and not is_exit:
                if show_invalid:
                    if is_start:
                        grid[cy][cx] = 'S'
                    elif is_exit:
                        grid[cy][cx] = 'E'
                    else:
                        grid[cy][cx] = '■'
                elif is_start:
                    grid[cy][cx] = 'S'
                elif is_exit:
                    grid[cy][cx] = 'E'
                continue
            
            # Valid cell - mark start/exit or passage
            if is_start:
                grid[cy][cx] = 'S'
            elif is_exit:
                grid[cy][cx] = 'E'
            else:
                grid[cy][cx] = '·'
            
            # Mark walls (absence of passages) - swap UP/DOWN due to display reversal
            if not (cell_for_walls & FLAG_DOWN):
                h_walls[cy - 1][cx] = True
            if not (cell_for_walls & FLAG_UP):
                h_walls[cy + 1][cx] = True
            if not (cell_for_walls & FLAG_LEFT):
                v_walls[cy][cx - 1] = True
            if not (cell_for_walls & FLAG_RIGHT):
                v_walls[cy][cx + 1] = True
    
    # Second pass: draw walls and corners
    for y in range(grid_h):
        for x in range(grid_w):
            # Skip cells (odd positions)
            if y % 2 == 1 and x % 2 == 1:
                continue
            
            # Horizontal wall
            if y % 2 == 0 and x % 2 == 1:
                if h_walls[y][x]:
                    grid[y][x] = '─'
            
            # Vertical wall
            elif y % 2 == 1 and x % 2 == 0:
                if v_walls[y][x]:
                    grid[y][x] = '│'
            
            # Corner/intersection
            elif y % 2 == 0 and x % 2 == 0:
                up = h_walls[y][x - 1] if x > 0 else False
                down = h_walls[y][x + 1] if x < grid_w - 1 else False
                left = v_walls[y - 1][x] if y > 0 else False
                right = v_walls[y + 1][x] if y < grid_h - 1 else False
                
                # Choose appropriate box-drawing character
                connections = (up, down, left, right)
                if connections == (True, True, True, True):
                    grid[y][x] = '┼'
                elif connections == (True, True, True, False):
                    grid[y][x] = '├'
                elif connections == (True, True, False, True):
                    grid[y][x] = '┤'
                elif connections == (True, False, True, True):
                    grid[y][x] = '┴'
                elif connections == (False, True, True, True):
                    grid[y][x] = '┬'
                elif connections == (True, True, False, False):
                    grid[y][x] = '│'
                elif connections == (False, False, True, True):
                    grid[y][x] = '─'
                elif connections == (True, False, True, False):
                    grid[y][x] = '└'
                elif connections == (True, False, False, True):
                    grid[y][x] = '┘'
                elif connections == (False, True, True, False):
                    grid[y][x] = '┌'
                elif connections == (False, True, False, True):
                    grid[y][x] = '┐'
                elif connections == (True, False, False, False):
                    grid[y][x] = '╵'
                elif connections == (False, True, False, False):
                    grid[y][x] = '╷'
                elif connections == (False, False, True, False):
                    grid[y][x] = '╴'
                elif connections == (False, False, False, True):
                    grid[y][x] = '╶'
    
    # Convert grid to string (reversed so top of cylinder shows at top)
    output = []
    for row in grid:
        output.append(''.join(row))
    
    return '\n'.join(reversed(output))


def visualize_maze_text(maze_data, show_invalid=False):
    """Visualize maze as text showing passage directions for each cell.
    
    Each cell is a 4-character string containing L, R, U, D for passages.
    """
    width = maze_data['width']
    height = maze_data['height']
    exit_x = maze_data['exit_x']
    maze = maze_data['maze']
    
    output = []
    
    for y in range(height):
        row = []
        for x in range(width):
            cell = maze[x][y]
            
            # Build passage string (swap U/D due to display reversal)
            passages = ""
            if cell & FLAG_LEFT:
                passages += "L"
            if cell & FLAG_RIGHT:
                passages += "R"
            if cell & FLAG_DOWN:  # Swapped: DOWN in data = UP in display
                passages += "U"
            if cell & FLAG_UP:    # Swapped: UP in data = DOWN in display
                passages += "D"
            
            # Handle invalid cells
            if cell & FLAG_INVALID:
                if show_invalid:
                    cell_str = "XXXX"
                else:
                    cell_str = "    "
            else:
                # Pad to 4 characters
                cell_str = passages.ljust(4)
            
            row.append(cell_str)
        
        output.append(" ".join(row))
    
    # Reverse to match physical orientation
    return '\n'.join(reversed(output))


def main():
    parser = argparse.ArgumentParser(
        description='Visualize PuzzleBox maze files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s maze.txt
  %(prog)s maze.txt --ascii
  %(prog)s maze.txt --show-invalid
  %(prog)s maze.txt --info
        """
    )
    parser.add_argument('filename', help='Maze file to visualize')
    parser.add_argument('--ascii', action='store_true',
                       help='Use ASCII characters instead of Unicode')
    parser.add_argument('--text', action='store_true',
                       help='Use text format showing passage directions (L/R/U/D)')
    parser.add_argument('--show-invalid', action='store_true',
                       help='Show invalid cells (normally hidden)')
    parser.add_argument('--info', action='store_true',
                       help='Show maze information only (no visualization)')
    
    args = parser.parse_args()
    
    try:
        maze_data = parse_maze_file(args.filename)
        
        # Print info
        print(f"Maze: {args.filename}")
        print(f"Dimensions: {maze_data['width']}x{maze_data['height']}")
        if maze_data['exit_x'] is not None:
            print(f"Exit X: {maze_data['exit_x']}")
        print(f"Legend: S = Start (entry), E = Exit")
        print()
        
        if not args.info:
            # Visualize
            if args.text:
                print(visualize_maze_text(maze_data, args.show_invalid))
            elif args.ascii:
                print(visualize_maze_ascii(maze_data, args.show_invalid))
            else:
                print(visualize_maze_unicode(maze_data, args.show_invalid))
    
    except FileNotFoundError:
        print(f"Error: File not found: {args.filename}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
