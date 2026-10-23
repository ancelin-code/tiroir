"""Writing a schema in its canonical form."""

from collections.abc import Mapping
from typing import Any

from tiroir.core.schema.model import DrawerType, Field, Schema
from tiroir.core.yaml_io import dump_yaml


def _field_entry(field: Field) -> dict[str, Any]:
    entry: dict[str, Any] = {"type": field.type}
    optional = (
        ("required", field.required),
        ("values", field.values),
        ("pattern", field.pattern),
        ("default", field.default),
        ("description", field.description),
    )
    entry.update({k: v for k, v in optional if v is not None})
    return entry


def _drawer_type_entry(drawer_type: DrawerType) -> dict[str, Any]:
    entry: dict[str, Any] = {"label": drawer_type.label}
    if drawer_type.label_plural is not None:
        entry["label_plural"] = drawer_type.label_plural
    if drawer_type.description is not None:
        entry["description"] = drawer_type.description
    entry["path"] = drawer_type.path
    entry["fields"] = {n: _field_entry(f) for n, f in drawer_type.fields.items()}
    entry["summary"] = {
        "template": drawer_type.summary.template,
        "sections": drawer_type.summary.sections,
    }
    if drawer_type.log is not None:
        entry["log"] = _present({"template": drawer_type.log.template})
    if drawer_type.detect is not None:
        entry["detect"] = _present(
            {"names": drawer_type.detect.names, "cwd": drawer_type.detect.cwd}
        )
    if drawer_type.inject is not None:
        entry["inject"] = _present(
            {
                "sections": drawer_type.inject.sections,
                "max_tokens": drawer_type.inject.max_tokens,
            }
        )
    return entry


def _present(entries: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entries.items() if v is not None}


def dump_schema(schema: Schema) -> str:
    """The schema in canonical form: the keys in the order of the contract."""
    data: dict[str, Any] = {
        "tiroir": schema.tiroir,
        "store": _present(
            {
                "id": schema.store.id,
                "name": schema.store.name,
                "audience": schema.store.audience,
                "language": schema.store.language,
                "description": schema.store.description,
            }
        ),
    }
    if schema.shared is not None:
        data["shared"] = _present(
            {
                "path": schema.shared.path,
                "topics": schema.shared.topics,
                "conventions": schema.shared.conventions,
            }
        )
    if schema.context is not None:
        data["context"] = _present(
            {"conventions_max_tokens": schema.context.conventions_max_tokens}
        )
    data["drawer_types"] = {
        name: _drawer_type_entry(t) for name, t in schema.drawer_types.items()
    }
    return dump_yaml(data, separate_top_level=True)
