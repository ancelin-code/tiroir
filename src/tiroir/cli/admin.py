"""The administration CLI: `tiroir admin …`, run inside the server's container."""

import argparse
import ipaddress
import sqlite3
from collections.abc import Callable
from contextlib import closing
from os import environ
from pathlib import Path
from typing import Any

import uvicorn
from loguru import logger

from tiroir.core import Access, AdminContext, Audience, CoreError, open_core, serverdb
from tiroir.core.presets import preset_path
from tiroir.core.serverdb import Member, ServerDbError

DEFAULT_DATA_DIR = "/data"
PORT = 8080
INITIAL_ADMIN_HANDLE = "admin"
# Where a request may come from with an X-Forwarded-For uvicorn believes: the
# Compose network that holds Caddy (`compose.yaml`), else only this container.
TRUSTED_PROXIES_VARIABLE = "TIROIR_TRUSTED_PROXIES"
DEFAULT_TRUSTED_PROXIES = "127.0.0.1"
# Where the presets live: `presets/` of the repository, copied into the image.
PRESETS_VARIABLE = "TIROIR_PRESETS"
DEFAULT_PRESETS_DIR = "/app/presets"
# Exit codes of the CLI contract for a failure of the core.
EXIT_FAILED = 1
EXIT_REFUSED = 3
EXIT_BUSY = 5


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


def _exit_code(error: CoreError) -> int:
    """The exit code of the CLI contract for a core failure."""
    if error.code == "store.busy":
        return EXIT_BUSY
    if error.code.startswith("access.") or error.code == "scope.denied":
        return EXIT_REFUSED
    return EXIT_FAILED


def _acting_admin(conn: sqlite3.Connection) -> str | None:
    """The handle of the first enabled administrator, who acts for the operator."""
    admins = [m for m in serverdb.list_members(conn) if m.is_admin and not m.disabled]
    return admins[0].handle if admins else None


def _with_admin(run: Callable[[AdminContext], None]) -> int:
    """Run `run` as the server's administrator; a core failure becomes an exit code."""
    with closing(serverdb.open_server_db(_data_dir())) as conn:
        handle = _acting_admin(conn)
    if handle is None:
        return _error("the server has no administrator: run `tiroir admin init`")
    core = open_core(_data_dir(), start_workers=False)
    try:
        run(core.admin(handle))
    except CoreError as error:
        logger.error(f"error: {error.code}: {error.message}")
        return _exit_code(error)
    finally:
        core.close()
    return 0


def _stores(args: argparse.Namespace) -> int:
    def run(admin: AdminContext) -> None:
        if (args.action or "list") == "list":
            for store in admin.stores():
                logger.info(
                    f"{store.name}\t{store.audience.value}\t{store.language}"
                    f"\t{store.members} members"
                )
            return
        preset = None
        if args.preset is not None:
            presets = Path(environ.get(PRESETS_VARIABLE, DEFAULT_PRESETS_DIR))
            preset = preset_path(presets, args.preset)
        created = admin.create_store(
            args.name, Audience(args.audience), args.language, args.owner, preset
        )
        logger.info(f"store: {created.name}")

    return _with_admin(run)


def _grant(args: argparse.Namespace) -> int:
    def run(admin: AdminContext) -> None:
        admin.grant(args.handle, args.store, Access(args.access))
        logger.info(f"{args.handle}: {args.access} access to {args.store}")

    return _with_admin(run)


def _revoke(args: argparse.Namespace) -> int:
    def run(admin: AdminContext) -> None:
        admin.revoke(args.handle, args.store)
        logger.info(f"{args.handle}: no access to {args.store}")

    return _with_admin(run)


def _index(args: argparse.Namespace) -> int:
    def run(admin: AdminContext) -> None:
        for report in admin.index(args.store, args.rebuild).stores:
            logger.info(
                f"{report.store}: {report.files_indexed} files indexed,"
                f" {report.chunks} chunks"
            )

    return _with_admin(run)


def trusted_proxies(value: str) -> list[str]:
    """The networks of a comma-separated list; raises `ValueError` on anything else.

    A wildcard is refused: anyone could then choose the address tiroir sees.
    """
    networks = [part.strip() for part in value.split(",") if part.strip()]
    if not networks:
        raise ValueError("no network")
    return [str(ipaddress.ip_network(network, strict=False)) for network in networks]


def proxy_options(proxies: list[str]) -> dict[str, Any]:
    """Uvicorn's options that take the client's address from trusted proxies only."""
    return {"proxy_headers": True, "forwarded_allow_ips": proxies}


def _serve(_args: argparse.Namespace) -> int:
    value = environ.get(TRUSTED_PROXIES_VARIABLE, DEFAULT_TRUSTED_PROXIES)
    try:
        proxies = trusted_proxies(value)
    except ValueError:
        return _error(f"{TRUSTED_PROXIES_VARIABLE} must list IP networks")
    # The application is named by string: the CLI never imports the server.
    uvicorn.run(
        "tiroir.server.app:app_from_env",
        factory=True,
        host="0.0.0.0",  # the container's port, behind Caddy
        port=PORT,
        workers=1,
        log_config=None,
        access_log=False,
        **proxy_options(proxies),
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
    stores = admin_commands.add_parser("stores", help="list and create stores")
    stores.set_defaults(run=_stores)
    store_actions = stores.add_subparsers(dest="action")
    store_actions.add_parser("list")
    add_store = store_actions.add_parser("add")
    add_store.add_argument("name")
    add_store.add_argument("--audience", required=True, choices=["personal", "team"])
    add_store.add_argument("--language", required=True)
    add_store.add_argument("--owner")
    add_store.add_argument("--preset")
    grant = admin_commands.add_parser("grant", help="give a member access to a store")
    grant.set_defaults(run=_grant)
    grant.add_argument("handle")
    grant.add_argument("store")
    grant.add_argument("access", choices=["read", "write"])
    revoke = admin_commands.add_parser("revoke", help="remove a member's access")
    revoke.set_defaults(run=_revoke)
    revoke.add_argument("handle")
    revoke.add_argument("store")
    index = admin_commands.add_parser("index", help="bring indexes up to date")
    index.set_defaults(run=_index)
    index.add_argument("--store")
    index.add_argument("--rebuild", action="store_true")
    admin_commands.add_parser("serve", help="run the server").set_defaults(run=_serve)
