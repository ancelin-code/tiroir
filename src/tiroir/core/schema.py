"""The store schema (`tiroir.yaml`): loading, validation and canonical writing.

The shape, defaults and error codes are fixed by the schema contract
(`delivery/contracts/schema.md`). Loading reports every violation it finds,
not only the first. Optional keys are kept as written (`None` when absent);
the defaults the contract names are exposed as properties.

Checking that a template holds exactly the headings of `summary.sections`
needs the template file, so it belongs to the code that reads the store.
"""

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal, get_args

from tiroir.core.errors import CoreError, Violation
from tiroir.core.yaml_io import (
    YamlError,
    dump_yaml,
    item_line,
    key_line,
    load_yaml,
    node_line,
)

SUPPORTED_VERSION = 1

Audience = Literal["personal", "team"]
FieldType = Literal["text", "number", "date", "boolean", "enum", "list"]
FieldValue = str | int | float | bool | date | tuple[str, ...]

_AUDIENCES: tuple[str, ...] = get_args(Audience)
_FIELD_TYPES: tuple[str, ...] = get_args(FieldType)
_DETECTABLE_TYPES = ("text", "list")
_RESERVED_FIELDS = ("type", "author", "date")
_SLUG = re.compile(r"[a-z0-9]+(?:[-_][a-z0-9]+)*")
_LANGUAGE = re.compile(r"[a-z]{2}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")

INVALID = "schema.invalid"
UNSUPPORTED_VERSION = "schema.unsupported-version"
INVALID_PATH = "schema.invalid-path"
UNKNOWN_SECTION = "schema.unknown-section"
INVALID_DETECT = "schema.invalid-detect"
METADATA_INVALID = "metadata.invalid"


@dataclass(frozen=True)
class Store:
    id: str
    name: str
    audience: Audience
    language: str
    description: str | None = None


@dataclass(frozen=True)
class Shared:
    path: str | None = None
    topics: tuple[str, ...] | None = None
    conventions: str | None = None


@dataclass(frozen=True)
class Context:
    conventions_max_tokens: int | None = None


@dataclass(frozen=True)
class Field:
    type: FieldType
    required: bool | None = None
    values: tuple[str, ...] | None = None
    pattern: str | None = None
    default: FieldValue | None = None
    description: str | None = None

    @property
    def is_required(self) -> bool:
        return bool(self.required)


@dataclass(frozen=True)
class Summary:
    template: str
    sections: tuple[str, ...]


@dataclass(frozen=True)
class Log:
    template: str | None = None


@dataclass(frozen=True)
class Detect:
    names: tuple[str, ...] | None = None
    cwd: str | None = None


@dataclass(frozen=True)
class Inject:
    sections: tuple[str, ...] | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class DrawerType:
    label: str
    path: str
    fields: Mapping[str, Field]
    summary: Summary
    label_plural: str | None = None
    description: str | None = None
    log: Log | None = None
    detect: Detect | None = None
    inject: Inject | None = None

    @property
    def inject_sections(self) -> tuple[str, ...]:
        """Sections injected on detection: the declared ones, else all."""
        if self.inject is not None and self.inject.sections is not None:
            return self.inject.sections
        return self.summary.sections

    @property
    def inject_max_tokens(self) -> int:
        if self.inject is not None and self.inject.max_tokens is not None:
            return self.inject.max_tokens
        return 800


@dataclass(frozen=True)
class Schema:
    tiroir: int
    store: Store
    drawer_types: Mapping[str, DrawerType]
    shared: Shared | None = None
    context: Context | None = None

    @property
    def shared_path(self) -> str:
        if self.shared is not None and self.shared.path is not None:
            return self.shared.path
        return "shared"

    @property
    def conventions_max_tokens(self) -> int:
        if self.context is not None and self.context.conventions_max_tokens is not None:
            return self.context.conventions_max_tokens
        return 1500


def _failure(violations: list[Violation]) -> CoreError:
    detail = "\n".join(str(v) for v in violations)
    count = len(violations)
    noun = "violation" if count == 1 else "violations"
    return CoreError(
        violations[0].code,
        f"the schema has {count} {noun}:\n{detail}",
        tuple(violations),
    )


