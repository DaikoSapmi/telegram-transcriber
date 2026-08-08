import shutil
import wave
from array import array
from pathlib import Path

import pytest

from config.settings import Settings
from src.transcriber import Transcriber
from src.transcription_types import TranscriptSegment


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="FFmpeg is not installed")
def test_ffmpeg_normalizes_to_mono_16khz_pcm(tmp_path: Path):
    source = tmp_path / "source.wav"
    destination = tmp_path / "normalized.wav"
    frames = array("h")
    for index in range(8000):
        value = 1000 if index % 2 else -1000
        frames.extend((value, value))
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(8000)
        audio.writeframes(frames.tobytes())

    transcriber = Transcriber(Settings())
    transcriber._normalize_audio(source, destination)
    samples = transcriber._read_wav_range(destination, 0.0, 1.0)

    with wave.open(str(destination), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == 16000
        assert audio.getsampwidth() == 2
    assert 15_990 <= len(samples) <= 16_000
    assert 0.99 <= transcriber._wav_duration(destination) <= 1.01


def test_completed_checkpoint_finishes_without_loading_a_model(tmp_path: Path):
    source = tmp_path / "source.wav"
    work = tmp_path / "work"
    work.mkdir()
    frames = array("h", [0] * 16_000)
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(frames.tobytes())
    shutil.copyfile(source, work / "normalized.wav")

    config = Settings(whisper_segment_seconds=10)
    transcriber = Transcriber(config)
    transcriber._write_checkpoint(
        work / "checkpoint.json",
        source=source,
        language="no",
        model_name=config.norwegian_model,
        duration=1.0,
        chunk_count=1,
        next_index=1,
        segments=[TranscriptSegment("Ferdig del.", 0.0, 1.0)],
    )

    result = transcriber.transcribe(source, "no", work)
    assert result.text == "Ferdig del."
    assert transcriber.model is None


def test_long_recording_is_transcribed_as_independent_short_segments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = tmp_path / "source.wav"
    work = tmp_path / "work"
    work.mkdir()
    frames = array("h", [1000] * (25 * 16_000))
    with wave.open(str(source), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16_000)
        audio.writeframes(frames.tobytes())
    shutil.copyfile(source, work / "normalized.wav")

    config = Settings(whisper_segment_seconds=10, sami_num_beams=1)
    transcriber = Transcriber(config)
    calls = []
    monkeypatch.setattr(transcriber, "_ensure_model", lambda _model_name: None)

    def fake_transcribe_window(
        samples,
        *,
        language,
        offset_seconds,
        prompt,
        monitor=None,
        allow_mps_fallback=True,
    ):
        calls.append((len(samples), language, offset_seconds, prompt))
        duration = len(samples) / config.sample_rate
        return [
            TranscriptSegment(
                f"Del {len(calls)}.", offset_seconds, offset_seconds + duration
            )
        ]

    monkeypatch.setattr(transcriber, "_transcribe_window", fake_transcribe_window)
    result = transcriber.transcribe(source, "sme", work, glossary="Kárášjohka")

    assert [call[0] for call in calls] == [160_000, 160_000, 80_000]
    assert [call[2] for call in calls] == [0, 10, 20]
    assert {call[3] for call in calls} == {"Ord og navn: Kárášjohka"}
    assert result.text == "Del 1.\n\nDel 2.\n\nDel 3."
