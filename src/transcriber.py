"""Local, restart-friendly long-form Whisper transcription."""

from __future__ import annotations

import gc
import inspect
import json
import logging
import math
import os
import subprocess
import wave
from collections.abc import Callable
from pathlib import Path

import numpy as np

from config.settings import Settings, settings
from src.transcription_types import TranscriptionResult, TranscriptSegment

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]
CancelCallback = Callable[[], bool]


class TranscriptionCancelled(RuntimeError):
    """Raised at a safe checkpoint when a user has requested cancellation."""


class Transcriber:
    """Sequential long-form Whisper engine that keeps only one model in memory."""

    def __init__(self, config: Settings = settings):
        self.config = config
        self.processor = None
        self.model = None
        self.loaded_model_name: str | None = None
        self.device: str | None = None
        self._forced_device: str | None = None

    def transcribe(
        self,
        audio_path: str | Path,
        language: str,
        work_dir: str | Path,
        progress: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
        glossary: str = "",
    ) -> TranscriptionResult:
        source = Path(audio_path)
        if not source.exists():
            raise FileNotFoundError(f"Lydfil ikke funnet: {source}")
        if language not in {"no", "sme", "auto"}:
            raise ValueError(f"Ugyldig lydspråk: {language}")

        work = Path(work_dir)
        work.mkdir(parents=True, exist_ok=True)
        normalized = work / "normalized.wav"
        report = progress or (lambda _percent, _text: None)
        cancelled = should_cancel or (lambda: False)

        self._checkpoint(cancelled)
        if not self._is_normalized_audio(normalized):
            report(3, "Konverterer lyd til 16 kHz mono")
            self._normalize_audio(source, normalized)
        else:
            report(3, "Bruker eksisterende normalisert lyd")
        duration = self._wav_duration(normalized)
        if duration <= 0:
            raise RuntimeError("Lydfilen har ingen lesbar lyd")

        self._checkpoint(cancelled)
        model_name = self.config.model_for_language(language)
        chunk_seconds = self.config.whisper_segment_seconds
        chunk_count = max(1, math.ceil(duration / chunk_seconds))
        checkpoint_path = work / "checkpoint.json"
        start_index, merged = self._load_checkpoint(
            checkpoint_path,
            source=source,
            language=language,
            model_name=model_name,
            duration=duration,
            chunk_count=chunk_count,
        )
        if start_index:
            report(7, f"Gjenopptar fra del {start_index + 1} av {chunk_count}")
        if start_index < chunk_count:
            report(8, f"Laster modell: {model_name}")
            self._ensure_model(model_name)

        for index in range(start_index, chunk_count):
            self._checkpoint(cancelled)
            core_start = index * chunk_seconds
            core_end = min(duration, (index + 1) * chunk_seconds)
            samples = self._read_wav_range(normalized, core_start, core_end)

            percent = 10 + int(82 * index / chunk_count)
            report(percent, f"Transkriberer del {index + 1} av {chunk_count}")
            # Every segment is intentionally independent. Feeding the previous
            # output back into Whisper caused errors and repetitions to spread
            # through the remainder of long Northern Sámi recordings.
            prompt = self._build_prompt(glossary or self.config.glossary)
            progress_span = max(1.0, 82.0 / chunk_count)

            def monitor(
                ratio: float,
                base_percent: int = percent,
                span: float = progress_span,
                part: int = index + 1,
            ) -> None:
                self._checkpoint(cancelled)
                current = min(91, base_percent + int(span * max(0.0, min(1.0, ratio))))
                report(current, f"Transkriberer del {part} av {chunk_count}")

            window_segments = self._transcribe_window(
                samples,
                language=language,
                offset_seconds=core_start,
                prompt=prompt,
                monitor=monitor,
            )
            merged.extend(window_segments)
            self._write_checkpoint(
                checkpoint_path,
                source=source,
                language=language,
                model_name=model_name,
                duration=duration,
                chunk_count=chunk_count,
                next_index=index + 1,
                segments=merged,
            )

            del samples
            self._release_device_cache()

        self._checkpoint(cancelled)
        report(94, "Slår sammen segmenter")
        return TranscriptionResult(
            segments=merged,
            duration_seconds=duration,
            model_name=model_name,
            language=language,
        )

    def _ensure_model(self, model_name: str) -> None:
        if self.model is not None and self.loaded_model_name == model_name:
            return
        self.unload_model()

        try:
            import torch
            from transformers import AutoProcessor, WhisperForConditionalGeneration
        except ImportError as error:
            raise RuntimeError(
                "Whisper-avhengigheter mangler. Kjør ./setup.sh først."
            ) from error

        device = self._forced_device or self._select_device(torch)
        dtype = torch.float16 if device in {"mps", "cuda"} else torch.float32
        logger.info("Laster %s på %s med %s", model_name, device, dtype)
        try:
            processor = AutoProcessor.from_pretrained(model_name, local_files_only=True)
            model = WhisperForConditionalGeneration.from_pretrained(
                model_name,
                torch_dtype=dtype,
                local_files_only=True,
                use_safetensors=True,
            )
        except OSError as error:
            raise RuntimeError(
                f"Whisper-modellen {model_name} finnes ikke komplett lokalt. "
                "Kjør ./venv/bin/python scripts/download_models.py og prøv igjen."
            ) from error
        try:
            model.to(device)
        except (NotImplementedError, RuntimeError):
            if device != "mps":
                raise
            logger.exception("Kunne ikke flytte modellen til MPS; laster den på CPU")
            del model
            del processor
            gc.collect()
            self._forced_device = "cpu"
            self._ensure_model(model_name)
            return
        model.eval()

        self.processor = processor
        self.model = model
        self.loaded_model_name = model_name
        self.device = device

    def unload_model(self) -> None:
        self.processor = None
        self.model = None
        self.loaded_model_name = None
        self.device = None
        gc.collect()
        self._release_device_cache()

    def _select_device(self, torch_module) -> str:
        requested = self.config.asr_device
        if requested != "auto":
            if requested == "mps" and not torch_module.backends.mps.is_available():
                logger.warning("MPS er ikke tilgjengelig; bruker CPU")
                return "cpu"
            if requested == "cuda" and not torch_module.cuda.is_available():
                logger.warning("CUDA er ikke tilgjengelig; bruker CPU")
                return "cpu"
            return requested
        if torch_module.cuda.is_available():
            return "cuda"
        if torch_module.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _transcribe_window(
        self,
        samples: np.ndarray,
        *,
        language: str,
        offset_seconds: float,
        prompt: str,
        monitor: Callable[[float], None] | None = None,
        allow_mps_fallback: bool = True,
    ) -> list[TranscriptSegment]:
        if self.processor is None or self.model is None or self.device is None:
            raise RuntimeError("Ingen modell er lastet")

        import torch

        try:
            duration = len(samples) / self.config.sample_rate
            is_long_form = duration > 30
            inputs = self.processor(
                samples,
                sampling_rate=self.config.sample_rate,
                return_tensors="pt",
                return_attention_mask=True,
                **self._processor_options(duration),
            )
            feature_frames = int(inputs.input_features.shape[-1])
            max_source_positions = int(
                getattr(self.model.config, "max_source_positions", 1500)
            )
            self._assert_longform_input_coverage(
                duration, feature_frames, max_source_positions
            )
            input_features = inputs.input_features.to(
                self.device, dtype=self.model.dtype
            )
            attention_mask = getattr(inputs, "attention_mask", None)
            if attention_mask is not None:
                attention_mask = attention_mask.to(self.device)

            generation: dict = {
                "input_features": input_features,
                "return_timestamps": True,
                "num_beams": self._num_beams_for_language(language),
                "condition_on_prev_tokens": False,
                "temperature": self.config.temperatures,
                "compression_ratio_threshold": self.config.compression_ratio_threshold,
                "logprob_threshold": self.config.logprob_threshold,
                "no_speech_threshold": self.config.no_speech_threshold,
            }
            if attention_mask is not None:
                generation["attention_mask"] = attention_mask
            generation.update(self._language_generation_options(language))
            if prompt:
                prompt_ids = self.processor.get_prompt_ids(prompt, return_tensors="pt")
                maximum = max(2, int(self.model.config.max_target_positions // 2 - 1))
                if prompt_ids.numel() > maximum:
                    prompt_ids = torch.cat(
                        (prompt_ids[:1], prompt_ids[-(maximum - 1) :])
                    )
                generation["prompt_ids"] = prompt_ids.to(self.device)
                generation["prompt_condition_type"] = "first-segment"

            if is_long_form:
                generation["return_segments"] = True
                if (
                    monitor
                    and "monitor_progress"
                    in inspect.signature(self.model.generate).parameters
                ):
                    generation["monitor_progress"] = lambda values: monitor(
                        self._progress_ratio(values)
                    )

            with torch.inference_mode():
                generated = self.model.generate(**generation)
            decoded = self._decode_generated(generated, offset_seconds, duration)
            self._assert_longform_output_coverage(
                decoded,
                samples,
                offset_seconds=offset_seconds,
                duration=duration,
            )
            return decoded
        except TranscriptionCancelled:
            raise
        except RuntimeError:
            if self.device == "mps" and allow_mps_fallback:
                logger.exception(
                    "MPS feilet; laster samme modell på CPU og prøver delen på nytt"
                )
                model_name = self.loaded_model_name
                self.unload_model()
                self._forced_device = "cpu"
                if not model_name:
                    raise
                self._ensure_model(model_name)
                return self._transcribe_window(
                    samples,
                    language=language,
                    offset_seconds=offset_seconds,
                    prompt=prompt,
                    monitor=monitor,
                    allow_mps_fallback=False,
                )
            raise

    @staticmethod
    def _language_generation_options(language: str) -> dict[str, str]:
        """Preserve the SME fine-tune's decoder IDs instead of forcing a language."""
        if language == "sme":
            # Northern Sámi is not an original Whisper language token. This
            # fine-tune uses its own forced decoder IDs, including a surrogate
            # language token. Passing either language="sme" or a generic task
            # makes Transformers discard those model-specific IDs.
            return {}
        options = {"task": "transcribe"}
        if language == "no":
            options["language"] = "no"
        return options

    def _num_beams_for_language(self, language: str) -> int:
        if language == "sme":
            return self.config.sami_num_beams
        return self.config.num_beams

    @staticmethod
    def _processor_options(duration: float) -> dict[str, str | bool]:
        """Never let the feature extractor cut long recordings to 30 seconds."""
        is_long_form = duration > 30
        return {
            "truncation": not is_long_form,
            "padding": "longest" if is_long_form else "max_length",
        }

    @staticmethod
    def _assert_longform_input_coverage(
        duration: float, feature_frames: int, max_source_positions: int
    ) -> None:
        """Fail instead of silently sending only Whisper's first 30-second window."""
        short_form_frames = max_source_positions * 2
        if duration > 30 and feature_frames <= short_form_frames:
            raise RuntimeError(
                "Lang lyd ble trunkert til Whispers 30-sekundersvindu før "
                "transkribering. Jobben stoppes uten å levere et ufullstendig resultat."
            )

    def _assert_longform_output_coverage(
        self,
        segments: list[TranscriptSegment],
        samples: np.ndarray,
        *,
        offset_seconds: float,
        duration: float,
    ) -> None:
        """Reject an early-stopped transcript when substantial audible audio remains."""
        if duration <= 30:
            return
        relative_end = max(
            (segment.end - offset_seconds for segment in segments), default=0.0
        )
        if relative_end >= duration - 30:
            return
        tail_start = min(duration, max(0.0, relative_end + 5))
        start_sample = int(tail_start * self.config.sample_rate)
        tail = samples[start_sample:]
        frame_size = self.config.sample_rate
        complete_frames = len(tail) // frame_size
        if complete_frames <= 0:
            return
        framed = tail[: complete_frames * frame_size].reshape(
            complete_frames, frame_size
        )
        rms = np.sqrt(np.mean(np.square(framed, dtype=np.float64), axis=1))
        if int(np.count_nonzero(rms >= 0.01)) >= 2:
            raise RuntimeError(
                "Whisper-resultatet stoppet før den hørbare lyden var ferdig. "
                "Jobben stoppes uten å levere en trunkert transkripsjon."
            )

    def _decode_generated(
        self, generated, offset: float, duration: float
    ) -> list[TranscriptSegment]:
        raw_segments = None
        if isinstance(generated, dict):
            raw_segments = generated.get("segments")
        elif hasattr(generated, "segments"):
            raw_segments = generated.segments

        if raw_segments:
            if isinstance(raw_segments[0], list):
                raw_segments = raw_segments[0]
            decoded: list[TranscriptSegment] = []
            for raw in raw_segments:
                text = self.processor.decode(
                    raw["tokens"], skip_special_tokens=True
                ).strip()
                if not text:
                    continue
                decoded.append(
                    TranscriptSegment(
                        text=text,
                        start=offset + self._scalar(raw["start"]),
                        end=offset + self._scalar(raw["end"]),
                    )
                )
            if decoded:
                return decoded

        sequences = (
            generated.get("sequences") if isinstance(generated, dict) else generated
        )
        if hasattr(sequences, "sequences"):
            sequences = sequences.sequences
        sequence = sequences[0] if getattr(sequences, "ndim", 1) > 1 else sequences
        decoded = self.processor.tokenizer.decode(
            sequence,
            skip_special_tokens=True,
            output_offsets=True,
            time_precision=0.02,
        )
        if isinstance(decoded, dict):
            offsets = decoded.get("offsets") or []
            timestamped = []
            for item in offsets:
                timestamps = item.get("timestamp") or (0.0, duration)
                end = timestamps[1] if timestamps[1] is not None else duration
                text = item.get("text", "").strip()
                if text:
                    timestamped.append(
                        TranscriptSegment(
                            text, offset + float(timestamps[0]), offset + float(end)
                        )
                    )
            if timestamped:
                return timestamped
            text = str(decoded.get("text", "")).strip()
        else:
            text = str(decoded).strip()
        return [TranscriptSegment(text, offset, offset + duration)] if text else []

    def _build_prompt(self, glossary: str) -> str:
        if not glossary.strip():
            return ""
        return f"Ord og navn: {glossary.strip()}"[-self.config.prompt_context_chars :]

    def _normalize_audio(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(self.config.sample_rate),
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except FileNotFoundError as error:
            raise RuntimeError(
                "FFmpeg er ikke installert eller finnes ikke i PATH"
            ) from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or str(error)).strip()
            raise RuntimeError(
                f"FFmpeg kunne ikke konvertere lydfilen: {detail}"
            ) from error

    def _is_normalized_audio(self, path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            with wave.open(str(path), "rb") as audio:
                return (
                    audio.getnchannels() == 1
                    and audio.getsampwidth() == 2
                    and audio.getframerate() == self.config.sample_rate
                    and audio.getnframes() > 0
                )
        except (EOFError, OSError, wave.Error):
            return False

    def _load_checkpoint(
        self,
        path: Path,
        *,
        source: Path,
        language: str,
        model_name: str,
        duration: float,
        chunk_count: int,
    ) -> tuple[int, list[TranscriptSegment]]:
        if not path.is_file():
            return 0, []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            stat = source.stat()
            expected = {
                "source_size": stat.st_size,
                "source_mtime_ns": stat.st_mtime_ns,
                "language": language,
                "model_name": model_name,
                "sample_rate": self.config.sample_rate,
                "segmentation_strategy": "independent-fixed-v1",
                "segment_seconds": self.config.whisper_segment_seconds,
                "num_beams": self._num_beams_for_language(language),
                "chunk_count": chunk_count,
            }
            if any(payload.get(key) != value for key, value in expected.items()):
                return 0, []
            if abs(float(payload.get("duration", -1)) - duration) > 0.1:
                return 0, []
            next_index = int(payload["next_index"])
            if not 0 <= next_index <= chunk_count:
                return 0, []
            segments = [TranscriptSegment(**item) for item in payload["segments"]]
            logger.info("Gjenopptar fra kontrollpunkt %s (del %d)", path, next_index)
            return next_index, segments
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
            logger.warning("Ignorerer ugyldig kontrollpunkt: %s", path, exc_info=True)
            return 0, []

    def _write_checkpoint(
        self,
        path: Path,
        *,
        source: Path,
        language: str,
        model_name: str,
        duration: float,
        chunk_count: int,
        next_index: int,
        segments: list[TranscriptSegment],
    ) -> None:
        stat = source.stat()
        payload = {
            "source_size": stat.st_size,
            "source_mtime_ns": stat.st_mtime_ns,
            "language": language,
            "model_name": model_name,
            "sample_rate": self.config.sample_rate,
            "segmentation_strategy": "independent-fixed-v1",
            "segment_seconds": self.config.whisper_segment_seconds,
            "num_beams": self._num_beams_for_language(language),
            "chunk_count": chunk_count,
            "duration": duration,
            "next_index": next_index,
            "segments": [segment.to_dict() for segment in segments],
        }
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, path)

    @staticmethod
    def _wav_duration(path: Path) -> float:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / audio.getframerate()

    def _read_wav_range(self, path: Path, start: float, end: float) -> np.ndarray:
        with wave.open(str(path), "rb") as audio:
            if (
                audio.getnchannels() != 1
                or audio.getframerate() != self.config.sample_rate
            ):
                raise RuntimeError("Normalisert lyd har uventet format")
            start_frame = max(0, int(start * audio.getframerate()))
            frame_count = max(0, int((end - start) * audio.getframerate()))
            audio.setpos(min(start_frame, audio.getnframes()))
            raw = audio.readframes(frame_count)
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    @staticmethod
    def _checkpoint(should_cancel: CancelCallback) -> None:
        if should_cancel():
            raise TranscriptionCancelled("Jobben ble avbrutt av brukeren")

    @staticmethod
    def _progress_ratio(values) -> float:
        try:
            current = float(values[0, 0].item())
            total = float(values[0, 1].item())
            return current / total if total > 0 else 0.0
        except (AttributeError, IndexError, TypeError, ValueError):
            return 0.0

    @staticmethod
    def _scalar(value) -> float:
        return float(value.item()) if hasattr(value, "item") else float(value)

    @staticmethod
    def _release_device_cache() -> None:
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            if hasattr(torch, "mps") and hasattr(torch.mps, "empty_cache"):
                torch.mps.empty_cache()
        except (ImportError, RuntimeError):
            pass
