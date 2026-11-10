"""Presets: a directory under `presets/<name>/` read as a store's file set."""

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from tiroir.core.errors import CoreError
from tiroir.core.layout import SCHEMA_FILE
from tiroir.core.schema import Audience, dump_schema, load_schema

README = "README.md"
DATA_FOLDER = "data"
SERVER_FOLDER = "presets"
BUNDLED = "bundled"
SERVER = "server"
_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


@dataclass(frozen=True)
class PresetInfo:
    """An available preset: its name, and its origin (`bundled` or `server`)."""

    name: str
    origin: str


def server_presets_dir(data_dir: Path) -> Path:
    """The administrator's presets folder, kept on the data volume."""
    return data_dir / SERVER_FOLDER


def _names(presets_dir: Path) -> set[str]:
    """The valid preset names found as folders in `presets_dir`."""
    if not presets_dir.is_dir():
        return set()
    return {
        entry.name
        for entry in presets_dir.iterdir()
        if entry.is_dir() and _NAME.fullmatch(entry.name)
    }


def available_presets(bundled_dir: Path, data_dir: Path) -> list[PresetInfo]:
    """Every preset of the bundled and server folders, by name then origin."""
    found = [PresetInfo(name, BUNDLED) for name in _names(bundled_dir)]
    found += [PresetInfo(name, SERVER) for name in _names(server_presets_dir(data_dir))]
    return sorted(found, key=lambda info: (info.name, info.origin))


def resolve_preset(bundled_dir: Path, data_dir: Path, name: str) -> Path:
    """The directory of preset `name`, bundled or the administrator's.

    Raises `preset.unknown` when there is none, and `preset.conflict` when both
    folders have one: the administrator's must be renamed.
    """
    server_dir = server_presets_dir(data_dir)
    in_server = name in _names(server_dir)
    if in_server and name in _names(bundled_dir):
        raise CoreError(
            "preset.conflict",
            f"{server_dir / name} has the name of a bundled preset: rename that folder",
        )
    return preset_path(server_dir if in_server else bundled_dir, name)


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
