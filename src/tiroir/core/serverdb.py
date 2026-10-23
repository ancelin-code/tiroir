"""The server database: members, grants and stores, in `<data>/server.db`.

ADR-004 keeps everything the server knows about members and access here, never
in a store's repository; ADR-015 adds the OAuth clients, codes and tokens and
the web sessions. Every other module reaches the database through this one, so
that it can be swapped later.
"""

import hashlib
import re
import secrets
import sqlite3
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from loguru import logger

DB_NAME = "server.db"

HANDLE_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}")

_HASHER = PasswordHasher()  # Argon2id by default


class ServerDbError(Exception):
    """A request the server database refuses."""


class InvalidHandle(ServerDbError):
    """The handle is not a lowercase slug."""


class HandleTaken(ServerDbError):
    """The handle belongs to a member; handles are never reused."""


class UnknownMember(ServerDbError):
    """No member has this handle."""


class MemberDisabled(ServerDbError):
    """The member is already disabled."""


class ClientStoreFull(ServerDbError):
    """Every registered client still has a live token or code: none can go."""


@dataclass(frozen=True)
class Member:
    id: str
    handle: str
    display_name: str
    is_admin: bool
    must_change_password: bool
    created: str
    disabled: str | None


def load_migrations() -> tuple[str, ...]:
    """The SQL scripts of `migrations/`, ordered by their number.

    Script `NNNN_name.sql` brings the schema from version `NNNN - 1` to `NNNN`;
    the numbers start at 1 and have no gap.
    """
    folder = resources.files(__package__).joinpath("migrations")
    files = sorted(
        (f for f in folder.iterdir() if f.name.endswith(".sql")),
        key=lambda f: f.name,
    )
    for expected, file in enumerate(files, start=1):
        if not file.name.startswith(f"{expected:04d}_"):
            raise RuntimeError(f"migration {file.name} should be number {expected:04d}")
    return tuple(file.read_text(encoding="utf-8") for file in files)


MIGRATIONS = load_migrations()


def _current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return int(row[0] or 0)


def migrate(conn: sqlite3.Connection, migrations: Sequence[str] = MIGRATIONS) -> int:
    """Apply the missing migrations in order, one transaction each."""
    version = _current_version(conn)
    for target in range(version + 1, len(migrations) + 1):
        # One script, so that a failure rolls the migration and its version
        # back together: `executescript` commits any transaction opened before.
        script = (
            f"BEGIN;\n{migrations[target - 1]}\n;\n"
            f"DELETE FROM schema_version;\n"
            f"INSERT INTO schema_version (version) VALUES ({target});\n"
            "COMMIT;"
        )
        try:
            conn.executescript(script)
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        logger.info("server database migrated to version {}", target)
    return max(version, len(migrations))


def open_server_db(data_dir: Path | str) -> sqlite3.Connection:
    """Open `<data>/server.db`, creating it and applying missing migrations."""
    directory = Path(data_dir)
    directory.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(directory / DB_NAME, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def generate_password() -> str:
    return secrets.token_urlsafe(12)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


_COLUMNS = "id, handle, display_name, is_admin, must_change_password, created, disabled"


def _member(row: tuple[str, str, str, int, int, str, str | None]) -> Member:
    return Member(
        id=row[0],
        handle=row[1],
        display_name=row[2],
        is_admin=bool(row[3]),
        must_change_password=bool(row[4]),
        created=row[5],
        disabled=row[6],
    )


def create_member(
    conn: sqlite3.Connection,
    handle: str,
    display_name: str,
    password: str,
    *,
    is_admin: bool = False,
    must_change_password: bool = True,
) -> Member:
    if not HANDLE_PATTERN.fullmatch(handle):
        raise InvalidHandle(handle)
    member_id = uuid.uuid4().hex
    created = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        conn.execute(
            "INSERT INTO members (id, handle, display_name, password_hash,"
            " is_admin, must_change_password, created) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                member_id,
                handle,
                display_name,
                _HASHER.hash(password),
                int(is_admin),
                int(must_change_password),
                created,
            ),
        )
    except sqlite3.IntegrityError as error:
        raise HandleTaken(handle) from error
    logger.info("member created: {}", member_id)
    return Member(
        member_id, handle, display_name, is_admin, must_change_password, created, None
    )


def find_member(conn: sqlite3.Connection, handle: str) -> Member | None:
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM members WHERE handle = ?", (handle,)
    ).fetchone()
    return None if row is None else _member(row)


