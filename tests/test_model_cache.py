import json
from pathlib import Path

import numpy as np
import pytest
from safetensors.numpy import save_file

from src.model_cache import format_gigabytes, validate_model_snapshot


def _write_processor_files(path: Path) -> None:
    (path / "config.json").write_text("{}", encoding="utf-8")
    (path / "preprocessor_config.json").write_text("{}", encoding="utf-8")
    (path / "tokenizer.json").write_text("{}", encoding="utf-8")


def test_validates_single_safetensors_model(tmp_path: Path):
    _write_processor_files(tmp_path)
    save_file(
        {"weight": np.array([1.0], dtype=np.float32)},
        tmp_path / "model.safetensors",
    )

    snapshot = validate_model_snapshot(tmp_path, verify_tensor_headers=True)

    assert [file.name for file in snapshot.weight_files] == ["model.safetensors"]
    assert snapshot.weight_bytes > 0


def test_validates_sharded_safetensors_model(tmp_path: Path):
    _write_processor_files(tmp_path)
    save_file(
        {"first": np.array([1.0], dtype=np.float32)},
        tmp_path / "model-00001-of-00002.safetensors",
    )
    save_file(
        {"second": np.array([2.0], dtype=np.float32)},
        tmp_path / "model-00002-of-00002.safetensors",
    )
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps(
            {
                "weight_map": {
                    "first": "model-00001-of-00002.safetensors",
                    "second": "model-00002-of-00002.safetensors",
                }
            }
        ),
        encoding="utf-8",
    )

    snapshot = validate_model_snapshot(tmp_path, verify_tensor_headers=True)

    assert len(snapshot.weight_files) == 2
    assert snapshot.weight_bytes == sum(
        file.stat().st_size for file in snapshot.weight_files
    )


def test_rejects_missing_safetensors_shard(tmp_path: Path):
    _write_processor_files(tmp_path)
    (tmp_path / "model.safetensors.index.json").write_text(
        json.dumps({"weight_map": {"first": "missing.safetensors"}}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="Modellvekter mangler"):
        validate_model_snapshot(tmp_path)


def test_formats_decimal_model_size():
    assert format_gigabytes(6_170_000_000) == "6.17 GB"
