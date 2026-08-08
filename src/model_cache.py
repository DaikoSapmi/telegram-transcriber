"""Download and validate the minimal local files needed by Whisper models."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from huggingface_hub import snapshot_download
from safetensors import safe_open

MODEL_ALLOW_PATTERNS = (
    "config.json",
    "generation_config.json",
    "preprocessor_config.json",
    "processor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.json",
    "vocabulary.json",
    "merges.txt",
    "normalizer.json",
    "model.safetensors",
    "model.safetensors.index.json",
    "model-*.safetensors",
)


@dataclass(frozen=True, slots=True)
class ModelSnapshot:
    path: Path
    weight_files: tuple[Path, ...]
    weight_bytes: int


def download_model(model_name: str) -> ModelSnapshot:
    """Download only Transformers processor/config and Safetensors weights."""
    snapshot = snapshot_download(
        repo_id=model_name,
        allow_patterns=list(MODEL_ALLOW_PATTERNS),
        max_workers=4,
    )
    return validate_model_snapshot(snapshot, verify_tensor_headers=True)


def cached_model(model_name: str) -> ModelSnapshot:
    """Return a validated local snapshot without making a network request."""
    snapshot = snapshot_download(
        repo_id=model_name,
        allow_patterns=list(MODEL_ALLOW_PATTERNS),
        local_files_only=True,
    )
    return validate_model_snapshot(snapshot)


def model_is_cached(model_name: str) -> bool:
    try:
        cached_model(model_name)
    except (OSError, RuntimeError, ValueError):
        return False
    return True


def validate_model_snapshot(
    snapshot: str | Path, *, verify_tensor_headers: bool = False
) -> ModelSnapshot:
    path = Path(snapshot)
    for filename in ("config.json", "preprocessor_config.json"):
        if not (path / filename).is_file():
            raise RuntimeError(f"Modellfil mangler: {filename}")

    tokenizer_ready = (path / "tokenizer.json").is_file() or all(
        (path / filename).is_file() for filename in ("vocab.json", "merges.txt")
    )
    if not tokenizer_ready:
        raise RuntimeError("Tokeniseringsfiler mangler")

    index_path = path / "model.safetensors.index.json"
    if index_path.is_file():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            filenames = sorted(set(index["weight_map"].values()))
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise RuntimeError("Ugyldig Safetensors-indeks") from error
        weight_files = tuple(path / filename for filename in filenames)
    else:
        weight_files = (path / "model.safetensors",)

    missing = [file.name for file in weight_files if not file.is_file()]
    if missing:
        raise RuntimeError(f"Modellvekter mangler: {', '.join(missing)}")
    if any(file.stat().st_size == 0 for file in weight_files):
        raise RuntimeError("En Safetensors-fil er tom")

    if verify_tensor_headers:
        for file in weight_files:
            try:
                with safe_open(file, framework="np", device="cpu") as tensors:
                    if not list(tensors.keys()):
                        raise RuntimeError(f"Ingen modellvekter i {file.name}")
            except Exception as error:
                if isinstance(error, RuntimeError):
                    raise
                raise RuntimeError(
                    f"Kunne ikke validere Safetensors-filen {file.name}"
                ) from error

    return ModelSnapshot(
        path=path,
        weight_files=weight_files,
        weight_bytes=sum(file.stat().st_size for file in weight_files),
    )


def format_gigabytes(byte_count: int) -> str:
    return f"{byte_count / 1_000_000_000:.2f} GB"
