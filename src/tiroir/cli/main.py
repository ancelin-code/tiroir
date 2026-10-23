"""Entry point of the `tiroir` command."""

from __future__ import annotations

import sys
from importlib.metadata import version
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import Message, Record

from tiroir.cli.admin import run

USAGE = "usage: tiroir [--version] [--help] admin ..."


# The sinks look the streams up on each message, so pytest's capture still sees
# them after replacing sys.stdout and sys.stderr.
def _to_stdout(message: Message) -> None:
    sys.stdout.write(message)


def _to_stderr(message: Message) -> None:
    sys.stderr.write(message)


def _below_warning(record: Record) -> bool:
    return record["level"].no < logger.level("WARNING").no


def setup_logging() -> None:
    """Write bare messages: INFO and below to stdout, WARNING and above to
    stderr, the two streams of the CLI contract."""
    logger.remove()
    logger.add(
        _to_stdout,
        format="{message}",
        level="INFO",
        filter=_below_warning,
        diagnose=False,
    )
    logger.add(_to_stderr, format="{message}", level="WARNING", diagnose=False)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "admin":
        return run(args[1:])
    if "--version" in args:
        logger.info(version("tiroir"))
        return 0
    if "--help" in args or not args:
        logger.info(USAGE)
        return 0
    logger.error(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
