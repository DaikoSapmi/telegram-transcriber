from pathlib import Path

import numpy as np
import pytest

from config.settings import Settings
from src.transcriber import Transcriber
from src.transcription_types import TranscriptSegment


def test_text_overlap_is_removed_at_chunk_boundary():
    previous = "Dette er slutten på en viktig setning"
    current = "en viktig setning som fortsetter videre"
    assert Transcriber.remove_text_overlap(previous, current) == "som fortsetter videre"


def test_short_or_different_overlap_is_preserved():
    assert (
        Transcriber.remove_text_overlap("ja det", "ja det stemmer") == "ja det stemmer"
    )
    assert Transcriber.remove_text_overlap("første tema", "andre tema") == "andre tema"


def test_near_identical_overlap_is_removed():
    previous = "Vi avslutter denne viktige setningen her"
    current = "denne viktige setning her og fortsetter"
    assert Transcriber.remove_text_overlap(previous, current) == "og fortsetter"


def test_timestamp_midpoint_assigns_overlap_to_one_core():
    segments = [
        TranscriptSegment("before", 8.0, 12.0),
        TranscriptSegment("inside", 11.0, 14.0),
        TranscriptSegment("after", 19.0, 23.0),
    ]
    kept = Transcriber._segments_for_core(segments, 10.0, 20.0, is_last=False)
    assert [segment.text for segment in kept] == ["before", "inside"]


def test_language_generation_options_preserve_sme_model_defaults():
    assert Transcriber._language_generation_options("sme") == {}
    assert Transcriber._language_generation_options("no") == {
        "task": "transcribe",
        "language": "no",
    }
    assert Transcriber._language_generation_options("auto") == {"task": "transcribe"}


def test_longform_processor_explicitly_disables_truncation():
    assert Transcriber._processor_options(474.0) == {
        "truncation": False,
        "padding": "longest",
    }
    assert Transcriber._processor_options(30.0) == {
        "truncation": True,
        "padding": "max_length",
    }


def test_longform_input_guard_rejects_a_30_second_feature_window():
    with pytest.raises(RuntimeError, match="30-sekundersvindu"):
        Transcriber._assert_longform_input_coverage(474.0, 3000, 1500)
    Transcriber._assert_longform_input_coverage(474.0, 47404, 1500)


def test_longform_output_guard_rejects_audible_untranscribed_tail():
    transcriber = Transcriber(Settings(sample_rate=10))
    audible = np.full(1000, 0.02, dtype=np.float32)
    truncated = [TranscriptSegment("Álgu.", 0.0, 20.0)]

    with pytest.raises(RuntimeError, match="trunkert transkripsjon"):
        transcriber._assert_longform_output_coverage(
            truncated,
            audible,
            offset_seconds=0.0,
            duration=100.0,
        )

    transcriber._assert_longform_output_coverage(
        truncated,
        np.zeros_like(audible),
        offset_seconds=0.0,
        duration=100.0,
    )
    transcriber._assert_longform_output_coverage(
        [TranscriptSegment("Olles.", 0.0, 80.0)],
        audible,
        offset_seconds=0.0,
        duration=100.0,
    )


def test_checkpoint_roundtrip_and_source_validation(tmp_path: Path):
    source = tmp_path / "audio.m4a"
    source.write_bytes(b"original")
    checkpoint = tmp_path / "checkpoint.json"
    transcriber = Transcriber(Settings(main_chunk_seconds=60, overlap_seconds=3))
    segments = [TranscriptSegment("Bures.", 0.0, 2.0)]

    transcriber._write_checkpoint(
        checkpoint,
        source=source,
        language="sme",
        model_name="sami-model",
        duration=120.0,
        chunk_count=2,
        next_index=1,
        segments=segments,
    )
    next_index, restored = transcriber._load_checkpoint(
        checkpoint,
        source=source,
        language="sme",
        model_name="sami-model",
        duration=120.0,
        chunk_count=2,
    )
    assert next_index == 1
    assert restored == segments

    source.write_bytes(b"changed source")
    assert transcriber._load_checkpoint(
        checkpoint,
        source=source,
        language="sme",
        model_name="sami-model",
        duration=120.0,
        chunk_count=2,
    ) == (0, [])
