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
from src.summarizer import Summarizer

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
        self.summarizer = Summarizer()
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
    
    def _is_private_chat(self, update: Update) -> bool:
        """Sjekker om melding kommer fra privat chat (ikke gruppe)."""
        chat = update.effective_chat
        if chat and chat.type != 'private':
            logger.warning(f"Forsøk på bruk i gruppe: {chat.type}, ID={chat.id}")
            return False
        return True
    
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
        # Sjekk at det er privat chat
        if not self._is_private_chat(update):
            await update.message.reply_text(
                "⛔ Jeg fungerer kun i private chatter, ikke i grupper.\n"
                "Start en privat samtale med meg istedenfor."
            )
            return
        
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
        summary_status = "✅ Tilgjengelig" if self.summarizer.is_available() else "❌ Konfigurer LLM i .env"
        
        await update.message.reply_text(
            "📖 Hjelp\n\n"
            "1️⃣ Send meg en lydfil (m4a, mp3, wav, ogg)\n"
            "2️⃣ Jeg spør om format og språk\n"
            "3️⃣ Motta Word-dokument\n\n"
            "*Format:*\n"
            "1️⃣ Full transkripsjon\n"
            f"2️⃣ Møtereferat ({summary_status})\n\n"
            "*Dokument-språk:*\n"
            "🇳🇴 n = Norsk\n"
            "🇬🇧 e = Engelsk\n\n"
            "*Ekstra:*\n"
            "⏱️ 'tidsstempel' = med tidskoder\n\n"
            "*Eksempel:* 1 n (transkripsjon på norsk)\n"
            "*Eksempel:* 2 e tidsstempel (referat på engelsk)\n\n"
            "*LLM for møtereferat:*\n"
            "Støtter: OpenAI, Anthropic, Gemini, Kimi, Ollama\n"
            "Anbefalt: Ollama (gratis, lokal, privat)\n\n"
            "Tips: Skriv 'samisk' før fil for nordsamisk lyd"
        )
    
    async def _handle_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Håndterer voice messages og audio."""
        if not self._is_private_chat(update):
            return
        
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Ingen tilgang.")
            return
        
        try:
            # Last ned fil
            file_obj = update.message.voice or update.message.audio
            file_name = f"audio_{file_obj.file_id}.ogg"
            
            await update.message.reply_text("⏳ Laster ned fil...")
            file_path = await self._download_file(file_obj, context, suffix=".ogg")
            
            # Lagre filinfo og spør om format
            context.user_data['pending_file'] = file_path
            context.user_data['file_name'] = file_name
            
            await self._ask_format_and_language(update, context)
            
        except Exception as e:
            logger.error(f"Feil ved håndtering av audio: {e}")
            await update.message.reply_text(f"❌ Feil: {str(e)}")
    
    async def _handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Håndterer dokument (inkludert lydfiler sendt som doc)."""
        if not self._is_private_chat(update):
            return  # Ignorer gruppe-meldinger helt
        
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
            # Last ned
            await update.message.reply_text("⏳ Laster ned fil...")
            file_path = await self._download_file(document, context)
            
            # Lagre filinfo og spør om format
            context.user_data['pending_file'] = file_path
            context.user_data['file_name'] = document.file_name
            
            await self._ask_format_and_language(update, context)
            
        except Exception as e:
            logger.error(f"Feil ved håndtering av dokument: {e}")
            await update.message.reply_text(f"❌ Feil: {str(e)}")
    
    async def _ask_format_and_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Spør bruker om ønsket format og språk."""
        summary_available = self.summarizer.is_available()
        
        message = "📋 Hva ønsker du?\n\n"
        message += "*Format:*\n"
        message += "1️⃣ Full transkripsjon (alt som ble sagt)\n"
        
        if summary_available:
            message += "2️⃣ Møtereferat (oppsummering med aksjonspunkter)\n\n"
        else:
            message += "(Møtereferat krever OPENAI_API_KEY i .env)\n\n"
        
        message += "*Dokument-språk:*\n"
        message += "🇳🇴 Norsk (svar 'n')\n"
        message += "🇬🇧 Engelsk (svar 'e')\n\n"
        
        message += "*Ekstra:*\n"
        message += "⏱️ Skriv 'tidsstempel' for tidskoder\n\n"
        
        message += "📌 *Eksempel:* 1 n (full transkripsjon på norsk)\n"
        message += "📌 *Eksempel:* 2 e tidsstempel (referat på engelsk med tidskoder)"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def _handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Håndterer tekstmeldinger (format/språk valg etc)."""
        if not self._is_private_chat(update):
            return
        
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Ingen tilgang.")
            return
        
        text = update.message.text.lower().strip()
        
        # Sjekk om vi venter på format-svar
        if 'pending_file' in context.user_data:
            await self._handle_format_selection(update, context, text)
            return
        
        # Gamle kommandoer (bakoverkompatibilitet)
        if "samisk" in text or "nordsamisk" in text:
            context.user_data['language'] = 'sme'
            await update.message.reply_text("✅ Lydspråk satt til: Nordsamisk")
        
        elif text in ['hjelp', 'help']:
            await self._cmd_help(update, context)
        
        else:
            await update.message.reply_text(
                "🤔 Send meg en lydfil først!\n\n"
                "Jeg støtter: m4a, mp3, wav, ogg\n\n"
                "Skriv /help for mer info."
            )
    
    async def _handle_format_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
        """Håndterer brukerens valg av format og språk."""
        parts = text.split()
        
        # Standard verdier
        output_format = "transcript"  # eller "summary"
        doc_language = "no"  # eller "en"
        include_timestamps = False
        audio_language = context.user_data.get('audio_language', 'no')
        
        # Parse valg
        for part in parts:
            if part == '1':
                output_format = "transcript"
            elif part == '2':
                if self.summarizer.is_available():
                    output_format = "summary"
                else:
                    await update.message.reply_text(
                        "⚠️ Møtereferat krever OPENAI_API_KEY i .env\n"
                        "Jeg lager full transkripsjon istedenfor."
                    )
                    output_format = "transcript"
            elif part == 'n':
                doc_language = "no"
            elif part == 'e':
                doc_language = "en"
            elif part in ['tidsstempel', 'timestamp', 't']:
                include_timestamps = True
        
        # Hent filinfo
        file_path = context.user_data.pop('pending_file', None)
        file_name = context.user_data.pop('file_name', 'unknown')
        
        if not file_path or not os.path.exists(file_path):
            await update.message.reply_text("❌ Filen ble ikke funnet. Send på nytt.")
            return
        
        # Start prosessering
        await self._process_transcription(
            update, context, file_path, file_name, 
            audio_language, doc_language, include_timestamps, output_format
        )
    
    async def _process_transcription(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        file_path: str,
        file_name: str,
        audio_language: str,
        doc_language: str,
        include_timestamps: bool,
        output_format: str = "transcript"
    ) -> None:
        """Prosesserer transkribering/referat og sender resultat."""
        try:
            logger.info(f"Starter: {file_name} | Format: {output_format} | Doc-språk: {doc_language}")
            
            # Transkriber alltid først
            await update.message.reply_text(
                f"🎙️ Transkriberer på {self._get_language_name(audio_language)}...\n"
                "Dette kan ta noen minutter."
            )
            
            segments = self.transcriber.transcribe(
                file_path,
                language=audio_language,
                include_timestamps=include_timestamps
            )
            
            logger.info(f"Transkribering fullført: {len(segments)} segmenter")
            
            if output_format == "summary" and self.summarizer.is_available():
                # Generer møtereferat
                await update.message.reply_text("🤖 Genererer møtereferat med AI...")
                
                # Slå sammen til én tekst
                full_transcript = "\n\n".join([seg[0] for seg in segments])
                
                summary = self.summarizer.generate_meeting_summary(
                    transcript=full_transcript,
                    language=doc_language,
                    meeting_title=f"Møte - {file_name}"
                )
                
                # Generer referat-dokument
                doc_path = self.doc_generator.generate_summary(
                    summary=summary,
                    original_filename=file_name,
                    language=doc_language,
                    transcript_segments=segments if include_timestamps else None
                )
                
                caption = f"✅ Møtereferat ferdig!\n📄 Språk: {'Norsk' if doc_language == 'no' else 'English'}"
                
            else:
                # Generer standard transkripsjon
                await update.message.reply_text("📝 Genererer transkripsjonsdokument...")
                
                doc_path = self.doc_generator.generate(
                    segments=segments,
                    original_filename=file_name,
                    language=doc_language,
                    include_speakers=settings.include_speaker_detection,
                    include_timestamps=include_timestamps
                )
                
                caption = f"✅ Transkripsjon ferdig!\n📝 Språk: {self._get_language_name(audio_language)}\n📄 Dokument: {'Norsk' if doc_language == 'no' else 'English'}"
            
            # Send dokument
            await update.message.reply_document(
                document=open(doc_path, 'rb'),
                caption=caption
            )
            
            # Opprydding
            if settings.delete_temp_files:
                Path(file_path).unlink(missing_ok=True)
                doc_path.unlink(missing_ok=True)
            
            # Reset brukerdata
            context.user_data.clear()
            
        except Exception as e:
            logger.error(f"Feil ved prosessering: {e}")
            await update.message.reply_text(f"❌ Feil: {str(e)}")
    
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
