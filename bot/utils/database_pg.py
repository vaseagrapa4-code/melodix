"""
PostgreSQL storage layer (for Neon / any Postgres).

Mirrors the SQLite `Database` class API exactly, so the rest of the bot does
not care which backend is used. Selected automatically when DATABASE_URL is a
postgres:// / postgresql:// connection string (see database.create_database).

Uses asyncpg with a small connection pool. Great for free cloud Postgres like
Neon or Supabase, where data is permanent across restarts/redeploys.
"""

import json
import logging
import secrets
import time

import asyncpg

logger = logging.getLogger(__name__)

RECENT_LIMIT = 10
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class PostgresDatabase:
    def __init__(self, dsn: str) -> None:
        # Neon requires SSL; asyncpg understands sslmode in the URL, but we
        # also normalise the scheme it expects.
        self.dsn = dsn.replace("postgresql+asyncpg://", "postgresql://")
        self.pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id        BIGINT PRIMARY KEY,
                    language       TEXT NOT NULL,
                    name           TEXT DEFAULT '',
                    download_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS recent_tracks (
                    id         BIGSERIAL PRIMARY KEY,
                    user_id    BIGINT NOT NULL,
                    data       TEXT NOT NULL,
                    created_at BIGINT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_recent_user
                    ON recent_tracks(user_id, id DESC);

                CREATE TABLE IF NOT EXISTS playlists (
                    code        TEXT PRIMARY KEY,
                    owner_id    BIGINT NOT NULL,
                    owner_name  TEXT DEFAULT '',
                    name        TEXT NOT NULL,
                    photo_id    TEXT DEFAULT '',
                    uses        INTEGER NOT NULL DEFAULT 0,
                    created_at  BIGINT NOT NULL
                );
                ALTER TABLE playlists ADD COLUMN IF NOT EXISTS owner_name TEXT DEFAULT '';
                ALTER TABLE playlists ADD COLUMN IF NOT EXISTS photo_id TEXT DEFAULT '';
                ALTER TABLE playlists ADD COLUMN IF NOT EXISTS is_private INTEGER NOT NULL DEFAULT 0;

                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    id            BIGSERIAL PRIMARY KEY,
                    playlist_code TEXT NOT NULL
                        REFERENCES playlists(code) ON DELETE CASCADE,
                    data          TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pltracks_code
                    ON playlist_tracks(playlist_code);

                CREATE TABLE IF NOT EXISTS playlist_openers (
                    playlist_code TEXT NOT NULL
                        REFERENCES playlists(code) ON DELETE CASCADE,
                    user_id       BIGINT NOT NULL,
                    PRIMARY KEY (playlist_code, user_id)
                );
                """
            )
        logger.info("Database ready (PostgreSQL)")

    # ------------------------------------------------------------------ #
    #  Users / language                                                  #
    # ------------------------------------------------------------------ #
    async def get_language(self, user_id: int) -> str | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT language FROM users WHERE user_id = $1", user_id
            )
            return row["language"] if row else None

    async def set_language(self, user_id: int, language: str, name: str = "") -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, language, name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                    language = EXCLUDED.language,
                    name = CASE WHEN EXCLUDED.name <> ''
                                THEN EXCLUDED.name ELSE users.name END
                """,
                user_id, language, name,
            )

    async def ensure_user(self, user_id: int, language: str, name: str = "") -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (user_id, language, name)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET
                    name = CASE WHEN EXCLUDED.name <> ''
                                THEN EXCLUDED.name ELSE users.name END
                """,
                user_id, language, name,
            )

    # ------------------------------------------------------------------ #
    #  Download counter + user leaderboard                               #
    # ------------------------------------------------------------------ #
    async def increment_downloads(self, user_id: int) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET download_count = download_count + 1 "
                "WHERE user_id = $1",
                user_id,
            )

    async def top_downloaders(self, limit: int = 10) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT user_id, name, download_count
                FROM users
                WHERE download_count > 0
                ORDER BY download_count DESC, user_id ASC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    #  Recent tracks                                                     #
    # ------------------------------------------------------------------ #
    async def add_recent_track(self, user_id: int, track: dict) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO recent_tracks (user_id, data, created_at) "
                "VALUES ($1, $2, $3)",
                user_id, json.dumps(track), int(time.time()),
            )
            await conn.execute(
                """
                DELETE FROM recent_tracks
                WHERE user_id = $1 AND id NOT IN (
                    SELECT id FROM recent_tracks
                    WHERE user_id = $1 ORDER BY id DESC LIMIT $2
                )
                """,
                user_id, RECENT_LIMIT,
            )

    async def get_recent_tracks(self, user_id: int) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM recent_tracks WHERE user_id = $1 ORDER BY id DESC",
                user_id,
            )
            return [json.loads(r["data"]) for r in rows]

    # ------------------------------------------------------------------ #
    #  Playlists                                                         #
    # ------------------------------------------------------------------ #
    async def _gen_code(self, conn) -> str:
        while True:
            code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))
            exists = await conn.fetchrow(
                "SELECT 1 FROM playlists WHERE code = $1", code
            )
            if not exists:
                return code

    async def create_playlist(
        self, owner_id: int, name: str, owner_name: str = "",
        custom_code: str = "", is_private: bool = False,
    ) -> tuple[str, str | None]:
        from .database import (MAX_PLAYLISTS_PER_USER, PlaylistError,
                               is_valid_custom_code, normalize_code)

        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM playlists WHERE owner_id = $1", owner_id
            )
            if count >= MAX_PLAYLISTS_PER_USER:
                return PlaylistError.TOO_MANY_PLAYLISTS, None
            dupe = await conn.fetchrow(
                "SELECT 1 FROM playlists WHERE owner_id = $1 "
                "AND LOWER(name) = LOWER($2)",
                owner_id, name,
            )
            if dupe:
                return PlaylistError.NAME_TAKEN, None

            if custom_code:
                if not is_valid_custom_code(custom_code):
                    return PlaylistError.BAD_CODE, None
                code = normalize_code(custom_code)
                taken = await conn.fetchrow(
                    "SELECT 1 FROM playlists WHERE code = $1", code
                )
                if taken:
                    return PlaylistError.CODE_TAKEN, None
            else:
                code = await self._gen_code(conn)

            await conn.execute(
                "INSERT INTO playlists "
                "(code, owner_id, owner_name, name, is_private, created_at) "
                "VALUES ($1, $2, $3, $4, $5, $6)",
                code, owner_id, owner_name, name,
                1 if is_private else 0, int(time.time()),
            )
            return PlaylistError.OK, code

    async def set_playlist_photo(self, code: str, photo_id: str, owner_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE playlists SET photo_id = $1 "
                "WHERE code = $2 AND owner_id = $3",
                photo_id, code, owner_id,
            )
            return result.endswith("1")

    async def get_playlist(self, code: str) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM playlists WHERE code = $1", code
            )
            return dict(row) if row else None

    async def list_user_playlists(self, owner_id: int) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.code, p.owner_id, p.name, p.uses, p.created_at,
                       COUNT(t.id) AS track_count
                FROM playlists p
                LEFT JOIN playlist_tracks t ON t.playlist_code = p.code
                WHERE p.owner_id = $1
                GROUP BY p.code
                ORDER BY p.created_at DESC
                """,
                owner_id,
            )
            return [dict(r) for r in rows]

    async def add_track_to_playlist(self, code: str, track: dict) -> str:
        from .database import MAX_TRACKS_PER_PLAYLIST, PlaylistError

        async with self.pool.acquire() as conn:
            exists = await conn.fetchrow(
                "SELECT 1 FROM playlists WHERE code = $1", code
            )
            if not exists:
                return PlaylistError.NOT_FOUND
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM playlist_tracks WHERE playlist_code = $1",
                code,
            )
            if count >= MAX_TRACKS_PER_PLAYLIST:
                return PlaylistError.PLAYLIST_FULL
            await conn.execute(
                "INSERT INTO playlist_tracks (playlist_code, data) "
                "VALUES ($1, $2)",
                code, json.dumps(track),
            )
            return PlaylistError.OK

    async def get_playlist_tracks(self, code: str) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM playlist_tracks WHERE playlist_code = $1 "
                "ORDER BY id ASC",
                code,
            )
            return [json.loads(r["data"]) for r in rows]

    async def delete_playlist(self, code: str, owner_id: int) -> bool:
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM playlists WHERE code = $1 AND owner_id = $2",
                code, owner_id,
            )
            # asyncpg returns e.g. "DELETE 1"
            return result.endswith("1")

    async def increment_playlist_uses(self, code: str, user_id: int = 0) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE playlists SET uses = uses + 1 WHERE code = $1", code
            )
            if user_id:
                await conn.execute(
                    "INSERT INTO playlist_openers (playlist_code, user_id) "
                    "VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    code, user_id,
                )

    async def top_playlists(self, limit: int = 10) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.code, p.name, p.owner_name,
                       COUNT(DISTINCT o.user_id) AS people
                FROM playlists p
                LEFT JOIN playlist_openers o ON o.playlist_code = p.code
                WHERE p.is_private = 0
                GROUP BY p.code
                HAVING COUNT(DISTINCT o.user_id) > 0
                ORDER BY people DESC, p.uses DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]
