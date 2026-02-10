# src/transcriber.py
"""Transkribering med NbAiLab Whisper."""
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
import logging

import torch
import numpy as np
from transformers import WhisperProcessor, WhisperForConditionalGeneration

logger = logging.getLogger(__name__)


class Transcriber:
    """Håndterer tale-til-tekst transkribering."""
    
    def __init__(self, model_name: str = "NbAiLab/nb-whisper-large", device: str = "auto"):
        self.model_name = model_name
        self.device = self._get_device(device)
        self.processor: Optional[WhisperProcessor] = None
        self.model: Optional[WhisperForConditionalGeneration] = None
        
        logger.info(f"Initialiserer transkriber med modell: {model_name}")
        self._load_model()
    
    def _get_device(self, device: str) -> str:
        """Velger beste tilgjengelige enhet."""
        if device != "auto":
            return device
        
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    def _load_model(self) -> None:
        """Laster Whisper-modell."""
        try:
            logger.info(f"Laster modell til {self.device}...")
            self.processor = WhisperProcessor.from_pretrained(self.model_name)
            self.model = WhisperForConditionalGeneration.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info("Modell lastet vellykket")
        except Exception as e:
            logger.error(f"Kunne ikke laste modell: {e}")
            raise
    
    def transcribe(
        self, 
        audio_path: str, 
        language: str = "no",
        include_timestamps: bool = False
    ) -> List[Tuple[str, Optional[float]]]:
        """
        Transkriberer lydfil.
        
        Args:
            audio_path: Sti til lydfil
            language: Språkkode (no, sme, en, nn)
            include_timestamps: Om tidsstempler skal inkluderes
            
        Returns:
            Liste med (tekst, timestamp) tupler
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Lydfil ikke funnet: {audio_path}")
        
        logger.info(f"Starter transkribering av {audio_path} på språk: {language}")
        
        # Last audio
        audio = self._load_audio(audio_path)
        
        # Splitt i chunks hvis nødvendig
        chunk_length = 30  # sekunder
        chunks = self._split_audio(audio, chunk_length)
        
        results = []
        current_time = 0.0
        
        for i, chunk in enumerate(chunks):
            logger.debug(f"Prosesserer chunk {i+1}/{len(chunks)}")
            
            text = self._transcribe_chunk(chunk, language)
            
            if include_timestamps:
                results.append((text, current_time))
                current_time += chunk_length
            else:
                results.append((text, None))
        
        logger.info(f"Transkribering fullført. {len(results)} segmenter.")
        return results
    
    def _load_audio(self, audio_path: str) -> np.ndarray:
        """Laster og konverterer audio til riktig format."""
        try:
            from pydub import AudioSegment
            
            # Last audio
            audio = AudioSegment.from_file(audio_path)
            
            # Konverter til mono, 16kHz
            audio = audio.set_channels(1)
            audio = audio.set_frame_rate(16000)
            
            # Konverter til numpy array
            samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            samples = samples / 32768.0  # Normaliser til [-1, 1]
            
            return samples
            
        except Exception as e:
            logger.error(f"Kunne ikke laste audio: {e}")
            raise
    
    def _split_audio(self, audio: np.ndarray, chunk_length_sec: int) -> List[np.ndarray]:
        """Splitter audio i chunks."""
        samples_per_chunk = chunk_length_sec * 16000
        
        if len(audio) <= samples_per_chunk:
            return [audio]
        
        chunks = []
        for i in range(0, len(audio), samples_per_chunk):
            chunk = audio[i:i + samples_per_chunk]
            chunks.append(chunk)
        
        return chunks
    
    def _transcribe_chunk(self, audio_chunk: np.ndarray, language: str) -> str:
        """Transkriberer ett audio chunk."""
        try:
            # Preprocess
            input_features = self.processor(
                audio_chunk, 
                sampling_rate=16000, 
                return_tensors="pt"
            ).input_features.to(self.device)
            
            # Generer
            with torch.no_grad():
                predicted_ids = self.model.generate(
                    input_features,
                    language=language,
                    task="transcribe"
                )
            
            # Dekoder
            text = self.processor.batch_decode(
                predicted_ids, 
                skip_special_tokens=True
            )[0].strip()
            
            return text
            
        except Exception as e:
            logger.error(f"Feil ved transkribering av chunk: {e}")
            return "[Transkriberingsfeil]"
    
    def detect_speakers(self, segments: List[str]) -> List[Tuple[str, str]]:
        """
        Prøver å detektere ulike talere.
        
        Returns:
            Liste med (speaker_id, tekst)
        """
        # Forenklet implementasjon - i praksis ville dette krevd
        # mer avansert analyse eller ekstern tjeneste
        results = []
        current_speaker = "Person 1"
        
        for i, segment in enumerate(segments):
            # Bytt taler hver 3. segment (forenklet logikk)
            if i > 0 and i % 3 == 0:
                current_speaker = f"Person {(i // 3) + 1}"
            
            results.append((current_speaker, segment))
        
        return results
