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

# Alphabet for share codes (no ambiguous chars like O/0, I/1).
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


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
                        name        TEXT NOT NULL,
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

    async def create_playlist(self, owner_id: int, name: str) -> str:
        def _create() -> str:
            with self._connect() as conn:
                code = self._gen_code(conn)
                conn.execute(
                    "INSERT INTO playlists (code, owner_id, name, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (code, owner_id, name, int(time.time())),
                )
                conn.commit()
                return code

        return await asyncio.to_thread(_create)

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

    async def add_track_to_playlist(self, code: str, track: dict) -> bool:
        def _add() -> bool:
            with self._connect() as conn:
                exists = conn.execute(
                    "SELECT 1 FROM playlists WHERE code = ?", (code,)
                ).fetchone()
                if not exists:
                    return False
                conn.execute(
                    "INSERT INTO playlist_tracks (playlist_code, data) "
                    "VALUES (?, ?)",
                    (code, json.dumps(track)),
                )
                conn.commit()
                return True

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

    async def increment_playlist_uses(self, code: str) -> None:
        """Count when someone opens/uses a shared playlist (popularity)."""
        def _inc() -> None:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE playlists SET uses = uses + 1 WHERE code = ?",
                    (code,),
                )
                conn.commit()

        await asyncio.to_thread(_inc)

    async def top_playlists(self, limit: int = 10) -> list[dict]:
        def _top() -> list[dict]:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT p.code, p.name, p.uses,
                           COUNT(t.id) AS track_count
                    FROM playlists p
                    LEFT JOIN playlist_tracks t ON t.playlist_code = p.code
                    GROUP BY p.code
                    HAVING track_count > 0
                    ORDER BY p.uses DESC, track_count DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]

        return await asyncio.to_thread(_top)
