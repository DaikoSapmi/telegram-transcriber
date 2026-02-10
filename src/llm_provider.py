# src/llm_provider.py
"""Abstraksjon for ulike LLM-leverandører."""
import os
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstrakt baseklasse for LLM-providere."""
    
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
        """Genererer tekst fra LLM."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Sjekker om provider er tilgjengelig."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self._client = None
        
        if self.api_key:
            try:
                import openai
                openai.api_key = self.api_key
                self._client = openai
                logger.info(f"OpenAI provider initialisert: {self.model}")
            except Exception as e:
                logger.error(f"Kunne ikke initialisere OpenAI: {e}")
    
    def is_available(self) -> bool:
        return self._client is not None
    
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
        if not self._client:
            raise ValueError("OpenAI ikke initialisert")
        
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3
        )
        return response.choices[0].message.content


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-haiku-20240307"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        self._client = None
        
        if self.api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
                logger.info(f"Anthropic provider initialisert: {self.model}")
            except Exception as e:
                logger.error(f"Kunne ikke initialisere Anthropic: {e}")
    
    def is_available(self) -> bool:
        return self._client is not None
    
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
        if not self._client:
            raise ValueError("Anthropic ikke initialisert")
        
        message = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        return message.content[0].text


class GeminiProvider(LLMProvider):
    """Google Gemini provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self._client = None
        
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._client = genai
                self._model = genai.GenerativeModel(self.model)
                logger.info(f"Gemini provider initialisert: {self.model}")
            except Exception as e:
                logger.error(f"Kunne ikke initialisere Gemini: {e}")
    
    def is_available(self) -> bool:
        return self._client is not None
    
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
        if not self._client:
            raise ValueError("Gemini ikke initialisert")
        
        response = self._model.generate_content(
            f"{system_prompt}\n\n{user_prompt}",
            generation_config={"max_output_tokens": max_tokens, "temperature": 0.3}
        )
        return response.text


class KimiProvider(LLMProvider):
    """Moonshot AI Kimi provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "kimi-k2.5"):
        self.api_key = api_key or os.getenv("KIMI_API_KEY")
        self.model = model or os.getenv("KIMI_MODEL", "kimi-k2.5")
        self._client = None
        
        if self.api_key:
            try:
                from openai import OpenAI
                # Kimi bruker OpenAI-kompatibelt API
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url="https://api.moonshot.cn/v1"
                )
                logger.info(f"Kimi provider initialisert: {self.model}")
            except Exception as e:
                logger.error(f"Kunne ikke initialisere Kimi: {e}")
    
    def is_available(self) -> bool:
        return self._client is not None
    
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
        if not self._client:
            raise ValueError("Kimi ikke initialisert")
        
        response = self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.3
        )
        return response.choices[0].message.content


class OllamaProvider(LLMProvider):
    """Ollama (lokal LLM) provider."""
    
    def __init__(self, host: Optional[str] = None, model: str = "llama3.2"):
        self.host = host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2")
        self._available = False
        
        # Sjekk om Ollama kjører
        try:
            import requests
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            if response.status_code == 200:
                self._available = True
                logger.info(f"Ollama provider initialisert: {self.model} @ {self.host}")
            else:
                logger.warning(f"Ollama svarte med status {response.status_code}")
        except Exception as e:
            logger.info(f"Ollama ikke tilgjengelig (ikke installert eller ikke kjørende): {e}")
    
    def is_available(self) -> bool:
        return self._available
    
    def generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
        if not self._available:
            raise ValueError("Ollama ikke tilgjengelig")
        
        import requests
        
        response = requests.post(
            f"{self.host}/api/generate",
            json={
                "model": self.model,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": max_tokens}
            }
        )
        response.raise_for_status()
        return response.json()["response"]


class LLMProviderFactory:
    """Factory for å velge riktig LLM provider."""
    
    PROVIDERS = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "claude": AnthropicProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "kimi": KimiProvider,
        "moonshot": KimiProvider,
        "ollama": OllamaProvider,
    }
    
    @classmethod
    def get_provider(cls, preferred: Optional[str] = None) -> Optional[LLMProvider]:
        """
        Returnerer første tilgjengelige provider.
        
        Args:
            preferred: Foretrukket provider (fra PROVIDERS keys)
        """
        # Sjekk foretrukket først
        if preferred and preferred.lower() in cls.PROVIDERS:
            provider = cls.PROVIDERS[preferred.lower()]()
            if provider.is_available():
                logger.info(f"Bruker foretrukket provider: {preferred}")
                return provider
            else:
                logger.warning(f"Foretrukket provider {preferred} ikke tilgjengelig")
        
        # Prøv alle i prioritert rekkefølge
        priority_order = ["openai", "anthropic", "gemini", "kimi", "ollama"]
        
        for provider_name in priority_order:
            if provider_name in cls.PROVIDERS:
                provider = cls.PROVIDERS[provider_name]()
                if provider.is_available():
                    logger.info(f"Bruker provider: {provider_name}")
                    return provider
        
        logger.warning("Ingen LLM provider tilgjengelig")
        return None
    
    @classmethod
    def list_available(cls) -> list:
        """Returnerer liste over tilgjengelige providere."""
        available = []
        for name, provider_class in cls.PROVIDERS.items():
            provider = provider_class()
            if provider.is_available():
                available.append(name)
        return list(set(available))  # Fjern duplikater
