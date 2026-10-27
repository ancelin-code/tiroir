"""The core API: member-scoped calls over stores created from a preset."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from tiroir.core import (
    Access,
    Audience,
    Core,
    CoreError,
    DrawerRef,
    Entry,
    Filters,
    Kind,
    Log,
    Scope,
    Summary,
    open_core,
    serverdb,
    to_json,
)

PRESET = Path(__file__).resolve().parents[2] / "presets" / "accounting-firm"
CLIENT = "clients/c001"


@pytest.fixture
def core(tmp_path: Path) -> Iterator[Core]:
    """A core with an administrator, Alice and Bob, and no store."""
    conn = serverdb.open_server_db(tmp_path)
    serverdb.create_member(conn, "root", "Root", "pw", is_admin=True)
    serverdb.create_member(conn, "alice", "Alice Martin", "pw")
    serverdb.create_member(conn, "bob", "Bob Durand", "pw")
    conn.close()
    opened = open_core(tmp_path, start_workers=False)
    yield opened
    opened.close()


@pytest.fixture
def cabinet(core: Core) -> Core:
    """The core with Alice's personal store `cabinet` made from the preset."""
    core.admin("root").create_store(
        "cabinet", Audience.PERSONAL, "fr", owner="alice", preset=PRESET
    )
    return core


def test_create_store_grants_the_owner_and_makes_it_their_default(
    core: Core,
) -> None:
    # Given
    admin = core.admin("root")

    # When
    created = admin.create_store(
        "cabinet", Audience.PERSONAL, "fr", owner="alice", preset=PRESET
    )

    # Then
    [store] = core.member("alice").stores()
    assert (store.id, store.name, store.audience, store.language) == (
        created.id,
        "cabinet",
        Audience.PERSONAL,
        "fr",
    )
    assert (store.access, store.is_default) == (Access.WRITE, True)


def test_list_drawers_lists_the_presets_clients(cabinet: Core) -> None:
    # Given
    alice = cabinet.member("alice")

    # When
    drawers = alice.list_drawers()

    # Then
    assert len(drawers) == 23
    assert {d.store for d in drawers} == {"cabinet"}
    assert CLIENT in {d.drawer for d in drawers}
    assert alice.list_drawers("cabinet", "client") == drawers


def test_append_log_applies_in_a_personal_store_and_search_finds_it(
    cabinet: Core,
) -> None:
    # Given
    alice = cabinet.member("alice")
    ref = DrawerRef("cabinet", CLIENT)

    # When
    outcome = alice.append_log(ref, "Relance zorglubex envoyée.")
    result = alice.search("zorglubex", Scope(drawers=(ref,)))

    # Then
    assert outcome.applied
    assert outcome.proposal is None
    assert outcome.commit
    assert [h.store for h in result.hits] == ["cabinet"]
    assert result.hits[0].kind is Kind.LOG
    assert not result.abstained
    assert [d.value for d in result.degraded] == ["vectors-pending"]


def test_read_returns_the_summary_the_log_and_an_entry(cabinet: Core) -> None:
    # Given
    alice = cabinet.member("alice")
    ref = DrawerRef("cabinet", CLIENT)
    scope = Scope(drawers=(ref,))

    # When
    summary = alice.read(Summary(ref), scope)
    log = alice.read(Log(ref, limit=3), scope)
    entry_id = log.items[0].path.rpartition("/")[2].removesuffix(".md")
    entry = alice.read(Entry(ref, entry_id), scope)
    older = alice.read(Log(ref, limit=50, before=entry_id), scope)

    # Then
    assert summary.items[0].path == f"{CLIENT}/summary.md"
    assert len(log.items) == 3
    assert entry.items == (log.items[0],)
    assert entry_id not in [i.path for i in older.items]
    assert len(older.items) == 10


def test_read_outside_the_scope_is_denied(cabinet: Core) -> None:
    # Given
    alice = cabinet.member("alice")
    ref = DrawerRef("cabinet", CLIENT)

    # When
    with pytest.raises(CoreError) as raised:
        alice.read(Summary(ref), Scope())

    # Then
    assert raised.value.code == "scope.denied"


def test_read_of_an_unknown_drawer_fails(cabinet: Core) -> None:
    # Given
    ref = DrawerRef("cabinet", "clients/none")

    # When
    with pytest.raises(CoreError) as raised:
        cabinet.member("alice").read(Summary(ref), Scope(all_drawers=True))

    # Then
    assert raised.value.code == "drawer.unknown"


def test_ungranted_member_sees_the_store_as_unknown(cabinet: Core) -> None:
    # Given
    bob = cabinet.member("bob")
    ref = DrawerRef("cabinet", CLIENT)
    missing = DrawerRef("missing", CLIENT)
    calls = [
        lambda: bob.list_drawers("cabinet"),
        lambda: bob.read(Summary(ref), Scope(drawers=(ref,))),
        lambda: bob.search("x", Scope(drawers=(ref,))),
        lambda: bob.search("x", Scope(), Filters(stores=("cabinet",))),
        lambda: bob.append_log(ref, "x"),
    ]

    # When
    codes = []
    for call in calls:
        with pytest.raises(CoreError) as raised:
            call()
        codes.append((raised.value.code, raised.value.message))
    with pytest.raises(CoreError) as absent:
        bob.append_log(missing, "x")

    # Then
    assert {code for code, _ in codes} == {"store.unknown"}
    assert bob.stores() == []
    assert absent.value.code == "store.unknown"


