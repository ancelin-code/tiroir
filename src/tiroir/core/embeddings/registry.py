"""The models tiroir supports for embedding, with what is needed to run each.

The candidates are the ones ADR-006 evaluates. Every revision is a pinned
commit of the source repository, so a download is reproducible.
"""

from dataclasses import dataclass
from typing import Literal

Pooling = Literal["mean", "cls"]


@dataclass(frozen=True)
class ModelSpec:
    """One supported model and the attributes ADR-006 requires of it."""

    model_id: str
    repository: str
    revision: str
    onnx_file: str
    tokenizer_file: str
    extra_files: tuple[str, ...]
    dimension: int
    licence: str
    max_tokens: int
    pooling: Pooling
    normalize: bool
    query_prefix: str
    passage_prefix: str
    resident_mb: int | None
    default_threshold: float | None

    @property
    def files(self) -> tuple[str, ...]:
        """Every repository file the model needs, the ONNX graph first."""
        return (self.onnx_file, *self.extra_files, self.tokenizer_file)


_E5_PREFIXES = {"query_prefix": "query: ", "passage_prefix": "passage: "}

# `resident_mb` is None until measured (eval-003); so is `default_threshold`
# until calibrated. The MiniLM figure is ADR-006's first probe.
MODELS: dict[str, ModelSpec] = {
    spec.model_id: spec
    for spec in (
        ModelSpec(
            model_id="paraphrase-multilingual-MiniLM-L12-v2",
            repository="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            revision="e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
            onnx_file="onnx/model.onnx",
            tokenizer_file="tokenizer.json",
            extra_files=(),
            dimension=384,
            licence="Apache-2.0",
            max_tokens=128,
            pooling="mean",
            normalize=True,
            query_prefix="",
            passage_prefix="",
            resident_mb=670,
            default_threshold=None,
        ),
        ModelSpec(
            model_id="multilingual-e5-small",
            repository="intfloat/multilingual-e5-small",
            revision="614241f622f53c4eeff9890bdc4f31cfecc418b3",
            onnx_file="onnx/model.onnx",
            tokenizer_file="tokenizer.json",
            extra_files=(),
            dimension=384,
            licence="MIT",
            max_tokens=512,
            pooling="mean",
            normalize=True,
            resident_mb=None,
            default_threshold=None,
            **_E5_PREFIXES,
        ),
        ModelSpec(
            model_id="multilingual-e5-base",
            repository="intfloat/multilingual-e5-base",
            revision="d128750597153bb5987e10b1c3493a34e5a4502a",
            onnx_file="onnx/model.onnx",
            tokenizer_file="tokenizer.json",
            extra_files=(),
            dimension=768,
            licence="MIT",
            max_tokens=512,
            pooling="mean",
            normalize=True,
            resident_mb=None,
            default_threshold=None,
            **_E5_PREFIXES,
        ),
        ModelSpec(
            model_id="multilingual-e5-large",
            repository="intfloat/multilingual-e5-large",
            revision="3d7cfbdacd47fdda877c5cd8a79fbcc4f2a574f3",
            onnx_file="onnx/model.onnx",
            tokenizer_file="tokenizer.json",
            extra_files=("onnx/model.onnx_data",),
            dimension=1024,
            licence="MIT",
            max_tokens=512,
            pooling="mean",
            normalize=True,
            resident_mb=None,
            default_threshold=None,
            **_E5_PREFIXES,
        ),
        ModelSpec(
            model_id="bge-m3",
            repository="Xenova/bge-m3",
            revision="4de13258303883538bd53b696b452bf8099f0858",
            onnx_file="onnx/model.onnx",
            tokenizer_file="tokenizer.json",
            extra_files=("onnx/model.onnx_data",),
            dimension=1024,
            licence="MIT",
            max_tokens=8192,
            pooling="cls",
            normalize=True,
            query_prefix="",
            passage_prefix="",
            resident_mb=None,
            default_threshold=None,
        ),
    )
}

# Provisional: the evaluation in `eval-003` replaces it.
DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def get_model(model_id: str) -> ModelSpec:
    """Return the spec of `model_id`; raise `KeyError` if it is not supported."""
    return MODELS[model_id]
