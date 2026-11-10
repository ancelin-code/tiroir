"""Shape and content of the developer preset and its synthetic dataset."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from tiroir.cli.main import main
from tiroir.core import Scope, open_core, serverdb
from tiroir.core.presets import load_preset
from tiroir.core.schema import load_schema

PRESETS = Path(__file__).resolve().parents[2] / "presets"
PRESET = PRESETS / "developer"
DATA = PRESET / "data"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
LOG_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{6})Z-([a-z0-9]+)-[a-z0-9]{4}\.md")
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\w")
URL = re.compile(r"https?://([\w.-]+)")
HOST = re.compile(r"\b(?:[a-z0-9-]+\.)+(?:com|org|net|io|dev|fr|app)\b")
RESERVED = ("example.com", "example.org")


def reserved(host: str) -> bool:
    """Whether a hostname is a reserved domain or one of its subdomains."""
    return any(host == d or host.endswith(f".{d}") for d in RESERVED)


def load_yaml(text: str) -> Any:
    return YAML(typ="safe").load(text)


def split(path: Path) -> tuple[dict[str, Any], str]:
    """Return a Markdown file's YAML frontmatter and its body."""
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert match, f"{path}: no frontmatter"
    return load_yaml(match.group(1)), match.group(2)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def summaries() -> list[Path]:
    return sorted(DATA.glob("repos/*/summary.md"))


def logs() -> list[Path]:
    return sorted(DATA.glob("repos/*/log/*/*/*.md"))


def all_text() -> str:
    """Return every Markdown file of the preset, joined."""
    return "\n".join(p.read_text(encoding="utf-8") for p in PRESET.rglob("*.md"))


@pytest.fixture(scope="module")
def repo_type() -> dict[str, Any]:
    return load_yaml((PRESET / "tiroir.yaml").read_text(encoding="utf-8"))[
        "drawer_types"
    ]["repo"]


def test_schema_validates_and_declares_detection() -> None:
    # Given
    text = (PRESET / "tiroir.yaml").read_text(encoding="utf-8")

    # When
    schema = load_schema(text)

    # Then
    repo = schema.drawer_types["repo"]
    assert (schema.store.language, schema.store.audience) == ("en", "personal")
    assert repo.path == "repos/{slug}"
    assert list(repo.summary.sections) == [
        "Purpose",
        "Architecture",
        "Conventions",
        "Decisions",
        "Gotchas",
        "Open questions",
    ]


def test_schema_references_existing_files(repo_type: dict[str, Any]) -> None:
    # Given
    schema = load_yaml((PRESET / "tiroir.yaml").read_text(encoding="utf-8"))
    referenced = [
        repo_type["summary"]["template"],
        repo_type["log"]["template"],
        schema["shared"]["conventions"],
    ]

    # When
    missing = [path for path in referenced if not (PRESET / path).is_file()]

    # Then
    assert missing == []
    assert {p.name for p in (PRESET / "shared").glob("*.md")} >= {
        "conventions.md",
        "release-checklist.md",
        "code-review-guide.md",
    }


def test_dataset_has_at_least_twenty_drawers() -> None:
    # Given
    paths = summaries()

    # When
    count = len(paths)

    # Then
    assert count >= 20


def test_every_summary_matches_the_schema(repo_type: dict[str, Any]) -> None:
    # Given
    fields = repo_type["fields"]
    sections = repo_type["summary"]["sections"]
    pattern = re.compile(fields["slug"]["pattern"])

    # When
    problems: list[str] = []
    for path in summaries():
        meta, body = split(path)
        expected = ["type", *[name for name in fields if name in meta]]
        if list(meta) != expected or meta.get("type") != "repo":
            problems.append(f"{path}: keys {list(meta)} are not in schema order")
        if set(meta) - {"type", *fields}:
            problems.append(f"{path}: unknown fields")
        if {n for n, f in fields.items() if f.get("required")} - set(meta):
            problems.append(f"{path}: missing required fields")
        if not pattern.fullmatch(str(meta.get("slug", ""))):
            problems.append(f"{path}: slug")
        if path.parent.name != slugify(str(meta.get("slug", ""))):
            problems.append(f"{path}: folder does not match the slug")
        if not isinstance(meta.get("name"), str):
            problems.append(f"{path}: name")
        aliases = meta.get("aliases")
        if not isinstance(aliases, list) or not all(
            isinstance(a, str) for a in aliases
        ):
            problems.append(f"{path}: aliases")
        for key in ("language", "status"):
            if meta.get(key) not in fields[key]["values"]:
                problems.append(f"{path}: {key}")
        if re.findall(r"^## (.+)$", body, re.MULTILINE) != sections:
            problems.append(f"{path}: sections")

    # Then
    assert problems == []


