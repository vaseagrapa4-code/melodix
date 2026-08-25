"""
Music search & download.

Any plain text message (that is not a command) is treated as a search query.
The query can be a song title, an artist, or a fragment of lyrics. Results are
sorted with the most popular track first and shown as inline buttons, paginated
with a "More tracks" button. Tapping a result downloads and sends the audio.

Every delivered track is remembered (per user) so it can later be trimmed with
/cut or added to a playlist.
"""

import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.config import Config
from bot.handlers.common import resolve_language
from bot.keyboards.inline import (
    audio_actions_keyboard,
    playlist_target_keyboard,
    results_keyboard,
)
from bot.services.music_service import MusicService
from bot.services.sources.base import Track
from bot.utils.database import Database
from bot.utils.i18n import Translator

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
#  Shared helper: download a track and send it to the chat.
#  Reused by search results, playlist playback and (indirectly) elsewhere.
# ---------------------------------------------------------------------------
def _signature(bot_username: str) -> str:
    """The '@bot' credit shown under every delivered audio (like the ref UI)."""
    return f"@{bot_username}" if bot_username else ""


async def deliver_track(
    message: Message,
    user_id: int,
    track: Track,
    lang: str,
    translator: Translator,
    music: MusicService,
    config: Config,
    db: Database,
    bot_username: str = "",
    status_message: Message | None = None,
) -> None:
    """Download `track`, send it as audio, record it, update the counter."""
    status = status_message or await message.answer(translator.get(lang, "downloading"))
    await status.edit_text(translator.get(lang, "downloading"))

    try:
        path = await music.download(track, config.download_dir)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Download error: %s", exc)
        path = None

    if not path:
        await status.edit_text(translator.get(lang, "download_error"))
        return

    if path.stat().st_size > config.max_file_size_bytes:
        await status.edit_text(
            translator.get(lang, "file_too_big", limit=config.max_file_size_mb)
        )
        _safe_unlink(path)
        return

    await status.edit_text(translator.get(lang, "sending"))
    try:
        # Remember this track for /cut and playlist features.
        await db.add_recent_track(user_id, track.__dict__)
        await db.increment_downloads(user_id)

        # Find the index of this track in the user's recent list so the
        # "Add to playlist" button can reference it.
        recent = await db.get_recent_tracks(user_id)  # newest first -> index 0

        await message.answer_audio(
            audio=FSInputFile(path),
            title=track.title,
            performer=track.artist or None,
            caption=_signature(bot_username),  # "@bot" credit under the audio
            reply_markup=audio_actions_keyboard(
                0,
                translator.get(lang, "add_to_playlist"),
                # Show Lyrics + More-from-artist under every delivered song.
                lyrics_label=translator.get(lang, "btn_lyrics"),
                more_artist_label=translator.get(lang, "btn_more_artist"),
            ),
        )
        await status.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Send audio failed: %s", exc)
        await status.edit_text(translator.get(lang, "generic_error"))
    finally:
        _safe_unlink(path)


@router.message(F.text & ~F.text.startswith("/"))
async def on_search(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
    music: MusicService,
    config: Config,
) -> None:
    """Treat any non-command text as a music search query."""
    lang = await resolve_language(db, translator, message.from_user.id)
    query = message.text.strip()

    # Send a lightweight placeholder we can turn into the result list.
    # (No noisy "Searching: ..." text — just a minimal placeholder.)
    status = await message.answer("...")

    try:
        tracks = await music.search(query, config.max_search_results)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Search error: %s", exc)
        await status.edit_text(translator.get(lang, "search_error"))
        return

    if not tracks:
        await status.edit_text(translator.get(lang, "no_results"))
        return

    # Cache results for pagination + selection.
    await state.update_data(results=[t.__dict__ for t in tracks])

    await status.edit_text(
        translator.get(lang, "choose_result"),
        reply_markup=results_keyboard(
            tracks, page=0, page_size=config.page_size,
            more_label=translator.get(lang, "more_tracks"),
        ),
    )


