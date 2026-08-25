"""
Common commands: /start, /help, /cancel.

These handlers receive shared objects (translator, db, config) through
aiogram's dependency injection — they are passed as workflow data in main.py
and simply appear as function arguments.
"""

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.keyboards.inline import language_keyboard
from bot.utils.database import Database
from bot.utils.i18n import Translator

logger = logging.getLogger(__name__)
router = Router()


async def resolve_language(db: Database, translator: Translator, user_id: int) -> str:
    """Return the user's stored language, or the default one."""
    lang = await db.get_language(user_id)
    return lang or translator.default_language


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    """
    /start always shows the language selection menu first, as required.
    We also store the user's display name for the leaderboard.
    """
    await state.clear()
    # Remember the user (and their name) without overwriting an existing language.
    name = message.from_user.full_name or message.from_user.username or ""
    await db.ensure_user(message.from_user.id, translator.default_language, name)
    await message.answer(
        translator.get(translator.default_language, "choose_language"),
        reply_markup=language_keyboard(translator),
    )


@router.message(Command("help"))
async def cmd_help(
    message: Message,
    db: Database,
    translator: Translator,
) -> None:
    lang = await resolve_language(db, translator, message.from_user.id)
    await message.answer(translator.get(lang, "help"))


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message,
    state: FSMContext,
    db: Database,
    translator: Translator,
) -> None:
    """Abort any ongoing multi-step operation (like cutting)."""
    await state.clear()
    lang = await resolve_language(db, translator, message.from_user.id)
    await message.answer(translator.get(lang, "cancelled"))