def test_slugs_are_unique_once_slugified() -> None:
    # Given
    slugs = [slugify(split(path)[0]["slug"]) for path in summaries()]

    # When
    distinct = set(slugs)

    # Then
    assert len(distinct) == len(slugs)


def test_two_drawer_names_overlap() -> None:
    # Given
    slugs = {split(path)[0]["slug"] for path in summaries()}

    # When
    overlapping = {s for s in slugs if any(o.startswith(f"{s}-") for o in slugs)}

    # Then
    assert {"api", "api-gateway"} <= slugs
    assert "api" in overlapping


def test_every_drawer_has_five_to_twenty_five_log_entries() -> None:
    # Given
    drawers = [path.parent for path in summaries()]

    # When
    counts = {d.name: len(list(d.glob("log/*/*/*.md"))) for d in drawers}

    # Then
    assert all(5 <= count <= 25 for count in counts.values()), counts


def test_every_log_entry_is_valid_and_filed_by_date() -> None:
    # Given
    paths = logs()

    # When
    problems: list[str] = []
    years: set[int] = set()
    for path in paths:
        meta, body = split(path)
        stamp = meta.get("date")
        if set(meta) != {"date", "author"} or not isinstance(stamp, datetime):
            problems.append(f"{path}: frontmatter")
            continue
        if stamp.utcoffset() != timedelta(0):
            problems.append(f"{path}: date is not UTC")
        years.add(stamp.year)
        name = LOG_NAME.fullmatch(path.name)
        if name is None:
            problems.append(f"{path}: file name")
            continue
        day, time, author = name.groups()
        if day != f"{stamp:%Y-%m-%d}" or time != f"{stamp:%H%M%S}":
            problems.append(f"{path}: file name does not match the date")
        if author != meta["author"]:
            problems.append(f"{path}: author")
        if (path.parent.parent.name, path.parent.name) != (
            f"{stamp:%Y}",
            f"{stamp:%m}",
        ):
            problems.append(f"{path}: folder does not match the date")
        if not body.strip():
            problems.append(f"{path}: empty body")

    # Then
    assert problems == []
    assert years == {2025, 2026}


def test_data_has_tickets_issues_versions_and_error_codes() -> None:
    # Given
    text = all_text()

    # When
    tickets = set(re.findall(r"\bPROJ-\d{4}\b", text))
    issues = set(re.findall(r"#\d{3}\b", text))
    versions = set(re.findall(r"\bv\d+\.\d+\.\d+\b", text))
    codes = set(re.findall(r"\bE\d{4}\b", text))

    # Then
    assert len(tickets) >= 20
    assert len(issues) >= 20
    assert len(versions) >= 20
    assert len(codes) >= 3


def test_every_address_uses_a_reserved_domain() -> None:
    # Given
    text = all_text()

    # When
    emails = [e for e in EMAIL.findall(text) if not reserved(e.split("@")[1])]
    urls = [h for h in URL.findall(text) if not reserved(h)]
    hosts = [h for h in HOST.findall(text) if not reserved(h)]

    # Then
    assert (emails, urls, hosts) == ([], [], [])


def test_readme_states_the_data_is_synthetic() -> None:
    # Given
    readme = (PRESET / "README.md").read_text(encoding="utf-8")

    # When
    stated = "synthetic" in readme and "example.com" in readme

    # Then
    assert stated


def test_preset_loads_as_a_file_set() -> None:
    # Given
    path = PRESET

    # When
    files = load_preset(path)

    # Then
    assert "repos/api/summary.md" in files
    assert "repos/api-gateway/summary.md" in files
    assert "shared/release-checklist.md" in files
    assert "README.md" not in files


def test_store_created_from_the_preset_indexes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    monkeypatch.setenv("TIROIR_DATA", str(tmp_path))
    monkeypatch.setenv("TIROIR_PRESETS", str(PRESETS))
    conn = serverdb.open_server_db(tmp_path)
    serverdb.create_member(conn, "root", "Root", "pw", is_admin=True)
    serverdb.create_member(conn, "alice", "Alice Martin", "pw")
    conn.close()
    argv = [
        "admin", "stores", "add", "dev", "--audience", "personal",
        "--language", "en", "--owner", "alice", "--preset", "developer",
    ]  # fmt: skip

    # When
    code = main(argv)

    # Then
    core = open_core(tmp_path, start_workers=False)
    found = core.member("alice").search("Quillfold", Scope(all_drawers=True))
    assert code == 0
    assert found.hits
