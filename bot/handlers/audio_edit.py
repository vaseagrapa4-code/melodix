"""
Audio editing: trim a track between two timecodes.

New flow (as requested): the user picks one of the songs the bot recently sent
them, instead of having to re-upload an audio file.

  1. /cut                 -> bot shows buttons with your recently received songs
  2. tap a song           -> bot asks for "start end" timecodes
  3. send timecodes       -> bot downloads that song, cuts it, returns a NEW file

The output is always a brand-new file created from the selected segment.
"""

import logging
import time
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message

from bot.config import Config
from bot.handlers.common import resolve_language
from bot.handlers.states import CutStates
from bot.keyboards.inline import cut_pick_keyboard
from bot.services.music_service import MusicService
from bot.services.sources.base import Track
from bot.utils.audio import cut_audio, parse_timecode
from bot.utils.database import Database
from bot.utils.i18n import Translator

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("cut"))
async def cmd_cut(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    """Start the cutting flow by listing recently received songs."""
    lang = await resolve_language(db, translator, message.from_user.id)
    recent = await db.get_recent_tracks(message.from_user.id)

    if not recent:
        await message.answer(translator.get(lang, "cut_no_recent"))
        return

    await state.set_state(CutStates.waiting_for_times)
    await state.update_data(cut_candidates=recent)
    await message.answer(
        translator.get(lang, "cut_choose_track"),
        reply_markup=cut_pick_keyboard(recent),
    )


@router.callback_query(F.data.startswith("cutpick:"))
async def on_cut_pick(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    """User chose which recent song to trim; ask for timecodes."""
    lang = await resolve_language(db, translator, callback.from_user.id)
    index = int(callback.data.split(":", 1)[1])

    data = await state.get_data()
    candidates = data.get("cut_candidates") or await db.get_recent_tracks(callback.from_user.id)
    try:
        chosen = candidates[index]
    except (IndexError, TypeError):
        await callback.answer(translator.get(lang, "generic_error"), show_alert=True)
        return

    await state.update_data(cut_track=chosen)
    await state.set_state(CutStates.waiting_for_times)
    await callback.message.edit_text(translator.get(lang, "cut_ask_times"))
    await callback.answer()


@router.message(CutStates.waiting_for_times, F.text)
async def receive_times(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
    music: MusicService,
    config: Config,
    bot_username: str,
) -> None:
    """Parse timecodes, download the chosen track, cut it and send the result."""
    lang = await resolve_language(db, translator, message.from_user.id)

    data = await state.get_data()
    track_dict = data.get("cut_track")
    if not track_dict:
        # User typed times before choosing a song.
        await message.answer(translator.get(lang, "cut_choose_track"))
        return

    parts = message.text.replace("-", " ").split()
    if len(parts) != 2:
        await message.answer(translator.get(lang, "cut_bad_format"))
        return

    start = parse_timecode(parts[0])
    end = parse_timecode(parts[1])
    if start is None or end is None:
        await message.answer(translator.get(lang, "cut_bad_format"))
        return
    if end <= start:
        await message.answer(translator.get(lang, "cut_range_error"))
        return

    status = await message.answer(translator.get(lang, "cut_processing"))

    # Download the source track first (it was only kept as metadata).
    track = Track(**track_dict)
    try:
        if track.source == "telegram":
            # Imported from Telegram: download by file_id via the bot itself.
            import time as _t
            file = await message.bot.get_file(track.id)
            src_path = config.download_dir / f"tg_{message.from_user.id}_{int(_t.time())}.audio"
            await message.bot.download_file(file.file_path, destination=src_path)
        else:
            src_path = await music.download(track, config.download_dir)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Cut download failed: %s", exc)
        src_path = None

    if not src_path:
        await status.edit_text(translator.get(lang, "download_error"))
        await state.clear()
        return

    dst_path = config.download_dir / f"cut_{message.from_user.id}_{int(time.time())}.mp3"
    ok = await cut_audio(src_path, dst_path, start, end)
    if not ok:
        await status.edit_text(translator.get(lang, "cut_error"))
        _cleanup(src_path)
        await state.clear()
        return

    try:
        signature = f"\n\n@{bot_username}" if bot_username else ""
        await message.answer_audio(
            audio=FSInputFile(dst_path),
            caption=translator.get(lang, "cut_done") + signature,
            title=f"{track.title} (cut)",
            performer=track.artist or None,
        )
        await status.delete()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to send cut audio: %s", exc)
        await status.edit_text(translator.get(lang, "generic_error"))
    finally:
        _cleanup(src_path)
        _cleanup(dst_path)
        await state.clear()


def _cleanup(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Cleanup failed for %s: %s", path, exc)
