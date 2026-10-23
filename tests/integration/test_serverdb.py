import sqlite3
from pathlib import Path

import pytest

from tiroir.core import serverdb


def test_open_creates_schema_at_latest_version(tmp_path: Path) -> None:
    # Given
    data = tmp_path / "data"

    # When
    conn = serverdb.open_server_db(data)

    # Then
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert {"members", "grants", "stores", "schema_version"} <= tables
    assert version == len(serverdb.MIGRATIONS)


def test_old_database_at_version_zero_gets_missing_migrations(tmp_path: Path) -> None:
    # Given
    old = sqlite3.connect(tmp_path / serverdb.DB_NAME)
    old.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
    old.execute("INSERT INTO schema_version (version) VALUES (0)")
    old.commit()
    old.close()

    # When
    conn = serverdb.open_server_db(tmp_path)

    # Then
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert version == len(serverdb.MIGRATIONS)
    assert serverdb.list_members(conn) == []


def test_migrations_apply_in_order_and_only_once() -> None:
    # Given
    conn = sqlite3.connect(":memory:", isolation_level=None)
    first = "CREATE TABLE one (x);"
    second = "CREATE TABLE two (x);"

    # When
    serverdb.migrate(conn, (first,))
    serverdb.migrate(conn, (first, second))
    serverdb.migrate(conn, (first, second))

    # Then
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    assert {"one", "two"} <= tables
    assert version == 2


def test_failed_migration_leaves_the_version_unchanged() -> None:
    # Given
    conn = sqlite3.connect(":memory:", isolation_level=None)
    broken = "CREATE TABLE t (x); SELECT * FROM table_that_does_not_exist;"

    # When
    with pytest.raises(sqlite3.OperationalError):
        serverdb.migrate(conn, (broken,))

    # Then
    version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    tables = conn.execute("SELECT name FROM sqlite_master WHERE name='t'").fetchall()
    assert version is None
    assert tables == []


def test_failed_skeleton_migration_leaves_no_table() -> None:
    # Given
    conn = sqlite3.connect(":memory:", isolation_level=None)
    skeleton_then_fail = (
        serverdb.MIGRATIONS[0] + "\nSELECT * FROM table_that_does_not_exist;"
    )

    # When
    with pytest.raises(sqlite3.OperationalError):
        serverdb.migrate(conn, (skeleton_then_fail,))

    # Then
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE name IN ('members', 'stores', 'grants')"
    ).fetchall()
    assert tables == []


def test_packaged_migrations_are_numbered_without_gap() -> None:
    # Given / When
    migrations = serverdb.load_migrations()

    # Then
    assert len(migrations) >= 1
    assert "CREATE TABLE members" in migrations[0]


def test_create_and_find_member_hashes_with_argon2id(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)

    # When
    created = serverdb.create_member(conn, "bob", "Bob Martin", "s3cret-pass")

    # Then
    found = serverdb.find_member(conn, "bob")
    stored = serverdb.password_hash(conn, "bob")
    assert found == created
    assert found is not None and found.must_change_password
    assert stored is not None and stored.startswith("$argon2id$")
    assert "s3cret-pass" not in stored
    assert serverdb.verify_password(stored, "s3cret-pass")
    assert not serverdb.verify_password(stored, "other")


def test_duplicate_handle_is_refused(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    serverdb.create_member(conn, "bob", "Bob", "pw")

    # When / Then
    with pytest.raises(serverdb.HandleTaken):
        serverdb.create_member(conn, "bob", "Other Bob", "pw")


@pytest.mark.parametrize("handle", ["", "Bob", "b o b", "../x", "-bob"])
def test_invalid_handle_is_refused(tmp_path: Path, handle: str) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)

    # When / Then
    with pytest.raises(serverdb.InvalidHandle):
        serverdb.create_member(conn, handle, "Bob", "pw")


def test_disable_member_keeps_the_handle_reserved(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    serverdb.create_member(conn, "bob", "Bob", "pw")

    # When
    disabled = serverdb.disable_member(conn, "bob")

    # Then
    assert disabled.disabled is not None
    with pytest.raises(serverdb.HandleTaken):
        serverdb.create_member(conn, "bob", "Bob again", "pw")
    with pytest.raises(serverdb.MemberDisabled):
        serverdb.disable_member(conn, "bob")


def test_disable_unknown_member_fails(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)

    # When / Then
    with pytest.raises(serverdb.UnknownMember):
        serverdb.disable_member(conn, "nobody")


def test_disable_revokes_grants(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    member = serverdb.create_member(conn, "bob", "Bob", "pw")
    conn.execute("INSERT INTO stores VALUES ('s1', 'team', 'team', 'fr', '2026-01-01')")
    conn.execute("INSERT INTO grants VALUES (?, 's1', 'read')", (member.id,))

    # When
    serverdb.disable_member(conn, "bob")

    # Then
    assert conn.execute("SELECT COUNT(*) FROM grants").fetchone()[0] == 0


def test_reset_password_flags_the_change(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    serverdb.create_member(conn, "bob", "Bob", "old", must_change_password=False)

    # When
    member = serverdb.reset_password(conn, "bob", "new")

    # Then
    stored = serverdb.password_hash(conn, "bob")
    assert member.must_change_password
    assert stored is not None and serverdb.verify_password(stored, "new")
