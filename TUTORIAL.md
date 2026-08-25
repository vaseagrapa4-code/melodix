# 📘 Step-by-Step Tutorial — From Zero to a Running Music Bot

This guide assumes you have **never** done this before. Follow each step in
order. It covers **what to download, where to put it, and what to type**.

---

## ✅ Overview: the 3 things you must install

| # | What            | Why                                        |
|---|-----------------|--------------------------------------------|
| 1 | **Python 3.11+**| Runs the bot code                          |
| 2 | **ffmpeg**      | Converts/cuts audio (required by the bot)  |
| 3 | **The bot files** (this project) | The actual bot           |

Plus one thing you **create online**:

| 4 | **A bot token** from @BotFather | Lets your code control a Telegram bot |

---

## STEP 1 — Install Python

1. Go to **https://www.python.org/downloads/**
2. Download the latest **Python 3.x** for your OS.
3. Run the installer.
   - **Windows users: on the first screen, TICK ✅ “Add Python to PATH”.**
     This is the most common mistake — don't skip it.
4. Verify it works. Open a terminal:
   - Windows: press `Win`, type **cmd**, press Enter.
   - macOS: open **Terminal**.
   - Linux: open your terminal.
5. Type:
   ```bash
   python --version
   ```
   You should see something like `Python 3.12.x`.
   (On macOS/Linux you may need `python3 --version`.)

---

## STEP 2 — Install ffmpeg

ffmpeg is a free tool the bot uses to build and cut audio files.

### Windows
1. Go to **https://www.gyan.dev/ffmpeg/builds/**
2. Under “release builds”, download **`ffmpeg-release-essentials.zip`**.
3. Unzip it, e.g. to `C:\ffmpeg`. Inside you'll find a `bin` folder
   containing `ffmpeg.exe`.
4. Add that `bin` folder to your PATH:
   - Press `Win`, type **“environment variables”**, open
     *“Edit the system environment variables”*.
   - Click **Environment Variables…** → under *System variables* select
     **Path** → **Edit** → **New** → paste `C:\ffmpeg\bin` → OK everywhere.
5. **Close and reopen** the terminal, then test:
   ```bash
   ffmpeg -version
   ```

### macOS
1. Install Homebrew if you don't have it: https://brew.sh
2. Then:
   ```bash
   brew install ffmpeg
   ffmpeg -version
   ```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install ffmpeg
ffmpeg -version
```

If `ffmpeg -version` prints version info, you're good.

---

## STEP 3 — Get the bot files

You already have the project folder **`telegram-music-bot`**. Put it somewhere
easy to find, for example:

- Windows: `C:\Users\YourName\telegram-music-bot`
- macOS/Linux: `/home/yourname/telegram-music-bot`

The folder must contain the `bot/` folder, `requirements.txt`, and
`.env.example` (see the structure in **README.md**).

Open a terminal **inside this folder**:
- Windows: open the folder in File Explorer, click the address bar, type
  `cmd`, press Enter.
- macOS/Linux: `cd /path/to/telegram-music-bot`

---

## STEP 4 — Create your Telegram bot & get the token

1. Open Telegram and search for **@BotFather** (the one with the blue check).
2. Send `/newbot`.
3. Choose a **name** (any text, e.g. “My Music Bot”).
4. Choose a **username** — it must end in `bot` (e.g. `my_music_1234_bot`).
5. BotFather replies with a **token** that looks like:
   ```
   7712345678:AAF3xYz0abcDEFghIJKlmNOpQRstuVWxyz1
   ```
6. **Copy this token.** Keep it secret — anyone with it can control your bot.

---

## STEP 5 — Install the Python dependencies

Inside the project folder, in your terminal:

### 5a. Create a virtual environment (isolates the bot's packages)
```bash
python -m venv .venv
```
(macOS/Linux: use `python3 -m venv .venv` if needed.)

### 5b. Activate it
- **Windows (cmd):**
  ```bash
  .venv\Scripts\activate
  ```
- **Windows (PowerShell):**
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
- **macOS/Linux:**
  ```bash
  source .venv/bin/activate
  ```
Your prompt should now start with `(.venv)`.

### 5c. Install the packages
```bash
pip install -r requirements.txt
```
This installs aiogram, yt-dlp, python-dotenv and mutagen.

---

## STEP 6 — Create your .env file (where your token goes)

The bot reads its settings from a file named **`.env`** in the project root.

1. Make a copy of the example file:
   - **Windows:**
     ```bash
     copy .env.example .env
     ```
   - **macOS/Linux:**
     ```bash
     cp .env.example .env
     ```
2. Open **`.env`** in any text editor (Notepad, VS Code, etc.).
3. Find this line:
   ```
   BOT_TOKEN=123456789:PUT-YOUR-REAL-TOKEN-HERE
   ```
   Replace the right-hand side with the token from BotFather:
   ```
   BOT_TOKEN=7712345678:AAF3xYz0abcDEFghIJKlmNOpQRstuVWxyz1
   ```
4. (Optional) change `DEFAULT_LANGUAGE`, `MUSIC_SOURCES`, etc. Defaults are fine.
5. **Save the file.**

> ⚠️ The file must be named exactly `.env` (not `.env.txt`). In Notepad, choose
> *“Save as type: All Files”* when saving.

---

## STEP 7 — Run the bot

Still inside the project folder, with `(.venv)` active:

```bash
python -m bot.main
```

You should see logs like:
```
... | INFO | Loaded locale: en
... | INFO | Loaded locale: ru
... | INFO | Database ready at .../data/bot.db
... | INFO | Bot is up. Press Ctrl+C to stop.
```

**Leave this terminal open** — the bot runs as long as it's open.
To stop the bot, press `Ctrl+C`.

---

## STEP 8 — Use your bot in Telegram

1. In Telegram, open the chat with your bot (search its `@username`).
2. Send **`/start`** → pick a language (Russian / English / Romanian).
3. **Search music**: just type, for example:
   - a title: `Bohemian Rhapsody`
   - an artist: `Queen`
   - a lyric line: `is this the real life is this just fantasy`
   Then tap the result you want — the bot sends the audio.
4. **Change language** anytime: send **`/language`**.
5. **Cut audio**:
   - Send **`/cut`**
   - Send (or forward) an **audio file**
   - Send the time range, e.g. `00:00:30 00:01:15`
   - The bot returns a **new, trimmed** audio file.
6. **Help**: `/help` · **Cancel** an operation: `/cancel`

---

## 🛟 Troubleshooting

| Problem | Fix |
|--------|-----|
| `'python' is not recognized` | Reinstall Python with **“Add to PATH”** ticked, reopen terminal. |
| `'ffmpeg' is not recognized` / cutting fails | ffmpeg isn't on PATH. Redo **STEP 2** and reopen the terminal. |
| `BOT_TOKEN is not set` | Your `.env` is missing or the token line wasn't edited/saved. Redo **STEP 6**. |
| `pip install` errors | Make sure the venv is active (`(.venv)` in prompt), upgrade pip: `python -m pip install --upgrade pip`. |
| Bot starts but doesn't reply | Check the token is correct; make sure only **one** copy of the bot is running. |
| Downloads fail / “all sources unavailable” | Update yt-dlp: `pip install -U yt-dlp` (YouTube changes often). |
| “File is too big” | Telegram bots can only send up to 50 MB. Pick a shorter track. |

---

## 🔁 Running it again later

Every time you want to start the bot:
```bash
cd /path/to/telegram-music-bot
# activate venv:
source .venv/bin/activate         # Windows: .venv\Scripts\activate
python -m bot.main
```

That's it — you now have a fully working multi-language music bot. 🎉
