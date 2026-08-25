"""
Leaderboards.

/top shows a menu with two boards:
  * Top playlists  -> most-used shared playlists
  * Top users      -> users who downloaded the most tracks
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.handlers.common import resolve_language
from bot.keyboards.inline import top_menu_keyboard
from bot.utils.database import Database
from bot.utils.i18n import Translator

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("top"))
async def cmd_top(message: Message, db: Database, translator: Translator) -> None:
    lang = await resolve_language(db, translator, message.from_user.id)
    await message.answer(
        translator.get(lang, "top_menu"),
        reply_markup=top_menu_keyboard(translator, lang),
    )


@router.callback_query(F.data.startswith("topmenu:"))
async def on_top_menu(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
) -> None:
    lang = await resolve_language(db, translator, callback.from_user.id)
    which = callback.data.split(":", 1)[1]

    if which == "playlists":
        rows = await db.top_playlists(limit=10)
        if not rows:
            await callback.message.edit_text(translator.get(lang, "top_playlists_empty"))
        else:
            lines = [translator.get(lang, "top_playlists_header"), ""]
            for i, r in enumerate(rows, start=1):
                lines.append(
                    translator.get(
                        lang, "top_playlists_item",
                        rank=i, name=r["name"], uses=r["uses"],
                        count=r["track_count"], code=r["code"],
                    )
                )
            await callback.message.edit_text("\n".join(lines))

    elif which == "users":
        rows = await db.top_downloaders(limit=10)
        if not rows:
            await callback.message.edit_text(translator.get(lang, "top_users_empty"))
        else:
            lines = [translator.get(lang, "top_users_header"), ""]
            for i, r in enumerate(rows, start=1):
                name = r["name"] or f"User {r['user_id']}"
                lines.append(
                    translator.get(
                        lang, "top_users_item",
                        rank=i, name=name, count=r["download_count"],
                    )
                )
            await callback.message.edit_text("\n".join(lines))

    await callback.answer()
