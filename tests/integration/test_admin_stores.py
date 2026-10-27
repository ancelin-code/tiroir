"""`tiroir admin stores|grant|revoke|index` through `main()`."""

from pathlib import Path

import pytest

from tiroir.cli.main import main
from tiroir.core import Scope, open_core, serverdb

PRESETS = Path(__file__).resolve().parents[2] / "presets"
ADD = [
    "admin", "stores", "add", "cabinet", "--audience", "personal",
    "--language", "fr", "--owner", "alice", "--preset", "accounting-firm",
]  # fmt: skip


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data directory with an administrator, Alice and Bob."""
    monkeypatch.setenv("TIROIR_DATA", str(tmp_path))
    monkeypatch.setenv("TIROIR_PRESETS", str(PRESETS))
    conn = serverdb.open_server_db(tmp_path)
    serverdb.create_member(conn, "root", "Root", "pw", is_admin=True)
    serverdb.create_member(conn, "alice", "Alice Martin", "pw")
    serverdb.create_member(conn, "bob", "Bob Durand", "pw")
    conn.close()
    return tmp_path


def test_add_creates_grants_and_indexes_the_store(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    argv = ADD

    # When
    code = main(argv)
    listed = main(["admin", "stores", "list"])

    # Then
    out = capsys.readouterr().out
    core = open_core(data_dir, start_workers=False)
    [store] = core.member("alice").stores()
    found = core.member("alice").search("TVA", Scope(all_drawers=True))
    assert (code, listed) == (0, 0)
    assert "cabinet\tpersonal\tfr\t1 members" in out
    assert (store.name, store.access.value, store.is_default) == (
        "cabinet",
        "write",
        True,
    )
    assert found.hits


def test_personal_store_without_owner_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given
    argv = [
        "admin", "stores", "add", "cabinet", "--audience", "personal",
        "--language", "fr", "--preset", "accounting-firm",
    ]  # fmt: skip

    # When
    code = main(argv)

    # Then
    assert code == 1
    assert "params.invalid" in capsys.readouterr().err
    assert main(["admin", "stores", "list"]) == 0
    assert capsys.readouterr().out == ""


def test_unknown_preset_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    argv = [*ADD[:-1], "nope"]

    # When
    code = main(argv)

    # Then
    assert code == 1
    assert "preset.unknown" in capsys.readouterr().err


def test_second_grant_on_a_personal_store_is_refused(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given
    main(ADD)

    # When
    code = main(["admin", "grant", "bob", "cabinet", "read"])

    # Then
    assert code == 3
    assert "access.personal" in capsys.readouterr().err


def test_grant_and_revoke_on_a_team_store(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    main(
        [
            "admin",
            "stores",
            "add",
            "team",
            "--audience",
            "team",
            "--language",
            "fr",
            "--preset",
            "accounting-firm",
        ]  # fmt: skip
    )
    capsys.readouterr()

    # When
    granted = main(["admin", "grant", "bob", "team", "read"])
    after_grant = open_core(data_dir, start_workers=False).member("bob").stores()
    revoked = main(["admin", "revoke", "bob", "team"])
    after_revoke = open_core(data_dir, start_workers=False).member("bob").stores()

    # Then
    assert (granted, revoked) == (0, 0)
    assert capsys.readouterr().out == (
        "bob: read access to team\nbob: no access to team\n"
    )
    assert [s.name for s in after_grant] == ["team"]
    assert after_revoke == []


def test_grant_of_an_unknown_store_fails(capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    argv = ["admin", "grant", "bob", "missing", "read"]

    # When
    code = main(argv)

    # Then
    assert code == 1
    assert "error: store.unknown: no store missing" in capsys.readouterr().err


def test_index_rebuild_keeps_the_hits(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    main(ADD)
    member = open_core(data_dir, start_workers=False).member("alice")
    before = member.search("TVA", Scope(all_drawers=True))
    capsys.readouterr()

    # When
    code = main(["admin", "index", "--store", "cabinet", "--rebuild"])

    # Then
    after = member.search("TVA", Scope(all_drawers=True))
    assert code == 0
    assert capsys.readouterr().out.startswith("cabinet: ")
    assert before.hits
    assert after == before


def test_index_of_every_store(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    main(ADD)
    capsys.readouterr()

    # When
    code = main(["admin", "index"])

    # Then
    assert code == 0
    assert capsys.readouterr().out.startswith("cabinet: 0 files indexed")


def test_command_needs_an_administrator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    monkeypatch.setenv("TIROIR_DATA", str(tmp_path / "empty"))

    # When
    code = main(["admin", "stores", "list"])

    # Then
    assert code == 1
    assert "tiroir admin init" in capsys.readouterr().err
