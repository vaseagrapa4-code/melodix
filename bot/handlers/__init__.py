"""Aggregate all routers so main.py can include them in one place."""

from aiogram import Router

from . import audio_edit, common, language, leaderboard, music, playlist


def get_main_router() -> Router:
    """Combine every feature router into a single root router."""
    root = Router()
    root.include_router(common.router)
    root.include_router(language.router)
    root.include_router(playlist.router)
    root.include_router(leaderboard.router)
    root.include_router(audio_edit.router)
    root.include_router(music.router)  # music is last: it catches free text
    return root
