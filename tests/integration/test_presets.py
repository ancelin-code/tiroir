"""Loading a preset directory as a store's file set."""

from pathlib import Path

import pytest

from tiroir.core.errors import CoreError
from tiroir.core.presets import load_preset, preset_path, with_identity
from tiroir.core.schema import load_schema

PRESETS = Path(__file__).resolve().parents[2] / "presets"


def test_load_preset_puts_the_data_at_the_root_without_the_readme() -> None:
    # Given
    path = preset_path(PRESETS, "accounting-firm")

    # When
    files = load_preset(path)

    # Then
    assert "tiroir.yaml" in files
    assert "clients/c001/summary.md" in files
    assert "shared/conventions.md" in files
    assert "README.md" not in files
    assert not any(name.startswith("data/") for name in files)


def test_with_identity_names_the_new_store() -> None:
    # Given
    files = load_preset(PRESETS / "accounting-firm")

    # When
    store_id, renamed = with_identity(files, "cabinet", "personal", "en")

    # Then
    store = load_schema(renamed["tiroir.yaml"].decode()).store
    assert (store.id, store.name, store.audience, store.language) == (
        store_id,
        "cabinet",
        "personal",
        "en",
    )
    assert store_id != load_schema(files["tiroir.yaml"].decode()).store.id
    assert renamed["clients/c001/summary.md"] == files["clients/c001/summary.md"]


@pytest.mark.parametrize("name", ["nope", "../presets", ""])
def test_unknown_preset_is_refused(name: str) -> None:
    # Given
    presets = PRESETS

    # When
    with pytest.raises(CoreError) as raised:
        preset_path(presets, name)

    # Then
    assert raised.value.code == "preset.unknown"


def test_preset_with_an_invalid_schema_is_refused(tmp_path: Path) -> None:
    # Given
    (tmp_path / "tiroir.yaml").write_text("tiroir: 1\n")

    # When
    with pytest.raises(CoreError) as raised:
        load_preset(tmp_path)

    # Then
    assert raised.value.code == "schema.invalid"


def test_preset_without_a_schema_is_refused(tmp_path: Path) -> None:
    # Given
    (tmp_path / "README.md").write_text("empty\n")

    # When
    with pytest.raises(CoreError) as raised:
        load_preset(tmp_path)

    # Then
    assert raised.value.code == "schema.invalid"
