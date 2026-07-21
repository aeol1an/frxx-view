import argparse
from pathlib import Path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="View weather radar data.")
    parser.add_argument(
        "-d",
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="case directory to open (default: current working directory)",
    )
    return parser.parse_args(argv)
