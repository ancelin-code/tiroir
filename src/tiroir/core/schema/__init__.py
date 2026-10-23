"""The store schema (`tiroir.yaml`): loading, validation and canonical writing.

The shape, defaults and error codes are fixed by the schema contract
(`delivery/contracts/schema.md`). Loading reports every violation it finds,
not only the first. Optional keys are kept as written (`None` when absent);
the defaults the contract names are exposed as properties.

Checking that a template holds exactly the headings of `summary.sections`
needs the template file, so it belongs to the code that reads the store.
"""

from tiroir.core.schema.codes import (
    INVALID,
    INVALID_DETECT,
    INVALID_PATH,
    METADATA_INVALID,
    UNKNOWN_SECTION,
    UNSUPPORTED_VERSION,
)
from tiroir.core.schema.dump import dump_schema
from tiroir.core.schema.load import SUPPORTED_VERSION, load_schema
from tiroir.core.schema.metadata import validate_metadata
from tiroir.core.schema.model import (
    Audience,
    Context,
    Detect,
    DrawerType,
    Field,
    FieldType,
    FieldValue,
    Inject,
    Log,
    Schema,
    Shared,
    Store,
    Summary,
)

__all__ = [
    "INVALID",
    "INVALID_DETECT",
    "INVALID_PATH",
    "METADATA_INVALID",
    "SUPPORTED_VERSION",
    "UNKNOWN_SECTION",
    "UNSUPPORTED_VERSION",
    "Audience",
    "Context",
    "Detect",
    "DrawerType",
    "Field",
    "FieldType",
    "FieldValue",
    "Inject",
    "Log",
    "Schema",
    "Shared",
    "Store",
    "Summary",
    "dump_schema",
    "load_schema",
    "validate_metadata",
]
