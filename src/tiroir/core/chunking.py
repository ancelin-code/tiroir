"""Cutting files into chunks (ADR-007).

Pure functions on a file's body, frontmatter already removed: a summary yields
one chunk per section, a log entry one chunk (split at paragraphs above 400
tokens), a shared document one chunk per level-2 section.
"""

import re
from dataclasses import dataclass
from enum import Enum

LOG_CHUNK_TOKENS = 400

# A closing run of `#` only counts after a space, so `## C#` keeps its `#`.
_HEADING = re.compile(r"##[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")


class Kind(Enum):
    """What a chunk comes from."""

    SUMMARY = "summary"
    LOG = "log"
    SHARED = "shared"


@dataclass(frozen=True)
class Chunk:
    """A piece of a file: its section heading (`None` before the first) and text."""

    section: str | None
    text: str


def sections(body: str) -> list[Chunk]:
    """The body cut at level-2 headings, outside code fences, empty parts dropped.

    The text before the first heading comes first, with no section. The heading
    line itself is not part of the text.
    """
    parts: list[tuple[str | None, list[str]]] = [(None, [])]
    fenced = False
    for line in body.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        heading = None if fenced else _HEADING.fullmatch(line)
        if heading is not None:
            parts.append((heading.group(1), []))
        else:
            parts[-1][1].append(line)
    chunks = [Chunk(name, "\n".join(lines).strip()) for name, lines in parts]
    return [chunk for chunk in chunks if chunk.text]


def summary_chunks(body: str) -> list[Chunk]:
    """One chunk per section of a summary."""
    return sections(body)


def shared_chunks(body: str) -> list[Chunk]:
    """One chunk per level-2 section of a shared document."""
    return sections(body)


def log_chunks(body: str, max_tokens: int = LOG_CHUNK_TOKENS) -> list[Chunk]:
    """One chunk for a log entry; above `max_tokens` words, cut at paragraphs.

    Paragraphs are grouped greedily up to `max_tokens` words; a single longer
    paragraph stays whole.
    """
    paragraphs = [p.strip() for p in _PARAGRAPH_BREAK.split(body) if p.strip()]
    groups: list[list[str]] = []
    size = 0
    for paragraph in paragraphs:
        count = len(paragraph.split())
        if groups and size + count <= max_tokens:
            groups[-1].append(paragraph)
            size += count
        else:
            groups.append([paragraph])
            size = count
    return [Chunk(None, "\n\n".join(group)) for group in groups]
