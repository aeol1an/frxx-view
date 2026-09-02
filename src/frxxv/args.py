import argparse
import json
from pathlib import Path
import sys


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
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        metavar="PATH",
        help="apply a temporary highest-priority config file",
    )
    config_actions = parser.add_mutually_exclusive_group()
    config_actions.add_argument(
        "--addconfig",
        type=Path,
        metavar="PATH",
        help="add a config file to the override list and exit",
    )
    config_actions.add_argument(
        "--removeconfig",
        type=Path,
        metavar="PATH",
        help="remove a config file from the override list and exit",
    )
    config_actions.add_argument(
        "--dumpconfig",
        action="store_true",
        help="print the default config as JSON and exit",
    )
    return parser.parse_args(argv)


def handle_config_action(args) -> bool:
    """Run a requested config-only action and report whether one was present."""
    if not (args.addconfig or args.removeconfig or args.dumpconfig):
        return False

    from frxxv.config import ConfigManager, USER_CONFIG

    try:
        if args.addconfig is not None:
            config_path = args.addconfig.expanduser().resolve()
            USER_CONFIG.add_config(config_path)
            print(f"Added config: {config_path}")
        elif args.removeconfig is not None:
            config_path = args.removeconfig.expanduser().resolve()
            USER_CONFIG.remove_config(config_path)
            print(f"Removed config: {config_path}")
        else:
            print(json.dumps(ConfigManager.default_config, indent=2))
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    return True
