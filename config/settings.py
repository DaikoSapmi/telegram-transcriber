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
    
    # User authorization
    # Kommaseparert liste med godkjente Telegram bruker-ID-er eller brukernavn
    # Eksempel: "123456789,987654321,@brukernavn"
    allowed_users: str = field(default_factory=lambda: os.getenv("ALLOWED_USERS", ""))
    
    # LLM (for møtereferat) - Støtter: openai, anthropic, gemini, kimi, ollama
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "auto"))  # auto = velg første tilgjengelige
    llm_max_tokens: int = field(default=4000)
    
    # OpenAI
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    openai_model: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    
    # Anthropic Claude
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307"))
    
    # Google Gemini
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
    
    # Kimi (Moonshot AI)
    kimi_api_key: str = field(default_factory=lambda: os.getenv("KIMI_API_KEY", ""))
    kimi_model: str = field(default_factory=lambda: os.getenv("KIMI_MODEL", "kimi-k2.5"))
    
    # Ollama (lokal LLM)
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.2"))
    
    def get_allowed_users(self) -> set:
        """Returnerer sett med godkjente brukere."""
        if not self.allowed_users:
            return set()  # Tom = alle tillatt (ikke anbefalt i produksjon)
        
        users = set()
        for user in self.allowed_users.split(","):
            user = user.strip()
            if user:
                users.add(user)
        return users
    
    def is_user_allowed(self, user_id: str, username: str = "") -> bool:
        """Sjekker om bruker er godkjent."""
        allowed = self.get_allowed_users()
        
        # Hvis ingen restriksjoner, tillat alle
        if not allowed:
            return True
        
        # Sjekk bruker-ID
        if str(user_id) in allowed:
            return True
        
        # Sjekk brukernavn
        if username and f"@{username}" in allowed:
            return True
        
        return False
    
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
