"""Fetch a model's files once, then use them with no network access."""

import os
from collections.abc import Mapping
from pathlib import Path

from huggingface_hub import hf_hub_download
from loguru import logger

from tiroir.core.embeddings.registry import ModelSpec
from tiroir.core.errors import CoreError

MODELS_ENV = "TIROIR_MODELS"


def is_complete(spec: ModelSpec, directory: Path) -> bool:
    """Whether every file of the model is present in `directory`."""
    return all((directory / name).is_file() for name in spec.files)


def offline_root(env: Mapping[str, str] | None = None) -> Path | None:
    """Return the directory named by `TIROIR_MODELS`, or None when it is unset."""
    value = (os.environ if env is None else env).get(MODELS_ENV)
    return Path(value) if value else None


def offline_model(spec: ModelSpec, root: Path) -> Path:
    """Return the model's directory under `root`, which is never downloaded into.

    Raises `embedding.model-missing` when the directory lacks a file of the model.
    """
    directory = root / spec.model_id
    if not is_complete(spec, directory):
        raise CoreError(
            "embedding.model-missing",
            f"model {spec.model_id} is not complete in {MODELS_ENV}",
        )
    return directory


def download_model(spec: ModelSpec, data_dir: Path) -> Path:
    """Return `<data>/models/<model-id>/`, fetching the model there if needed.

    The model is fetched at its pinned revision on first use and used offline
    once complete. A failed download raises `embedding.download-failed`.
    """
    directory = data_dir / "models" / spec.model_id
    if is_complete(spec, directory):
        return directory
    logger.info("downloading embedding model {}", spec.model_id)
    try:
        for name in spec.files:
            hf_hub_download(
                repo_id=spec.repository,
                filename=name,
                revision=spec.revision,
                local_dir=directory,
            )
    except Exception as error:
        logger.error(
            "embedding model {} download failed: {}",
            spec.model_id,
            type(error).__name__,
        )
        raise CoreError(
            "embedding.download-failed",
            f"could not download model {spec.model_id}",
        ) from error
    return directory
