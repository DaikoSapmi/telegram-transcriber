#!/usr/bin/env python3
"""
Gemini Client - Korrektur for samisk og norsk tekst.
Bruker Google Gemini API (google.genai) for grammatikk og rettskriving.
"""
import os
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiClient:
    """
    Klient for Google Gemini API.
    Brukes til korrektur av samisk og norsk tekst.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3-flash-preview"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY må settes i .env")
        
        # Importer google.genai (nytt API)
        try:
            from google import genai
            self.genai = genai
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"✅ Gemini initialisert ({model})")
        except ImportError:
            logger.error("❌ google-genai ikke installert")
            raise
    
    def correct_text(self, text: str, language: str = "sme") -> str:
        """
        Korrekturleser tekst.
        
        Args:
            text: Tekst som skal korrekturleses
            language: Språk (sme=nordsamisk, no=norsk)
        
        Returns:
            Korrigert tekst
        """
        try:
            if language == "sme":
                prompt = f"Korrekturles denne nordsamiske teksten. BEHOLD alle ord og innhold nøyaktig som de er. Kun tegnsetting og store/små bokstaver kan rettes. Returner kun den korrigerte teksten:\n\n{text}"
            else:
                prompt = f"Korrekturles denne norske teksten. BEHOLD alle ord og innhold nøyaktig som de er. Kun tegnsetting og store/små bokstaver kan rettes. Returner kun den korrigerte teksten:\n\n{text}"
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            
            if response and response.text:
                return response.text.strip()
            else:
                logger.warning("Tomt svar fra Gemini")
                return text
                
        except Exception as e:
            logger.error(f"Gemini feil: {e}")
            return text


def test_gemini():
    """Test Gemini."""
    import os
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY ikke satt")
        return
    
    client = GeminiClient(api_key)
    
    test = "buorre beaivi mun lean boahtán kárášjohkii"
    print(f"Input: {test}")
    result = client.correct_text(test, "sme")
    print(f"Output: {result}")


if __name__ == "__main__":
    test_gemini()
