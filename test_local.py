#!/usr/bin/env python3
"""
test_local.py - Test transkribering uten Telegram
Brukes for å verifisere at alt fungerer før du kobler til Telegram.
"""
import os
import sys
import tempfile
from pathlib import Path

# Legg til src i path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from src.transcriber import Transcriber
from src.document_generator import DocumentGenerator


def create_test_audio():
    """Oppretter en test-lydfil (hvis ingen finnes)."""
    print("📝 Oppretter test-lydfil...")
    
    try:
        from pydub import AudioSegment
        import numpy as np
        
        # Generer 5 sekunder med test-lyd (sinusbølge)
        sample_rate = 16000
        duration = 5
        frequency = 440  # A4 tone
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        audio_data = (np.sin(2 * np.pi * frequency * t) * 32767).astype(np.int16)
        
        # Konverter til AudioSegment
        audio = AudioSegment(
            audio_data.tobytes(),
            frame_rate=sample_rate,
            sample_width=2,
            channels=1
        )
        
        # Lagre
        test_file = Path("temp/test_audio.wav")
        test_file.parent.mkdir(exist_ok=True)
        audio.export(test_file, format="wav")
        
        print(f"✅ Test-lydfil opprettet: {test_file}")
        return str(test_file)
        
    except ImportError:
        print("❌ pydub ikke installert ennå")
        print("   Kjør først: ./setup.sh")
        return None
    except Exception as e:
        print(f"❌ Feil ved oppretting av test-lyd: {e}")
        return None


def test_transcription():
    """Tester transkribering."""
    print("\n🎙️  Tester transkribering...")
    print("=" * 50)
    
    # Sjekk om test-fil finnes
    test_file = "temp/test_audio.wav"
    if not os.path.exists(test_file):
        test_file = create_test_audio()
        if not test_file:
            print("\n⚠️  Kunne ikke opprette test-lyd")
            print("    Du kan teste med en ekte lydfil i stedet:")
            print("    1. Legg en .wav, .mp3 eller .m4a fil i temp/ mappen")
            print("    2. Kjør denne testen på nytt")
            return False
    
    try:
        # Initialiser transkriber
        print("\n📥 Laster Whisper-modell...")
        print("   (Dette kan ta flere minutter første gang)")
        transcriber = Transcriber(
            model_name=settings.asr_model,
            device=settings.asr_device
        )
        print("✅ Modell lastet!")
        
        # Test norsk
        print("\n🇳🇴 Tester norsk transkribering...")
        segments = transcriber.transcribe(test_file, language="no", include_timestamps=False)
        print(f"✅ Transkribert {len(segments)} segment(er)")
        if segments:
            print(f"   Tekst: {segments[0][0][:100]}...")
        
        # Generer dokument
        print("\n📝 Genererer Word-dokument...")
        doc_gen = DocumentGenerator()
        doc_path = doc_gen.generate(
            segments=segments,
            original_filename="test_audio.wav",
            language="no",
            duration_seconds=5.0,
            include_speakers=True,
            include_timestamps=False
        )
        print(f"✅ Dokument generert: {doc_path}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Feil under testing: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """Tester konfigurasjon."""
    print("\n⚙️  Sjekker konfigurasjon...")
    print("=" * 50)
    
    # Sjekk om .env finnes
    if not os.path.exists(".env"):
        print("❌ .env fil ikke funnet")
        print("   Kjør: cp .env.example .env")
        print("   Rediger med dine innstillinger")
        return False
    
    print("✅ .env fil funnet")
    
    # Sjekk om token er satt
    if settings.telegram_bot_token and "your_bot_token" not in settings.telegram_bot_token:
        print("✅ TELEGRAM_BOT_TOKEN satt")
    else:
        print("⚠️  TELEGRAM_BOT_TOKEN ikke satt ennå")
        print("   Hent fra @BotFather når du er klar")
    
    # Vis innstillinger
    print(f"\n📋 Nåværende innstillinger:")
    print(f"   Modell: {settings.asr_model}")
    print(f"   Enhet: {settings.asr_device}")
    print(f"   Standardspråk: {settings.default_language}")
    print(f"   Godkjente brukere: {settings.allowed_users or '(alle - IKKE anbefalt)'}")
    
    return True


def main():
    """Hovedfunksjon."""
    print("🧪 Telegram Transcriber - Lokal Test")
    print("=" * 50)
    print()
    print("Denne testen sjekker:")
    print("  1. Konfigurasjon")
    print("  2. Whisper-modell (nedlasting + lasting)")
    print("  3. Transkribering")
    print("  4. Word-dokument generering")
    print()
    
    # Test 1: Konfigurasjon
    if not test_config():
        print("\n❌ Konfigurasjonstest feilet")
        sys.exit(1)
    
    # Spør om bruker vil fortsette
    print()
    response = input("Vil du teste transkribering? (krever nedlasting av Whisper, 3-5GB) [j/N]: ")
    if response.lower() not in ['j', 'ja', 'y', 'yes']:
        print("\n👍 Konfigurasjon OK! Klar til å kjøre med Telegram.")
        print("   Når du er klar, kjør: ./start.sh")
        return
    
    # Test 2: Transkribering
    if test_transcription():
        print("\n" + "=" * 50)
        print("🎉 All testing vellykket!")
        print("=" * 50)
        print("\nDu er klar til å koble til Telegram:")
        print("  1. Hent bot token fra @BotFather")
        print("  2. Legg det inn i .env filen")
        print("  3. Kjør: ./start.sh")
    else:
        print("\n❌ Transkriberingstest feilet")
        print("   Sjekk feilmeldinger over")
        sys.exit(1)


if __name__ == "__main__":
    main()