def test_bob_searches_only_what_he_was_granted(cabinet: Core) -> None:
    # Given
    cabinet.member("alice").append_log(DrawerRef("cabinet", CLIENT), "zorglubex")

    # When
    result = cabinet.member("bob").search("zorglubex", Scope(all_drawers=True))

    # Then
    assert result.hits == ()
    assert result.abstained


def test_read_only_member_cannot_write(cabinet: Core) -> None:
    # Given
    team = cabinet.admin("root")
    team.create_store("shared-team", Audience.TEAM, "fr", preset=PRESET)
    team.grant("bob", "shared-team", Access.READ)
    ref = DrawerRef("shared-team", CLIENT)

    # When
    with pytest.raises(CoreError) as raised:
        cabinet.member("bob").append_log(ref, "x")

    # Then
    assert raised.value.code == "access.read-only"


def test_revoke_takes_effect_at_the_next_call(cabinet: Core) -> None:
    # Given
    admin = cabinet.admin("root")
    ref = DrawerRef("cabinet", CLIENT)
    alice = cabinet.member("alice")
    assert alice.stores()

    # When
    admin.revoke("alice", "cabinet")

    # Then
    assert alice.stores() == []
    with pytest.raises(CoreError) as raised:
        alice.append_log(ref, "x")
    assert raised.value.code == "store.unknown"


def test_personal_store_refuses_a_second_grant(cabinet: Core) -> None:
    # Given
    admin = cabinet.admin("root")

    # When
    with pytest.raises(CoreError) as raised:
        admin.grant("bob", "cabinet", Access.READ)

    # Then
    assert raised.value.code == "access.personal"


def test_personal_store_needs_an_owner(core: Core) -> None:
    # Given
    admin = core.admin("root")

    # When
    with pytest.raises(CoreError) as raised:
        admin.create_store("solo", Audience.PERSONAL, "fr", preset=PRESET)

    # Then
    assert raised.value.code == "params.invalid"
    assert admin.stores() == []


@pytest.mark.parametrize("name", ["", "Cabinet", "two words"])
def test_store_name_must_be_a_slug(core: Core, name: str) -> None:
    # Given
    admin = core.admin("root")

    # When
    with pytest.raises(CoreError) as raised:
        admin.create_store(name, Audience.TEAM, "fr", preset=PRESET)

    # Then
    assert raised.value.code == "params.invalid"
    assert admin.stores() == []


def test_store_name_is_unique(cabinet: Core) -> None:
    # Given
    admin = cabinet.admin("root")

    # When
    with pytest.raises(CoreError) as raised:
        admin.create_store("cabinet", Audience.TEAM, "fr", preset=PRESET)

    # Then
    assert raised.value.code == "store.exists"
    assert len(admin.stores()) == 1


def test_admin_context_is_for_administrators(core: Core) -> None:
    # Given
    member = "alice"

    # When
    with pytest.raises(CoreError) as raised:
        core.admin(member)

    # Then
    assert raised.value.code == "access.not-admin"


def test_unknown_member_is_revoked(core: Core) -> None:
    # Given
    ghost = core.member("ghost")

    # When
    with pytest.raises(CoreError) as raised:
        ghost.stores()

    # Then
    assert raised.value.code == "auth.revoked"


def test_member_without_a_default_store_cannot_use_the_default(
    cabinet: Core,
) -> None:
    # Given
    cabinet.admin("root").create_store("team", Audience.TEAM, "fr", preset=PRESET)
    cabinet.admin("root").grant("bob", "team", Access.WRITE)

    # When
    with pytest.raises(CoreError) as raised:
        cabinet.member("bob")._granted(None)

    # Then
    assert raised.value.code == "store.no-default"


def test_rebuild_gives_the_same_hits(cabinet: Core) -> None:
    # Given
    alice = cabinet.member("alice")
    alice.append_log(DrawerRef("cabinet", CLIENT), "Relance zorglubex envoyée.")
    before = alice.search("zorglubex TVA", Scope(all_drawers=True))

    # When
    report = cabinet.admin("root").index("cabinet", rebuild=True)
    after = alice.search("zorglubex TVA", Scope(all_drawers=True))

    # Then
    assert report.stores[0].rebuilt
    assert before.hits
    assert after == before


def test_results_serialise_to_json(cabinet: Core) -> None:
    # Given
    alice = cabinet.member("alice")
    alice.append_log(DrawerRef("cabinet", CLIENT), "zorglubex")
    result = alice.search("zorglubex", Scope(all_drawers=True))

    # When
    data = json.loads(to_json(result))

    # Then
    assert data["hits"][0]["store"] == "cabinet"
    assert data["hits"][0]["kind"] == "log"
    assert data["degraded"] == ["vectors-pending"]
    assert data["abstained"] is False
