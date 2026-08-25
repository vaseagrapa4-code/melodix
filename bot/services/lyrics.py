"""
Lyrics fetching via the free lyrics.ovh API.

No API key required. Returns plain-text lyrics or None if not found. Because
different sources store metadata messily (e.g. the artist inside the title), we
try several (artist, title) combinations before giving up.
"""

import logging
import urllib.parse

import aiohttp

logger = logging.getLogger(__name__)

_LYRICS_URL = "https://api.lyrics.ovh/v1/{artist}/{title}"


async def _fetch_one(artist: str, title: str) -> str | None:
    """Try a single (artist, title) pair against lyrics.ovh."""
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


async def get_lyrics(artist: str, title: str, uploader: str = "") -> str | None:
    """
    Fetch lyrics, trying several artist/title combinations.

    Returns the lyrics text or None if nothing matched.
    """
    from bot.utils.metadata import best_lyrics_queries

    for a, t in best_lyrics_queries(title, artist, uploader):
        result = await _fetch_one(a, t)
        if result:
            return result
    return None
