"""
Import audio from other bots / chats.

Telegram does NOT let a bot read your chats with other bots — that's forbidden
by the platform. The permitted (and simple) way to bring music from another bot
into this one is to FORWARD it here: when you forward (or just send) an audio
file to this bot, we capture it.

What we do with a received/forwarded audio:
  * remember it (so it appears in /cut and can be added to playlists)
  * confirm it's imported, with an "Add to playlist" button

Re-sending later is instant because Telegram audio already has a file_id — no
download/re-upload needed.
"""

import logging

from aiogram import F, Router
from aiogram.types import Message

from bot.handlers.common import resolve_language
from bot.keyboards.inline import audio_actions_keyboard
from bot.utils.database import Database
from bot.utils.i18n import Translator

logger = logging.getLogger(__name__)
router = Router()


@router.message(F.audio)
async def on_audio_received(
    message: Message,
    db: Database,
    translator: Translator,
) -> None:
    """
    Capture an audio file sent or forwarded to the bot (e.g. from another
    music bot) and store it so it can be added to a playlist or trimmed.
    """
    lang = await resolve_language(db, translator, message.from_user.id)
    audio = message.audio

    # Build a track that re-sends instantly by file_id (source="telegram").
    track = {
        "source": "telegram",
        "id": audio.file_id,
        "title": audio.title or (audio.file_name or "Audio"),
        "artist": audio.performer or "",
        "duration": int(audio.duration or 0),
        "views": 0,
    }
    await db.add_recent_track(message.from_user.id, track)

    # index 0 = newest recent track, used by the "Add to playlist" button.
    await message.answer(
        translator.get(
            lang, "import_saved",
            title=track["title"], artist=track["artist"] or "?",
        ),
        reply_markup=audio_actions_keyboard(
            0,
            translator.get(lang, "add_to_playlist"),
            lyrics_label=translator.get(lang, "btn_lyrics"),
            more_artist_label=translator.get(lang, "btn_more_artist"),
        ),
    )
