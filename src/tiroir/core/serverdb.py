"""The server database: members, grants and stores, in `<data>/server.db`.

ADR-004 keeps everything the server knows about members and access here, never
in a store's repository. Every other module reaches the database through this
one, so that it can be swapped later.
"""

import re
import secrets
import sqlite3
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
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
