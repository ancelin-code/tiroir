"""Creating, reading and writing stores as bare Git repositories."""

import re
import subprocess
import sys
import threading
from pathlib import Path

import pygit2
import pytest

from tiroir.core.errors import CoreError
from tiroir.core.layout import render_frontmatter
from tiroir.core.schema import load_schema
from tiroir.core.store import (
    Author,
    StoreReader,
    StoreWriter,
    append_log,
    create_drawer_files,
    create_store,
    repository_path,
)

PRESET = Path(__file__).resolve().parents[2] / "presets" / "accounting-firm"
STORE_ID = "7c1d4a62-3e5b-4f08-9a17-d2b6c8e0f413"
ALICE = Author("alice", "Alice Martin", "mcp")
ENTRY = re.compile(
    r"clients/c001/log/(\d{4})/(\d{2})/\1-\2-\d{2}T\d{6}Z-alice-[a-z0-9]{4}\.md"
)
WORKER = """
import sys
from pathlib import Path
from tiroir.core.store import Author, append_log

data_dir, store_id, worker = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
author = Author(f"proc{worker}", f"Process {worker}", "cli")
for i in range(20):
    append_log(data_dir, store_id, "clients/c001", f"Entry p{worker}-{i}.", author)
"""


def preset_files() -> dict[str, bytes]:
    """The accounting-firm preset as a store's file set: its data at the root."""
    files: dict[str, bytes] = {}
    for path in PRESET.rglob("*"):
        relative = path.relative_to(PRESET)
        if not path.is_file() or relative.as_posix() == "README.md":
            continue
        parts = relative.parts[1:] if relative.parts[0] == "data" else relative.parts
        files["/".join(parts)] = path.read_bytes()
    return files


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """A data directory holding the preset's store."""
    create_store(tmp_path, STORE_ID, preset_files(), ALICE)
    return tmp_path


def objects(data_dir: Path) -> list[str]:
    """Every file of the repository, to show that nothing was written."""
    root = repository_path(data_dir, STORE_ID)
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())


def test_create_store_makes_a_bare_repository_with_one_commit(tmp_path: Path) -> None:
    # Given
    files = preset_files()

    # When
    commit_id = create_store(tmp_path, STORE_ID, files, ALICE)

    # Then
    repo = pygit2.Repository(str(tmp_path / "stores" / f"{STORE_ID}.git"))
    commit = repo.get(commit_id)
    assert isinstance(commit, pygit2.Commit)
    assert repo.is_bare
    assert str(repo.references["refs/heads/main"].target) == commit_id
    assert commit.parents == []
    assert commit.message == (
        "tiroir: store-init store\n\n"
        "Tiroir-Op: store-init\nTiroir-Author: alice\nTiroir-Via: mcp\n"
    )
    assert (commit.author.name, commit.author.email) == (
        "Alice Martin",
        "alice@tiroir.invalid",
    )
    assert (commit.committer.name, commit.committer.email) == (
        "Alice Martin",
        "alice@tiroir.invalid",
    )
    assert StoreReader(tmp_path, STORE_ID).files() == sorted([*files, "MEMORY.md"])


def test_create_store_generates_memory_from_the_drawers(tmp_path: Path) -> None:
    # Given
    files = preset_files()

    # When
    create_store(tmp_path, STORE_ID, files, ALICE)

    # Then
    memory = StoreReader(tmp_path, STORE_ID).read("MEMORY.md")
    assert memory is not None
    lines = memory.decode("utf-8").splitlines()
    drawer_lines = [line for line in lines if line.startswith("- [[")]
    assert lines[0] == "# cabinet-exemple"
    assert "## Clients" in lines
    assert len(drawer_lines) == len(list((PRESET / "data" / "clients").iterdir()))
    assert drawer_lines == sorted(drawer_lines)
    assert drawer_lines[0] == (
        "- [[clients/c001/summary]] — Client: C001, Boulangerie Bérenger, Bérenger, BB"
    )


def test_create_store_refuses_an_invalid_schema(tmp_path: Path) -> None:
    # Given
    files = {**preset_files(), "tiroir.yaml": b"tiroir: 1\nstore: {}\n"}

    # When
    with pytest.raises(CoreError) as caught:
        create_store(tmp_path, STORE_ID, files, ALICE)

    # Then
    assert caught.value.code == "schema.invalid"
    assert not (tmp_path / "stores").exists()


