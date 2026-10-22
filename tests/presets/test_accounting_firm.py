"""Shape and content of the accounting-firm preset and its synthetic dataset."""

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

PRESET = Path(__file__).resolve().parents[2] / "presets" / "accounting-firm"
DATA = PRESET / "data"
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
LOG_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})T(\d{6})Z-([a-z0-9]+)-[a-z0-9]{4}\.md")
SIREN = re.compile(r"\b\d{3} ?\d{3} ?\d{3}\b")
INVOICE = re.compile(r"\b20\d{2}-\d{3}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w.-]+")
TOP_LEVEL_REQUIRED = {"tiroir", "store", "drawer_types"}
STORE_REQUIRED = {"id", "name", "audience", "language"}
TYPE_REQUIRED = {"label", "path", "fields", "summary"}


def load_yaml(text: str) -> Any:
    return YAML(typ="safe").load(text)


def split(path: Path) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    assert match, f"{path}: no frontmatter"
    return load_yaml(match.group(1)), match.group(2)


def luhn_valid(digits: str) -> bool:
    total = 0
    for i, char in enumerate(reversed(digits)):
        value = int(char) * (2 if i % 2 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return load_yaml((PRESET / "tiroir.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client_type(schema: dict[str, Any]) -> dict[str, Any]:
    return schema["drawer_types"]["client"]


def summaries() -> list[Path]:
    return sorted(DATA.glob("clients/*/summary.md"))


def logs() -> list[Path]:
    return sorted(DATA.glob("clients/*/log/*/*/*.md"))


def all_data_text() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DATA.rglob("*.md"))


def test_schema_has_every_required_key(schema: dict[str, Any]) -> None:
    # Given
    client = schema["drawer_types"]["client"]

    # When
    top_missing = TOP_LEVEL_REQUIRED - schema.keys()
    store_missing = STORE_REQUIRED - schema["store"].keys()
    type_missing = TYPE_REQUIRED - client.keys()

    # Then
    assert top_missing == set()
    assert store_missing == set()
    assert type_missing == set()
    assert schema["tiroir"] == 1
    assert schema["store"]["language"] == "fr"
    assert "sections" in client["summary"]
    assert all("type" in field for field in client["fields"].values())


def test_schema_describes_the_type_and_its_fields(client_type: dict[str, Any]) -> None:
    # Given
    fields = client_type["fields"]

    # When
    undescribed = [name for name, field in fields.items() if "description" not in field]

    # Then
    assert "description" in client_type
    assert undescribed == []


def test_schema_references_existing_files(
    schema: dict[str, Any], client_type: dict[str, Any]
) -> None:
    # Given
    referenced = [
        client_type["summary"]["template"],
        client_type["log"]["template"],
        schema["shared"]["conventions"],
    ]

    # When
    missing = [path for path in referenced if not (PRESET / path).is_file()]

    # Then
    assert missing == []


def test_summary_template_has_the_schema_sections(client_type: dict[str, Any]) -> None:
    # Given
    text = (PRESET / client_type["summary"]["template"]).read_text(encoding="utf-8")

    # When
    headings = re.findall(r"^## (.+)$", text, re.MULTILINE)

    # Then
    assert headings == client_type["summary"]["sections"]


def test_dataset_has_at_least_twenty_drawers() -> None:
    # Given
    paths = summaries()

    # When
    count = len(paths)

    # Then
    assert count >= 20


def test_every_summary_matches_the_schema(client_type: dict[str, Any]) -> None:
    # Given
    fields = client_type["fields"]
    sections = client_type["summary"]["sections"]
    pattern = re.compile(fields["code"]["pattern"])

    # When
    problems: list[str] = []
    for path in summaries():
        meta, body = split(path)
        expected_keys = ["type", *[name for name in fields if name in meta]]
        if list(meta) != expected_keys:
            problems.append(f"{path}: keys {list(meta)} are not in schema order")
        if meta.get("type") != "client":
            problems.append(f"{path}: type")
        unknown = set(meta) - {"type", *fields}
        missing = {n for n, f in fields.items() if f.get("required")} - set(meta)
        if unknown or missing:
            problems.append(f"{path}: unknown {unknown}, missing {missing}")
        if not pattern.fullmatch(str(meta.get("code", ""))):
            problems.append(f"{path}: code")
        if path.parent.name != str(meta.get("code", "")).lower():
            problems.append(f"{path}: folder does not match the code")
        if meta.get("legal_form") not in fields["legal_form"]["values"]:
            problems.append(f"{path}: legal_form")
        if not isinstance(meta.get("fiscal_year_end"), date):
            problems.append(f"{path}: fiscal_year_end")
        if not isinstance(meta.get("aliases"), list):
            problems.append(f"{path}: aliases")
        if re.findall(r"^## (.+)$", body, re.MULTILINE) != sections:
            problems.append(f"{path}: sections")

    # Then
    assert problems == []


def test_codes_are_unique() -> None:
    # Given
    codes = [split(path)[0]["code"] for path in summaries()]

    # When
    distinct = set(codes)

    # Then
    assert len(distinct) == len(codes)


def test_every_drawer_has_five_to_thirty_log_entries() -> None:
    # Given
    drawers = [path.parent for path in summaries()]

    # When
    counts = {d.name: len(list(d.glob("log/*/*/*.md"))) for d in drawers}

    # Then
    assert all(5 <= count <= 30 for count in counts.values()), counts


def test_every_log_entry_is_valid_and_filed_by_date() -> None:
    # Given
    paths = logs()

    # When
    problems: list[str] = []
    years: set[int] = set()
    for path in paths:
        meta, body = split(path)
        name = LOG_NAME.fullmatch(path.name)
        stamp = meta.get("date")
        if set(meta) != {"date", "author"} or not isinstance(stamp, datetime):
            problems.append(f"{path}: frontmatter")
            continue
        years.add(stamp.year)
        if name is None:
            problems.append(f"{path}: file name")
            continue
        day, time, author = name.groups()
        if day != f"{stamp:%Y-%m-%d}" or time != f"{stamp:%H%M%S}":
            problems.append(f"{path}: file name does not match the date")
        if author != meta["author"]:
            problems.append(f"{path}: author")
        folders = (path.parent.parent.name, path.parent.name)
        if folders != (f"{stamp:%Y}", f"{stamp:%m}"):
            problems.append(f"{path}: folder does not match the date")
        if not body.strip():
            problems.append(f"{path}: empty body")

    # Then
    assert problems == []
    assert years == {2025, 2026}


def test_data_has_sirens_with_and_without_spaces() -> None:
    # Given
    text = all_data_text()

    # When
    found = SIREN.findall(text)

    # Then
    assert any(" " in siren for siren in found)
    assert any(" " not in siren for siren in found)


def test_data_has_invoice_numbers() -> None:
    # Given
    text = all_data_text()

    # When
    found = INVOICE.findall(text)

    # Then
    assert any(number.startswith("2026-") for number in found)
    assert any(number.startswith("2025-") for number in found)
    assert len(set(found)) >= 20


def test_data_has_accented_surnames_and_inflections() -> None:
    # Given
    text = all_data_text()

    # When
    words = set(re.findall(r"[\w'-]+", text.lower()))

    # Then
    assert {"bérenger", "thévenet", "rességuier", "çelik"} <= words
    assert {"déclaration", "déclarations"} <= words
    assert {"échéance", "échéances"} <= words


def test_no_siren_is_a_valid_registered_number() -> None:
    # Given
    sirens = {s.replace(" ", "") for s in SIREN.findall(all_data_text())}
    sirens -= {n.replace("-", "") for n in INVOICE.findall(all_data_text())}

    # When
    valid = [s for s in sirens if len(s) == 9 and luhn_valid(s)]

    # Then
    assert sirens
    assert valid == []


def test_every_email_uses_the_reserved_domain() -> None:
    # Given
    text = all_data_text() + (PRESET / "shared" / "conventions.md").read_text("utf-8")

    # When
    foreign = [e for e in EMAIL.findall(text) if not e.endswith("@example.fr")]

    # Then
    assert foreign == []


def test_readme_states_the_data_is_synthetic() -> None:
    # Given
    readme = (PRESET / "README.md").read_text(encoding="utf-8")

    # When
    stated = "synthetic" in readme and "example.fr" in readme and "Luhn" in readme

    # Then
    assert stated
