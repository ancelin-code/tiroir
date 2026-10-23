"""Checking a summary's frontmatter against its drawer type."""

from collections.abc import Mapping
from typing import Any

from tiroir.core.errors import Violation
from tiroir.core.schema.codes import METADATA_INVALID
from tiroir.core.schema.fields import RESERVED_FIELDS, value_problem
from tiroir.core.schema.model import DrawerType
from tiroir.core.yaml_io import key_line, node_line


def validate_metadata(
    drawer_type: DrawerType, mapping: Mapping[str, Any]
) -> list[Violation]:
    """Every way `mapping` (a summary's frontmatter) breaks the type's fields.

    Messages give the field and the expected type, never the value. The
    reserved keys `type`, `author` and `date` are not checked here.
    """
    violations: list[Violation] = []

    def report(name: str, message: str) -> None:
        """Record a `metadata.invalid` violation on the field `name`."""
        violations.append(
            Violation(METADATA_INVALID, name, message, key_line(mapping, name))
        )

    for name, field in drawer_type.fields.items():
        value = mapping.get(name)
        if value is None:
            if field.is_required:
                violations.append(
                    Violation(
                        METADATA_INVALID,
                        name,
                        "missing required field",
                        node_line(mapping),
                    )
                )
            continue
        problem = value_problem(field, value)
        if problem is not None:
            report(name, f"expected {problem}")
    for name in mapping:
        if name not in drawer_type.fields and name not in RESERVED_FIELDS:
            report(str(name), "unknown field")
    return violations
