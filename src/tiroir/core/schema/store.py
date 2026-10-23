"""The `store`, `shared` and `context` blocks."""

import re
import uuid
from typing import Any, get_args

from tiroir.core.schema.checker import Checker
from tiroir.core.schema.model import Audience, Context, Shared, Store
from tiroir.core.yaml_io import (
    key_line,
)

_AUDIENCES: tuple[str, ...] = get_args(Audience)
_LANGUAGE = re.compile(r"[a-z]{2}")


def check_store(c: Checker, root: Any) -> Store | None:
    """The `store` block: id, name, audience, language and description."""
    node = root.get("store")
    where = "store"
    line = key_line(root, "store")
    keys = ("id", "name", "audience", "language", "description")
    if c.mapping(node, where, line, keys, keys[:4]) is None:
        return None
    store_id = c.string(node, "id", where)
    if store_id is not None and not _is_uuid(store_id):
        c.invalid("store.id", "expected a UUID", key_line(node, "id"))
    name = c.string(node, "name", where)
    if name is not None:
        c.slug(name, "store.name", key_line(node, "name"), "slug")
    audience = c.string(node, "audience", where)
    if audience is not None and audience not in _AUDIENCES:
        c.invalid(
            "store.audience",
            f"expected one of: {', '.join(_AUDIENCES)}",
            key_line(node, "audience"),
        )
    language = c.string(node, "language", where)
    if language is not None and not _LANGUAGE.fullmatch(language):
        c.invalid(
            "store.language",
            "expected an ISO 639-1 language code, for example en",
            key_line(node, "language"),
        )
    description = c.string(node, "description", where)
    if (
        store_id is None
        or name is None
        or audience not in _AUDIENCES
        or language is None
    ):
        return None
    return Store(store_id, name, audience, language, description)  # type: ignore[arg-type]


def _is_uuid(value: str) -> bool:
    """Whether `value` is a canonical UUID."""
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


def check_shared(c: Checker, root: Any) -> Shared | None:
    """The optional `shared` block."""
    if "shared" not in root:
        return None
    node = root["shared"]
    line = key_line(root, "shared")
    if c.mapping(node, "shared", line, ("path", "topics", "conventions")) is None:
        return None
    return Shared(
        c.path_key(node, "path", "shared"),
        c.string_list(node, "topics", "shared"),
        c.path_key(node, "conventions", "shared"),
    )


def check_context(c: Checker, root: Any) -> Context | None:
    """The optional `context` block."""
    if "context" not in root:
        return None
    node = root["context"]
    line = key_line(root, "context")
    if c.mapping(node, "context", line, ("conventions_max_tokens",)) is None:
        return None
    return Context(c.integer(node, "conventions_max_tokens", "context"))
