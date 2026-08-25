"""
Music sources powered by yt-dlp.

yt-dlp can search YouTube with a plain text query, which naturally handles
searches by song title, artist name, OR a snippet of the lyrics (YouTube's
search indexes lyric text). It then downloads the best audio stream and
converts it to mp3 via ffmpeg.

We expose two logical sources so that if one is throttled the bot automatically
tries the other:
  * YouTubeSource  -> regular YouTube search  (ytsearch)
  * YTMusicSource  -> YouTube Music search    (music.youtube.com/search URL)

Note: yt-dlp has NO "ytmsearch" prefix, so YouTube Music is queried through its
search URL and the results are filtered to real playable tracks.
"""

import asyncio
import base64
import logging
import os
import tempfile
import urllib.parse
from pathlib import Path

import yt_dlp

from .base import MusicSource, Track

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Cookies support (needed on cloud servers).
#  YouTube blocks data-center IPs with "Sign in to confirm you're not a bot".
#  Passing cookies from a logged-in browser session fixes this.
#
#  Two ways to provide cookies (checked in this order):
#    1. YT_COOKIES_B64  -> the whole cookies.txt, base64-encoded (best for
#                          Render/cloud: paste it as one env var).
#    2. COOKIES_FILE    -> a path to a cookies.txt file on disk.
# ---------------------------------------------------------------------------
_COOKIES_FILE_ENV = os.getenv("COOKIES_FILE", "cookies.txt")
_COOKIES_B64_ENV = "YT_COOKIES_B64"
_cookies_path_cache: str | None = None


def _get_cookies_file() -> str | None:
    """Return a path to a cookies.txt, materializing it from base64 if needed."""
    global _cookies_path_cache
    if _cookies_path_cache and Path(_cookies_path_cache).exists():
        return _cookies_path_cache

    # 1) Base64 env var (best for cloud hosts).
    b64 = os.getenv(_COOKIES_B64_ENV)
    if b64:
        try:
            data = base64.b64decode(b64)
            tmp = Path(tempfile.gettempdir()) / "yt_cookies.txt"
            tmp.write_bytes(data)
            _cookies_path_cache = str(tmp)
            logger.info("Loaded YouTube cookies from %s", _COOKIES_B64_ENV)
            return _cookies_path_cache
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not decode %s: %s", _COOKIES_B64_ENV, exc)

    # 2) A cookies file on disk.
    if _COOKIES_FILE_ENV and Path(_COOKIES_FILE_ENV).exists():
        _cookies_path_cache = _COOKIES_FILE_ENV
        return _cookies_path_cache

    return None


def _with_cookies(opts: dict) -> dict:
    """Add the cookiefile option to a yt-dlp options dict, if cookies exist."""
    cookies = _get_cookies_file()
    if cookies:
        opts["cookiefile"] = cookies
    return opts


# Extensions Telegram plays natively as audio -> no conversion needed.
_PLAYABLE_EXTS = {".mp3", ".m4a", ".aac"}


def _ensure_playable(path: Path) -> Path:
    """
    Make sure the audio file is in a Telegram-friendly format.

    If it's already mp3/m4a/aac we return it untouched (NO re-encoding — fast).
    Only webm/opus/ogg get converted to m4a (fast copy of the AAC/Opus stream
    into an m4a container when possible, else a light re-encode).
    """
    import subprocess

    if path.suffix.lower() in _PLAYABLE_EXTS:
        return path

    out = path.with_suffix(".m4a")
    # First try a stream COPY (no re-encode) — instant. Works if the source is
    # already AAC. If it fails (e.g. Opus), fall back to a light AAC re-encode.
    for args in (
        ["-c:a", "copy"],
        ["-c:a", "aac", "-b:a", "192k"],
    ):
        try:
            proc = subprocess.run(
                ["ffmpeg", "-y", "-i", str(path), *args, str(out)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=120,
            )
            if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
                return out
        except Exception:  # noqa: BLE001
            continue
    # Conversion failed; return the original file and hope Telegram accepts it.
    return path


class _YtDlpBase(MusicSource):
    """Shared download logic for the YouTube-family sources."""

    async def download(self, track: Track, dest_dir: Path) -> Path | None:
        return await asyncio.to_thread(self._download_sync, track, dest_dir)

    def _download_sync(self, track: Track, dest_dir: Path) -> Path | None:
        url = track.id
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={track.id}"

        out_template = str(dest_dir / "%(id)s.%(ext)s")
        opts = _with_cookies({
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            # Prefer already-compressed audio (m4a/mp3). We do NOT add an
            # ffmpeg postprocessor here — if the file is already m4a/mp3/aac
            # (the common case) we send it as-is with ZERO re-encoding, which
            # is the biggest speed win on slow cloud CPUs. Only webm/opus get
            # converted afterwards by _ensure_playable().
            "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best",
            "outtmpl": out_template,
            "noplaylist": True,
            # Abort early if the audio is larger than the send limit (~50 MB).
            "max_filesize": 50 * 1024 * 1024,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web_safari", "tv"],
                }
            },
        })
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:  # noqa: BLE001 - handled as "no file" / retry
            logger.warning("[%s] download failed for %s: %s", self.name, url, exc)
            info = self._retry_android_only(url, dest_dir)
            if info is None:
                return None
        path = self._find_output(info, dest_dir)
        return _ensure_playable(path) if path else None

    @staticmethod
    def _find_output(info: dict, dest_dir: Path) -> Path | None:
        """Locate the audio file yt-dlp produced (mp3/m4a/etc.)."""
        video_id = (info or {}).get("id")
        if not video_id:
            return None
        # Prefer mp3, then any audio file with this id.
        mp3 = dest_dir / f"{video_id}.mp3"
        if mp3.exists():
            return mp3
        for ext in ("m4a", "webm", "opus", "aac", "ogg"):
            cand = dest_dir / f"{video_id}.{ext}"
            if cand.exists():
                return cand
        for cand in dest_dir.glob(f"{video_id}.*"):
            return cand
        return None

    def _retry_android_only(self, url: str, dest_dir: Path):
        """Last-resort retry using only the android player client."""
        out_template = str(dest_dir / "%(id)s.%(ext)s")
        opts = _with_cookies({
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": out_template,
            "noplaylist": True,
            "max_filesize": 50 * 1024 * 1024,
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        })
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[%s] android retry failed for %s: %s", self.name, url, exc)
            return None

    @staticmethod
    def _to_track(entry: dict, source_name: str) -> Track | None:
        """Convert a yt-dlp flat entry into a Track, skipping non-tracks."""
        if not entry:
            return None
        url = entry.get("url") or entry.get("id", "")
        title = entry.get("title")
        # Skip entries that are not playable songs (channels, playlists, etc.).
        if not title or "/watch" not in (url if url.startswith("http") else "/watch"):
            # For plain video ids (regular ytsearch) there is no '/watch' in the
            # url, so only apply the watch filter to full URLs.
            if url.startswith("http") and "/watch" not in url:
                return None
        if not title:
            return None
        return Track(
            source=source_name,
            id=url,
            title=title,
            artist=entry.get("uploader") or entry.get("channel") or "",
            duration=int(entry.get("duration") or 0),
            views=int(entry.get("view_count") or 0),
        )


