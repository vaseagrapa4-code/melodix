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
    """Got the name; show creation options (private toggle + custom code)."""
    from bot.keyboards.inline import playlist_create_options_keyboard

    lang = await resolve_language(db, translator, message.from_user.id)
    name = message.text.strip()[:60] or "Playlist"
    await state.update_data(new_name=name, new_private=False, new_code="")
    await state.set_state(PlaylistStates.choosing_options)
    await message.answer(
        translator.get(lang, "playlist_options", name=name),
        reply_markup=playlist_create_options_keyboard(
            translator, lang, is_private=False, has_code=False
        ),
    )


async def _refresh_options(callback, state, translator, lang):
    """Redraw the options screen from current FSM state."""
    from bot.keyboards.inline import playlist_create_options_keyboard

    data = await state.get_data()
    await callback.message.edit_text(
        translator.get(lang, "playlist_options", name=data.get("new_name", "")),
        reply_markup=playlist_create_options_keyboard(
            translator, lang,
            is_private=data.get("new_private", False),
            has_code=bool(data.get("new_code")),
        ),
    )


@router.callback_query(
    PlaylistStates.choosing_options, F.data.startswith("plopt:")
)
async def on_create_options(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    from bot.utils.database import PlaylistError

    lang = await resolve_language(db, translator, callback.from_user.id)
    action = callback.data.split(":", 1)[1]

    if action == "toggle_private":
        data = await state.get_data()
        await state.update_data(new_private=not data.get("new_private", False))
        await _refresh_options(callback, state, translator, lang)
        await callback.answer()
        return

    if action == "set_code":
        await state.set_state(PlaylistStates.waiting_for_custom_code)
        await callback.message.answer(translator.get(lang, "playlist_ask_custom_code"))
        await callback.answer()
        return

    if action == "create":
        data = await state.get_data()
        name = data.get("new_name", "Playlist")
        owner_name = callback.from_user.full_name or callback.from_user.username or ""
        status, code = await db.create_playlist(
            callback.from_user.id, name, owner_name,
            custom_code=data.get("new_code", ""),
            is_private=data.get("new_private", False),
        )
        await state.clear()
        if status == PlaylistError.NAME_TAKEN:
            await callback.message.edit_text(translator.get(lang, "playlist_name_taken", name=name))
        elif status == PlaylistError.TOO_MANY_PLAYLISTS:
            await callback.message.edit_text(translator.get(lang, "playlist_too_many"))
        elif status == PlaylistError.CODE_TAKEN:
            await callback.message.edit_text(translator.get(lang, "playlist_code_taken"))
        elif status == PlaylistError.BAD_CODE:
            await callback.message.edit_text(translator.get(lang, "playlist_code_bad"))
        else:
            priv = translator.get(
                lang, "playlist_created_private" if data.get("new_private") else "playlist_created"
            )
            await callback.message.edit_text(priv.format(name=name, code=code))
        await callback.answer()
        return


@router.message(PlaylistStates.waiting_for_custom_code, F.text)
async def on_custom_code(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    """Store the typed custom code and return to the options screen."""
    from bot.keyboards.inline import playlist_create_options_keyboard
    from bot.utils.database import is_valid_custom_code, normalize_code

    lang = await resolve_language(db, translator, message.from_user.id)
    code = normalize_code(message.text)
    if not is_valid_custom_code(code):
        await message.answer(translator.get(lang, "playlist_code_bad"))
        return
    await state.update_data(new_code=code)
    await state.set_state(PlaylistStates.choosing_options)
    data = await state.get_data()
    await message.answer(
        translator.get(lang, "playlist_options_code", code=code, name=data.get("new_name", "")),
        reply_markup=playlist_create_options_keyboard(
            translator, lang,
            is_private=data.get("new_private", False),
            has_code=True,
        ),
    )


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
    await _open_playlist(
        message, code, lang, db, translator,
        count_use=True, opener_id=message.from_user.id,
    )


@router.callback_query(F.data.startswith("plopen:"))
async def on_playlist_open(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
) -> None:
    lang = await resolve_language(db, translator, callback.from_user.id)
    code = callback.data.split(":", 1)[1]
    # Opening your own playlist from "My playlists" should not inflate the
    # popularity counter, so count_use=False here. Pass opener_id so the
    # owner can open their own private playlist.
    await _open_playlist(
        callback.message, code, lang, db, translator,
        count_use=False, opener_id=callback.from_user.id,
    )
    await callback.answer()


async def _open_playlist(
    message: Message,
    code: str,
    lang: str,
    db: Database,
    translator: Translator,
    count_use: bool,
    opener_id: int = 0,
) -> None:
    """Show a playlist's tracks (shared helper for code / button opening)."""
    pl = await db.get_playlist(code)
    if not pl:
        await message.answer(translator.get(lang, "playlist_not_found"))
        return

    # Private playlists can only be opened by their owner.
    if pl.get("is_private") and pl.get("owner_id") != opener_id:
        await message.answer(translator.get(lang, "playlist_is_private"))
        return

    tracks = await db.get_playlist_tracks(code)
    if not tracks:
        await message.answer(translator.get(lang, "playlist_empty"))
        return

    if count_use:
        # Record this distinct opener for the "people who tried it" metric.
        await db.increment_playlist_uses(code, user_id=opener_id)

    owner = pl.get("owner_name") or translator.get(lang, "playlist_owner_unknown")
    caption = translator.get(
        lang, "playlist_opened",
        name=pl["name"], code=code, count=len(tracks), owner=owner,
    )
    keyboard = playlist_tracks_keyboard(code, tracks)

    # If the playlist has a cover photo, send it ABOVE the tracks with the
    # caption + buttons. Fall back to a plain text message if sending fails.
    photo_id = pl.get("photo_id")
    if photo_id:
        try:
            await message.answer_photo(
                photo=photo_id, caption=caption, reply_markup=keyboard
            )
            return
        except Exception as exc:  # noqa: BLE001 - log why, then fall back
            logger.warning("Could not send playlist cover for %s: %s", code, exc)
    await message.answer(caption, reply_markup=keyboard)


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


@router.callback_query(F.data.startswith("plphoto:"))
async def on_playlist_photo_request(
    callback: CallbackQuery,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    """Owner tapped 'Set photo' — ask them to send a photo."""
    lang = await resolve_language(db, translator, callback.from_user.id)
    code = callback.data.split(":", 1)[1]
    pl = await db.get_playlist(code)
    if not pl or pl["owner_id"] != callback.from_user.id:
        await callback.answer(translator.get(lang, "generic_error"), show_alert=True)
        return
    await state.set_state(PlaylistStates.waiting_for_photo)
    await state.update_data(photo_code=code)
    await callback.message.answer(translator.get(lang, "playlist_ask_photo"))
    await callback.answer()


@router.message(PlaylistStates.waiting_for_photo, F.photo)
async def on_playlist_photo_received(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    """Save the smallest version of the sent photo as the playlist cover."""
    lang = await resolve_language(db, translator, message.from_user.id)
    data = await state.get_data()
    code = data.get("photo_code")
    await state.clear()
    if not code:
        return
    # message.photo is a list of sizes (smallest -> largest). Use the LARGEST
    # (last) — its file_id is the most reliable to re-send later.
    photo_id = message.photo[-1].file_id
    ok = await db.set_playlist_photo(code, photo_id, message.from_user.id)
    if ok:
        logger.info("Playlist %s photo set (file_id=%s...)", code, photo_id[:15])
        await message.answer(translator.get(lang, "playlist_photo_set"))
    else:
        await message.answer(translator.get(lang, "generic_error"))


@router.message(PlaylistStates.waiting_for_photo)
async def on_playlist_photo_wrong(
    message: Message,
    db: Database,
    translator: Translator,
) -> None:
    """User sent something that isn't a photo."""
    lang = await resolve_language(db, translator, message.from_user.id)
    await message.answer(translator.get(lang, "playlist_ask_photo"))


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
