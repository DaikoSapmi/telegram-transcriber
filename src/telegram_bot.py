# src/telegram_bot.py
"""Telegram bot for mottak av lydfiler og sending av transkripsjoner."""
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional

from telegram import Update, Document
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config.settings import settings
from src.transcriber import Transcriber
from src.document_generator import DocumentGenerator

# Sett opp logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class TranscriptionBot:
    """Telegram bot for transkribering."""
    
    def __init__(self):
        self.transcriber: Optional[Transcriber] = None
        self.doc_generator = DocumentGenerator()
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Initialiser transkriber
        try:
            self.transcriber = Transcriber(
                model_name=settings.asr_model,
                device=settings.asr_device
            )
        except Exception as e:
            logger.error(f"Kunne ikke initialisere transkriber: {e}")
            raise
    
    def run(self) -> None:
        """Starter bot-en."""
        settings.validate()
        
        application = Application.builder().token(settings.telegram_bot_token).build()
        
        # Registrer handlers
        application.add_handler(CommandHandler("start", self._cmd_start))
        application.add_handler(CommandHandler("help", self._cmd_help))
        application.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, self._handle_audio))
        application.add_handler(MessageHandler(filters.Document.ALL, self._handle_document))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text))
        
        logger.info("Bot starter...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    
    def _is_authorized(self, update: Update) -> bool:
        """Sjekker om bruker er autorisert."""
        user = update.effective_user
        if not user:
            return False
        
        user_id = str(user.id)
        username = user.username or ""
        
        if not settings.is_user_allowed(user_id, username):
            logger.warning(f"Uautorisert tilgang forsøkt: ID={user_id}, username={username}")
            return False
        
        return True
    
    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Håndterer /start kommando."""
        if not self._is_authorized(update):
            await update.message.reply_text(
                "⛔ Beklager, du har ikke tilgang til denne bot-en.\n"
                "Kontakt administrator hvis du mener dette er en feil."
            )
            return
        
        await update.message.reply_text(
            "🎙️ Velkommen til Transkriberingsbot!\n\n"
            "Send meg en lydfil (m4a, mp3, wav, ogg) så transkriberer jeg den til et Word-dokument.\n\n"
            "Kommandoer:\n"
            "/help - Vis hjelp\n\n"
            "Tips: Skriv 'samisk' hvis filen er på nordsamisk."
        )
    
    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Håndterer /help kommando."""
        await update.message.reply_text(
            "📖 Hjelp\n\n"
            "1. Send meg en lydfil direkte, eller\n"
            "2. Send som dokument (hvis filen er stor)\n\n"
            "Jeg støtter: m4a, mp3, wav, ogg\n\n"
            "Valgfritt:\n"
            "• Skriv 'samisk' for nordsamisk transkribering\n"
            "• Skriv 'med tidsstempel' for tidskoder\n\n"
            "Standard: Norsk (bokmål), uten tidsstempler"
        )
    
    async def _handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Håndterer voice messages og audio."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Ingen tilgang.")
            return
        
        try:
            # Bestem språk fra tidligere meldinger
            language = self._detect_language(context)
            include_timestamps = self._detect_timestamp_request(context)
            
            # Last ned fil
            file_obj = update.message.voice or update.message.audio
            file_name = f"audio_{file_obj.file_id}.ogg"
            
            await update.message.reply_text("⏳ Laster ned fil...")
            file_path = await self._download_file(file_obj, context, suffix=".ogg")
            
            # Transkriber
            await self._process_transcription(
                update, context, file_path, file_name, language, include_timestamps
            )
            
        except Exception as e:
            logger.error(f"Feil ved håndtering av audio: {e}")
            await update.message.reply_text(f"❌ Feil: {str(e)}")
    
    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Håndterer dokument (inkludert lydfiler sendt som doc)."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Ingen tilgang.")
            return
        
        document = update.message.document
        
        # Sjekk at det er en lydfil
        if not self._is_audio_file(document.file_name):
            await update.message.reply_text(
                "⚠️ Dette ser ikke ut som en lydfil.\n"
                "Jeg støtter: m4a, mp3, wav, ogg"
            )
            return
        
        try:
            # Bestem språk
            language = self._detect_language(context)
            include_timestamps = self._detect_timestamp_request(context)
            
            # Last ned
            await update.message.reply_text("⏳ Laster ned fil...")
            file_path = await self._download_file(document, context)
            
            # Transkriber
            await self._process_transcription(
                update, context, file_path, document.file_name, language, include_timestamps
            )
            
        except Exception as e:
            logger.error(f"Feil ved håndtering av dokument: {e}")
            await update.message.reply_text(f"❌ Feil: {str(e)}")
    
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Håndterer tekstmeldinger (språkvalg etc)."""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Ingen tilgang.")
            return
        
        text = update.message.text.lower()
        
        if "samisk" in text or "nordsamisk" in text:
            context.user_data['language'] = 'sme'
            await update.message.reply_text("✅ Språk satt til: Nordsamisk")
        
        elif "norsk" in text or "bokmål" in text:
            context.user_data['language'] = 'no'
            await update.message.reply_text("✅ Språk satt til: Norsk (bokmål)")
        
        elif "tidsstempel" in text or "timestamp" in text:
            context.user_data['include_timestamps'] = True
            await update.message.reply_text("✅ Tidsstempling aktivert")
        
        else:
            await update.message.reply_text(
                "🤔 Forstod ikke helt.\n"
                "Skriv 'samisk' for nordsamisk, eller\n"
                "'med tidsstempel' for tidskoder.\n\n"
                "Eller send meg en lydfil!"
            )
    
    async def _process_transcription(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        file_path: str,
        file_name: str,
        language: str,
        include_timestamps: bool
    ) -> None:
        """Prosesserer transkribering og sender resultat."""
        try:
            logger.info(f"Starter transkribering: {file_name} på språk: {language}")
            
            # Transkriber
            await update.message.reply_text(
                f"🎙️ Transkriberer på {self._get_language_name(language)}...\n"
                "Dette kan ta noen minutter."
            )
            
            segments = self.transcriber.transcribe(
                file_path,
                language=language,
                include_timestamps=include_timestamps
            )
            
            logger.info(f"Transkribering fullført: {len(segments)} segmenter")
            
            # Generer dokument
            await update.message.reply_text("📝 Genererer Word-dokument...")
            
            doc_path = self.doc_generator.generate(
                segments=segments,
                original_filename=file_name,
                language=language,
                include_speakers=settings.include_speaker_detection,
                include_timestamps=include_timestamps
            )
            
            # Send dokument
            await update.message.reply_document(
                document=open(doc_path, 'rb'),
                caption=f"✅ Ferdig!\n"
                        f"Språk: {self._get_language_name(language)}\n"
                        f"Segmenter: {len(segments)}"
            )
            
            # Opprydding
            if settings.delete_temp_files:
                Path(file_path).unlink(missing_ok=True)
                doc_path.unlink(missing_ok=True)
            
            # Reset brukerdata
            context.user_data.clear()
            
        except Exception as e:
            logger.error(f"Feil ved transkribering: {e}")
            await update.message.reply_text(f"❌ Feil under transkribering: {str(e)}")
    
    async def _download_file(self, file_obj, context: ContextTypes.DEFAULT_TYPE, suffix: str = ".tmp") -> str:
        """Laster ned fil fra Telegram."""
        file = await context.bot.get_file(file_obj.file_id)
        
        # Bruk riktig filendelse basert på type
        if hasattr(file_obj, 'mime_type'):
            mime_type = file_obj.mime_type or ""
            logger.info(f"MIME-type: {mime_type}")
            if "ogg" in mime_type:
                suffix = ".ogg"
            elif "mp3" in mime_type:
                suffix = ".mp3"
            elif "mp4" in mime_type:
                suffix = ".m4a"
            elif "wav" in mime_type:
                suffix = ".wav"
        
        file_path = self.temp_dir / f"{file_obj.file_id}{suffix}"
        await file.download_to_drive(file_path)
        
        # Logg filinfo
        import os
        file_size = os.path.getsize(file_path)
        logger.info(f"Fil lastet ned: {file_path} ({file_size} bytes)")
        
        return str(file_path)
    
    def _detect_language(self, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Detekterer ønsket språk."""
        return context.user_data.get('language', settings.default_language)
    
    def _detect_timestamp_request(self, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """Sjekker om bruker vil ha tidsstempler."""
        return context.user_data.get('include_timestamps', settings.include_timestamp)
    
    def _is_audio_file(self, filename: str) -> bool:
        """Sjekker om fil er lydfil."""
        audio_extensions = {'.m4a', '.mp3', '.wav', '.ogg', '.oga', '.opus'}
        return Path(filename).suffix.lower() in audio_extensions
    
    def _get_language_name(self, code: str) -> str:
        """Returnerer lesbart språknavn."""
        mapping = {
            'no': 'Norsk',
            'sme': 'Nordsamisk',
            'en': 'Engelsk',
            'nn': 'Nynorsk'
        }
        return mapping.get(code, code)


def main():
    """Entry point."""
    bot = TranscriptionBot()
    bot.run()


if __name__ == '__main__':
    main()
