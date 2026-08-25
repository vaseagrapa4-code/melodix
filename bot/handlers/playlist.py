"""
Playlist system.

Each user can create playlists. A playlist gets a short share CODE (e.g.
'K7QP4M'); anyone who enters that code can open the playlist and download its
tracks. Opening a shared playlist increases its 'uses' counter, which powers
the playlist leaderboard (see leaderboard.py).

Flow:
  /playlist -> menu: Create / My playlists / Open by code
  Create    -> ask name -> create -> show share code
  My        -> list playlists (open / delete)
  Open      -> ask code -> show tracks -> tap to download
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.handlers.common import resolve_language
from bot.handlers.music import deliver_track
from bot.handlers.states import PlaylistStates
from bot.keyboards.inline import (
    playlist_list_keyboard,
    playlist_menu_keyboard,
    playlist_tracks_keyboard,
)
from bot.services.music_service import MusicService
from bot.services.sources.base import Track
from bot.utils.database import Database
from bot.utils.i18n import Translator

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("playlist"))
async def cmd_playlist(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    await state.clear()
    lang = await resolve_language(db, translator, message.from_user.id)
    await message.answer(
        translator.get(lang, "playlist_menu"),
        reply_markup=playlist_menu_keyboard(translator, lang),
    )


@router.callback_query(F.data.startswith("plmenu:"))
async def on_playlist_menu(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    lang = await resolve_language(db, translator, callback.from_user.id)
    action = callback.data.split(":", 1)[1]

    if action == "create":
        await state.set_state(PlaylistStates.waiting_for_name)
        await callback.message.edit_text(translator.get(lang, "playlist_ask_name"))

    elif action == "my":
        playlists = await db.list_user_playlists(callback.from_user.id)
        if not playlists:
            await callback.message.edit_text(translator.get(lang, "playlist_none"))
        else:
            await callback.message.edit_text(
                translator.get(lang, "playlist_list_header"),
                reply_markup=playlist_list_keyboard(playlists, translator, lang),
            )

    elif action == "open":
        await state.set_state(PlaylistStates.waiting_for_code)
        await callback.message.edit_text(translator.get(lang, "playlist_ask_code"))

    await callback.answer()


@router.message(PlaylistStates.waiting_for_name, F.text)
async def on_playlist_name(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    lang = await resolve_language(db, translator, message.from_user.id)
    name = message.text.strip()[:60] or "Playlist"
    code = await db.create_playlist(message.from_user.id, name)
    await state.clear()
    await message.answer(translator.get(lang, "playlist_created", name=name, code=code))


@router.message(PlaylistStates.waiting_for_code, F.text)
async def on_playlist_code(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    lang = await resolve_language(db, translator, message.from_user.id)
    code = message.text.strip().upper()
    await state.clear()
    await _open_playlist(message, code, lang, db, translator, count_use=True)


@router.callback_query(F.data.startswith("plopen:"))
async def on_playlist_open(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
) -> None:
    lang = await resolve_language(db, translator, callback.from_user.id)
    code = callback.data.split(":", 1)[1]
    # Opening your own playlist from "My playlists" should not inflate the
    # popularity counter, so count_use=False here.
    await _open_playlist(callback.message, code, lang, db, translator, count_use=False)
    await callback.answer()


async def _open_playlist(
    message: Message,
    code: str,
    lang: str,
    db: Database,
    translator: Translator,
    count_use: bool,
) -> None:
    """Show a playlist's tracks (shared helper for code / button opening)."""
    pl = await db.get_playlist(code)
    if not pl:
        await message.answer(translator.get(lang, "playlist_not_found"))
        return

    tracks = await db.get_playlist_tracks(code)
    if not tracks:
        await message.answer(translator.get(lang, "playlist_empty"))
        return

    if count_use:
        await db.increment_playlist_uses(code)

    await message.answer(
        translator.get(lang, "playlist_opened", name=pl["name"], code=code, count=len(tracks)),
        reply_markup=playlist_tracks_keyboard(code, tracks),
    )


@router.callback_query(F.data.startswith("plpick:"))
async def on_playlist_track_pick(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
    music: MusicService,
    config: Config,
    bot_username: str,
) -> None:
    """Download a track chosen from an opened playlist."""
    lang = await resolve_language(db, translator, callback.from_user.id)
    _, code, index = callback.data.split(":", 2)

    tracks = await db.get_playlist_tracks(code)
    try:
        track = Track(**tracks[int(index)])
    except (ValueError, IndexError, TypeError):
        await callback.answer(translator.get(lang, "generic_error"), show_alert=True)
        return

    await callback.answer()
    status = await callback.message.answer(translator.get(lang, "downloading"))
    await deliver_track(
        callback.message, callback.from_user.id, track, lang,
        translator, music, config, db, bot_username=bot_username,
        status_message=status,
    )


@router.callback_query(F.data.startswith("pldel:"))
async def on_playlist_delete(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
) -> None:
    lang = await resolve_language(db, translator, callback.from_user.id)
    code = callback.data.split(":", 1)[1]
    ok = await db.delete_playlist(code, callback.from_user.id)
    if ok:
        await callback.answer(translator.get(lang, "playlist_deleted"), show_alert=False)
        # Refresh the list.
        playlists = await db.list_user_playlists(callback.from_user.id)
        if playlists:
            await callback.message.edit_reply_markup(
                reply_markup=playlist_list_keyboard(playlists, translator, lang)
            )
        else:
            await callback.message.edit_text(translator.get(lang, "playlist_none"))
    else:
        await callback.answer(translator.get(lang, "generic_error"), show_alert=True)
