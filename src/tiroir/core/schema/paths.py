"""Path patterns of drawer types, and whether two of them collide."""

import re
from collections.abc import Mapping
from typing import Any

from tiroir.core.schema.checker import Checker
from tiroir.core.schema.codes import INVALID_PATH
from tiroir.core.schema.model import DrawerType, Field
from tiroir.core.yaml_io import (
    key_line,
)

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")


def _segment_bounds(segment: str) -> tuple[str, str] | None:
    """Literal text before the first and after the last placeholder, or `None`."""
    found = list(_PLACEHOLDER.finditer(segment))
    if not found:
        return None
    return segment[: found[0].start()], segment[found[-1].end() :]


def _literal_fits(literal: str, bounds: tuple[str, str]) -> bool:
    head, tail = bounds
    return (
        len(literal) >= len(head) + len(tail)
        and literal.startswith(head)
        and literal.endswith(tail)
    )


def _segments_overlap(a: str, b: str) -> bool:
    bounds_a, bounds_b = _segment_bounds(a), _segment_bounds(b)
    if bounds_a is None and bounds_b is None:
        return a == b
    if bounds_a is None and bounds_b is not None:
        return _literal_fits(a, bounds_b)
    if bounds_a is not None and bounds_b is None:
        return _literal_fits(b, bounds_a)
    assert bounds_a is not None and bounds_b is not None
    (head_a, tail_a), (head_b, tail_b) = bounds_a, bounds_b
    return (head_a.startswith(head_b) or head_b.startswith(head_a)) and (
        tail_a.endswith(tail_b) or tail_b.endswith(tail_a)
    )


def patterns_overlap(a: str, b: str) -> bool:
    """Whether one folder could match both patterns, or sit inside the other."""
    parts_a, parts_b = a.split("/"), b.split("/")
    return all(_segments_overlap(x, y) for x, y in zip(parts_a, parts_b, strict=False))


def check_path_pattern(
    c: Checker,
    value: str,
    path: str,
    line: int | None,
    fields: Mapping[str, Field] | None,
) -> None:
    c.path_value(value, path, line)
    if fields is None:  # a field is invalid: placeholders cannot be judged
        return
    names = _PLACEHOLDER.findall(value)
    literal = _PLACEHOLDER.sub("", value)
    if "{" in literal or "}" in literal:
        c.report(INVALID_PATH, path, "unbalanced brace in the path pattern", line)
    for name in names:
        if name not in fields:
            c.report(
                INVALID_PATH,
                path,
                f"placeholder {{{name}}} is not a declared field",
                line,
            )
    if not any(n in fields and fields[n].is_required for n in names):
        c.report(
            INVALID_PATH,
            path,
            "expected at least one placeholder of a required field",
            line,
        )


def check_overlaps(c: Checker, root: Any, types: Mapping[str, DrawerType]) -> None:
    names = list(types)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            if patterns_overlap(types[first].path, types[second].path):
                node = root["drawer_types"][second]
                c.report(
                    INVALID_PATH,
                    f"drawer_types.{second}.path",
                    f"overlaps the path of drawer type {first}",
                    key_line(node, "path"),
                )