def test_create_store_refuses_another_store_id(tmp_path: Path) -> None:
    # Given
    other_id = "0d6c1e9a-0000-4000-8000-000000000001"

    # When
    with pytest.raises(CoreError) as caught:
        create_store(tmp_path, other_id, preset_files(), ALICE)

    # Then
    assert caught.value.code == "schema.invalid"
    assert not (tmp_path / "stores").exists()


def test_create_store_refuses_an_existing_store(store: Path) -> None:
    # Given
    head = StoreReader(store, STORE_ID).head()

    # When
    with pytest.raises(CoreError) as caught:
        create_store(store, STORE_ID, preset_files(), ALICE)

    # Then
    assert caught.value.code == "store.exists"
    assert StoreReader(store, STORE_ID).head() == head
    assert [p.name for p in (store / "stores").iterdir()] == [f"{STORE_ID}.git"]


def test_append_log_adds_one_entry_in_one_commit(store: Path) -> None:
    # Given
    reader = StoreReader(store, STORE_ID)
    before = reader.head()

    # When
    commit_id = append_log(
        store, STORE_ID, "clients/c001", "Relance envoyée pour la TVA.", ALICE
    )

    # Then
    commit = reader.repo.get(commit_id)
    assert isinstance(commit, pygit2.Commit)
    assert reader.head() == commit_id
    assert [str(p) for p in commit.parent_ids] == [before]
    changed = reader.changed_paths(before, commit_id)
    assert len(changed) == 1
    assert ENTRY.fullmatch(changed[0])
    assert reader.read(changed[0], before) is None
    entry = reader.read(changed[0])
    assert entry is not None
    assert entry.decode("utf-8").endswith("---\nRelance envoyée pour la TVA.\n")
    assert re.match(
        r"---\ndate: \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\nauthor: alice\n---\n",
        entry.decode("utf-8"),
    )
    assert (commit.author.name, commit.author.email) == (
        "Alice Martin",
        "alice@tiroir.invalid",
    )
    assert (commit.committer.name, commit.committer.email) == (
        "Alice Martin",
        "alice@tiroir.invalid",
    )
    assert commit.message == (
        "tiroir: log-append clients/c001\n\n"
        "Tiroir-Op: log-append\n"
        "Tiroir-Drawer: clients/c001\n"
        "Tiroir-Author: alice\n"
        "Tiroir-Via: mcp\n"
    )


def test_append_log_to_an_unknown_drawer_is_refused(store: Path) -> None:
    # Given
    before = objects(store)

    # When
    with pytest.raises(CoreError) as caught:
        append_log(store, STORE_ID, "clients/c999", "Texte.", ALICE)

    # Then
    assert caught.value.code == "drawer.unknown"
    assert objects(store) == before


def test_append_log_to_an_unknown_store_is_refused(tmp_path: Path) -> None:
    # Given
    data_dir = tmp_path

    # When
    with pytest.raises(CoreError) as caught:
        append_log(data_dir, STORE_ID, "clients/c001", "Texte.", ALICE)

    # Then
    assert caught.value.code == "store.unknown"


def test_append_log_refuses_a_store_whose_schema_is_invalid(store: Path) -> None:
    # Given
    # a commit made outside StoreWriter, which would refuse it, breaks the schema
    repo = pygit2.Repository(str(repository_path(store, STORE_ID)))
    head = repo.get(repo.references["refs/heads/main"].target)
    assert isinstance(head, pygit2.Commit)
    builder = repo.TreeBuilder(head.tree)
    builder.insert(
        "tiroir.yaml", repo.create_blob(b"tiroir: 1\n"), pygit2.enums.FileMode.BLOB
    )
    signature = ALICE.signature()
    repo.create_commit(
        "refs/heads/main", signature, signature, "x", builder.write(), [head.id]
    )
    before = objects(store)

    # When
    with pytest.raises(CoreError) as caught:
        append_log(store, STORE_ID, "clients/c001", "Texte.", ALICE)

    # Then
    assert caught.value.code == "schema.invalid"
    assert objects(store) == before


