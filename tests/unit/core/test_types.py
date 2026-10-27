import json
from datetime import date

import pytest

from tiroir.core import Access, CoreError, DrawerRef, StoreInfo, to_json
from tiroir.core.types import Audience


def test_drawer_ref_parses_and_prints_store_colon_drawer() -> None:
    # Given
    text = "cabinet:clients/c042"

    # When
    ref = DrawerRef.parse(text)

    # Then
    assert (ref.store, ref.drawer) == ("cabinet", "clients/c042")
    assert str(ref) == text


@pytest.mark.parametrize("text", ["", "cabinet", ":clients/c1", "cabinet:"])
def test_drawer_ref_refuses_anything_else(text: str) -> None:
    # Given
    candidate = text

    # When
    with pytest.raises(CoreError) as raised:
        DrawerRef.parse(candidate)

    # Then
    assert raised.value.code == "params.invalid"


def test_to_json_writes_enums_by_value_and_nested_types() -> None:
    # Given
    info = StoreInfo("id", "cabinet", Audience.TEAM, "fr", Access.READ, False)

    # When
    data = json.loads(to_json({"stores": (info,), "day": date(2026, 1, 2)}))

    # Then
    assert data == {
        "stores": [
            {
                "id": "id",
                "name": "cabinet",
                "audience": "team",
                "language": "fr",
                "access": "read",
                "is_default": False,
            }
        ],
        "day": "2026-01-02",
    }
