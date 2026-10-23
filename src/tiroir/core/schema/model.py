"""The schema as typed, immutable values."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Literal

Audience = Literal["personal", "team"]
FieldType = Literal["text", "number", "date", "boolean", "enum", "list"]
FieldValue = str | int | float | bool | date | tuple[str, ...]


@dataclass(frozen=True)
class Store:
    """The identity of the store."""

    id: str
    name: str
    audience: Audience
    language: str
    description: str | None = None


@dataclass(frozen=True)
class Shared:
    """Where the shared notes and conventions live."""

    path: str | None = None
    topics: tuple[str, ...] | None = None
    conventions: str | None = None


@dataclass(frozen=True)
class Context:
    """Limits on the context given to agents."""

    conventions_max_tokens: int | None = None


@dataclass(frozen=True)
class Field:
    """A metadata field a drawer type declares."""

    type: FieldType
    required: bool | None = None
    values: tuple[str, ...] | None = None
    pattern: str | None = None
    default: FieldValue | None = None
    description: str | None = None

    @property
    def is_required(self) -> bool:
        """Whether the field must be given (absent means optional)."""
        return bool(self.required)


@dataclass(frozen=True)
class Summary:
    """The summary template of a drawer type and the headings it holds."""

    template: str
    sections: tuple[str, ...]


@dataclass(frozen=True)
class Log:
    """The log settings of a drawer type."""

    template: str | None = None


@dataclass(frozen=True)
class Detect:
    """How a drawer is recognised from the agent's working context."""

    names: tuple[str, ...] | None = None
    cwd: str | None = None


@dataclass(frozen=True)
class Inject:
    """What is injected into the context once a drawer is detected."""

    sections: tuple[str, ...] | None = None
    max_tokens: int | None = None


@dataclass(frozen=True)
class DrawerType:
    """A kind of drawer: its folder pattern, fields and summary."""

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
        """The token budget of the injection, 800 unless declared."""
        if self.inject is not None and self.inject.max_tokens is not None:
            return self.inject.max_tokens
        return 800


@dataclass(frozen=True)
class Schema:
    """A validated `tiroir.yaml`."""

    tiroir: int
    store: Store
    drawer_types: Mapping[str, DrawerType]
    shared: Shared | None = None
    context: Context | None = None

    @property
    def shared_path(self) -> str:
        """The folder of the shared notes, `shared` unless declared."""
        if self.shared is not None and self.shared.path is not None:
            return self.shared.path
        return "shared"

    @property
    def conventions_max_tokens(self) -> int:
        """The token budget of the conventions, 1500 unless declared."""
        if self.context is not None and self.context.conventions_max_tokens is not None:
            return self.context.conventions_max_tokens
        return 1500
