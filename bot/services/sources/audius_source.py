"""
Audius music source.

Audius (audius.co) is a free, decentralized music platform with a public API
that needs NO API key and is NOT blocked on data-center IPs — so it works
reliably on cloud servers (Render), just like SoundCloud. It's a great third
source alongside SoundCloud and YouTube.

We use the public API directly over HTTP (via aiohttp), which is fast and
avoids yt-dlp's node-selection issues. Each track object already contains a
ready-to-use `stream.url` pointing at a CDN.
"""

import asyncio
import logging
import urllib.parse
from pathlib import Path

import aiohttp

from .base import MusicSource, Track

logger = logging.getLogger(__name__)

_API = "https://api.audius.co"
_APP = "melodix"
_HEADERS = {"User-Agent": "Melodix/1.0"}


class AudiusSource(MusicSource):
    name = "audius"

    async def search(self, query: str, limit: int) -> list[Track]:
        url = (
            f"{_API}/v1/tracks/search?query={urllib.parse.quote(query)}"
            f"&app_name={_APP}"
        )
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            async with aiohttp.ClientSession(timeout=timeout, headers=_HEADERS) as s:
                async with s.get(url) as r:
                    if r.status != 200:
                        return []
                    data = await r.json(content_type=None)
        except Exception as exc:  # noqa: BLE001 - let MusicService try next source
            logger.warning("[audius] search failed: %s", exc)
            return []

        tracks: list[Track] = []
        for t in (data or {}).get("data", []) or []:
            # Only keep tracks we can actually stream.
            if not t.get("is_streamable"):
                continue
            stream = (t.get("stream") or {}).get("url")
            if not stream:
                continue
            user = t.get("user") or {}
            tracks.append(
                Track(
                    source=self.name,
                    id=stream,  # the direct CDN URL — used by download()
                    title=t.get("title", "Unknown"),
                    artist=user.get("name") or "",
                    duration=int(t.get("duration") or 0),
                    views=int(t.get("play_count") or 0),
                )
            )
            if len(tracks) >= limit:
                break
        logger.info("[audius] '%s' -> %d results", query, len(tracks))
        return tracks

    async def download(self, track: Track, dest_dir: Path) -> Path | None:
        # track.id is already a direct CDN stream URL.
        dest = dest_dir / f"audius_{abs(hash(track.id))}.mp3"
        try:
            timeout = aiohttp.ClientTimeout(total=120)
            async with aiohttp.ClientSession(timeout=timeout, headers=_HEADERS) as s:
                async with s.get(track.id) as r:
                    if r.status != 200:
                        logger.warning("[audius] download HTTP %s", r.status)
                        return None
                    data = await r.read()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[audius] download failed: %s", exc)
            return None

        if len(data) < 10000:  # too small to be a real track
            return None
        dest.write_bytes(data)
        logger.info("[audius] downloaded %s (%d bytes)", dest.name, len(data))
        return dest
