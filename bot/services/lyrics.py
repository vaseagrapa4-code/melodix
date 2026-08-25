"""
Lyrics fetching via the free lyrics.ovh API.

No API key required. Returns plain-text lyrics or None if not found. Some songs
simply are not in the database (404) — that is handled gracefully.
"""

import logging
import urllib.parse

import aiohttp

logger = logging.getLogger(__name__)

_LYRICS_URL = "https://api.lyrics.ovh/v1/{artist}/{title}"


async def get_lyrics(artist: str, title: str) -> str | None:
    """Fetch lyrics for a song. Returns the text or None if unavailable."""
    if not title:
        return None
    url = _LYRICS_URL.format(
        artist=urllib.parse.quote(artist or ""),
        title=urllib.parse.quote(title),
    )
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
    except Exception as exc:  # noqa: BLE001 - lyrics are best-effort
        logger.warning("Lyrics fetch failed: %s", exc)
        return None

    lyrics = (data or {}).get("lyrics", "").strip()
    return lyrics or None
