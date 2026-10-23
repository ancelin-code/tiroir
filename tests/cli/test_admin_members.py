from pathlib import Path

import pytest

from tiroir.cli.main import main
from tiroir.core import serverdb


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("TIROIR_DATA", str(tmp_path))
    return tmp_path


def _password(output: str) -> str:
    return output.strip().splitlines()[-1].rsplit(": ", 1)[-1]


def test_init_creates_database_and_one_administrator(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    argv = ["admin", "init"]

    # When
    code = main(argv)

    # Then
    out = capsys.readouterr().out
    conn = serverdb.open_server_db(data_dir)
    members = serverdb.list_members(conn)
    assert code == 0
    assert [(m.handle, m.is_admin, m.must_change_password) for m in members] == [
        ("admin", True, True)
    ]
    assert "admin" in out
    stored = serverdb.password_hash(conn, "admin")
    assert stored is not None
    assert serverdb.verify_password(stored, _password(out))


def test_second_init_refuses_with_exit_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given
    main(["admin", "init"])
    capsys.readouterr()

    # When
    code = main(["admin", "init"])

    # Then
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "already has an administrator" in captured.err


def test_init_reports_a_taken_admin_handle_with_exit_1(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given
    main(["admin", "members", "add", "admin", "--name", "Not an administrator"])
    capsys.readouterr()

    # When
    code = main(["admin", "init"])

    # Then
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert "handle 'admin' is already used" in captured.err


def test_add_member_prints_initial_password_only_once(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    argv = ["admin", "members", "add", "bob", "--name", "Bob Martin"]

    # When
    code = main(argv)

    # Then
    out = capsys.readouterr().out
    conn = serverdb.open_server_db(data_dir)
    member = serverdb.find_member(conn, "bob")
    stored = serverdb.password_hash(conn, "bob")
    assert code == 0
    assert member is not None
    assert member.display_name == "Bob Martin"
    assert member.must_change_password and not member.is_admin
    assert stored is not None and stored.startswith("$argon2id$")
    assert serverdb.verify_password(stored, _password(out))
    main(["admin", "members", "list"])
    assert _password(out) not in capsys.readouterr().out


def test_disable_member_then_report_disabled_and_unknown(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    main(["admin", "members", "add", "bob", "--name", "Bob"])
    capsys.readouterr()

    # When
    first = main(["admin", "members", "disable", "bob"])
    again = main(["admin", "members", "disable", "bob"])
    unknown = main(["admin", "members", "disable", "nobody"])

    # Then
    err = capsys.readouterr().err
    member = serverdb.find_member(serverdb.open_server_db(data_dir), "bob")
    assert (first, again, unknown) == (0, 1, 1)
    assert member is not None and member.disabled is not None
    assert "member 'bob' is disabled" in err
    assert "unknown member 'nobody'" in err


def test_add_duplicate_or_invalid_handle_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given
    main(["admin", "members", "add", "bob", "--name", "Bob"])
    capsys.readouterr()

    # When
    duplicate = main(["admin", "members", "add", "bob", "--name", "Bob"])
    invalid = main(["admin", "members", "add", "Bad Handle", "--name", "X"])

    # Then
    assert (duplicate, invalid) == (1, 1)
    assert "already used" in capsys.readouterr().err


def test_reset_password_sets_a_new_one_to_change(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    main(["admin", "members", "add", "bob", "--name", "Bob"])
    capsys.readouterr()

    # When
    code = main(["admin", "members", "reset-password", "bob"])

    # Then
    out = capsys.readouterr().out
    conn = serverdb.open_server_db(data_dir)
    stored = serverdb.password_hash(conn, "bob")
    assert code == 0
    assert stored is not None
    assert serverdb.verify_password(stored, _password(out))


def test_usage_error_exits_2(capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    argv = ["admin", "members", "add"]

    # When
    code = main(argv)

    # Then
    assert code == 2
    assert capsys.readouterr().err.startswith("usage: tiroir admin")
