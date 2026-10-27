"""Presets: a directory under `presets/<name>/` read as a store's file set."""

import re
import uuid
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from tiroir.core.errors import CoreError
from tiroir.core.layout import SCHEMA_FILE
from tiroir.core.schema import Audience, dump_schema, load_schema

README = "README.md"
DATA_FOLDER = "data"
_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


def preset_path(presets_dir: Path, name: str) -> Path:
    """The directory of preset `name`; raises `preset.unknown` when there is none."""
    path = presets_dir / name
    if not _NAME.fullmatch(name) or not path.is_dir():
        raise CoreError("preset.unknown", f"no preset {name}")
    return path


def load_preset(path: Path) -> dict[str, bytes]:
    """The preset's files keyed by store path: `data/` at the root, no README.

    Validates `tiroir.yaml` with `tiroir.core.schema`; raises `schema.invalid`.
    """
    files: dict[str, bytes] = {}
    for file in sorted(path.rglob("*")):
        relative = file.relative_to(path)
        if not file.is_file() or relative.as_posix() == README:
            continue
        parts = (
            relative.parts[1:] if relative.parts[0] == DATA_FOLDER else relative.parts
        )
        files["/".join(parts)] = file.read_bytes()
    text = files.get(SCHEMA_FILE)
    if text is None:
        raise CoreError("schema.invalid", f"{SCHEMA_FILE} is missing from the preset")
    load_schema(text.decode("utf-8"))
    return files


def with_identity(
    files: Mapping[str, bytes], name: str, audience: Audience, language: str
) -> tuple[str, dict[str, bytes]]:
    """A new store id and `files` with `tiroir.yaml` naming the store's identity."""
    schema = load_schema(files[SCHEMA_FILE].decode("utf-8"))
    store_id = str(uuid.uuid4())
    store = replace(
        schema.store, id=store_id, name=name, audience=audience, language=language
    )
    result = dict(files)
    result[SCHEMA_FILE] = dump_schema(replace(schema, store=store)).encode("utf-8")
    return store_id, result
