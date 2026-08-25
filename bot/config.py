"""
Central configuration for the bot.

Every setting is read from environment variables (loaded from the .env file),
so you never hard-code secrets like the bot token in the source code.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a .env file located in the project root (if present).
load_dotenv()

# Project root = the folder that contains this "bot" package's parent.
BASE_DIR = Path(__file__).resolve().parent.parent


def _get_bool(name: str, default: bool = False) -> bool:
    """Read a boolean-like environment variable."""
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    """Holds all runtime configuration in one typed object."""

    bot_token: str
    default_language: str = "ru"
    music_sources: list[str] = field(default_factory=lambda: ["ytmusic", "youtube"])
    max_file_size_mb: int = 49
    max_search_results: int = 24
    page_size: int = 8
    download_dir: Path = BASE_DIR / "downloads"
    database_path: Path = BASE_DIR / "data" / "bot.db"
    database_url: str = ""  # if set to a postgres:// URL, use Postgres instead
    log_level: str = "INFO"

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


def load_config() -> Config:
    """
    Build a Config object from environment variables.

    Raises a clear error if the required BOT_TOKEN is missing so the user
    immediately understands what to fix.
    """
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or "PUT-YOUR-REAL-TOKEN" in token:
        raise RuntimeError(
            "BOT_TOKEN is not set. Copy .env.example to .env and paste the "
            "token you got from @BotFather."
        )

    sources_raw = os.getenv("MUSIC_SOURCES", "ytmusic,youtube")
    sources = [s.strip() for s in sources_raw.split(",") if s.strip()]

    download_dir = BASE_DIR / os.getenv("DOWNLOAD_DIR", "downloads")
    database_path = BASE_DIR / os.getenv("DATABASE_PATH", "data/bot.db")

    # Make sure the folders we need actually exist.
    download_dir.mkdir(parents=True, exist_ok=True)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    return Config(
        bot_token=token,
        default_language=os.getenv("DEFAULT_LANGUAGE", "ru").strip(),
        music_sources=sources,
        max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "49")),
        max_search_results=int(os.getenv("MAX_SEARCH_RESULTS", "24")),
        page_size=int(os.getenv("PAGE_SIZE", "8")),
        download_dir=download_dir,
        database_path=database_path,
        database_url=os.getenv("DATABASE_URL", "").strip(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
    )
