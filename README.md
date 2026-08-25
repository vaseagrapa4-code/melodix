# 🎵 Telegram Music Bot

A complete, well-structured Telegram bot (Python + **aiogram 3**) that:

- **Multi-language** – `/start` shows a language menu (Russian included, always). Switch anytime with `/language`. Add new languages by dropping a JSON file in `bot/locales/`.
- **Music search & download** – type a **song title**, an **artist name**, or a **line of lyrics**; the bot searches, shows a result list, and sends the audio file.
- **Multiple sources with auto-fallback** – uses YouTube Music + YouTube via `yt-dlp`; if one source fails it automatically tries the next.
- **Audio editing** – `/cut` trims a track between two timecodes (`00:00:30 00:01:15`) and returns a **new** audio file.
- **Production niceties** – `.env` configuration, SQLite persistence, logging, and error handling throughout.

---

## 📁 Project structure

```
telegram-music-bot/
├─ bot/
│  ├─ main.py                  # entry point (python -m bot.main)
│  ├─ config.py                # reads settings from .env
│  ├─ handlers/
│  │  ├─ __init__.py           # combines all routers
│  │  ├─ common.py             # /start, /help, /cancel
│  │  ├─ language.py           # /language + language buttons
│  │  ├─ music.py              # text search + result buttons + download
│  │  ├─ audio_edit.py         # /cut trimming flow
│  │  └─ states.py             # FSM states
│  ├─ keyboards/
│  │  └─ inline.py             # inline keyboards (languages, results)
│  ├─ locales/
│  │  ├─ ru.json               # Russian  (mandatory)
│  │  ├─ en.json               # English
│  │  └─ ro.json               # Romanian
│  ├─ services/
│  │  ├─ music_service.py      # orchestrates sources + fallback logic
│  │  └─ sources/
│  │     ├─ base.py            # Track model + MusicSource interface
│  │     └─ ytdlp_source.py    # YouTube / YouTube Music sources
│  └─ utils/
│     ├─ i18n.py               # translation loader
│     ├─ database.py           # SQLite: remembers each user's language
│     └─ audio.py              # timecode parsing + ffmpeg cutting
├─ data/                       # SQLite DB lives here (auto-created)
├─ downloads/                  # temporary audio files (auto-cleaned)
├─ .env.example               # copy to .env and fill in
├─ requirements.txt
└─ README.md
```

---

## 🚀 Quick start

> Full beginner tutorial (what to download and where) is in **TUTORIAL.md**.

```bash
# 1. Install ffmpeg (required for downloading + cutting)
#    Windows: https://www.gyan.dev/ffmpeg/builds/  (add to PATH)
#    macOS:   brew install ffmpeg
#    Ubuntu:  sudo apt install ffmpeg

# 2. Create a virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure
cp .env.example .env               # Windows: copy .env.example .env
#    then edit .env and paste your BOT_TOKEN from @BotFather

# 4. Run
python -m bot.main
```

Open your bot in Telegram and send `/start`.

---

## ⚙️ Configuration (.env)

| Variable            | Meaning                                              | Default          |
|---------------------|------------------------------------------------------|------------------|
| `BOT_TOKEN`         | Token from @BotFather (**required**)                 | –                |
| `DEFAULT_LANGUAGE`  | Language before the user picks one                   | `ru`             |
| `MUSIC_SOURCES`     | Ordered, comma-separated sources to try              | `ytmusic,youtube`|
| `MAX_FILE_SIZE_MB`  | Max audio size to send (Telegram bot limit is 50)    | `49`             |
| `MAX_SEARCH_RESULTS`| How many results to show                             | `8`              |
| `DOWNLOAD_DIR`      | Temp folder for audio                                | `downloads`      |
| `DATABASE_PATH`     | SQLite file                                          | `data/bot.db`    |
| `LOG_LEVEL`         | DEBUG / INFO / WARNING / ERROR                       | `INFO`           |

---

## ➕ Adding a new language

1. Copy `bot/locales/en.json` to e.g. `bot/locales/de.json`.
2. Translate every value (keep the keys unchanged).
3. Set `language_name` to the name shown on the button (e.g. `"Deutsch"`).
4. Restart the bot — the new language appears in the menu automatically.

## ➕ Adding a new music source

1. Create a class in `bot/services/sources/` that subclasses `MusicSource`
   and implements `search()` and `download()`.
2. Register it in `_SOURCE_REGISTRY` in `bot/services/music_service.py`.
3. Add its name to `MUSIC_SOURCES` in `.env`.

---

## 🧩 How the pieces fit

- `main.py` loads config, builds the shared services (DB, translator, music),
  injects them into every handler, and starts long-polling.
- Free-text messages → `music.py` → `MusicService.search()` → result buttons.
- Tapping a result → `MusicService.download()` (with source fallback) → audio.
- `/cut` → `audio_edit.py` collects an audio file + timecodes → `utils/audio.cut_audio()`.

## ⚠️ Notes & legal

- `yt-dlp` downloads from YouTube. Downloading copyrighted material may be
  restricted in your country / by YouTube's Terms of Service. Use responsibly
  and only for content you are allowed to download.
- Telegram bots can send files up to **50 MB**. Larger tracks are rejected with
  a friendly message.
