"""
SQLite storage layer.

Tables
------
users            : each user's chosen language + display name + download count
recent_tracks    : the last tracks a user received (used by /cut to pick a song)
playlists        : user-created playlists, each identified by a short CODE
playlist_tracks  : the tracks that belong to a playlist

We use plain sqlite3 wrapped in asyncio.to_thread so the event loop is never
blocked. For a small/medium bot this is simple and fast enough.
"""

import asyncio
import json
import logging
import secrets
import sqlite3
import string
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# How many recent tracks to remember per user (for the /cut picker).
RECENT_LIMIT = 10

# Playlist limits (protect the free database from abuse).
MAX_TRACKS_PER_PLAYLIST = 500
MAX_PLAYLISTS_PER_USER = 50

# Alphabet for share codes (no ambiguous chars like O/0, I/1).
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


# Result codes returned by create_playlist / add_track_to_playlist so handlers
# can show the right message.
class PlaylistError:
    OK = "ok"
    NAME_TAKEN = "name_taken"
    TOO_MANY_PLAYLISTS = "too_many_playlists"
    PLAYLIST_FULL = "playlist_full"
    NOT_FOUND = "not_found"
    CODE_TAKEN = "code_taken"       # custom code already used by someone
    BAD_CODE = "bad_code"          # custom code has invalid characters/length
    PRIVATE = "private"            # playlist is private, not the owner


# Rules for a custom playlist code (e.g. "Music").
CODE_MIN_LEN = 3
CODE_MAX_LEN = 20
_CODE_ALLOWED = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"


def normalize_code(code: str) -> str:
    """Normalize a code to the canonical form used for storage/lookup."""
    return (code or "").strip().upper()


def is_valid_custom_code(code: str) -> bool:
    """Check a user-supplied custom code (letters/digits/underscore only)."""
    c = normalize_code(code)
    if not (CODE_MIN_LEN <= len(c) <= CODE_MAX_LEN):
        return False
    return all(ch in _CODE_ALLOWED for ch in c)


