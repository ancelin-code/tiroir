"""The walker that collects violations instead of raising."""

import re
from collections.abc import Mapping
from typing import Any

from tiroir.core.errors import CoreError, Violation
from tiroir.core.schema.codes import INVALID, INVALID_PATH
from tiroir.core.yaml_io import (
    item_line,
    key_line,
)

_SLUG = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")


def failure(violations: list[Violation]) -> CoreError:
    detail = "\n".join(str(v) for v in violations)
    count = len(violations)
    noun = "violation" if count == 1 else "violations"
    return CoreError(
        violations[0].code,
        f"the schema has {count} {noun}:\n{detail}",
        tuple(violations),
    )


class Checker:
    """Walks the parsed document, collecting violations instead of raising."""

    def __init__(self) -> None:
        self.violations: list[Violation] = []

    def report(self, code: str, path: str, message: str, line: int | None) -> None:
        self.violations.append(Violation(code, path, message, line))

    def invalid(self, path: str, message: str, line: int | None) -> None:
        self.report(INVALID, path, message, line)

    def mapping(
        self,
        node: object,
        path: str,
        line: int | None,
        keys: tuple[str, ...],
        required: tuple[str, ...] = (),
    ) -> Any:
        """Return `node` when it is a mapping of known keys, reporting the rest."""
        if not isinstance(node, Mapping):
            self.invalid(path, "expected a mapping", line)
            return None
        for key in node:
            if key not in keys:
                self.invalid(
                    join(path, str(key)),
                    f"unknown key, expected one of: {', '.join(keys)}",
                    key_line(node, key),
                )
        for key in required:
            if key not in node:
                self.invalid(join(path, key), "missing required key", line)
        return node

    def string(self, parent: Any, key: str, path: str) -> str | None:
        if key not in parent:
            return None
        value = parent[key]
        if not isinstance(value, str):
            self.invalid(join(path, key), "expected a string", key_line(parent, key))
            return None
        return str(value)

    def slug(self, value: object, path: str, line: int | None, what: str) -> bool:
        if isinstance(value, str) and _SLUG.fullmatch(value):
            return True
        self.invalid(
            path, f"expected a {what} (lowercase letters, digits, - and _)", line
        )
        return False

    def integer(self, parent: Any, key: str, path: str) -> int | None:
        if key not in parent:
            return None
        value = parent[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            self.invalid(
                join(path, key), "expected a positive integer", key_line(parent, key)
            )
            return None
        return int(value)

    def boolean(self, parent: Any, key: str, path: str) -> bool | None:
        if key not in parent:
            return None
        value = parent[key]
        if not isinstance(value, bool):
            self.invalid(join(path, key), "expected a boolean", key_line(parent, key))
            return None
        return value

    def string_list(
        self, parent: Any, key: str, path: str, *, minimum: int = 0
    ) -> tuple[str, ...] | None:
        if key not in parent:
            return None
        value = parent[key]
        where = join(path, key)
        line = key_line(parent, key)
        if not isinstance(value, list):
            self.invalid(where, "expected a list of strings", line)
            return None
        ok = True
        for index, item in enumerate(value):
            if not isinstance(item, str):
                self.invalid(
                    f"{where}[{index}]", "expected a string", item_line(value, index)
                )
                ok = False
        if not ok:
            return None
        if len(value) < minimum:
            self.invalid(where, f"expected at least {minimum} item(s)", line)
        return tuple(str(item) for item in value)

    def path_value(self, value: str, path: str, line: int | None) -> None:
        segments = value.split("/")
        if (
            value.startswith("/")
            or "\\" in value
            or any(s in ("", ".", "..") for s in segments)
        ):
            self.report(
                INVALID_PATH,
                path,
                "expected a path relative to the store root, using / and no . or ..",
                line,
            )

    def path_key(self, parent: Any, key: str, path: str) -> str | None:
        value = self.string(parent, key, path)
        if value is not None:
            self.path_value(value, join(path, key), key_line(parent, key))
        return value


def join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key
