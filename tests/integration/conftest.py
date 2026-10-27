"""Fixtures shared by the integration tests."""

from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from mcp_support import Firm, mint_token

from tiroir.core import Audience, open_core, serverdb
from tiroir.core.store import Author, create_store

PRESET = Path(__file__).resolve().parents[2] / "presets" / "accounting-firm"
STORE_ID = "7c1d4a62-3e5b-4f08-9a17-d2b6c8e0f413"
ALICE = Author("alice", "Alice Martin", "mcp")


def preset_files() -> dict[str, bytes]:
    """The accounting-firm preset as a store's file set: its data at the root."""
    files: dict[str, bytes] = {}
    for path in PRESET.rglob("*"):
        relative = path.relative_to(PRESET)
        if not path.is_file() or relative.as_posix() == "README.md":
            continue
        parts = relative.parts[1:] if relative.parts[0] == "data" else relative.parts
        files["/".join(parts)] = path.read_bytes()
    return files


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """A data directory holding the preset's store."""
    create_store(tmp_path, STORE_ID, preset_files(), ALICE)
    return tmp_path


@pytest.fixture
def store_id() -> str:
    """The id of the preset's store."""
    return STORE_ID


@pytest.fixture
def author() -> Author:
    """The member writing in the tests."""
    return ALICE


@pytest.fixture
def firm(tmp_path: Path) -> Iterator[Firm]:
    """Alice owns the personal store `cabinet`; Bob has no grant; Carol is disabled."""
    with closing(serverdb.open_server_db(tmp_path)) as conn:
        serverdb.create_member(conn, "root", "Root", "pw", is_admin=True)
        ids = {
            handle: serverdb.create_member(conn, handle, name, "pw").id
            for handle, name in [
                ("alice", "Alice Martin"),
                ("bob", "Bob Durand"),
                ("carol", "Carol Petit"),
            ]
        }
    core = open_core(tmp_path, start_workers=False)
    core.admin("root").create_store(
        "cabinet", Audience.PERSONAL, "fr", owner="alice", preset=PRESET
    )
    core.close()
    tokens = {handle: mint_token(tmp_path, member) for handle, member in ids.items()}
    with closing(serverdb.open_server_db(tmp_path)) as conn:
        serverdb.disable_member(conn, "carol")
    yield Firm(tmp_path, tokens)
