"""The command line's own output: results on stdout, diagnostics on stderr.

This is what the user asked the command for, in the formats the CLI contract
fixes. It is not logging: logs go through loguru (ADR-002).
"""

import sys


def out(text: str) -> None:
    """Write one line of the command's result to stdout."""
    sys.stdout.write(text + "\n")


def err(text: str) -> None:
    """Write one line of diagnostics to stderr; never memory content (Y5)."""
    sys.stderr.write(text + "\n")
