# src/summarizer.py
"""LLM-basert oppsummering av transkripsjoner til møtereferat."""
import os
import logging
from typing import Optional, List, Dict

from config.settings import settings
from src.llm_provider import LLMProviderFactory

logger = logging.getLogger(__name__)


class Summarizer:
    """Genererer møtereferat fra transkripsjon ved hjelp av LLM."""
    
    def __init__(self):
        self.max_tokens = settings.llm_max_tokens
        self.preferred_provider = getattr(settings, 'llm_provider', None)
        
        # Velg beste tilgjengelige provider
        self.provider = LLMProviderFactory.get_provider(self.preferred_provider)
        
        if self.provider:
            logger.info(f"Summarizer initialisert med provider: {self.provider.__class__.__name__}")
        else:
            logger.warning("Ingen LLM provider tilgjengelig - møtereferat-funksjon vil ikke fungere")
            logger.info("Tilgjengelige providere: " + ", ".join(LLMProviderFactory.list_available()))
    
    def is_available(self) -> bool:
        """Sjekker om LLM er tilgjengelig."""
        return self.provider is not None
    
    def generate_meeting_summary(
        self, 
        transcript: str,
        language: str = "no",
        meeting_title: str = "Møte",
        duration_minutes: Optional[int] = None
    ) -> Dict[str, str]:
        """
        Genererer møtereferat fra transkripsjon.
        
        Args:
            transcript: Full transkripsjon som tekst
            language: 'no' for norsk, 'en' for engelsk
            meeting_title: Tittel på møtet
            duration_minutes: Varighet i minutter (valgfritt)
            
        Returns:
            Dict med 'summary', 'action_items', 'participants', 'key_decisions'
        """
        if not self.is_available():
            raise ValueError("LLM ikke tilgjengelig - sjekk OPENAI_API_KEY")
        
        logger.info(f"Genererer møtereferat på {language} med {self.provider.__class__.__name__}...")
        
        # Velg prompt basert på språk
        if language == "en":
            system_prompt = self._get_english_prompt()
        else:
            system_prompt = self._get_norwegian_prompt()
        
        # Bygg bruker-prompt
        user_prompt = self._build_user_prompt(transcript, meeting_title, duration_minutes)
        
        try:
            content = self.provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=self.max_tokens
            )
            
            logger.info("Møtereferat generert vellykket")
            
            # Parse svaret
            return self._parse_summary(content)
            
        except Exception as e:
            logger.error(f"Feil ved generering av møtereferat: {e}")
            raise
    
    def _get_norwegian_prompt(self) -> str:
        """Norsk system-prompt."""
        return """Du er en profesjonell møterapportør. Din oppgave er å analysere en møtetranskripsjon og lage et strukturert møtereferat.

Struktur referatet som følger:

## Hovedpunkter
- De viktigste temaene som ble diskutert (3-5 punkter)

## Deltakere
- Liste over personer som snakket (hvis identifiserbare fra teksten)

## Viktige beslutninger
- Konkrete beslutninger som ble tatt

## Aksjonspunkter
- Hva skal gjøres, av hvem, og når (hvis nevnt)

## Oppsummering
- Kort sammendrag av møtet (2-3 setninger)

Vær konsis, profesjonell og objektiv. Bruk punktlister der det passer."""
    
    def _get_english_prompt(self) -> str:
        """English system prompt."""
        return """You are a professional meeting reporter. Your task is to analyze a meeting transcript and create a structured meeting summary.

Structure the summary as follows:

## Key Points
- The main topics discussed (3-5 bullet points)

## Participants
- List of people who spoke (if identifiable from text)

## Important Decisions
- Specific decisions that were made

## Action Items
- What needs to be done, by whom, and when (if mentioned)

## Summary
- Brief overview of the meeting (2-3 sentences)

Be concise, professional, and objective. Use bullet points where appropriate."""
    
    def _build_user_prompt(
        self, 
        transcript: str,
        meeting_title: str,
        duration_minutes: Optional[int]
    ) -> str:
        """Bygger bruker-prompt."""
        duration_info = f"\nVarighet: {duration_minutes} minutter" if duration_minutes else ""
        
        return f"""Lag et møtereferat fra følgende transkripsjon:

Tittel: {meeting_title}{duration_info}

TRANSCRIPSJON:
{transcript[:15000]}  # Begrens til 15k tegn for å spare tokens

Referat:"""
    
    def _parse_summary(self, content: str) -> Dict[str, str]:
        """Parser LLM-svaret til strukturert format."""
        result = {
            "full_text": content,
            "summary": "",
            "action_items": "",
            "participants": "",
            "key_decisions": ""
        }
        
        # Del opp i seksjoner
        lines = content.split('\n')
        current_section = None
        sections = {
            "Hovedpunkter": "summary",
            "Key Points": "summary",
            "Deltakere": "participants",
            "Participants": "participants",
            "Viktige beslutninger": "key_decisions",
            "Important Decisions": "key_decisions",
            "Aksjonspunkter": "action_items",
            "Action Items": "action_items",
            "Oppsummering": "summary",
            "Summary": "summary"
        }
        
        for line in lines:
            # Sjekk om dette er en seksjonsoverskrift
            for header, key in sections.items():
                if header in line and line.strip().startswith('#'):
                    current_section = key
                    continue
            
            # Legg til linjen i riktig seksjon
            if current_section and line.strip():
                result[current_section] += line + '\n'
        
        return result
