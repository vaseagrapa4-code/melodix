"""Aggregate all routers so main.py can include them in one place."""

from aiogram import Router

from . import (audio_edit, common, import_audio, language, leaderboard, music,
               playlist)


def get_main_router() -> Router:
    """Combine every feature router into a single root router."""
    root = Router()
    root.include_router(common.router)
    root.include_router(language.router)
    root.include_router(playlist.router)
    root.include_router(leaderboard.router)
    root.include_router(audio_edit.router)   # /cut audio handling (state-based)
    root.include_router(import_audio.router)  # capture forwarded/sent audio
    root.include_router(music.router)         # music is last: catches free text
    return root
