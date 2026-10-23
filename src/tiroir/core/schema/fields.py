"""Drawer type fields: their declaration and the values they accept."""

import re
from collections.abc import Mapping
from dataclasses import replace
from datetime import date, datetime
from typing import Any, get_args

from tiroir.core.schema.checker import Checker
from tiroir.core.schema.model import Field, FieldType, FieldValue
from tiroir.core.yaml_io import (
    key_line,
)

_FIELD_TYPES: tuple[str, ...] = get_args(FieldType)
RESERVED_FIELDS = ("type", "author", "date")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def value_problem(field: Field, value: object) -> str | None:
    """What the field expected, or `None` when `value` is acceptable."""
    match field.type:
        case "text":
            if not isinstance(value, str):
                return "text"
            if field.pattern is not None and not re.fullmatch(field.pattern, value):
                return f"text matching the pattern {field.pattern}"
        case "number":
            if isinstance(value, bool) or not isinstance(value, int | float):
                return "number"
        case "date":
            if _as_date(value) is None:
                return "date YYYY-MM-DD"
        case "boolean":
            if not isinstance(value, bool):
                return "boolean"
        case "enum":
            allowed = field.values or ()
            if not isinstance(value, str) or value not in allowed:
                return f"one of: {', '.join(allowed)}"
        case "list":
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                return "list of text"
    return None


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _check_field(c: Checker, node: object, path: str, line: int | None) -> Field | None:
    keys = ("type", "required", "values", "pattern", "default", "description")
    if c.mapping(node, path, line, keys, ("type",)) is None:
        return None
    assert isinstance(node, Mapping)
    kind = c.string(node, "type", path)
    if kind is not None and kind not in _FIELD_TYPES:
        c.invalid(
            f"{path}.type",
            f"expected one of: {', '.join(_FIELD_TYPES)}",
            key_line(node, "type"),
        )
        kind = None
    required = c.boolean(node, "required", path)
    values = c.string_list(node, "values", path, minimum=1)
    pattern = c.string(node, "pattern", path)
    description = c.string(node, "description", path)
    if kind == "enum" and "values" not in node:
        c.invalid(f"{path}.values", "required for an enum field", line)
    if kind is not None and kind != "enum" and "values" in node:
        c.invalid(
            f"{path}.values", "only an enum field has values", key_line(node, "values")
        )
    if pattern is not None:
        if kind != "text":
            c.invalid(
                f"{path}.pattern",
                "only a text field has a pattern",
                key_line(node, "pattern"),
            )
            pattern = None
        else:
            try:
                re.compile(pattern)
            except re.error:
                c.invalid(
                    f"{path}.pattern",
                    "expected a valid regular expression",
                    key_line(node, "pattern"),
                )
                pattern = None
    if kind is None:
        return None
    field_type: FieldType = kind  # type: ignore[assignment]
    field = Field(field_type, required, values, pattern, None, description)
    return replace(field, default=_check_default(c, node, path, field))


def _check_default(
    c: Checker, node: Mapping[str, Any], path: str, field: Field
) -> FieldValue | None:
    if "default" not in node:
        return None
    raw = node["default"]
    problem = value_problem(field, raw)
    if problem is not None:
        c.invalid(
            f"{path}.default",
            f"expected a value of the field's type: {problem}",
            key_line(node, "default"),
        )
        return None
    if field.type == "date":
        return _as_date(raw)
    if isinstance(raw, list):
        return tuple(str(item) for item in raw)
    if isinstance(raw, str):
        return str(raw)
    return raw


def check_fields(
    c: Checker, node: Mapping[str, Any], path: str
) -> dict[str, Field] | None:
    if "fields" not in node:
        return None
    where = f"{path}.fields"
    raw = node["fields"]
    fields_line = key_line(node, "fields")
    if not isinstance(raw, Mapping):
        c.invalid(where, "expected a mapping", fields_line)
        return None
    if not raw:
        c.invalid(where, "expected at least one field", fields_line)
    fields: dict[str, Field] = {}
    for name in raw:
        field_path = f"{where}.{name}"
        name_line = key_line(raw, name)
        ok = c.slug(name, field_path, name_line, "field name")
        if name in RESERVED_FIELDS:
            c.invalid(field_path, "reserved field name", name_line)
            ok = False
        field = _check_field(c, raw[name], field_path, name_line)
        if ok and field is not None:
            fields[str(name)] = field
    return fields if len(fields) == len(raw) else None
