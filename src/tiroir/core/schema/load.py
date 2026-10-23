"""Parsing and validating the text of `tiroir.yaml`."""

from tiroir.core.errors import Violation
from tiroir.core.schema.checker import Checker, failure
from tiroir.core.schema.codes import INVALID, UNSUPPORTED_VERSION
from tiroir.core.schema.drawer_types import check_drawer_types
from tiroir.core.schema.model import Schema
from tiroir.core.schema.store import check_context, check_shared, check_store
from tiroir.core.yaml_io import YamlError, key_line, load_yaml

SUPPORTED_VERSION = 1


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
        raise failure([Violation(INVALID, "", error.message, error.line)]) from error
    c = Checker()
    known = ("tiroir", "store", "shared", "context", "drawer_types")
    if c.mapping(root, "", 1, known, ("tiroir", "store", "drawer_types")) is None:
        raise failure(c.violations)
    version = root.get("tiroir")
    if isinstance(version, int) and not isinstance(version, bool):
        if version > SUPPORTED_VERSION:
            raise failure(
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
    store = check_store(c, root) if "store" in root else None
    shared = check_shared(c, root)
    context = check_context(c, root)
    drawer_types = check_drawer_types(c, root)
    if c.violations or store is None or drawer_types is None:
        raise failure(c.violations)
    return Schema(int(version), store, drawer_types, shared, context)
