"""Entry point of the `tiroir` command."""

import sys
from importlib.metadata import version

from tiroir.cli.output import err, out

USAGE = "usage: tiroir [--version] [--help]"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--version" in args:
        out(version("tiroir"))
        return 0
    if "--help" in args or not args:
        out(USAGE)
        return 0
    err(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
