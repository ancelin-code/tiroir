"""The `summary`, `log`, `detect` and `inject` blocks of a drawer type."""

from collections.abc import Mapping
from typing import Any

from tiroir.core.schema.checker import Checker
from tiroir.core.schema.codes import INVALID_DETECT, UNKNOWN_SECTION
from tiroir.core.schema.model import Detect, Field, Inject, Log, Summary
from tiroir.core.yaml_io import item_line, key_line

_DETECTABLE_TYPES = ("text", "list")


def check_summary(c: Checker, node: Mapping[str, Any], path: str) -> Summary | None:
    """The `summary` block of a drawer type: template path and unique headings."""
    if "summary" not in node:
        return None
    where = f"{path}.summary"
    raw = node["summary"]
    summary_line = key_line(node, "summary")
    if (
        c.mapping(
            raw, where, summary_line, ("template", "sections"), ("template", "sections")
        )
        is None
    ):
        return None
    template = c.path_key(raw, "template", where)
    sections = c.string_list(raw, "sections", where, minimum=1)
    if sections is not None and len(set(sections)) != len(sections):
        c.invalid(
            f"{where}.sections",
            "section headings must be unique",
            key_line(raw, "sections"),
        )
    if template is None or sections is None:
        return None
    return Summary(template, sections)


def check_log(c: Checker, node: Mapping[str, Any], path: str) -> Log | None:
    """The `log` block of a drawer type: the optional template path."""
    if "log" not in node:
        return None
    where = f"{path}.log"
    raw = node["log"]
    if c.mapping(raw, where, key_line(node, "log"), ("template",)) is None:
        return None
    return Log(c.path_key(raw, "template", where))


def check_detect(
    c: Checker,
    node: Mapping[str, Any],
    path: str,
    fields: Mapping[str, Field] | None,
) -> Detect | None:
    """The `detect` block: names that must be declared text or list fields."""
    if "detect" not in node:
        return None
    where = f"{path}.detect"
    raw = node["detect"]
    if c.mapping(raw, where, key_line(node, "detect"), ("names", "cwd")) is None:
        return None
    names = c.string_list(raw, "names", where)
    cwd = c.string(raw, "cwd", where)
    if fields is None:  # a field is invalid: detected types cannot be judged
        return Detect(names, cwd)
    listed: list[tuple[str, str, int | None]] = []
    if names is not None:
        names_line = key_line(raw, "names")
        listed.extend(
            (f"{where}.names[{i}]", n, item_line(raw["names"], i) or names_line)
            for i, n in enumerate(names)
        )
    if cwd is not None:
        listed.append((f"{where}.cwd", cwd, key_line(raw, "cwd")))
    for item_path, name, line in listed:
        field = fields.get(name)
        if field is None:
            c.invalid(item_path, "expected the name of a declared field", line)
        elif field.type not in _DETECTABLE_TYPES:
            c.report(
                INVALID_DETECT,
                item_path,
                f"expected a text or list field, not {field.type}",
                line,
            )
    return Detect(names, cwd)


def check_inject(
    c: Checker, node: Mapping[str, Any], path: str, summary: Summary | None
) -> Inject | None:
    """The `inject` block: sections must be headings of the summary."""
    if "inject" not in node:
        return None
    where = f"{path}.inject"
    raw = node["inject"]
    if (
        c.mapping(raw, where, key_line(node, "inject"), ("sections", "max_tokens"))
        is None
    ):
        return None
    sections = c.string_list(raw, "sections", where)
    max_tokens = c.integer(raw, "max_tokens", where)
    if sections is not None and summary is not None:
        for index, section in enumerate(sections):
            if section not in summary.sections:
                c.report(
                    UNKNOWN_SECTION,
                    f"{where}.sections[{index}]",
                    "expected a heading declared in summary.sections",
                    item_line(raw["sections"], index),
                )
    return Inject(sections, max_tokens)
