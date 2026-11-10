import dataclasses

import pytest

from tiroir.core.embeddings.registry import DEFAULT_MODEL, MODELS, ModelSpec, get_model

CANDIDATES = {
    "paraphrase-multilingual-MiniLM-L12-v2",
    "multilingual-e5-small",
    "multilingual-e5-base",
    "multilingual-e5-large",
    "bge-m3",
}
# Licences compatible with Apache-2.0 (ADR-006).
PERMISSIVE = {"Apache-2.0", "MIT"}
# Attributes that may be None until measured or calibrated, or legitimately
# empty (no prefix, no extra file).
OPTIONAL = {
    "resident_mb",
    "default_threshold",
    "query_prefix",
    "passage_prefix",
    "extra_files",
}


def _is_unset(value: object) -> bool:
    """Whether `value` is empty; `False` is a set boolean, not a missing one."""
    return value is None or value == "" or (type(value) is int and value <= 0)


def test_registry_lists_the_five_candidates() -> None:
    # Given
    expected = CANDIDATES

    # When
    listed = set(MODELS)

    # Then
    assert listed == expected


@pytest.mark.parametrize("model_id", sorted(CANDIDATES))
def test_every_attribute_is_set(model_id: str) -> None:
    # Given
    spec = MODELS[model_id]

    # When
    missing = [
        field.name
        for field in dataclasses.fields(ModelSpec)
        if field.name not in OPTIONAL and _is_unset(getattr(spec, field.name))
    ]

    # Then
    assert missing == []
    assert spec.model_id == model_id
    assert len(spec.revision) == 40
    assert spec.licence in PERMISSIVE
    assert spec.pooling in {"mean", "cls"}
    assert spec.files[0] == spec.onnx_file


def test_specs_are_frozen() -> None:
    # Given
    spec = get_model(DEFAULT_MODEL)

    # When / Then
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.dimension = 1  # type: ignore[misc]


def test_default_model_is_registered() -> None:
    # Given
    default = DEFAULT_MODEL

    # When
    spec = get_model(default)

    # Then
    assert spec.model_id == "paraphrase-multilingual-MiniLM-L12-v2"


def test_unknown_model_raises() -> None:
    # Given
    model_id = "nope"

    # When / Then
    with pytest.raises(KeyError):
        get_model(model_id)
