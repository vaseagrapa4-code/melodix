"""
Application entry point.

Run with:  python -m bot.main   (from the project root)

This wires everything together:
  * loads config from .env
  * sets up logging
  * initializes the database, translator and music service
  * injects those shared objects into every handler
  * starts long-polling
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from bot.config import load_config
from bot.handlers import get_main_router
from bot.services.music_service import MusicService
from bot.utils.database import create_database
from bot.utils.i18n import Translator
from bot.utils.keepalive import start_keepalive

logger = logging.getLogger(__name__)


def setup_logging(level: str) -> None:
    """Configure root logging once at startup."""
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # yt-dlp is very chatty; keep it quiet unless we are debugging.
    logging.getLogger("yt_dlp").setLevel(logging.WARNING)


async def set_bot_commands(bot: Bot) -> None:
    """Register the command list shown in Telegram's menu."""
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Start / выбрать язык"),
            BotCommand(command="language", description="Change language / сменить язык"),
            BotCommand(command="cut", description="Trim audio / обрезать аудио"),
            BotCommand(command="playlist", description="Playlists / плейлисты"),
            BotCommand(command="top", description="Leaderboards / рейтинги"),
            BotCommand(command="help", description="Help / помощь"),
            BotCommand(command="cancel", description="Cancel / отмена"),
        ]
    )


async def set_bot_profile(bot: Bot) -> None:
    """
    Set the bot's display name and descriptions via the Bot API.

    - name: shown at the top of the chat and in search.
    - description: the "What can this bot do?" text on the start screen.
    - short_description: shown on the bot's profile page.

    NOTE: the profile PICTURE (icon) cannot be set through the Bot API — it
    must be uploaded once in @BotFather (see TUTORIAL). These calls are
    best-effort: Telegram rate-limits name changes, so we ignore failures.
    """
    name = "Melodix — Music Finder"
    description = (
        "Find and download any song by title, artist or a line of lyrics. "
        "See lyrics, discover more from the artist, trim tracks, build "
        "shareable playlists and climb the leaderboards. Multi-language. "
        "Send /start to begin."
    )
    short_description = "Download music, see lyrics, trim audio, share playlists."
    for setter, value in (
        (bot.set_my_name, name),
        (bot.set_my_description, description),
        (bot.set_my_short_description, short_description),
    ):
        try:
            await setter(value)
        except Exception as exc:  # noqa: BLE001 - non-fatal, often rate-limited
            logger.warning("Could not set bot profile field: %s", exc)


def check_ytdlp_version() -> None:
    """
    Ensure yt-dlp is recent; auto-update it if it looks outdated.

    TikTok/Instagram/YouTube change their sites constantly. An outdated yt-dlp
    produces errors like "Unable to extract universal data for rehydration".
    Rather than just warn, we try to upgrade it automatically into the SAME
    Python that runs the bot, so the fix is guaranteed to land in the right
    environment. If the upgrade cannot run, we print clear manual instructions.
    """
    import subprocess
    import sys

    def _version() -> str | None:
        try:
            import importlib

            import yt_dlp

            importlib.reload(yt_dlp.version)
            return yt_dlp.version.__version__
        except Exception:  # noqa: BLE001
            return None

    version = _version()
    if version:
        logger.info("yt-dlp version: %s", version)

    def _stamp(v: str | None) -> int:
        try:
            year, month, *_ = (int(p) for p in v.split("."))
            return year * 100 + month
        except Exception:  # noqa: BLE001
            return 0

    # Consider anything older than ~2 months outdated (yt-dlp ships often).
    from datetime import date

    today = date.today()
    current_stamp = today.year * 100 + today.month
    installed_stamp = _stamp(version)

    if version is None or installed_stamp < current_stamp - 1:
        logger.warning(
            "yt-dlp (%s) looks outdated — updating automatically...",
            version or "not installed",
        )
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade",
                 "--no-cache-dir", "yt-dlp"],
                check=True,
                capture_output=True,
                timeout=180,
            )
            new_version = _version()
            logger.info("yt-dlp updated to %s", new_version)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Auto-update of yt-dlp FAILED (%s). Please run manually:\n"
                "    %s -m pip install -U yt-dlp",
                exc, sys.executable,
            )


async def main() -> None:
    config = load_config()
    setup_logging(config.log_level)
    logger.info("Starting bot...")
    check_ytdlp_version()

    # Shared services -------------------------------------------------------
    db = create_database(config.database_url, config.database_path)
    await db.init()

    translator = Translator(default_language=config.default_language)
    music = MusicService(config.music_sources)

    # Bot & dispatcher ------------------------------------------------------
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Fetch the bot's own username so handlers can sign messages with @username.
    me = await bot.get_me()
    bot_username = me.username or ""
    logger.info("Running as @%s", bot_username)

    # Make shared objects available to every handler via dependency injection.
    dp["db"] = db
    dp["translator"] = translator
    dp["music"] = music
    dp["config"] = config
    dp["bot_username"] = bot_username

    dp.include_router(get_main_router())

    await set_bot_commands(bot)
    await set_bot_profile(bot)

    # Start the keep-alive HTTP server if the host provides a PORT (e.g. Render
    # free Web Service). Does nothing locally or on worker-type hosts.
    keepalive_runner = await start_keepalive()

    # Remove any leftover webhook and drop pending updates, then poll.
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot is up. Press Ctrl+C to stop.")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        if keepalive_runner is not None:
            await keepalive_runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
