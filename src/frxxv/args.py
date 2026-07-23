import argparse
from pathlib import Path


def _nonnegative_int(value: str) -> int:
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="View weather radar data.")
    parser.add_argument(
        "-d",
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="case directory to open (default: current working directory)",
    )
    parser.add_argument(
        "-n",
        "--filenum",
        type=_nonnegative_int,
        default=0,
        help="zero-based index of the first file to open (default: 0)",
    )
    return parser.parse_args(argv)
