"""
Common data structures and the abstract base class for music sources.

A "source" is anything that can (a) search for tracks and (b) download the
audio of a chosen track. New sources just implement this interface and get
registered in the MusicService — the rest of the bot stays unchanged.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class MusicSource(ABC):
    """Interface every music source must implement."""

    name: str = "base"

    @abstractmethod
    async def search(self, query: str, limit: int) -> list["Track"]:
        """Return a list of tracks matching the free-text query."""
        raise NotImplementedError

    @abstractmethod
    async def download(self, track: "Track", dest_dir: Path) -> Path | None:
        """Download the track's audio and return the resulting file path."""
        raise NotImplementedError


@dataclass
class Track:
    """A single search result / playlist entry."""

    source: str          # which source produced it (e.g. "youtube")
    id: str              # source-specific identifier / URL
    title: str           # song title
    artist: str = ""     # artist / uploader if known
    duration: int = 0    # seconds
    views: int = 0       # popularity signal (view count), used for sorting

    @property
    def label(self) -> str:
        """
        Text shown on the selection button.

        Format follows the reference UI: SONG TITLE first, then the creator,
        separated by an em dash — e.g. "FREAK (Hardstyle) - Slowed — Fyex".
        """
        who = f" — {self.artist}" if self.artist else ""
        text = f"{self.title}{who}".strip()
        # Telegram button text limit is 64 characters; keep a safe margin.
        return text[:58] + "…" if len(text) > 60 else text
