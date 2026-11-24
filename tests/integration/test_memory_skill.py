"""The member's memory skill: generated from granted stores, and its freshness."""

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from tiroir.core import (
    Access,
    Audience,
    Core,
    DrawerRef,
    Scope,
    Summary,
    open_core,
    serverdb,
)
from tiroir.core.layout import SCHEMA_FILE
from tiroir.core.skill import SKILL_PATH
from tiroir.core.store import Author, StoreWriter

FRENCH_PRESET = Path(__file__).resolve().parents[2] / "presets" / "accounting-firm"
ROOT = Author("root", "Root", "admin")

ENGLISH_SCHEMA = """\
tiroir: 1
store:
  id: 0b9a6f0e-2d4c-4f61-9a3e-5b7c8d9e0f12
  name: placeholder
  audience: personal
  language: en
shared:
  topics: [architecture, release process]
drawer_types:
  project:
    label: Project
    label_plural: Projects
    path: "projects/{slug}"
    fields:
      slug:
        type: text
        required: true
    summary:
      template: templates/project-summary.md
      sections: [Overview, Decisions]
"""


@pytest.fixture
def english_preset(tmp_path: Path) -> Path:
    """An English preset with one drawer type and no drawer."""
    preset = tmp_path / "presets" / "english"
    (preset / "templates").mkdir(parents=True)
    (preset / "tiroir.yaml").write_text(ENGLISH_SCHEMA, encoding="utf-8")
    (preset / "templates" / "project-summary.md").write_text(
        "# {slug}\n\n## Overview\n\nWhat it is.\n\n## Decisions\n\nWhat was decided.\n",
        encoding="utf-8",
    )
    return preset


@pytest.fixture
def core(tmp_path: Path, english_preset: Path) -> Iterator[Core]:
    """Alice owns `cabinet` (French, personal); Bob `atelier` (English, team)."""
    data = tmp_path / "data"
    conn = serverdb.open_server_db(data)
    serverdb.create_member(conn, "root", "Root", "pw", is_admin=True)
    serverdb.create_member(conn, "alice", "Alice Martin", "pw")
    serverdb.create_member(conn, "bob", "Bob Durand", "pw")
    conn.close()
    opened = open_core(data, start_workers=False)
    admin = opened.admin("root")
    admin.create_store(
        "cabinet", Audience.PERSONAL, "fr", owner="alice", preset=FRENCH_PRESET
    )
    admin.create_store(
        "atelier", Audience.TEAM, "en", owner="bob", preset=english_preset
    )
    yield opened
    opened.close()


def _skill_md(archive: bytes) -> str:
    """The `SKILL.md` an archive holds."""
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        return opened.read(SKILL_PATH).decode("utf-8")


def test_skill_of_a_french_member_is_in_french(core: Core) -> None:
    # Given
    alice = core.member("alice")

    # When
    archive = alice.memory_skill()

    # Then
    text = _skill_md(archive.data)
    head = YAML(typ="safe").load(text.removeprefix("---\n").partition("\n---\n")[0])
    assert head["name"] == "tiroir-memory"
    assert "Clients" in head["description"]
    assert "calendrier fiscal" in head["description"]
    assert "À utiliser" in head["description"]
    assert archive.file_name == "tiroir-memory.zip"


def test_skill_of_an_english_member_is_in_english(core: Core) -> None:
    # Given
    bob = core.member("bob")

    # When
    archive = bob.memory_skill()

    # Then
    text = _skill_md(archive.data)
    assert "Projects" in text
    assert "Use it whenever" in text
    assert "Clients" not in text


def test_skill_names_no_ungranted_store_no_drawer_and_no_summary(core: Core) -> None:
    # Given
    alice, bob = core.member("alice"), core.member("bob")
    drawers = alice.list_drawers()
    names = [str(d.fields["name"]) for d in drawers]
    first = DrawerRef("cabinet", drawers[0].drawer)
    summary = alice.read(Summary(first), Scope(drawers=(first,))).items[0].text
    summary_lines = [
        line
        for line in summary.splitlines()
        if len(line) > 20 and not line.startswith(("#", "---"))
    ]

    # When
    alice_text = _skill_md(alice.memory_skill().data)
    bob_text = _skill_md(bob.memory_skill().data)

    # Then
    assert "atelier" not in alice_text
    assert "cabinet" not in bob_text
    for name in names:
        assert name not in alice_text
    assert summary_lines
    for line in summary_lines:
        assert line not in alice_text


def test_status_reports_the_skill_stale_until_downloaded(core: Core) -> None:
    # Given
    alice = core.member("alice")
    before = alice.status()

    # When
    alice.memory_skill()
    after = alice.status()

    # Then
    assert before.skill_stale is True
    assert after.skill_stale is False


def test_a_grant_on_a_new_store_makes_the_skill_stale(core: Core) -> None:
    # Given
    alice = core.member("alice")
    alice.memory_skill()

    # When
    core.admin("root").grant("alice", "atelier", Access.READ)
    report = alice.status()

    # Then
    assert report.skill_stale is True


def _add_topic(core: Core, store_id: str, topic: str) -> None:
    """Commit the store's schema with one more shared topic."""
    with StoreWriter(core.data_dir, store_id) as writer:
        schema = (writer.read(SCHEMA_FILE) or b"").decode("utf-8")
        edited = schema.replace("calendrier fiscal", f"calendrier fiscal, {topic}")
        writer.commit("migration", ROOT, {SCHEMA_FILE: edited.encode("utf-8")})


def test_a_schema_change_makes_the_skill_stale(core: Core) -> None:
    # Given
    alice = core.member("alice")
    alice.memory_skill()
    [store] = alice.stores()

    # When
    _add_topic(core, store.id, "paie")
    report = alice.status()

    # Then
    assert report.skill_stale is True


def test_a_download_after_a_schema_change_is_fresh_and_follows_it(
    core: Core,
) -> None:
    # Given
    alice = core.member("alice")
    alice.memory_skill()
    [store] = alice.stores()
    _add_topic(core, store.id, "paie")

    # When
    archive = alice.memory_skill()
    report = alice.status()

    # Then
    assert "paie" in _skill_md(archive.data)
    assert report.skill_stale is False