class YouTubeSource(_YtDlpBase):
    """Regular YouTube search via the ytsearch prefix."""

    name = "youtube"

    async def search(self, query: str, limit: int) -> list[Track]:
        return await asyncio.to_thread(self._search_sync, query, limit)

    def _search_sync(self, query: str, limit: int) -> list[Track]:
        opts = _with_cookies({
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "extract_flat": True,
            "noplaylist": True,
            "skip_download": True,
        })
        tracks: list[Track] = []
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            for entry in (info or {}).get("entries", []) or []:
                t = self._to_track(entry, self.name)
                if t:
                    tracks.append(t)
        tracks.sort(key=lambda t: t.views, reverse=True)
        logger.info("[%s] '%s' -> %d results", self.name, query, len(tracks))
        return tracks


class YTMusicSource(_YtDlpBase):
    """YouTube Music search via the music.youtube.com search URL."""

    name = "ytmusic"

    async def search(self, query: str, limit: int) -> list[Track]:
        return await asyncio.to_thread(self._search_sync, query, limit)

    def _search_sync(self, query: str, limit: int) -> list[Track]:
        q = urllib.parse.quote(query)
        url = f"https://music.youtube.com/search?q={q}"
        opts = _with_cookies({
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "extract_flat": True,
            "noplaylist": True,
            "skip_download": True,
            # Keep the request small; we filter to tracks afterwards.
            "playlist_items": f"1-{max(limit * 3, 15)}",
        })
        tracks: list[Track] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # noqa: BLE001 - let MusicService try next source
            logger.warning("[ytmusic] search failed: %s", exc)
            return []

        for entry in (info or {}).get("entries", []) or []:
            t = self._to_track(entry, self.name)
            if t:
                tracks.append(t)
            if len(tracks) >= limit:
                break
        logger.info("[%s] '%s' -> %d results", self.name, query, len(tracks))
        return tracks


class SoundCloudSource(_YtDlpBase):
    """
    SoundCloud search + download via yt-dlp (scsearch).

    SoundCloud does NOT block data-center IPs the way YouTube does, so this
    source works reliably on cloud servers (Render) without cookies. It is the
    recommended primary source for hosted deployments.
    """

    name = "soundcloud"

    async def search(self, query: str, limit: int) -> list[Track]:
        return await asyncio.to_thread(self._search_sync, query, limit)

    def _search_sync(self, query: str, limit: int) -> list[Track]:
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "extract_flat": True,
            "noplaylist": True,
            "skip_download": True,
        }
        tracks: list[Track] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"scsearch{limit}:{query}", download=False)
        except Exception as exc:  # noqa: BLE001 - let MusicService try next source
            logger.warning("[soundcloud] search failed: %s", exc)
            return []

        for entry in (info or {}).get("entries", []) or []:
            if not entry:
                continue
            url = entry.get("url") or entry.get("id", "")
            title = entry.get("title")
            if not title or not url:
                continue
            tracks.append(
                Track(
                    source=self.name,
                    id=url,
                    title=title,
                    artist=entry.get("uploader") or entry.get("channel") or "",
                    duration=int(entry.get("duration") or 0),
                    views=int(entry.get("view_count") or 0),
                )
            )
        # SoundCloud search is already relevance-sorted; keep its order.
        logger.info("[%s] '%s' -> %d results", self.name, query, len(tracks))
        return tracks

    def _download_sync(self, track: Track, dest_dir: Path) -> Path | None:
        # SoundCloud needs no cookies / player_client tricks — simple download.
        # No forced re-encode: take the native audio and only fix it if needed.
        out_template = str(dest_dir / "%(id)s.%(ext)s")
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "format": "bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": out_template,
            "noplaylist": True,
            "max_filesize": 50 * 1024 * 1024,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(track.id, download=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[soundcloud] download failed for %s: %s", track.id, exc)
            return None
        path = self._find_output(info, dest_dir)
        return _ensure_playable(path) if path else None
