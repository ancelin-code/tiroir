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


def _grant(member_id: str, grant_id: str = "g1") -> serverdb.OAuthGrant:
    return serverdb.OAuthGrant(grant_id, "client-1", member_id, ("mcp",), None)


def _tokens(prefix: str, expires: int = 2_000_000_000) -> list[serverdb.OAuthTokenHash]:
    return [
        serverdb.OAuthTokenHash(f"{prefix}-access", "access", expires),
        serverdb.OAuthTokenHash(f"{prefix}-refresh", "refresh", expires),
    ]


def _count(conn: sqlite3.Connection, table: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_reused_refresh_token_deletes_its_grant(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    member = serverdb.create_member(conn, "bob", "Bob", "pw")
    other = _grant(member.id, "g2")
    serverdb.save_oauth_tokens(conn, other, _tokens("other"))
    serverdb.save_oauth_tokens(conn, _grant(member.id), _tokens("first"))
    serverdb.rotate_refresh_token(
        conn, "first-refresh", _grant(member.id), _tokens("second"), 2_000_000_000
    )

    # When
    reused = serverdb.revoke_reused_secret(conn, "first-refresh", "refresh", 0)

    # Then
    assert reused is True
    remaining = {row[0] for row in conn.execute("SELECT grant_id FROM oauth_tokens")}
    assert remaining == {"g2"}
    assert _count(conn, "oauth_spent_secrets") == 0


def test_secret_never_spent_is_not_reused(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    member = serverdb.create_member(conn, "bob", "Bob", "pw")
    serverdb.save_oauth_tokens(conn, _grant(member.id), _tokens("first"))

    # When
    reused = serverdb.revoke_reused_secret(conn, "unknown", "refresh", 0)

    # Then
    assert reused is False
    assert _count(conn, "oauth_tokens") == 2


def test_spent_code_revokes_the_tokens_it_issued(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    member = serverdb.create_member(conn, "bob", "Bob", "pw")
    spent = serverdb.SpentSecret("code-hash", "code", 2_000_000_000)
    serverdb.save_oauth_tokens(conn, _grant(member.id), _tokens("first"), spent)

    # When
    reused = serverdb.revoke_reused_secret(conn, "code-hash", "code", 0)

    # Then
    assert reused is True
    assert _count(conn, "oauth_tokens") == 0
    assert _count(conn, "oauth_spent_secrets") == 0


def test_spent_secrets_go_with_their_grant(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    member = serverdb.create_member(conn, "bob", "Bob", "pw")
    spent = serverdb.SpentSecret("code-hash", "code", 2_000_000_000)
    serverdb.save_oauth_tokens(conn, _grant(member.id), _tokens("first"), spent)
    serverdb.rotate_refresh_token(
        conn, "first-refresh", _grant(member.id), _tokens("second"), 2_000_000_000
    )

    # When
    serverdb.revoke_oauth_grant(conn, "second-access")

    # Then
    assert _count(conn, "oauth_tokens") == 0
    assert _count(conn, "oauth_spent_secrets") == 0


def test_expired_spent_secrets_are_forgotten(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    member = serverdb.create_member(conn, "bob", "Bob", "pw")
    old = serverdb.SpentSecret("old-code", "code", 1)
    serverdb.save_oauth_tokens(conn, _grant(member.id), _tokens("first"), old)

    # When
    serverdb.save_oauth_tokens(conn, _grant(member.id, "g2"), _tokens("second"))

    # Then
    assert _count(conn, "oauth_spent_secrets") == 0
    assert serverdb.revoke_reused_secret(conn, "old-code", "code", 0) is False


def test_full_client_store_forgets_the_oldest_idle_client(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    member = serverdb.create_member(conn, "bob", "Bob", "pw")
    for client_id in ("busy", "idle-old", "idle-new"):
        serverdb.save_oauth_client(conn, client_id, "{}", None, limit=3)
    busy = serverdb.OAuthGrant("g1", "busy", member.id, (), None)
    serverdb.save_oauth_tokens(conn, busy, _tokens("busy"))

    # When
    serverdb.save_oauth_client(conn, "latest", "{}", None, limit=3)

    # Then
    clients = {row[0] for row in conn.execute("SELECT client_id FROM oauth_clients")}
    assert clients == {"busy", "idle-new", "latest"}


def test_full_client_store_with_only_live_clients_refuses(tmp_path: Path) -> None:
    # Given
    conn = serverdb.open_server_db(tmp_path)
    member = serverdb.create_member(conn, "bob", "Bob", "pw")
    serverdb.save_oauth_client(conn, "busy", "{}", None, limit=1)
    busy = serverdb.OAuthGrant("g1", "busy", member.id, (), None)
    serverdb.save_oauth_tokens(conn, busy, _tokens("busy"))

    # When / Then
    with pytest.raises(serverdb.ClientStoreFull):
        serverdb.save_oauth_client(conn, "latest", "{}", None, limit=1)
    assert _count(conn, "oauth_clients") == 1