def list_members(conn: sqlite3.Connection) -> list[Member]:
    rows = conn.execute(f"SELECT {_COLUMNS} FROM members ORDER BY created, handle")
    return [_member(row) for row in rows.fetchall()]


def has_admin(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT 1 FROM members WHERE is_admin = 1 LIMIT 1").fetchone()
    return row is not None


def disable_member(conn: sqlite3.Connection, handle: str) -> Member:
    """Disable a member and revoke their grants; the handle stays reserved."""
    member = find_member(conn, handle)
    if member is None:
        raise UnknownMember(handle)
    if member.disabled is not None:
        raise MemberDisabled(handle)
    disabled = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute("BEGIN")
    conn.execute("UPDATE members SET disabled = ? WHERE id = ?", (disabled, member.id))
    conn.execute("DELETE FROM grants WHERE member = ?", (member.id,))
    conn.commit()
    logger.info("member disabled: {}", member.id)
    return find_member(conn, handle) or member


def reset_password(conn: sqlite3.Connection, handle: str, password: str) -> Member:
    """Set a new password the member must change at their next sign-in."""
    member = find_member(conn, handle)
    if member is None:
        raise UnknownMember(handle)
    if member.disabled is not None:
        raise MemberDisabled(handle)
    conn.execute(
        "UPDATE members SET password_hash = ?, must_change_password = 1 WHERE id = ?",
        (_HASHER.hash(password), member.id),
    )
    logger.info("member password reset: {}", member.id)
    return find_member(conn, handle) or member


def password_hash(conn: sqlite3.Connection, handle: str) -> str | None:
    row = conn.execute(
        "SELECT password_hash FROM members WHERE handle = ?", (handle,)
    ).fetchone()
    return None if row is None else str(row[0])


@cache
def _decoy_hash() -> str:
    return _HASHER.hash(secrets.token_urlsafe(16))


def authenticate(conn: sqlite3.Connection, handle: str, password: str) -> Member | None:
    """The active member with this handle and password, or `None`.

    An unknown handle costs a hash check too, so that timing does not tell
    which handles exist.
    """
    stored = password_hash(conn, handle)
    if stored is None:
        verify_password(_decoy_hash(), password)
        return None
    if not verify_password(stored, password):
        return None
    member = find_member(conn, handle)
    return member if member is not None and member.disabled is None else None


def change_password(conn: sqlite3.Connection, member_id: str, password: str) -> None:
    """Set the password the member chose; they no longer have to change it."""
    conn.execute(
        "UPDATE members SET password_hash = ?, must_change_password = 0 WHERE id = ?",
        (_HASHER.hash(password), member_id),
    )
    logger.info("member password changed: {}", member_id)


# Sign-in and OAuth (ADR-015). Every secret arrives here as its digest: this
# module never sees a token, a code or a client secret in clear.


def secret_digest(secret: str) -> str:
    """The stored form of a random secret (token, code, session, client secret)."""
    return hashlib.sha256(secret.encode()).hexdigest()


@dataclass(frozen=True)
class OAuthCode:
    client_id: str
    member: str
    scopes: tuple[str, ...]
    code_challenge: str
    redirect_uri: str
    redirect_uri_explicit: bool
    resource: str | None
    expires: float


@dataclass(frozen=True)
class OAuthGrant:
    """What an access token and its refresh token were issued for, together."""

    grant_id: str
    client_id: str
    member: str
    scopes: tuple[str, ...]
    resource: str | None


@dataclass(frozen=True)
class OAuthTokenHash:
    token_hash: str
    kind: Literal["access", "refresh"]
    expires: int


@dataclass(frozen=True)
class SpentSecret:
    """A code or refresh token already exchanged, remembered until `expires`."""

    secret_hash: str
    kind: Literal["code", "refresh"]
    expires: int


def _forget_idle_client(conn: sqlite3.Connection, now: float) -> bool:
    """Delete the oldest client with no live token or code; `False` if none."""
    cursor = conn.execute(
        "DELETE FROM oauth_clients WHERE client_id = ("
        " SELECT client_id FROM oauth_clients AS c"
        " WHERE NOT EXISTS (SELECT 1 FROM oauth_tokens AS t"
        "  WHERE t.client_id = c.client_id AND t.expires >= ?)"
        " AND NOT EXISTS (SELECT 1 FROM oauth_codes AS o"
        "  WHERE o.client_id = c.client_id AND o.expires >= ?)"
        " ORDER BY created, rowid LIMIT 1)",
        (now, now),
    )
    return cursor.rowcount == 1


def save_oauth_client(
    conn: sqlite3.Connection,
    client_id: str,
    metadata: str,
    secret_hash: str | None,
    *,
    limit: int | None = None,
) -> None:
    """Store a registered client, at most `limit` of them.

    When the store is full, the oldest client with no live token or code goes;
    raises `ClientStoreFull` when there is none.
    """
    created = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute("BEGIN")
    try:
        count = conn.execute("SELECT COUNT(*) FROM oauth_clients").fetchone()[0]
        if limit is not None and count >= limit:
            if not _forget_idle_client(conn, time.time()):
                raise ClientStoreFull(client_id)
            logger.info("oldest idle oauth client forgotten")
        conn.execute(
            "INSERT INTO oauth_clients (client_id, metadata, secret_hash, created)"
            " VALUES (?, ?, ?, ?)",
            (client_id, metadata, secret_hash, created),
        )
    except BaseException:
        conn.rollback()
        raise
    conn.commit()


def oauth_client(
    conn: sqlite3.Connection, client_id: str
) -> tuple[str, str | None] | None:
    """A registered client's metadata (JSON) and secret digest, or `None`."""
    row = conn.execute(
        "SELECT metadata, secret_hash FROM oauth_clients WHERE client_id = ?",
        (client_id,),
    ).fetchone()
    return None if row is None else (str(row[0]), row[1])


def save_oauth_code(conn: sqlite3.Connection, code_hash: str, code: OAuthCode) -> None:
    conn.execute(
        "INSERT INTO oauth_codes (code_hash, client_id, member, scopes,"
        " code_challenge, redirect_uri, redirect_uri_explicit, resource, expires)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            code_hash,
            code.client_id,
            code.member,
            " ".join(code.scopes),
            code.code_challenge,
            code.redirect_uri,
            int(code.redirect_uri_explicit),
            code.resource,
            code.expires,
        ),
    )


