"""
MusicService orchestrates all configured sources.

It provides these high-level operations used by the handlers:
  * search()          -> tries each source in order until one returns results
  * download()        -> downloads a chosen track, falling back to other sources
  * more_from_artist()-> finds more songs by the same artist

This is where the "if one source fails, automatically try another" rule from
the requirements is implemented.
"""

import logging
import time
from pathlib import Path

from .sources.audius_source import AudiusSource
from .sources.base import MusicSource, Track
from .sources.ytdlp_source import SoundCloudSource, YouTubeSource, YTMusicSource

logger = logging.getLogger(__name__)

# In-memory search cache: repeated/identical searches return instantly instead
# of hitting the network again. Entries expire after _CACHE_TTL seconds.
_CACHE_TTL = 600  # 10 minutes
_CACHE_MAX = 200   # cap entries to avoid unbounded memory use

# Registry mapping config names -> source classes. Add new sources here.
_SOURCE_REGISTRY: dict[str, type[MusicSource]] = {
    "soundcloud": SoundCloudSource,
    "audius": AudiusSource,
    "ytmusic": YTMusicSource,
    "youtube": YouTubeSource,
}


class MusicService:
    def __init__(self, source_names: list[str]) -> None:
        self.sources: list[MusicSource] = []
        for name in source_names:
            cls = _SOURCE_REGISTRY.get(name)
            if cls is None:
                logger.warning("Unknown music source '%s' — skipping", name)
                continue
            self.sources.append(cls())
        if not self.sources:
            # Guarantee at least one working source.
            logger.warning("No valid sources configured, defaulting to youtube")
            self.sources.append(YouTubeSource())
        logger.info(
            "MusicService using sources: %s",
            ", ".join(s.name for s in self.sources),
        )
        # query -> (timestamp, results) cache for fast repeat searches.
        self._cache: dict[str, tuple[float, list[Track]]] = {}

    async def more_from_artist(self, artist: str, limit: int) -> list[Track]:
        """Find more songs by the same artist (via the normal search)."""
        if not artist:
            return []
        # Searching the artist name returns their popular tracks.
        return await self.search(artist, limit)

    async def search(self, query: str, limit: int) -> list[Track]:
        """
        Search sources in order and return the first non-empty result set.

        Results are cached for a few minutes so repeated searches are instant.
        If a source raises an error we log it and move on to the next one.
        """
        key = f"{query.lower().strip()}|{limit}"
        now = time.time()

        # Serve from cache if fresh.
        cached = self._cache.get(key)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]

        results: list[Track] = []
        for source in self.sources:
            try:
                results = await source.search(query, limit)
                if results:
                    break
            except Exception as exc:  # noqa: BLE001 - we want to try next source
                logger.exception("Search failed on source %s: %s", source.name, exc)

        # Store in cache (with a simple size cap).
        if results:
            if len(self._cache) >= _CACHE_MAX:
                # Drop the oldest entry.
                oldest = min(self._cache, key=lambda k: self._cache[k][0])
                self._cache.pop(oldest, None)
            self._cache[key] = (now, results)
        return results

    # Skip tracks longer than this (very long = huge file, slow, and usually
    # over Telegram's 50 MB limit). ~40 min covers normal songs generously.
    MAX_DURATION_SECONDS = 40 * 60

    async def download(self, track: Track, dest_dir: Path) -> Path | None:
        """
        Download the given track, with robust fallbacks.

        1) Try the exact track on its own source.
        2) If that fails (e.g. a DRM-protected SoundCloud track), re-search the
           song on every source and try SEVERAL candidates each, skipping ones
           that are protected/unavailable or absurdly long — until one downloads.
        """
        # 1) Try the exact chosen track first (unless it's absurdly long).
        primary = next((s for s in self.sources if s.name == track.source), None)
        if primary is not None and not self._too_long(track):
            try:
                path = await primary.download(track, dest_dir)
                if path:
                    return path
            except Exception as exc:  # noqa: BLE001
                logger.exception("Download failed on %s: %s", primary.name, exc)

        # 2) Fallback: re-search the song and try multiple candidates per source.
        query = f"{track.artist} {track.title}".strip()
        ordered = ([primary] if primary else []) + [
            s for s in self.sources if s is not primary
        ]
        for source in ordered:
            if source is None:
                continue
            try:
                logger.info("Fallback search via %s for '%s'", source.name, query)
                candidates = await source.search(query, 5)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Fallback search failed on %s: %s", source.name, exc)
                continue
            # Prefer reasonably-sized tracks; skip huge mixes.
            candidates = sorted(candidates, key=self._too_long)
            for cand in candidates[:4]:
                if self._too_long(cand):
                    continue
                try:
                    path = await source.download(cand, dest_dir)
                    if path:
                        return path
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Candidate download failed on %s: %s",
                                   source.name, exc)
                    continue
        return None

    def _too_long(self, track: Track) -> bool:
        """True if a track is longer than the allowed max (0 = unknown, allow)."""
        dur = getattr(track, "duration", 0) or 0
        return dur > self.MAX_DURATION_SECONDS
