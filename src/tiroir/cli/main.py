"""Entry point of the `tiroir` command."""

import argparse
import sys
from importlib.metadata import version
from typing import TYPE_CHECKING

from loguru import logger

from tiroir.cli import admin

if TYPE_CHECKING:
    from loguru import Record


def _below_warning(record: "Record") -> bool:
    return record["level"].no < logger.level("WARNING").no


def setup_logging() -> None:
    """Write bare messages: INFO and below to stdout, WARNING and above to
    stderr, the two streams of the CLI contract."""
    logger.remove()
    logger.add(
        sys.stdout,
        format="{message}",
        level="INFO",
        filter=_below_warning,
        diagnose=False,
    )
    logger.add(sys.stderr, format="{message}", level="WARNING", diagnose=False)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tiroir")
    parser.add_argument("--version", action="version", version=version("tiroir"))
    commands = parser.add_subparsers(dest="command")
    admin.register(commands)
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:  # argparse: 0 after --version, 2 on a usage error
        return int(exit_.code or 0)
    if args.command is None:
        logger.info(parser.format_help().rstrip())
        return 0
    return int(args.run(args))


if __name__ == "__main__":
    raise SystemExit(main())