class _Checker:
    """Walks the parsed document, collecting violations instead of raising."""

    def __init__(self) -> None:
        self.violations: list[Violation] = []

    def report(self, code: str, path: str, message: str, line: int | None) -> None:
        self.violations.append(Violation(code, path, message, line))

    def invalid(self, path: str, message: str, line: int | None) -> None:
        self.report(INVALID, path, message, line)

    def mapping(
        self,
        node: object,
        path: str,
        line: int | None,
        keys: tuple[str, ...],
        required: tuple[str, ...] = (),
    ) -> Any:
        """Return `node` when it is a mapping of known keys, reporting the rest."""
        if not isinstance(node, Mapping):
            self.invalid(path, "expected a mapping", line)
            return None
        for key in node:
            if key not in keys:
                self.invalid(
                    _join(path, str(key)),
                    f"unknown key, expected one of: {', '.join(keys)}",
                    key_line(node, key),
                )
        for key in required:
            if key not in node:
                self.invalid(_join(path, key), "missing required key", line)
        return node

    def string(self, parent: Any, key: str, path: str) -> str | None:
        if key not in parent:
            return None
        value = parent[key]
        if not isinstance(value, str):
            self.invalid(_join(path, key), "expected a string", key_line(parent, key))
            return None
        return str(value)

    def slug(self, value: str, path: str, line: int | None, what: str) -> bool:
        if _SLUG.fullmatch(value):
            return True
        self.invalid(
            path, f"expected a {what} (lowercase letters, digits, - and _)", line
        )
        return False

    def integer(self, parent: Any, key: str, path: str) -> int | None:
        if key not in parent:
            return None
        value = parent[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            self.invalid(
                _join(path, key), "expected a positive integer", key_line(parent, key)
            )
            return None
        return int(value)

    def boolean(self, parent: Any, key: str, path: str) -> bool | None:
        if key not in parent:
            return None
        value = parent[key]
        if not isinstance(value, bool):
            self.invalid(_join(path, key), "expected a boolean", key_line(parent, key))
            return None
        return value

    def string_list(
        self, parent: Any, key: str, path: str, *, minimum: int = 0
    ) -> tuple[str, ...] | None:
        if key not in parent:
            return None
        value = parent[key]
        where = _join(path, key)
        line = key_line(parent, key)
        if not isinstance(value, list):
            self.invalid(where, "expected a list of strings", line)
            return None
        ok = True
        for index, item in enumerate(value):
            if not isinstance(item, str):
                self.invalid(
                    f"{where}[{index}]", "expected a string", item_line(value, index)
                )
                ok = False
        if not ok:
            return None
        if len(value) < minimum:
            self.invalid(where, f"expected at least {minimum} item(s)", line)
        return tuple(str(item) for item in value)

    def path_value(self, value: str, path: str, line: int | None) -> None:
        segments = value.split("/")
        if (
            value.startswith("/")
            or "\\" in value
            or any(s in ("", ".", "..") for s in segments)
        ):
            self.report(
                INVALID_PATH,
                path,
                "expected a path relative to the store root, using / and no . or ..",
                line,
            )

    def path_key(self, parent: Any, key: str, path: str) -> str | None:
        value = self.string(parent, key, path)
        if value is not None:
            self.path_value(value, _join(path, key), key_line(parent, key))
        return value


def _join(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _check_store(c: _Checker, root: Any, line: int | None) -> Store | None:
    node = root.get("store")
    where = "store"
    line = key_line(root, "store")
    keys = ("id", "name", "audience", "language", "description")
    if c.mapping(node, where, line, keys, keys[:4]) is None:
        return None
    store_id = c.string(node, "id", where)
    if store_id is not None and not _is_uuid(store_id):
        c.invalid("store.id", "expected a UUID", key_line(node, "id"))
    name = c.string(node, "name", where)
    if name is not None:
        c.slug(name, "store.name", key_line(node, "name"), "slug")
    audience = c.string(node, "audience", where)
    if audience is not None and audience not in _AUDIENCES:
        c.invalid(
            "store.audience",
            f"expected one of: {', '.join(_AUDIENCES)}",
            key_line(node, "audience"),
        )
    language = c.string(node, "language", where)
    if language is not None and not _LANGUAGE.fullmatch(language):
        c.invalid(
            "store.language",
            "expected an ISO 639-1 language code, for example en",
            key_line(node, "language"),
        )
    description = c.string(node, "description", where)
    if (
        store_id is None
        or name is None
        or audience not in _AUDIENCES
        or language is None
    ):
        return None
    return Store(store_id, name, audience, language, description)  # type: ignore[arg-type]


def _is_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


def _check_shared(c: _Checker, root: Any) -> Shared | None:
    if "shared" not in root:
        return None
    node = root["shared"]
    line = key_line(root, "shared")
    if c.mapping(node, "shared", line, ("path", "topics", "conventions")) is None:
        return None
    return Shared(
        c.path_key(node, "path", "shared"),
        c.string_list(node, "topics", "shared"),
        c.path_key(node, "conventions", "shared"),
    )


def _check_context(c: _Checker, root: Any) -> Context | None:
    if "context" not in root:
        return None
    node = root["context"]
    line = key_line(root, "context")
    if c.mapping(node, "context", line, ("conventions_max_tokens",)) is None:
        return None
    return Context(c.integer(node, "conventions_max_tokens", "context"))


def _value_problem(field: Field, value: object) -> str | None:
    """What the field expected, or `None` when `value` is acceptable."""
    match field.type:
        case "text":
            if not isinstance(value, str):
                return "text"
            if field.pattern is not None and not re.fullmatch(field.pattern, value):
                return f"text matching the pattern {field.pattern}"
        case "number":
            if isinstance(value, bool) or not isinstance(value, int | float):
                return "number"
        case "date":
            if _as_date(value) is None:
                return "date YYYY-MM-DD"
        case "boolean":
            if not isinstance(value, bool):
                return "boolean"
        case "enum":
            allowed = field.values or ()
            if not isinstance(value, str) or value not in allowed:
                return f"one of: {', '.join(allowed)}"
        case "list":
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                return "list of text"
    return None


def _as_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _ISO_DATE.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _check_field(
    c: _Checker, node: object, path: str, line: int | None
) -> Field | None:
    keys = ("type", "required", "values", "pattern", "default", "description")
    if c.mapping(node, path, line, keys, ("type",)) is None:
        return None
    assert isinstance(node, Mapping)
    kind = c.string(node, "type", path)
    if kind is not None and kind not in _FIELD_TYPES:
        c.invalid(
            f"{path}.type",
            f"expected one of: {', '.join(_FIELD_TYPES)}",
            key_line(node, "type"),
        )
        kind = None
    required = c.boolean(node, "required", path)
    values = c.string_list(node, "values", path, minimum=1)
    pattern = c.string(node, "pattern", path)
    description = c.string(node, "description", path)
    if kind == "enum" and "values" not in node:
        c.invalid(f"{path}.values", "required for an enum field", line)
    if kind is not None and kind != "enum" and "values" in node:
        c.invalid(
            f"{path}.values", "only an enum field has values", key_line(node, "values")
        )
    if pattern is not None:
        if kind != "text":
            c.invalid(
                f"{path}.pattern",
                "only a text field has a pattern",
                key_line(node, "pattern"),
            )
            pattern = None
        else:
            try:
                re.compile(pattern)
            except re.error:
                c.invalid(
                    f"{path}.pattern",
                    "expected a valid regular expression",
                    key_line(node, "pattern"),
                )
                pattern = None
    if kind is None:
        return None
    field_type: FieldType = kind  # type: ignore[assignment]
    field = Field(field_type, required, values, pattern, None, description)
    default = _check_default(c, node, path, field)
    return Field(field_type, required, values, pattern, default, description)


def _check_default(
    c: _Checker, node: Mapping[str, Any], path: str, field: Field
) -> FieldValue | None:
    if "default" not in node:
        return None
    raw = node["default"]
    problem = _value_problem(field, raw)
    if problem is not None:
        c.invalid(
            f"{path}.default",
            f"expected a value of the field's type: {problem}",
            key_line(node, "default"),
        )
        return None
    if field.type == "date":
        return _as_date(raw)
    if isinstance(raw, list):
        return tuple(str(item) for item in raw)
    if isinstance(raw, str):
        return str(raw)
    return raw


def _segment_bounds(segment: str) -> tuple[str, str] | None:
    """Literal text before the first and after the last placeholder, or `None`."""
    found = list(_PLACEHOLDER.finditer(segment))
    if not found:
        return None
    return segment[: found[0].start()], segment[found[-1].end() :]


def _literal_fits(literal: str, bounds: tuple[str, str]) -> bool:
    head, tail = bounds
    return (
        len(literal) >= len(head) + len(tail)
        and literal.startswith(head)
        and literal.endswith(tail)
    )


def _segments_overlap(a: str, b: str) -> bool:
    bounds_a, bounds_b = _segment_bounds(a), _segment_bounds(b)
    if bounds_a is None and bounds_b is None:
        return a == b
    if bounds_a is None and bounds_b is not None:
        return _literal_fits(a, bounds_b)
    if bounds_a is not None and bounds_b is None:
        return _literal_fits(b, bounds_a)
    assert bounds_a is not None and bounds_b is not None
    (head_a, tail_a), (head_b, tail_b) = bounds_a, bounds_b
    return (head_a.startswith(head_b) or head_b.startswith(head_a)) and (
        tail_a.endswith(tail_b) or tail_b.endswith(tail_a)
    )


def _patterns_overlap(a: str, b: str) -> bool:
    """Whether one folder could match both patterns, or sit inside the other."""
    parts_a, parts_b = a.split("/"), b.split("/")
    return all(_segments_overlap(x, y) for x, y in zip(parts_a, parts_b, strict=False))


def _check_path_pattern(
    c: _Checker,
    value: str,
    path: str,
    line: int | None,
    fields: Mapping[str, Field] | None,
) -> None:
    c.path_value(value, path, line)
    if fields is None:  # a field is invalid: placeholders cannot be judged
        return
    names = _PLACEHOLDER.findall(value)
    if _PLACEHOLDER.sub("", value).count("{") or _PLACEHOLDER.sub("", value).count("}"):
        c.report(INVALID_PATH, path, "unbalanced brace in the path pattern", line)
    for name in names:
        if name not in fields:
            c.report(
                INVALID_PATH,
                path,
                f"placeholder {{{name}}} is not a declared field",
                line,
            )
    if not any(n in fields and fields[n].is_required for n in names):
        c.report(
            INVALID_PATH,
            path,
            "expected at least one placeholder of a required field",
            line,
        )


def _check_drawer_type(
    c: _Checker, node: object, path: str, line: int | None
) -> DrawerType | None:
    keys = (
        "label",
        "label_plural",
        "description",
        "path",
        "fields",
        "summary",
        "log",
        "detect",
        "inject",
    )
    if (
        c.mapping(node, path, line, keys, ("label", "path", "fields", "summary"))
        is None
    ):
        return None
    assert isinstance(node, Mapping)
    label = c.string(node, "label", path)
    label_plural = c.string(node, "label_plural", path)
    description = c.string(node, "description", path)
    pattern = c.string(node, "path", path)
    fields = _check_fields(c, node, path, line)
    summary = _check_summary(c, node, path, line)
    if pattern is not None:
        _check_path_pattern(c, pattern, f"{path}.path", key_line(node, "path"), fields)
    log = _check_log(c, node, path)
    detect = _check_detect(c, node, path, fields)
    inject = _check_inject(c, node, path, summary)
    if label is None or pattern is None or fields is None or summary is None:
        return None
    return DrawerType(
        label, pattern, fields, summary, label_plural, description, log, detect, inject
    )


def _check_fields(
    c: _Checker, node: Mapping[str, Any], path: str, line: int | None
) -> dict[str, Field] | None:
    if "fields" not in node:
        return None
    where = f"{path}.fields"
    raw = node["fields"]
    fields_line = key_line(node, "fields")
    if not isinstance(raw, Mapping):
        c.invalid(where, "expected a mapping", fields_line)
        return None
    if not raw:
        c.invalid(where, "expected at least one field", fields_line)
    fields: dict[str, Field] = {}
    for name in raw:
        field_path = f"{where}.{name}"
        name_line = key_line(raw, name)
        ok = c.slug(str(name), field_path, name_line, "field name")
        if name in _RESERVED_FIELDS:
            c.invalid(field_path, "reserved field name", name_line)
            ok = False
        field = _check_field(c, raw[name], field_path, name_line)
        if ok and field is not None:
            fields[str(name)] = field
    return fields if len(fields) == len(raw) else None


def _check_summary(
    c: _Checker, node: Mapping[str, Any], path: str, line: int | None
) -> Summary | None:
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


def _check_log(c: _Checker, node: Mapping[str, Any], path: str) -> Log | None:
    if "log" not in node:
        return None
    where = f"{path}.log"
    raw = node["log"]
    if c.mapping(raw, where, key_line(node, "log"), ("template",)) is None:
        return None
    return Log(c.path_key(raw, "template", where))


def _check_detect(
    c: _Checker,
    node: Mapping[str, Any],
    path: str,
    fields: Mapping[str, Field] | None,
) -> Detect | None:
    if "detect" not in node:
        return None
    where = f"{path}.detect"
    raw = node["detect"]
    if c.mapping(raw, where, key_line(node, "detect"), ("names", "cwd")) is None:
        return None
    names = c.string_list(raw, "names", where)
    cwd = c.string(raw, "cwd", where)
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
        if fields is None:
            break
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


def _check_inject(
    c: _Checker, node: Mapping[str, Any], path: str, summary: Summary | None
) -> Inject | None:
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


def _check_overlaps(c: _Checker, root: Any, types: Mapping[str, DrawerType]) -> None:
    names = list(types)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            if _patterns_overlap(types[first].path, types[second].path):
                node = root["drawer_types"][second]
                c.report(
                    INVALID_PATH,
                    f"drawer_types.{second}.path",
                    f"overlaps the path of drawer type {first}",
                    key_line(node, "path"),
                )


def _check_drawer_types(c: _Checker, root: Any) -> dict[str, DrawerType] | None:
    if "drawer_types" not in root:
        return None
    raw = root["drawer_types"]
    line = key_line(root, "drawer_types")
    if not isinstance(raw, Mapping):
        c.invalid("drawer_types", "expected a mapping", line)
        return None
    if not raw:
        c.invalid("drawer_types", "expected at least one drawer type", line)
    types: dict[str, DrawerType] = {}
    for name in raw:
        path = f"drawer_types.{name}"
        name_line = key_line(raw, name)
        ok = c.slug(str(name), path, name_line, "drawer type name")
        drawer_type = _check_drawer_type(c, raw[name], path, name_line)
        if ok and drawer_type is not None:
            types[str(name)] = drawer_type
    _check_overlaps(c, root, types)
    return types if len(types) == len(raw) else None


def load_schema(text: str) -> Schema:
    """Parse and validate the text of `tiroir.yaml`.

    Raises `CoreError`. A format version above `SUPPORTED_VERSION` raises
    `schema.unsupported-version` alone, before anything else is read. Any
    other failure lists every violation; the error's code is the first
    violation's and each violation carries its own.
    """
    try:
        root = load_yaml(text)
    except YamlError as error:
        raise _failure([Violation(INVALID, "", error.message, error.line)]) from error
    c = _Checker()
    known = ("tiroir", "store", "shared", "context", "drawer_types")
    if c.mapping(root, "", 1, known, ("tiroir", "store", "drawer_types")) is None:
        raise _failure(c.violations)
    version = root.get("tiroir")
    if isinstance(version, int) and not isinstance(version, bool):
        if version > SUPPORTED_VERSION:
            raise _failure(
                [
                    Violation(
                        UNSUPPORTED_VERSION,
                        "tiroir",
                        f"format version {version} is newer than the supported "
                        f"version {SUPPORTED_VERSION}",
                        key_line(root, "tiroir"),
                    )
                ]
            )
        if version < 1:
            c.invalid("tiroir", "expected a positive integer", key_line(root, "tiroir"))
    elif "tiroir" in root:
        c.invalid("tiroir", "expected an integer", key_line(root, "tiroir"))
    store = _check_store(c, root, node_line(root)) if "store" in root else None
    shared = _check_shared(c, root)
    context = _check_context(c, root)
    drawer_types = _check_drawer_types(c, root)
    if c.violations or store is None or drawer_types is None:
        raise _failure(c.violations)
    return Schema(int(version), store, drawer_types, shared, context)


def _field_entry(field: Field) -> dict[str, Any]:
    entry: dict[str, Any] = {"type": field.type}
    optional = (
        ("required", field.required),
        ("values", field.values),
        ("pattern", field.pattern),
        ("default", field.default),
        ("description", field.description),
    )
    entry.update({k: v for k, v in optional if v is not None})
    return entry


def _drawer_type_entry(drawer_type: DrawerType) -> dict[str, Any]:
    entry: dict[str, Any] = {"label": drawer_type.label}
    if drawer_type.label_plural is not None:
        entry["label_plural"] = drawer_type.label_plural
    if drawer_type.description is not None:
        entry["description"] = drawer_type.description
    entry["path"] = drawer_type.path
    entry["fields"] = {n: _field_entry(f) for n, f in drawer_type.fields.items()}
    entry["summary"] = {
        "template": drawer_type.summary.template,
        "sections": drawer_type.summary.sections,
    }
    if drawer_type.log is not None:
        entry["log"] = _present({"template": drawer_type.log.template})
    if drawer_type.detect is not None:
        entry["detect"] = _present(
            {"names": drawer_type.detect.names, "cwd": drawer_type.detect.cwd}
        )
    if drawer_type.inject is not None:
        entry["inject"] = _present(
            {
                "sections": drawer_type.inject.sections,
                "max_tokens": drawer_type.inject.max_tokens,
            }
        )
    return entry


def _present(entries: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in entries.items() if v is not None}


def dump_schema(schema: Schema) -> str:
    """The schema in canonical form: the keys in the order of the contract."""
    data: dict[str, Any] = {
        "tiroir": schema.tiroir,
        "store": _present(
            {
                "id": schema.store.id,
                "name": schema.store.name,
                "audience": schema.store.audience,
                "language": schema.store.language,
                "description": schema.store.description,
            }
        ),
    }
    if schema.shared is not None:
        data["shared"] = _present(
            {
                "path": schema.shared.path,
                "topics": schema.shared.topics,
                "conventions": schema.shared.conventions,
            }
        )
    if schema.context is not None:
        data["context"] = _present(
            {"conventions_max_tokens": schema.context.conventions_max_tokens}
        )
    data["drawer_types"] = {
        name: _drawer_type_entry(t) for name, t in schema.drawer_types.items()
    }
    return dump_yaml(data, separate_top_level=True)


def validate_metadata(
    drawer_type: DrawerType, mapping: Mapping[str, Any]
) -> list[Violation]:
    """Every way `mapping` (a summary's frontmatter) breaks the type's fields.

    Messages give the field and the expected type, never the value. The
    reserved keys `type`, `author` and `date` are not checked here.
    """
    violations: list[Violation] = []

    def report(name: str, message: str) -> None:
        violations.append(
            Violation(METADATA_INVALID, name, message, key_line(mapping, name))
        )

    for name, field in drawer_type.fields.items():
        value = mapping.get(name)
        if value is None:
            if field.is_required:
                violations.append(
                    Violation(
                        METADATA_INVALID,
                        name,
                        "missing required field",
                        node_line(mapping),
                    )
                )
            continue
        problem = _value_problem(field, value)
        if problem is not None:
            report(name, f"expected {problem}")
    for name in mapping:
        if name not in drawer_type.fields and name not in _RESERVED_FIELDS:
            report(str(name), "unknown field")
    return violations