@router.callback_query(F.data.startswith("page:"))
async def on_page(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    translator: Translator,
    config: Config,
) -> None:
    """Show another page of the cached search results."""
    lang = await resolve_language(db, translator, callback.from_user.id)
    page = int(callback.data.split(":", 1)[1])

    data = await state.get_data()
    results = [Track(**r) for r in data.get("results", [])]
    if not results:
        await callback.answer()
        return

    await callback.message.edit_reply_markup(
        reply_markup=results_keyboard(
            results, page=page, page_size=config.page_size,
            more_label=translator.get(lang, "more_tracks"),
        )
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pick:"))
async def on_pick(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    translator: Translator,
    music: MusicService,
    config: Config,
    bot_username: str,
) -> None:
    """User tapped one of the search-result buttons."""
    lang = await resolve_language(db, translator, callback.from_user.id)
    choice = callback.data.split(":", 1)[1]

    if choice == "cancel":
        await state.clear()
        await callback.message.edit_text(translator.get(lang, "cancelled"))
        await callback.answer()
        return

    data = await state.get_data()
    results = data.get("results", [])
    try:
        track = Track(**results[int(choice)])
    except (ValueError, IndexError, TypeError):
        await callback.answer(translator.get(lang, "generic_error"), show_alert=True)
        return

    await callback.answer()
    await deliver_track(
        callback.message, callback.from_user.id, track, lang,
        translator, music, config, db, bot_username=bot_username,
        status_message=callback.message,
    )


@router.callback_query(F.data.startswith("addpl:"))
async def on_add_to_playlist(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
) -> None:
    """Open the 'choose a playlist' menu for the just-delivered track."""
    lang = await resolve_language(db, translator, callback.from_user.id)
    index = int(callback.data.split(":", 1)[1])

    playlists = await db.list_user_playlists(callback.from_user.id)
    if not playlists:
        await callback.answer(translator.get(lang, "playlist_add_no_lists"), show_alert=True)
        return

    await callback.message.answer(
        translator.get(lang, "playlist_choose_target"),
        reply_markup=playlist_target_keyboard(playlists, index),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pladd:"))
async def on_playlist_add_confirm(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
) -> None:
    """Add the referenced recent track to the chosen playlist."""
    lang = await resolve_language(db, translator, callback.from_user.id)
    _, code, index = callback.data.split(":", 2)

    recent = await db.get_recent_tracks(callback.from_user.id)
    try:
        track = recent[int(index)]
    except (ValueError, IndexError):
        await callback.answer(translator.get(lang, "generic_error"), show_alert=True)
        return

    ok = await db.add_track_to_playlist(code, track)
    if not ok:
        await callback.answer(translator.get(lang, "playlist_not_found"), show_alert=True)
        return

    pl = await db.get_playlist(code)
    await callback.message.edit_text(
        translator.get(lang, "playlist_added", name=pl["name"] if pl else code)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("lyrics:"))
async def on_lyrics(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
) -> None:
    """Show the lyrics of a delivered song (looked up by recent-track index)."""
    from bot.services.lyrics import get_lyrics

    lang = await resolve_language(db, translator, callback.from_user.id)
    index = int(callback.data.split(":", 1)[1])
    recent = await db.get_recent_tracks(callback.from_user.id)
    try:
        track = recent[index]
    except (IndexError, TypeError):
        await callback.answer(translator.get(lang, "generic_error"), show_alert=True)
        return

    await callback.answer(translator.get(lang, "lyrics_loading"))
    title = track.get("title", "")
    artist = track.get("artist", "")
    # `artist` may actually be the uploader (esp. SoundCloud); the lyrics
    # service tries several combinations to find a match.
    lyrics = await get_lyrics(artist, title, uploader=artist)
    if not lyrics:
        await callback.message.answer(translator.get(lang, "lyrics_not_found"))
        return

    header = translator.get(lang, "lyrics_header", title=title, artist=artist)
    text = f"{header}\n\n{lyrics}"
    # Telegram messages are capped at 4096 chars; split long lyrics safely.
    for chunk in _split_text(text, 4000):
        await callback.message.answer(chunk)


@router.callback_query(F.data.startswith("artist:"))
async def on_more_from_artist(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    translator: Translator,
    music: MusicService,
    config: Config,
) -> None:
    """Show more songs by the same artist as a selectable list."""
    lang = await resolve_language(db, translator, callback.from_user.id)
    index = int(callback.data.split(":", 1)[1])
    recent = await db.get_recent_tracks(callback.from_user.id)
    try:
        track = recent[index]
    except (IndexError, TypeError):
        await callback.answer(translator.get(lang, "generic_error"), show_alert=True)
        return

    # Recover a clean artist name (the stored `artist` may be an uploader
    # or embedded inside the title, e.g. "Buddy Holly - Weezer").
    from bot.utils.metadata import best_artist_name

    artist = best_artist_name(
        track.get("title", ""), track.get("artist", ""), track.get("artist", "")
    )
    if not artist:
        await callback.message.answer(translator.get(lang, "more_artist_none"))
        return
    await callback.answer(translator.get(lang, "more_artist_loading", artist=artist))
    results = await music.more_from_artist(artist, config.max_search_results)
    if not results:
        await callback.message.answer(translator.get(lang, "more_artist_none"))
        return

    # Reuse the normal search selection flow (pick:<index>).
    await state.update_data(results=[t.__dict__ for t in results])
    await callback.message.answer(
        translator.get(lang, "more_artist_header", artist=artist),
        reply_markup=results_keyboard(
            results, page=0, page_size=config.page_size,
            more_label=translator.get(lang, "more_tracks"),
        ),
    )


def _split_text(text: str, limit: int) -> list[str]:
    """Split text into chunks <= limit, breaking on line boundaries."""
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


def _safe_unlink(path: Path) -> None:
    """Delete a temp file without crashing if it is already gone."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Could not delete %s: %s", path, exc)