def oauth_code(conn: sqlite3.Connection, code_hash: str) -> OAuthCode | None:
    row = conn.execute(
        "SELECT client_id, member, scopes, code_challenge, redirect_uri,"
        " redirect_uri_explicit, resource, expires FROM oauth_codes"
        " WHERE code_hash = ?",
        (code_hash,),
    ).fetchone()
    if row is None:
        return None
    return OAuthCode(
        client_id=row[0],
        member=row[1],
        scopes=tuple(row[2].split()),
        code_challenge=row[3],
        redirect_uri=row[4],
        redirect_uri_explicit=bool(row[5]),
        resource=row[6],
        expires=float(row[7]),
    )


def consume_oauth_code(conn: sqlite3.Connection, code_hash: str) -> bool:
    """Delete a code; `False` when it was already used, so it works once."""
    cursor = conn.execute("DELETE FROM oauth_codes WHERE code_hash = ?", (code_hash,))
    return cursor.rowcount == 1


def _insert_tokens(
    conn: sqlite3.Connection, grant: OAuthGrant, tokens: Sequence[OAuthTokenHash]
) -> None:
    conn.executemany(
        "INSERT INTO oauth_tokens (token_hash, kind, grant_id, client_id, member,"
        " scopes, resource, expires) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                token.token_hash,
                token.kind,
                grant.grant_id,
                grant.client_id,
                grant.member,
                " ".join(grant.scopes),
                grant.resource,
                token.expires,
            )
            for token in tokens
        ],
    )


def _insert_spent(conn: sqlite3.Connection, grant_id: str, spent: SpentSecret) -> None:
    conn.execute(
        "INSERT INTO oauth_spent_secrets (secret_hash, kind, grant_id, expires)"
        " VALUES (?, ?, ?, ?)",
        (spent.secret_hash, spent.kind, grant_id, spent.expires),
    )


def _delete_grant(conn: sqlite3.Connection, grant_id: str) -> None:
    conn.execute("DELETE FROM oauth_tokens WHERE grant_id = ?", (grant_id,))
    conn.execute("DELETE FROM oauth_spent_secrets WHERE grant_id = ?", (grant_id,))


def _purge_expired(conn: sqlite3.Connection, now: float) -> None:
    conn.execute("DELETE FROM oauth_codes WHERE expires < ?", (now,))
    conn.execute("DELETE FROM oauth_tokens WHERE expires < ?", (now,))
    conn.execute("DELETE FROM oauth_spent_secrets WHERE expires < ?", (now,))
    conn.execute("DELETE FROM web_sessions WHERE expires < ?", (now,))


