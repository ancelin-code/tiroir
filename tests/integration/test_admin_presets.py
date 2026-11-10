"""The administrator's own presets in `<data>/presets/`, through `main()`."""

import shutil
import subprocess
from pathlib import Path

import pytest

from tiroir.cli.main import main
from tiroir.core import Audience, open_core, serverdb

BUNDLED = Path(__file__).resolve().parents[2] / "presets"


def add(store: str, preset: str) -> list[str]:
    return [
        "admin", "stores", "add", store, "--audience", "team",
        "--language", "fr", "--preset", preset,
    ]  # fmt: skip


@pytest.fixture(autouse=True)
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A data directory with an administrator, and the bundled presets."""
    data = tmp_path / "data"
    monkeypatch.setenv("TIROIR_DATA", str(data))
    monkeypatch.setenv("TIROIR_PRESETS", str(BUNDLED))
    conn = serverdb.open_server_db(data)
    serverdb.create_member(conn, "root", "Root", "pw", is_admin=True)
    conn.close()
    return data


def install(data: Path, name: str, source: str = "accounting-firm") -> Path:
    """Copy a bundled preset to the server's presets folder under `name`."""
    target = data / "presets" / name
    shutil.copytree(BUNDLED / source, target)
    return target


def test_server_preset_is_used_by_name(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    folder = install(data_dir, "acme")
    (folder / "shared" / "acme-only.md").write_text("# Acme only\n")

    # When
    code = main(add("acme-memory", "acme"))

    # Then
    core = open_core(data_dir, start_workers=False)
    [row] = core.admin("root").stores()
    [repository] = (data_dir / "stores").glob("*.git")
    files = subprocess.run(
        ["git", "--git-dir", str(repository), "ls-tree", "-r", "--name-only", "main"],
        capture_output=True, text=True, check=True,
    ).stdout.splitlines()  # fmt: skip
    assert (code, row.name) == (0, "acme-memory")
    assert "store: acme-memory" in capsys.readouterr().out
    assert "shared/acme-only.md" in files


def test_invalid_server_preset_is_refused_and_creates_nothing(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    broken = install(data_dir, "acme")
    (broken / "tiroir.yaml").write_text("tiroir: 1\nbogus: true\n")

    # When
    code = main(add("acme-memory", "acme"))

    # Then
    assert code == 1
    assert "schema.invalid" in capsys.readouterr().err
    core = open_core(data_dir, start_workers=False)
    assert core.admin("root").stores() == []
    assert not list((data_dir / "stores").glob("*.git"))


def test_invalid_server_preset_reports_the_messages_of_a_bundled_one(
    data_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given
    schema = "tiroir: 1\nbogus: true\n"
    bundled = tmp_path / "bundled"
    shutil.copytree(BUNDLED / "accounting-firm", bundled / "acme-bundled")
    (bundled / "acme-bundled" / "tiroir.yaml").write_text(schema)
    monkeypatch.setenv("TIROIR_PRESETS", str(bundled))
    (install(data_dir, "acme") / "tiroir.yaml").write_text(schema)
    main(add("from-bundled", "acme-bundled"))
    from_bundled = capsys.readouterr().err

    # When
    code = main(add("from-server", "acme"))

    # Then
    assert code == 1
    assert capsys.readouterr().err == from_bundled
    assert "bogus (line 2): unknown key" in from_bundled


def test_server_preset_named_like_a_bundled_one_conflicts(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    folder = install(data_dir, "accounting-firm")

    # When
    code = main(add("cabinet", "accounting-firm"))
    listed = main(["admin", "stores", "presets"])

    # Then
    captured = capsys.readouterr()
    assert code == 1
    assert "preset.conflict" in captured.err
    assert str(folder) in captured.err
    assert listed == 0
    assert "accounting-firm\tbundled" in captured.out
    assert "accounting-firm\tserver" in captured.out
    core = open_core(data_dir, start_workers=False)
    assert core.admin("root").stores() == []


def test_presets_lists_every_origin(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given
    install(data_dir, "acme")

    # When
    code = main(["admin", "stores", "presets"])

    # Then
    assert code == 0
    assert capsys.readouterr().out.splitlines() == [
        "accounting-firm\tbundled",
        "acme\tserver",
    ]


def test_server_preset_survives_a_new_image(data_dir: Path, tmp_path: Path) -> None:
    # Given
    install(data_dir, "acme")
    new_image = tmp_path / "new-image-presets"
    shutil.copytree(BUNDLED / "accounting-firm", new_image / "other")
    before = open_core(data_dir, start_workers=False, presets_dir=BUNDLED)
    before.close()

    # When
    core = open_core(data_dir, start_workers=False, presets_dir=new_image)
    admin = core.admin("root")
    listed = [(p.name, p.origin) for p in admin.presets()]
    acme = admin.preset_path("acme")
    admin.create_store("acme-memory", Audience.TEAM, "fr", preset=acme)

    # Then
    assert listed == [("acme", "server"), ("other", "bundled")]
    assert [s.name for s in admin.stores()] == ["acme-memory"]