def create_database(database_url: str | None, sqlite_path: Path):
    """
    Choose the storage backend automatically.

    * If DATABASE_URL is a postgres connection string (postgres:// or
      postgresql://) -> use PostgreSQL (permanent cloud DB, e.g. Neon).
    * Otherwise -> use local SQLite at sqlite_path.

    Both backends expose the exact same async methods, so the rest of the bot
    does not change.
    """
    if database_url and database_url.startswith(("postgres://", "postgresql://")):
        from .database_pg import PostgresDatabase

        logger.info("Using PostgreSQL storage backend")
        return PostgresDatabase(database_url)
    logger.info("Using SQLite storage backend")
    return Database(sqlite_path)


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # better concurrency
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ------------------------------------------------------------------ #
    #  Schema                                                            #
    # ------------------------------------------------------------------ #
    async def init(self) -> None:
        def _create() -> None:
            with self._connect() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id        INTEGER PRIMARY KEY,
                        language       TEXT NOT NULL,
                        name           TEXT DEFAULT '',
                        download_count INTEGER NOT NULL DEFAULT 0
                    );

                    CREATE TABLE IF NOT EXISTS recent_tracks (
                        id        INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id   INTEGER NOT NULL,
                        data      TEXT NOT NULL,     -- JSON of the Track
                        created_at INTEGER NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_recent_user
                        ON recent_tracks(user_id, id DESC);

                    CREATE TABLE IF NOT EXISTS playlists (
                        code        TEXT PRIMARY KEY,
                        owner_id    INTEGER NOT NULL,
                        owner_name  TEXT DEFAULT '',
                        name        TEXT NOT NULL,
                        photo_id    TEXT DEFAULT '',
                        is_private  INTEGER NOT NULL DEFAULT 0,
                        uses        INTEGER NOT NULL DEFAULT 0,
                        created_at  INTEGER NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS playlist_tracks (
                        id           INTEGER PRIMARY KEY AUTOINCREMENT,
                        playlist_code TEXT NOT NULL,
                        data         TEXT NOT NULL,   -- JSON of the Track
                        FOREIGN KEY (playlist_code)
                            REFERENCES playlists(code) ON DELETE CASCADE
                    );
                    CREATE INDEX IF NOT EXISTS idx_pltracks_code
                        ON playlist_tracks(playlist_code);

                    -- Which distinct users have opened/tried each playlist.
                    -- Used for the "people who tried it" leaderboard metric.
                    CREATE TABLE IF NOT EXISTS playlist_openers (
                        playlist_code TEXT NOT NULL,
                        user_id       INTEGER NOT NULL,
                        PRIMARY KEY (playlist_code, user_id),
                        FOREIGN KEY (playlist_code)
                            REFERENCES playlists(code) ON DELETE CASCADE
                    );
                    """
                )
                conn.commit()

        await asyncio.to_thread(_create)
        await asyncio.to_thread(self._migrate)
        logger.info("Database ready at %s", self.path)

    def _migrate(self) -> None:
        """
        Add any columns that are missing from older database versions.

        SQLite's "CREATE TABLE IF NOT EXISTS" never alters an existing table,
        so when we add new columns in a new bot version we must patch old DBs
        here. This makes upgrades seamless — no need to delete data/bot.db.
        """
        with self._connect() as conn:
            # Which columns already exist on the users table?
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
            migrations = {
                "name": "ALTER TABLE users ADD COLUMN name TEXT DEFAULT ''",
                "download_count": "ALTER TABLE users ADD COLUMN download_count INTEGER NOT NULL DEFAULT 0",
            }
            for column, sql in migrations.items():
                if column not in cols:
                    logger.info("Migrating DB: adding users.%s", column)
                    conn.execute(sql)

            # New playlist columns (owner_name, photo_id) for older DBs.
            pcols = {row["name"] for row in conn.execute("PRAGMA table_info(playlists)")}
            pmig = {
                "owner_name": "ALTER TABLE playlists ADD COLUMN owner_name TEXT DEFAULT ''",
                "photo_id": "ALTER TABLE playlists ADD COLUMN photo_id TEXT DEFAULT ''",
                "is_private": "ALTER TABLE playlists ADD COLUMN is_private INTEGER NOT NULL DEFAULT 0",
            }
            for column, sql in pmig.items():
                if column not in pcols:
                    logger.info("Migrating DB: adding playlists.%s", column)
                    conn.execute(sql)
            conn.commit()

    # ------------------------------------------------------------------ #
    #  Users / language                                                  #
    # ------------------------------------------------------------------ #
    async def get_language(self, user_id: int) -> str | None:
        def _get() -> str | None:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT language FROM users WHERE user_id = ?", (user_id,)
                ).fetchone()
                return row["language"] if row else None

        return await asyncio.to_thread(_get)

    async def set_language(self, user_id: int, language: str, name: str = "") -> None:
        def _set() -> None:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (user_id, language, name)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        language = excluded.language,
                        name = CASE WHEN excluded.name != ''
                                    THEN excluded.name ELSE users.name END
                    """,
                    (user_id, language, name),
                )
                conn.commit()

        await asyncio.to_thread(_set)

    async def ensure_user(self, user_id: int, language: str, name: str = "") -> None:
        """Create the user row if it does not exist (keeps existing language)."""
        def _ensure() -> None:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO users (user_id, language, name)
                    VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        name = CASE WHEN excluded.name != ''
                                    THEN excluded.name ELSE users.name END
                    """,
                    (user_id, language, name),
                )
                conn.commit()

        await asyncio.to_thread(_ensure)

    # ------------------------------------------------------------------ #
    #  Download counter + user leaderboard                               #
    # ------------------------------------------------------------------ #
    async def increment_downloads(self, user_id: int) -> None:
        def _inc() -> None:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET download_count = download_count + 1 "
                    "WHERE user_id = ?",
                    (user_id,),
                )
                conn.commit()

        await asyncio.to_thread(_inc)

    async def top_downloaders(self, limit: int = 10) -> list[dict]:
        def _top() -> list[dict]:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT user_id, name, download_count
                    FROM users
                    WHERE download_count > 0
                    ORDER BY download_count DESC, user_id ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]

        return await asyncio.to_thread(_top)

    # ------------------------------------------------------------------ #
    #  Recent tracks (used by the /cut picker)                           #
    # ------------------------------------------------------------------ #
    async def add_recent_track(self, user_id: int, track: dict) -> None:
        def _add() -> None:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO recent_tracks (user_id, data, created_at) "
                    "VALUES (?, ?, ?)",
                    (user_id, json.dumps(track), int(time.time())),
                )
                # Keep only the newest RECENT_LIMIT rows for this user.
                conn.execute(
                    """
                    DELETE FROM recent_tracks
                    WHERE user_id = ? AND id NOT IN (
                        SELECT id FROM recent_tracks
                        WHERE user_id = ? ORDER BY id DESC LIMIT ?
                    )
                    """,
                    (user_id, user_id, RECENT_LIMIT),
                )
                conn.commit()

        await asyncio.to_thread(_add)

    async def get_recent_tracks(self, user_id: int) -> list[dict]:
        def _get() -> list[dict]:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT data FROM recent_tracks WHERE user_id = ? "
                    "ORDER BY id DESC",
                    (user_id,),
                ).fetchall()
                return [json.loads(r["data"]) for r in rows]

        return await asyncio.to_thread(_get)

    # ------------------------------------------------------------------ #
    #  Playlists                                                         #
    # ------------------------------------------------------------------ #
    def _gen_code(self, conn: sqlite3.Connection) -> str:
        """Generate a short unique code like 'K7QP4M'."""
        while True:
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
            exists = conn.execute(
                "SELECT 1 FROM playlists WHERE code = ?", (code,)
            ).fetchone()
            if not exists:
                return code

    async def create_playlist(
        self, owner_id: int, name: str, owner_name: str = "",
        custom_code: str = "", is_private: bool = False,
    ) -> tuple[str, str | None]:
        """
        Create a playlist.

        Optional:
          custom_code -> a chosen code (e.g. "MUSIC"); must be unique globally.
          is_private  -> if True, only the owner can open it.

        Returns (status, code). status is one of PlaylistError.*:
          OK, NAME_TAKEN, TOO_MANY_PLAYLISTS, BAD_CODE, CODE_TAKEN
        """
        def _create() -> tuple[str, str | None]:
            with self._connect() as conn:
                # Per-user playlist limit.
                count = conn.execute(
                    "SELECT COUNT(*) AS c FROM playlists WHERE owner_id = ?",
                    (owner_id,),
                ).fetchone()["c"]
                if count >= MAX_PLAYLISTS_PER_USER:
                    return PlaylistError.TOO_MANY_PLAYLISTS, None

                # Name must be unique PER USER (case-insensitive).
                dupe = conn.execute(
                    "SELECT 1 FROM playlists WHERE owner_id = ? "
                    "AND LOWER(name) = LOWER(?)",
                    (owner_id, name),
                ).fetchone()
                if dupe:
                    return PlaylistError.NAME_TAKEN, None

                # Determine the code: custom (validated + unique) or random.
                if custom_code:
                    if not is_valid_custom_code(custom_code):
                        return PlaylistError.BAD_CODE, None
                    code = normalize_code(custom_code)
                    taken = conn.execute(
                        "SELECT 1 FROM playlists WHERE code = ?", (code,)
                    ).fetchone()
                    if taken:
                        return PlaylistError.CODE_TAKEN, None
                else:
                    code = self._gen_code(conn)

                conn.execute(
                    "INSERT INTO playlists "
                    "(code, owner_id, owner_name, name, is_private, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (code, owner_id, owner_name, name,
                     1 if is_private else 0, int(time.time())),
                )
                conn.commit()
                return PlaylistError.OK, code

        return await asyncio.to_thread(_create)

    async def set_playlist_photo(self, code: str, photo_id: str, owner_id: int) -> bool:
        """Set the small cover photo (Telegram file_id) — owner only."""
        def _set() -> bool:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE playlists SET photo_id = ? "
                    "WHERE code = ? AND owner_id = ?",
                    (photo_id, code, owner_id),
                )
                conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_set)

    async def get_playlist(self, code: str) -> dict | None:
        def _get() -> dict | None:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM playlists WHERE code = ?", (code,)
                ).fetchone()
                return dict(row) if row else None

        return await asyncio.to_thread(_get)

    async def list_user_playlists(self, owner_id: int) -> list[dict]:
        def _list() -> list[dict]:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT p.*, COUNT(t.id) AS track_count
                    FROM playlists p
                    LEFT JOIN playlist_tracks t ON t.playlist_code = p.code
                    WHERE p.owner_id = ?
                    GROUP BY p.code
                    ORDER BY p.created_at DESC
                    """,
                    (owner_id,),
                ).fetchall()
                return [dict(r) for r in rows]

        return await asyncio.to_thread(_list)

    async def add_track_to_playlist(self, code: str, track: dict) -> str:
        """
        Add a track to a playlist.

        Returns a PlaylistError status:
          OK            -> added
          NOT_FOUND     -> no such playlist
          PLAYLIST_FULL -> reached MAX_TRACKS_PER_PLAYLIST
        """
        def _add() -> str:
            with self._connect() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM playlists WHERE code = ?", (code,)
                ).fetchone()
                if not exists:
                    return PlaylistError.NOT_FOUND
                count = conn.execute(
                    "SELECT COUNT(*) AS c FROM playlist_tracks "
                    "WHERE playlist_code = ?",
                    (code,),
                ).fetchone()["c"]
                if count >= MAX_TRACKS_PER_PLAYLIST:
                    return PlaylistError.PLAYLIST_FULL
                conn.execute(
                    "INSERT INTO playlist_tracks (playlist_code, data) "
                    "VALUES (?, ?)",
                    (code, json.dumps(track)),
                )
                conn.commit()
                return PlaylistError.OK

        return await asyncio.to_thread(_add)

    async def get_playlist_tracks(self, code: str) -> list[dict]:
        def _get() -> list[dict]:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT data FROM playlist_tracks WHERE playlist_code = ? "
                    "ORDER BY id ASC",
                    (code,),
                ).fetchall()
                return [json.loads(r["data"]) for r in rows]

        return await asyncio.to_thread(_get)

    async def delete_playlist(self, code: str, owner_id: int) -> bool:
        """Delete a playlist only if the requester owns it."""
        def _del() -> bool:
            with self._connect() as conn:
                cur = conn.execute(
                    "DELETE FROM playlists WHERE code = ? AND owner_id = ?",
                    (code, owner_id),
                )
                conn.commit()
                return cur.rowcount > 0

        return await asyncio.to_thread(_del)

    async def increment_playlist_uses(self, code: str, user_id: int = 0) -> None:
        """
        Record that a playlist was opened/used.

        Increments the total 'uses' counter and, if a user_id is given, records
        that DISTINCT user as an opener (for the "people who tried it" metric).
        """
        def _inc() -> None:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE playlists SET uses = uses + 1 WHERE code = ?",
                    (code,),
                )
                if user_id:
                    conn.execute(
                        "INSERT OR IGNORE INTO playlist_openers "
                        "(playlist_code, user_id) VALUES (?, ?)",
                        (code, user_id),
                    )
                conn.commit()

        await asyncio.to_thread(_inc)

    async def top_playlists(self, limit: int = 10) -> list[dict]:
        """
        Most popular playlists, ranked by how many DISTINCT people tried them.
        """
        def _top() -> list[dict]:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT p.code, p.name, p.owner_name,
                           COUNT(DISTINCT o.user_id) AS people
                    FROM playlists p
                    LEFT JOIN playlist_openers o ON o.playlist_code = p.code
                    WHERE p.is_private = 0
                    GROUP BY p.code
                    HAVING people > 0
                    ORDER BY people DESC, p.uses DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]

        return await asyncio.to_thread(_top)
