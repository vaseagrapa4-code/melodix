"""
Tiny internationalization (i18n) helper.

All translations live in bot/locales/*.json. Each file is one language and
contains the same set of keys. To add a new language you simply drop a new
JSON file in that folder — no code changes needed.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


class Translator:
    """Loads every locale file once and serves translated strings."""

    def __init__(self, default_language: str = "ru") -> None:
        self.default_language = default_language
        self._translations: dict[str, dict[str, str]] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Read every *.json file inside the locales folder."""
        for file in sorted(LOCALES_DIR.glob("*.json")):
            lang_code = file.stem  # "ru.json" -> "ru"
            try:
                with file.open(encoding="utf-8") as fh:
                    self._translations[lang_code] = json.load(fh)
                logger.info("Loaded locale: %s", lang_code)
            except (OSError, json.JSONDecodeError) as exc:
                logger.error("Failed to load locale %s: %s", lang_code, exc)

        if self.default_language not in self._translations:
            # Fall back to any available language so the bot still runs.
            available = list(self._translations)
            if not available:
                raise RuntimeError("No locale files found in bot/locales/")
            logger.warning(
                "Default language '%s' missing, falling back to '%s'",
                self.default_language,
                available[0],
            )
            self.default_language = available[0]

    @property
    def languages(self) -> list[str]:
        """List of available language codes, e.g. ['en', 'ro', 'ru']."""
        return list(self._translations)

    def language_name(self, lang: str) -> str:
        """Human-readable name of a language, used on the menu buttons."""
        return self._translations.get(lang, {}).get("language_name", lang)

    def get(self, lang: str, key: str, **kwargs) -> str:
        """
        Return the translated string for `key` in language `lang`.

        Falls back to the default language, then to the key itself, so a
        missing translation never crashes the bot. `kwargs` are used for
        formatting placeholders like {query} or {limit}.
        """
        table = self._translations.get(lang) or self._translations.get(
            self.default_language, {}
        )
        text = table.get(key)
        if text is None:
            # Try the default language explicitly, then give up gracefully.
            text = self._translations.get(self.default_language, {}).get(key, key)
        try:
            return text.format(**kwargs) if kwargs else text
        except (KeyError, IndexError):
            return text
