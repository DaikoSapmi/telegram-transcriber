"""Telegram front end for the durable local transcription worker."""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import shutil
import time
import uuid
from contextlib import suppress
from pathlib import Path
from typing import ClassVar

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config.settings import Settings, settings
from src.job_processor import JobProcessor
from src.job_queue import JobQueue, TranscriptionJob
from src.transcriber import TranscriptionCancelled

logger = logging.getLogger(__name__)


class TranscriptionBot:
    """Responsive Telegram bot backed by one persistent local worker."""

    AUDIO_EXTENSIONS: ClassVar[frozenset[str]] = frozenset(
        {
            ".aac",
            ".flac",
            ".m4a",
            ".mp3",
            ".mp4",
            ".oga",
            ".ogg",
            ".opus",
            ".wav",
        }
    )

    def __init__(self, config: Settings = settings):
        self.config = config
        self.config.ensure_directories()
        self.queue = JobQueue(config.queue_db)
        self.processor = JobProcessor(self.queue, config)
        self.worker_task: asyncio.Task | None = None
        self.worker_wakeup: asyncio.Event | None = None
        self.stopping = False
        self.last_maintenance = 0.0

    def run(self) -> None:
        self.config.validate()
        application = self.build_application()
        logger.info(
            "Starter Telegram-bot med lokal_mode=%s", self.config.telegram_local_mode
        )
        application.run_polling(allowed_updates=Update.ALL_TYPES)

    def build_application(self) -> Application:
        """Build the application separately so configuration can be tested offline."""
        builder = (
            Application.builder()
            .token(self.config.telegram_bot_token)
            .concurrent_updates(self.config.telegram_concurrent_updates)
            .post_init(self._post_init)
            .post_shutdown(self._post_shutdown)
        )
        if self.config.telegram_local_mode:
            builder = (
                builder.base_url(self.config.telegram_base_url)
                .base_file_url(self.config.telegram_base_file_url)
                .local_mode(True)
            )
        application = builder.build()

        application.add_handler(CommandHandler("start", self._cmd_start))
        application.add_handler(CommandHandler("help", self._cmd_help))
        application.add_handler(CommandHandler("status", self._cmd_status))
        application.add_handler(CommandHandler("cancel", self._cmd_cancel))
        application.add_handler(
            CallbackQueryHandler(self._handle_callback, pattern=r"^(lang|out):")
        )
        application.add_handler(
            MessageHandler(filters.VOICE | filters.AUDIO, self._handle_audio)
        )
        application.add_handler(
            MessageHandler(filters.Document.ALL, self._handle_document)
        )
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_text)
        )
        application.add_error_handler(self._handle_error)
        return application

    async def _post_init(self, application: Application) -> None:
        recovered = self.queue.recover_interrupted()
        if recovered:
            logger.warning("La %d avbrutte jobber tilbake i køen", recovered)
        for job in self.queue.all_jobs():
            if job.status == "cancelled":
                self.processor.cleanup_cancelled(job)
        self.processor.purge_expired()
        self.worker_wakeup = asyncio.Event()
        self.worker_task = asyncio.create_task(
            self._worker_loop(application), name="transcription-worker"
        )

    async def _post_shutdown(self, _application: Application) -> None:
        self.stopping = True
        if self.worker_wakeup:
            self.worker_wakeup.set()
        if self.worker_task:
            self.worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.worker_task
        self.processor.transcriber.unload_model()

    async def _cmd_start(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._authorize_message(update):
            return
        await update.effective_message.reply_text(
            "🎙️ Lokal transkriberingsbot\n\n"
            "Send en lydfil. Du velger deretter talespråk og om resultatet skal være TXT, Word eller begge. "
            "Transkripsjonen kjøres lokalt på Mac-en.\n\n"
            "/status – vis aktive jobber\n"
            "/cancel – avbryt siste aktive jobb\n"
            "/help – vis hjelp"
        )

    async def _cmd_help(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._authorize_message(update):
            return
        local_note = (
            "Lokal Bot API-server er aktivert for filer opptil 2000 MB."
            if self.config.telegram_local_mode
            else "Offisiell Bot API er i bruk; botnedlasting er begrenset av Telegram."
        )
        await update.effective_message.reply_text(
            "Send m4a, mp3, wav, ogg, opus, flac, aac eller mp4.\n\n"
            "Språk:\n"
            "• Norsk – NbAiLab/nb-whisper-large\n"
            "• Nordsamisk – NbAiLab/whisper-large-sme\n"
            "• Automatisk – eksperimentell\n\n"
            "Jobbene kjøres én om gangen og overlever omstart. Bruk /status for fremdrift og "
            "/cancel for å avbryte.\n\n"
            f"{local_note}"
        )

    async def _cmd_status(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._authorize_message(update):
            return
        user = update.effective_user
        jobs = self.queue.active_for_user(user.id)
        if not jobs:
            latest = self.queue.latest_for_user(user.id)
            if not latest:
                await update.effective_message.reply_text("Ingen jobber er registrert.")
                return
            detail = (
                f"\nFeil: {latest.error[:500]}"
                if latest.status == "failed" and latest.error
                else ""
            )
            await update.effective_message.reply_text(
                "Ingen aktive jobber.\n\n"
                f"Siste jobb: {latest.original_filename}\n"
                f"ID: {latest.id} · status: {latest.status}{detail}"
            )
            return
        lines = ["Aktive jobber:"]
        for job in jobs:
            position = self.queue.position(job.id)
            queue_text = f" · køplass {position}" if position else ""
            lines.append(
                f"\n{self._status_icon(job.status)} {job.original_filename}\n"
                f"ID: {job.id} · {job.progress}% · {job.progress_text}{queue_text}"
            )
        await update.effective_message.reply_text("".join(lines))

    async def _cmd_cancel(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._authorize_message(update):
            return
        user = update.effective_user
        job = (
            self.queue.get(context.args[0])
            if context.args
            else self.queue.latest_active_for_user(user.id)
        )
        if not job or job.user_id != user.id:
            await update.effective_message.reply_text(
                "Fant ingen aktiv jobb å avbryte."
            )
            return
        cancelled = self.queue.request_cancel(job.id, user.id)
        if not cancelled:
            await update.effective_message.reply_text("Jobben er allerede avsluttet.")
            return
        if cancelled.status == "cancelled":
            await asyncio.to_thread(self.processor.cleanup_cancelled, cancelled)
            await update.effective_message.reply_text(f"⏹️ Jobb {job.id} er avbrutt.")
        else:
            await update.effective_message.reply_text(
                f"⏹️ Avbryter jobb {job.id} ved neste sikre kontrollpunkt."
            )

    async def _handle_audio(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._authorize_message(update):
            return
        media = update.effective_message.voice or update.effective_message.audio
        original_name = getattr(media, "file_name", None)
        if not original_name:
            extension = (
                ".ogg"
                if update.effective_message.voice
                else self._extension_for_mime(media.mime_type)
            )
            original_name = (
                f"lydopptak_{update.effective_message.date:%Y-%m-%d_%H-%M}{extension}"
            )
        await self._receive_file(update, context, media, original_name)

    async def _handle_document(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._authorize_message(update):
            return
        document = update.effective_message.document
        filename = Path(document.file_name or "lydopptak").name
        if Path(filename).suffix.lower() not in self.AUDIO_EXTENSIONS:
            await update.effective_message.reply_text(
                "Dette ser ikke ut som en støttet lydfil. Jeg støtter m4a, mp3, wav, ogg, opus, flac, aac og mp4."
            )
            return
        await self._receive_file(update, context, document, filename)

    async def _handle_text(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        if not await self._authorize_message(update):
            return
        await update.effective_message.reply_text("Send en lydfil, eller bruk /help.")

    async def _receive_file(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, media, filename: str
    ) -> None:
        size = int(getattr(media, "file_size", 0) or 0)
        maximum = self.config.max_file_size_mb * 1024 * 1024
        if size > maximum:
            await update.effective_message.reply_text(
                f"Filen er større enn grensen på {self.config.max_file_size_mb} MB."
            )
            return

        notice = await update.effective_message.reply_text(
            f"✅ Fil mottatt: {filename}\n📥 Laster ned …"
        )
        extension = Path(filename).suffix.lower() or self._extension_for_mime(
            getattr(media, "mime_type", "")
        )
        destination = Path(self.config.temp_dir) / f"{uuid.uuid4().hex}{extension}"
        try:
            telegram_file = await context.bot.get_file(media.file_id)
            local_source = Path(telegram_file.file_path or "")
            if self.config.telegram_local_mode and local_source.is_file():
                await asyncio.to_thread(shutil.copyfile, local_source, destination)
            else:
                await telegram_file.download_to_drive(custom_path=destination)
            actual_size = destination.stat().st_size
            if actual_size > maximum:
                destination.unlink(missing_ok=True)
                await notice.edit_text(
                    f"Filen er større enn grensen på {self.config.max_file_size_mb} MB."
                )
                return
            job = self.queue.create(
                chat_id=update.effective_chat.id,
                user_id=update.effective_user.id,
                message_id=update.effective_message.message_id,
                telegram_file_id=media.file_id,
                original_filename=Path(filename).name,
                source_path=str(destination),
            )
            await notice.edit_text(
                f"✅ Fil mottatt: {filename}\n\nVelg talespråk:",
                reply_markup=self._language_keyboard(job.id),
            )
        except Exception:
            destination.unlink(missing_ok=True)
            logger.exception("Kunne ikke motta Telegram-fil")
            await notice.edit_text(
                "❌ Kunne ikke laste ned filen. Kontroller lokal Bot API-server og loggen."
            )

    async def _handle_callback(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        if not self._is_private(update) or not self._is_authorized(update):
            await query.edit_message_text("⛔ Ingen tilgang.")
            return
        try:
            action, job_id, value = (query.data or "").split(":", 2)
        except ValueError:
            await query.edit_message_text("Ugyldig valg.")
            return

        if action == "lang":
            job = self.queue.set_language(job_id, update.effective_user.id, value)
            if not job:
                await query.edit_message_text(
                    "Valget er utløpt eller jobben er allerede endret."
                )
                return
            await query.edit_message_text(
                f"✅ Fil mottatt: {job.original_filename}\n"
                f"🗣️ Talespråk: {self.config.get_language_name(value)}\n\n"
                "Velg resultat:",
                reply_markup=self._output_keyboard(job.id),
            )
            return

        job = self.queue.enqueue(job_id, update.effective_user.id, value)
        if not job:
            await query.edit_message_text(
                "Valget er utløpt eller jobben er allerede lagt i kø."
            )
            return
        position = self.queue.position(job.id) or 1
        await query.edit_message_text(
            f"✅ Fil mottatt: {job.original_filename}\n"
            f"🗣️ Talespråk: {self.config.get_language_name(job.language or 'no')}\n"
            f"📄 Resultat: {self._output_name(value)}\n"
            f"📦 Plass i køen: {position}\n\n"
            f"Jobb-ID: {job.id}"
        )
        if self.worker_wakeup:
            self.worker_wakeup.set()

    async def _worker_loop(self, application: Application) -> None:
        while not self.stopping:
            job = self.queue.claim_next()
            if job:
                try:
                    await self._execute_job(application, job)
                except Exception:
                    logger.exception("Køarbeideren feilet utenfor jobbens feilvern")
                    await asyncio.sleep(self.config.worker_poll_seconds)
                continue
            if time.monotonic() - self.last_maintenance >= 3600:
                await asyncio.to_thread(self.processor.purge_expired)
                self.last_maintenance = time.monotonic()
            if not self.worker_wakeup:
                await asyncio.sleep(self.config.worker_poll_seconds)
                continue
            self.worker_wakeup.clear()
            try:
                await asyncio.wait_for(
                    self.worker_wakeup.wait(), timeout=self.config.worker_poll_seconds
                )
            except asyncio.TimeoutError:
                pass

    async def _execute_job(
        self, application: Application, job: TranscriptionJob
    ) -> None:
        progress_message = None
        event_loop = asyncio.get_running_loop()
        last_update = {"time": 0.0, "text": ""}

        def report(percent: int, text: str) -> None:
            self.queue.update_progress(job.id, percent, text)
            now = time.monotonic()
            if progress_message and (
                text != last_update["text"] or now - last_update["time"] >= 20
            ):
                last_update.update(time=now, text=text)
                event_loop.call_soon_threadsafe(
                    asyncio.create_task,
                    self._edit_progress(
                        application,
                        job.id,
                        progress_message.message_id,
                        job.chat_id,
                        percent,
                        text,
                    ),
                )

        try:
            progress_message = await application.bot.send_message(
                job.chat_id,
                f"🔊 Starter transkribering av {job.original_filename} …",
            )
            result_paths = await asyncio.to_thread(self.processor.process, job, report)
            if self.queue.is_cancel_requested(job.id):
                raise TranscriptionCancelled("Jobben ble avbrutt før levering")
            await progress_message.edit_text("📤 Sender resultat …")
            for index, path in enumerate(result_paths):
                caption = (
                    f"✅ Ferdig: {job.original_filename}\n"
                    f"Talespråk: {self.config.get_language_name(job.language or 'no')}"
                    if index == 0
                    else None
                )
                await application.bot.send_document(
                    chat_id=job.chat_id,
                    document=path,
                    filename=path.name,
                    caption=caption,
                )
            self.queue.mark_completed(job.id, (str(path) for path in result_paths))
            try:
                await asyncio.to_thread(
                    self.processor.cleanup_success, job, result_paths
                )
            except Exception:
                logger.exception("Opprydding etter fullført jobb %s feilet", job.id)
            with suppress(TelegramError):
                await progress_message.edit_text("✅ Ferdig")
        except TranscriptionCancelled:
            logger.info("Jobb %s ble avbrutt", job.id)
            self.queue.mark_cancelled(job.id)
            await asyncio.to_thread(self.processor.cleanup_cancelled, job)
            with suppress(TelegramError, AttributeError):
                await progress_message.edit_text("⏹️ Jobben ble avbrutt.")
        except Exception as error:
            logger.exception("Jobb %s feilet", job.id)
            self.queue.mark_failed(job.id, str(error))
            error_text = (
                f"❌ Transkriberingen feilet. Jobb-ID: {job.id}\n"
                "Filer beholdes midlertidig for feilsøking. Se loggen eller bruk /status."
            )
            with suppress(TelegramError):
                if progress_message:
                    await progress_message.edit_text(error_text)
                else:
                    await application.bot.send_message(job.chat_id, error_text)

    async def _edit_progress(
        self,
        application: Application,
        job_id: str,
        message_id: int,
        chat_id: int,
        percent: int,
        text: str,
    ) -> None:
        job = self.queue.get(job_id)
        if not job or job.status != "processing":
            return
        with suppress(TelegramError):
            await application.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"📝 {text} … {percent}%\nJobb-ID: {job_id}",
            )

    async def _authorize_message(self, update: Update) -> bool:
        if not self._is_private(update):
            if update.effective_message:
                await update.effective_message.reply_text(
                    "Jeg fungerer bare i private samtaler."
                )
            return False
        if not self._is_authorized(update):
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⛔ Du har ikke tilgang til denne boten."
                )
            return False
        return True

    @staticmethod
    def _is_private(update: Update) -> bool:
        return bool(update.effective_chat and update.effective_chat.type == "private")

    def _is_authorized(self, update: Update) -> bool:
        user = update.effective_user
        if not user:
            return False
        allowed = self.config.is_user_allowed(str(user.id), user.username or "")
        if not allowed:
            logger.warning(
                "Uautorisert tilgang: id=%s username=%s", user.id, user.username
            )
        return allowed

    @staticmethod
    def _language_keyboard(job_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Norsk", callback_data=f"lang:{job_id}:no")],
                [
                    InlineKeyboardButton(
                        "Nordsamisk", callback_data=f"lang:{job_id}:sme"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Automatisk – eksperimentell",
                        callback_data=f"lang:{job_id}:auto",
                    )
                ],
            ]
        )

    @staticmethod
    def _output_keyboard(job_id: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("TXT", callback_data=f"out:{job_id}:txt"),
                    InlineKeyboardButton("Word", callback_data=f"out:{job_id}:docx"),
                ],
                [InlineKeyboardButton("Begge", callback_data=f"out:{job_id}:both")],
            ]
        )

    @staticmethod
    def _output_name(value: str) -> str:
        return {"txt": "TXT", "docx": "Word", "both": "TXT + Word"}.get(value, value)

    @staticmethod
    def _status_icon(status: str) -> str:
        return {
            "awaiting_language": "❔",
            "awaiting_output": "❔",
            "queued": "📦",
            "processing": "📝",
        }.get(status, "•")

    @staticmethod
    def _extension_for_mime(mime_type: str | None) -> str:
        mime = (mime_type or "").lower()
        if "mpeg" in mime:
            return ".mp3"
        if "mp4" in mime or "m4a" in mime:
            return ".m4a"
        if "wav" in mime:
            return ".wav"
        if "flac" in mime:
            return ".flac"
        return ".ogg"

    async def _handle_error(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        logger.error(
            "Ubehandlet Telegram-feil for update=%r", update, exc_info=context.error
        )


def configure_logging(config: Settings) -> None:
    Path(config.log_dir).mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    file_handler = logging.handlers.RotatingFileHandler(
        Path(config.log_dir) / "telegram-transcriber.log",
        maxBytes=config.log_max_bytes,
        backupCount=config.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        handlers=[file_handler, console_handler],
        force=True,
    )


def main() -> None:
    configure_logging(settings)
    TranscriptionBot(settings).run()


if __name__ == "__main__":
    main()