def test_concurrent_appends_from_threads_and_processes_all_land(store: Path) -> None:
    # Given
    reader = StoreReader(store, STORE_ID)
    initial = reader.head()

    def append_twenty(worker: int) -> None:
        """Append twenty entries as one thread's author."""
        author = Author(f"thread{worker}", f"Thread {worker}", "mcp")
        for i in range(20):
            append_log(store, STORE_ID, "clients/c001", f"Entry t{worker}-{i}.", author)

    # When
    processes = [
        subprocess.Popen([sys.executable, "-c", WORKER, str(store), STORE_ID, str(n)])
        for n in range(2)
    ]
    threads = [threading.Thread(target=append_twenty, args=(n,)) for n in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    codes = [process.wait(timeout=120) for process in processes]

    # Then
    assert codes == [0, 0]
    history = list(reader.repo.walk(reader.head()))
    assert len(history) == 81
    assert all(len(commit.parents) == 1 for commit in history[:-1])
    assert str(history[-1].id) == initial
    for commit, parent in zip(history, history[1:], strict=False):
        assert commit.parents[0].id == parent.id
        assert len(reader.changed_paths(str(parent.id), str(commit.id))) == 1
    added = reader.changed_paths(initial, reader.head())
    bodies = {
        (reader.read(path) or b"").decode("utf-8").rsplit("---\n", 1)[1]
        for path in added
    }
    expected = {
        f"Entry {k}{w}-{i}.\n" for k in "tp" for w in range(2) for i in range(20)
    }
    assert len(added) == 80
    assert bodies == expected
    authors = {path.rsplit("/", 1)[1].split("-")[3] for path in added}
    assert authors == {"thread0", "thread1", "proc0", "proc1"}


def test_reader_lists_changed_paths_from_the_start(store: Path) -> None:
    # Given
    reader = StoreReader(store, STORE_ID)

    # When
    changed = reader.changed_paths(None, reader.head())

    # Then
    assert changed == reader.files()
    assert "tiroir.yaml" in changed


@pytest.mark.parametrize("commit", ["0" * 40, "deadbeef", "main^{tree}", "not a rev!"])
def test_reader_refuses_what_is_not_a_commit(store: Path, commit: str) -> None:
    # Given
    reader = StoreReader(store, STORE_ID)

    # When
    with pytest.raises(CoreError) as caught:
        reader.read("tiroir.yaml", commit)

    # Then
    assert caught.value.code == "store.unknown-commit"


def test_writer_refuses_a_head_moved_outside_the_lock(store: Path) -> None:
    # Given
    repo = pygit2.Repository(str(repository_path(store, STORE_ID)))
    signature = ALICE.signature()

    # When
    with StoreWriter(store, STORE_ID) as writer:
        head = repo.get(repo.references["refs/heads/main"].target)
        assert isinstance(head, pygit2.Commit)
        foreign = repo.create_commit(
            "refs/heads/main", signature, signature, "x", head.tree.id, [head.id]
        )
        with pytest.raises(CoreError) as caught:
            writer.commit("doc-create", ALICE, {"shared/note.md": b"# Note\n"})

    # Then
    assert caught.value.code == "store.foreign-change"
    assert StoreReader(store, STORE_ID).head() == str(foreign)


def test_writer_makes_a_single_commit(store: Path) -> None:
    # Given
    change = {"shared/note.md": b"# Note\n"}

    # When
    with StoreWriter(store, STORE_ID) as writer:
        writer.commit("doc-create", ALICE, change)
        with pytest.raises(RuntimeError) as caught:
            writer.commit("doc-create", ALICE, change)

    # Then
    assert "one commit" in str(caught.value)
    assert StoreReader(store, STORE_ID).read("shared/note.md") == b"# Note\n"


def test_create_drawer_files_renders_the_summary(store: Path) -> None:
    # Given
    reader = StoreReader(store, STORE_ID)
    schema = reader.schema()
    template = (reader.read("templates/client-summary.md") or b"").decode("utf-8")
    fields = {"code": "C042", "name": "Boulangerie Dupont"}

    # When
    files = create_drawer_files(schema, "client", fields, template)

    # Then
    assert list(files) == ["clients/c042/summary.md"]
    text = files["clients/c042/summary.md"].decode("utf-8")
    assert text.startswith(
        render_frontmatter({"type": "client", **fields}) + "# Boulangerie Dupont\n"
    )
    assert "## Échéances" in text


def test_create_drawer_files_validates_the_metadata(store: Path) -> None:
    # Given
    schema = load_schema(
        (StoreReader(store, STORE_ID).read("tiroir.yaml") or b"").decode("utf-8")
    )
    fields = {"code": "bad", "name": "Dupont"}

    # When
    with pytest.raises(CoreError) as caught:
        create_drawer_files(schema, "client", fields, "# {name}\n")

    # Then
    assert caught.value.code == "metadata.invalid"
