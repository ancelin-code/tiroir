"""The server database: members, grants and stores, in `<data>/server.db`.

ADR-004 keeps everything the server knows about members and access here, never
in a store's repository. Every other module reaches the database through this
one, so that it can be swapped later.
"""

import re
import secrets
import sqlite3
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

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


@dataclass(frozen=True)
class Member:
    id: str
    handle: str
    display_name: str
    is_admin: bool
    must_change_password: bool
    created: str
    disabled: str | None


Migration = Callable[[sqlite3.Connection], None]


def _create_skeleton(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE members (
            id TEXT PRIMARY KEY,
            handle TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            must_change_password INTEGER NOT NULL DEFAULT 0,
            created TEXT NOT NULL,
            disabled TEXT
        );
        CREATE TABLE stores (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            audience TEXT NOT NULL CHECK (audience IN ('personal', 'team')),
            language TEXT NOT NULL,
            created TEXT NOT NULL
        );
        CREATE TABLE grants (
            member TEXT NOT NULL REFERENCES members (id),
            store_id TEXT NOT NULL REFERENCES stores (id),
            access TEXT NOT NULL CHECK (access IN ('read', 'write')),
            PRIMARY KEY (member, store_id)
        );
        """
    )


# Ordered: entry `i` brings the schema from version `i` to version `i + 1`.
MIGRATIONS: Sequence[Migration] = (_create_skeleton,)


def _current_version(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return int(row[0] or 0)


def migrate(
    conn: sqlite3.Connection, migrations: Sequence[Migration] = MIGRATIONS
) -> int:
    """Apply the missing migrations in order, one transaction each."""
    version = _current_version(conn)
    for target in range(version + 1, len(migrations) + 1):
        conn.execute("BEGIN")
        try:
            migrations[target - 1](conn)
            conn.execute("DELETE FROM schema_version")
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (target,))
        except BaseException:
            conn.rollback()
            raise
        conn.commit()
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
