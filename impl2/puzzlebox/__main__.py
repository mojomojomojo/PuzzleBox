"""Entry point for running puzzlebox as a module: python -m puzzlebox."""

import sys
from io import StringIO

from .cli import parse_args
from .scad import generate


def main():
    cfg = parse_args()
    out = StringIO()

    try:
        generate(cfg, out)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    result = out.getvalue()

    if cfg.outfile:
        with open(cfg.outfile, "w") as f:
            f.write(result)
    else:
        sys.stdout.write(result)


if __name__ == "__main__":
    main()
