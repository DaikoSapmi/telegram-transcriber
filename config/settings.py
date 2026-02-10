# config/settings.py
"""Konfigurasjon for Telegram Transcriber."""
import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Applikasjonsinnstillinger."""
    
    # Telegram Bot
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    
    # ASR (Automatic Speech Recognition)
    asr_model: str = field(default="NbAiLab/nb-whisper-large")
    asr_device: str = field(default="auto")  # auto, cpu, mps, cuda
    default_language: str = field(default="no")  # no = norsk, sme = nordsamisk
    
    # Audio processing
    sample_rate: int = field(default=16000)
    chunk_duration: int = field(default=30)  # seconds per chunk for processing
    
    # Document generation
    include_timestamp: bool = field(default=False)  # Valgfritt
    include_speaker_detection: bool = field(default=True)  # Talegjenkjenning
    document_language: str = field(default="no")  # Alltid norsk i dokumentet
    
    # File handling
    max_file_size_mb: int = field(default=500)  # Ubegrenset praktisk talt
    temp_dir: str = field(default="temp")
    output_dir: str = field(default="output")
    
    # Security
    delete_temp_files: bool = field(default=True)
    
    def validate(self) -> None:
        """Validerer at nødvendige innstillinger er satt."""
        if not self.telegram_bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN må settes i .env filen")
    
    def get_language_name(self, code: str) -> str:
        """Returnerer språknavn fra kode."""
        mapping = {
            "no": "Norsk (bokmål)",
            "nn": "Norsk (nynorsk)",
            "sme": "Nordsamisk",
            "en": "Engelsk"
        }
        return mapping.get(code, code)


# Global settings instance
settings = Settings()