def save_oauth_tokens(
    conn: sqlite3.Connection,
    grant: OAuthGrant,
    tokens: Sequence[OAuthTokenHash],
    spent_code: SpentSecret | None = None,
) -> None:
    """Store a new grant's tokens and the code they came from; forget the expired."""
    conn.execute("BEGIN")
    _purge_expired(conn, time.time())
    _insert_tokens(conn, grant, tokens)
    if spent_code is not None:
        _insert_spent(conn, grant.grant_id, spent_code)
    conn.commit()


def rotate_refresh_token(
    conn: sqlite3.Connection,
    old_hash: str,
    grant: OAuthGrant,
    tokens: Sequence[OAuthTokenHash],
    spent_until: int,
) -> bool:
    """Replace a grant's tokens, once: `False` when the refresh token is gone.

    The old refresh token is remembered as spent until `spent_until`.
    """
    conn.execute("BEGIN")
    cursor = conn.execute(
        "DELETE FROM oauth_tokens WHERE token_hash = ? AND kind = 'refresh'",
        (old_hash,),
    )
    if cursor.rowcount != 1:
        conn.rollback()
        return False
    conn.execute("DELETE FROM oauth_tokens WHERE grant_id = ?", (grant.grant_id,))
    _insert_spent(conn, grant.grant_id, SpentSecret(old_hash, "refresh", spent_until))
    _insert_tokens(conn, grant, tokens)
    conn.commit()
    return True


def revoke_reused_secret(
    conn: sqlite3.Connection,
    secret_hash: str,
    kind: Literal["code", "refresh"],
    now: float,
) -> bool:
    """Delete the grant a spent code or refresh token led to, if it is one.

    `True` when the secret had already been exchanged: whoever presents it
    again may have stolen it, so every token of that grant goes.
    """
    conn.execute("BEGIN")
    row = conn.execute(
        "SELECT grant_id FROM oauth_spent_secrets"
        " WHERE secret_hash = ? AND kind = ? AND expires >= ?",
        (secret_hash, kind, now),
    ).fetchone()
    if row is None:
        conn.rollback()
        return False
    _delete_grant(conn, row[0])
    conn.commit()
    logger.warning("reused oauth {} revoked grant {}", kind, row[0])
    return True


def _grant(row: tuple[str, str, str, str, str | None]) -> OAuthGrant:
    return OAuthGrant(
        grant_id=row[0],
        client_id=row[1],
        member=row[2],
        scopes=tuple(row[3].split()),
        resource=row[4],
    )


def oauth_token(
    conn: sqlite3.Connection,
    token_hash: str,
    kind: Literal["access", "refresh"],
    now: float,
) -> tuple[OAuthGrant, int] | None:
    """An unexpired token's grant and expiry, whatever its member's status."""
    row = conn.execute(
        "SELECT grant_id, client_id, member, scopes, resource, expires"
        " FROM oauth_tokens WHERE token_hash = ? AND kind = ? AND expires >= ?",
        (token_hash, kind, now),
    ).fetchone()
    return None if row is None else (_grant(row[:5]), int(row[5]))


def active_member(conn: sqlite3.Connection, member_id: str) -> Member | None:
    """The member with this id, read now, unless they are disabled."""
    row = conn.execute(
        f"SELECT {_COLUMNS} FROM members WHERE id = ? AND disabled IS NULL",
        (member_id,),
    ).fetchone()
    return None if row is None else _member(row)


def revoke_oauth_grant(conn: sqlite3.Connection, token_hash: str) -> None:
    """Delete the tokens and spent secrets of the grant this token belongs to."""
    row = conn.execute(
        "SELECT grant_id FROM oauth_tokens WHERE token_hash = ?", (token_hash,)
    ).fetchone()
    if row is None:
        return
    conn.execute("BEGIN")
    _delete_grant(conn, row[0])
    conn.commit()


def create_web_session(
    conn: sqlite3.Connection, session_hash: str, member_id: str, expires: int
) -> None:
    conn.execute(
        "INSERT INTO web_sessions (session_hash, member, expires) VALUES (?, ?, ?)",
        (session_hash, member_id, expires),
    )


def web_session_member(
    conn: sqlite3.Connection, session_hash: str, now: float
) -> Member | None:
    """The active member of an unexpired web session, or `None`."""
    row = conn.execute(
        "SELECT member FROM web_sessions WHERE session_hash = ? AND expires >= ?",
        (session_hash, now),
    ).fetchone()
    return None if row is None else active_member(conn, row[0])


def delete_web_session(conn: sqlite3.Connection, session_hash: str) -> None:
    conn.execute("DELETE FROM web_sessions WHERE session_hash = ?", (session_hash,))
