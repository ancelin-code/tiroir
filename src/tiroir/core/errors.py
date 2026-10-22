"""Errors raised by the core."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    """One broken rule, located by key path and, when known, line.

    The message names rules and expected types, never the offending value, so
    it is free of memory content.
    """

    code: str
    path: str
    message: str
    line: int | None = None

    def __str__(self) -> str:
        where = self.path if self.line is None else f"{self.path} (line {self.line})"
        return f"{self.code}: {where}: {self.message}"


class CoreError(Exception):
    """A core failure with a stable `code`; the message carries no memory content.

    When the failure lists several violations, `code` is the first one's and
    `violations` holds every one, each with its own code.
    """

    def __init__(
        self,
        code: str,
        message: str,
        violations: tuple[Violation, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.violations = violations
