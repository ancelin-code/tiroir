"""The `drawer_types` block."""

from collections.abc import Mapping
from typing import Any

from tiroir.core.schema.checker import Checker
from tiroir.core.schema.drawer_parts import (
    check_detect,
    check_inject,
    check_log,
    check_summary,
)
from tiroir.core.schema.fields import check_fields
from tiroir.core.schema.model import DrawerType
from tiroir.core.schema.paths import check_overlaps, check_path_pattern
from tiroir.core.yaml_io import key_line


def _check_drawer_type(
    c: Checker, node: object, path: str, line: int | None
) -> DrawerType | None:
    keys = (
        "label",
        "label_plural",
        "description",
        "path",
        "fields",
        "summary",
        "log",
        "detect",
        "inject",
    )
    if (
        c.mapping(node, path, line, keys, ("label", "path", "fields", "summary"))
        is None
    ):
        return None
    assert isinstance(node, Mapping)
    label = c.string(node, "label", path)
    label_plural = c.string(node, "label_plural", path)
    description = c.string(node, "description", path)
    pattern = c.string(node, "path", path)
    fields = check_fields(c, node, path)
    summary = check_summary(c, node, path)
    if pattern is not None:
        check_path_pattern(c, pattern, f"{path}.path", key_line(node, "path"), fields)
    log = check_log(c, node, path)
    detect = check_detect(c, node, path, fields)
    inject = check_inject(c, node, path, summary)
    if label is None or pattern is None or fields is None or summary is None:
        return None
    return DrawerType(
        label, pattern, fields, summary, label_plural, description, log, detect, inject
    )


def check_drawer_types(c: Checker, root: Any) -> dict[str, DrawerType] | None:
    if "drawer_types" not in root:
        return None
    raw = root["drawer_types"]
    line = key_line(root, "drawer_types")
    if not isinstance(raw, Mapping):
        c.invalid("drawer_types", "expected a mapping", line)
        return None
    if not raw:
        c.invalid("drawer_types", "expected at least one drawer type", line)
    types: dict[str, DrawerType] = {}
    for name in raw:
        path = f"drawer_types.{name}"
        name_line = key_line(raw, name)
        ok = c.slug(name, path, name_line, "drawer type name")
        drawer_type = _check_drawer_type(c, raw[name], path, name_line)
        if ok and drawer_type is not None:
            types[str(name)] = drawer_type
    check_overlaps(c, root, types)
    return types if len(types) == len(raw) else None
