import numpy as np

from tiroir.core.embeddings.local import l2_normalize, pool, with_prefix
from tiroir.core.embeddings.registry import MODELS


def test_mean_pool_ignores_padding() -> None:
    # Given
    hidden = np.array([[[1, 2], [3, 4], [100, 100]]], dtype=np.float32)
    mask = np.array([[1, 1, 0]], dtype=np.int64)

    # When
    pooled = pool(hidden, mask, "mean")

    # Then
    assert pooled.dtype == np.float32
    assert pooled.tolist() == [[2.0, 3.0]]


def test_cls_pool_takes_the_first_token() -> None:
    # Given
    hidden = np.array([[[1, 2], [3, 4]]], dtype=np.float32)
    mask = np.array([[1, 1]], dtype=np.int64)

    # When
    pooled = pool(hidden, mask, "cls")

    # Then
    assert pooled.tolist() == [[1.0, 2.0]]


def test_l2_normalize_gives_unit_rows_and_keeps_zero() -> None:
    # Given
    vectors = np.array([[3, 4], [0, 0]], dtype=np.float32)

    # When
    out = l2_normalize(vectors)

    # Then
    assert out.dtype == np.float32
    assert out[0].tolist() == [0.6000000238418579, 0.800000011920929]
    assert out[1].tolist() == [0.0, 0.0]


def test_prefixes_follow_the_spec() -> None:
    # Given
    e5 = MODELS["multilingual-e5-small"]
    minilm = MODELS["paraphrase-multilingual-MiniLM-L12-v2"]

    # When
    query = with_prefix(e5.query_prefix, ["TVA"])
    passage = with_prefix(e5.passage_prefix, ["TVA"])
    plain = with_prefix(minilm.query_prefix, ["TVA"])

    # Then
    assert query == ["query: TVA"]
    assert passage == ["passage: TVA"]
    assert plain == ["TVA"]
