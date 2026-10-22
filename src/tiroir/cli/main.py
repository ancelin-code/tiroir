"""Entry point of the `tiroir` command."""

import sys
from importlib.metadata import version

from tiroir.cli.admin import run

USAGE = "usage: tiroir [--version] [--help] admin ..."


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] == "admin":
        return run(args[1:])
    if "--version" in args:
        print(version("tiroir"))
        return 0
    if "--help" in args or not args:
        print(USAGE)
        return 0
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
