"""
Language selection and switching.

/language re-shows the menu, and pressing any language button stores the
choice in the database and confirms in the chosen language.
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import language_keyboard
from bot.utils.database import Database
from bot.utils.i18n import Translator

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("language"))
async def cmd_language(message: Message, translator: Translator) -> None:
    """Dedicated command to change the language at any time."""
    await message.answer(
        translator.get(translator.default_language, "choose_language"),
        reply_markup=language_keyboard(translator),
    )


@router.callback_query(F.data.startswith("lang:"))
async def on_language_chosen(
    callback: CallbackQuery,
    db: Database,
    translator: Translator,
) -> None:
    """Handle a tap on one of the language buttons."""
    lang = callback.data.split(":", 1)[1]
    if lang not in translator.languages:
        await callback.answer("Unknown language", show_alert=True)
        return

    name = callback.from_user.full_name or callback.from_user.username or ""
    await db.set_language(callback.from_user.id, lang, name)
    logger.info("User %s set language to %s", callback.from_user.id, lang)

    # Confirm and then show the welcome text in the newly selected language.
    await callback.message.edit_text(translator.get(lang, "language_set"))
    await callback.message.answer(translator.get(lang, "welcome"))
    await callback.answer()
