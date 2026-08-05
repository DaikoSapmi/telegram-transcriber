"""Shared types for transcription and result generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class TranscriptSegment:
    text: str
    start: float
    end: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class TranscriptionResult:
    segments: list[TranscriptSegment]
    duration_seconds: float
    model_name: str
    language: str

    @property
    def text(self) -> str:
        return "\n\n".join(
            segment.text.strip() for segment in self.segments if segment.text.strip()
        )
