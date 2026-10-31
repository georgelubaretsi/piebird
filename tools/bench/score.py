"""Scores a bench folder: `uv run --locked python tools/bench/score.py [options] -- <out>`."""

import sys

from analysis.main import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
