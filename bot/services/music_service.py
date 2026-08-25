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
from pathlib import Path

from .sources.base import MusicSource, Track
from .sources.ytdlp_source import SoundCloudSource, YouTubeSource, YTMusicSource

logger = logging.getLogger(__name__)

# Registry mapping config names -> source classes. Add new sources here.
_SOURCE_REGISTRY: dict[str, type[MusicSource]] = {
    "soundcloud": SoundCloudSource,
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

    async def more_from_artist(self, artist: str, limit: int) -> list[Track]:
        """Find more songs by the same artist (via the normal search)."""
        if not artist:
            return []
        # Searching the artist name returns their popular tracks.
        return await self.search(artist, limit)

    async def search(self, query: str, limit: int) -> list[Track]:
        """
        Search sources in order and return the first non-empty result set.

        If a source raises an error we log it and move on to the next one.
        """
        for source in self.sources:
            try:
                results = await source.search(query, limit)
                if results:
                    return results
            except Exception as exc:  # noqa: BLE001 - we want to try next source
                logger.exception("Search failed on source %s: %s", source.name, exc)
        return []

    async def download(self, track: Track, dest_dir: Path) -> Path | None:
        """
        Download the given track.

        First try the source that produced the track, then any other source
        as a fallback (re-searching by the track title so a different source
        can still find and deliver the song).
        """
        # 1) Try the original source directly.
        primary = next((s for s in self.sources if s.name == track.source), None)
        if primary is not None:
            try:
                path = await primary.download(track, dest_dir)
                if path:
                    return path
            except Exception as exc:  # noqa: BLE001
                logger.exception("Download failed on %s: %s", primary.name, exc)

        # 2) Fallback: ask other sources to find the same song by title.
        query = f"{track.artist} {track.title}".strip()
        for source in self.sources:
            if primary is not None and source.name == primary.name:
                continue
            try:
                logger.info("Fallback download via %s for '%s'", source.name, query)
                alt = await source.search(query, 1)
                if alt:
                    path = await source.download(alt[0], dest_dir)
                    if path:
                        return path
            except Exception as exc:  # noqa: BLE001
                logger.exception("Fallback failed on %s: %s", source.name, exc)
        return None
