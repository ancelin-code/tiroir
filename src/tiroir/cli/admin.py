"""The administration CLI: `tiroir admin …`, run inside the server's container."""

import argparse
import sqlite3
from os import environ
from pathlib import Path

import uvicorn
from loguru import logger

from tiroir.core import serverdb
from tiroir.core.serverdb import Member, ServerDbError

DEFAULT_DATA_DIR = "/data"
PORT = 8080
INITIAL_ADMIN_HANDLE = "admin"


def _data_dir() -> Path:
    return Path(environ.get("TIROIR_DATA", DEFAULT_DATA_DIR))


def _error(message: str) -> int:
    logger.error(f"error: {message}")
    return 1


def _describe(error: ServerDbError, handle: str) -> str:
    match error:
        case serverdb.InvalidHandle():
            return f"{handle!r} is not a valid handle (lowercase letters, digits, - _)"
        case serverdb.HandleTaken():
            return f"handle {handle!r} is already used"
        case serverdb.UnknownMember():
            return f"unknown member {handle!r}"
        case serverdb.MemberDisabled():
            return f"member {handle!r} is disabled"
        case _:
            return str(error)


def _init(_args: argparse.Namespace) -> int:
    conn = serverdb.open_server_db(_data_dir())
    try:
        if serverdb.has_admin(conn):
            return _error("the server already has an administrator")
        password = serverdb.generate_password()
        serverdb.create_member(
            conn, INITIAL_ADMIN_HANDLE, "Administrator", password, is_admin=True
        )
    except ServerDbError as error:
        return _error(_describe(error, INITIAL_ADMIN_HANDLE))
    finally:
        conn.close()
    logger.info(f"administrator: {INITIAL_ADMIN_HANDLE}")
    logger.info(
        f"initial password (shown once, to change at first sign-in): {password}"
    )
    return 0


def _print_member(member: Member) -> None:
    flags: list[str] = []
    if member.is_admin:
        flags.append("admin")
    if member.disabled is not None:
        flags.append("disabled")
    suffix = f"  [{', '.join(flags)}]" if flags else ""
    logger.info(f"{member.handle}\t{member.display_name}{suffix}")


def _members(args: argparse.Namespace) -> int:
    conn = serverdb.open_server_db(_data_dir())
    try:
        return _members_action(conn, args)
    finally:
        conn.close()


def _members_action(conn: sqlite3.Connection, args: argparse.Namespace) -> int:
    action: str = args.action or "list"
    if action == "list":
        for member in serverdb.list_members(conn):
            _print_member(member)
        return 0
    handle: str = args.handle
    try:
        if action == "add":
            password = serverdb.generate_password()
            serverdb.create_member(
                conn, handle, args.name, password, is_admin=args.admin
            )
            logger.info(f"member: {handle}")
            logger.info(
                f"initial password (shown once, to change at first sign-in): {password}"
            )
        elif action == "disable":
            serverdb.disable_member(conn, handle)
            logger.info(f"{handle}: disabled")
        else:  # reset-password
            password = serverdb.generate_password()
            serverdb.reset_password(conn, handle, password)
            logger.info(
                f"{handle}: new password (shown once, to change at next sign-in)"
            )
            logger.info(password)
    except ServerDbError as error:
        return _error(_describe(error, handle))
    return 0


def _serve(_args: argparse.Namespace) -> int:
    # The application is named by string: the CLI never imports the server.
    uvicorn.run(
        "tiroir.server.app:app_from_env",
        factory=True,
        host="0.0.0.0",  # the container's port, behind Caddy
        port=PORT,
        workers=1,
        log_config=None,
        access_log=False,
    )
    return 0


def register(commands: "argparse._SubParsersAction[argparse.ArgumentParser]") -> None:
    """Add `tiroir admin …` to the command line's sub-commands."""
    admin = commands.add_parser("admin", help="administer this server")
    admin_commands = admin.add_subparsers(dest="admin_command", required=True)
    admin_commands.add_parser(
        "init", help="create the first administrator"
    ).set_defaults(run=_init)
    members = admin_commands.add_parser("members", help="list and change members")
    members.set_defaults(run=_members)
    actions = members.add_subparsers(dest="action")
    actions.add_parser("list")
    add = actions.add_parser("add")
    add.add_argument("handle")
    add.add_argument("--name", required=True)
    add.add_argument("--admin", action="store_true")
    actions.add_parser("disable").add_argument("handle")
    actions.add_parser("reset-password").add_argument("handle")
    admin_commands.add_parser("serve", help="run the server").set_defaults(run=_serve)
