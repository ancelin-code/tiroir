"""Every relative link in the README and the documentation resolves."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$", re.MULTILINE)


def _anchor(heading: str) -> str:
    """The GitHub anchor of a heading."""
    text = re.sub(r"[`*]", "", heading).lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def _documents() -> list[Path]:
    return [ROOT / "README.md", *sorted((ROOT / "docs").rglob("*.md"))]


def _broken(document: Path) -> list[str]:
    """The links of `document` whose file or heading does not exist."""
    broken: list[str] = []
    for target in LINK.findall(document.read_text(encoding="utf-8")):
        if re.match(r"[a-z][a-z0-9+.-]*:", target):
            continue
        path, _, fragment = target.partition("#")
        linked = (document.parent / path).resolve() if path else document
        if not linked.exists():
            broken.append(target)
        elif fragment and linked.suffix == ".md":
            headings = HEADING.findall(linked.read_text(encoding="utf-8"))
            if fragment not in {_anchor(heading) for heading in headings}:
                broken.append(target)
    return broken


def test_missing_files_and_headings_are_reported(tmp_path: Path) -> None:
    # Given
    (tmp_path / "other.md").write_text("# The `TIROIR_DATA` variable\n")
    document = tmp_path / "index.md"
    document.write_text(
        "[ok](other.md#the-tiroir_data-variable) [file](missing.md)"
        " [heading](other.md#nowhere) [web](https://example.org/nowhere)\n"
    )

    # When
    broken = _broken(document)

    # Then
    assert broken == ["missing.md", "other.md#nowhere"]


def test_every_relative_link_resolves() -> None:
    # Given
    documents = _documents()

    # When
    broken = {
        str(document.relative_to(ROOT)): found
        for document in documents
        if (found := _broken(document))
    }

    # Then
    assert broken == {}
