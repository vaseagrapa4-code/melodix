@echo off
REM ============================================================
REM  One-click launcher for the Telegram Music Bot (Windows)
REM  Just double-click this file, or run:  run.bat
REM  It sets up everything and starts the bot.
REM ============================================================
setlocal
cd /d "%~dp0"

echo ============================================
echo   Telegram Music Bot - one-click launcher
echo ============================================
echo.

REM --- 1. Create the virtual environment if it does not exist ----------
if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: could not create venv. Is Python installed and on PATH?
        pause
        exit /b 1
    )
) else (
    echo [1/4] Virtual environment already exists. OK.
)

REM Use the venv's python directly (no need to "activate").
set "PY=.venv\Scripts\python.exe"

REM --- 2. Upgrade pip and install dependencies ------------------------
echo [2/4] Upgrading pip...
"%PY%" -m pip install --upgrade pip

echo [3/4] Installing dependencies (this may take a minute)...
"%PY%" -m pip install "aiogram>=3.15" "python-dotenv>=1.0.1" mutagen "aiohttp>=3.9"
if errorlevel 1 (
    echo ERROR: dependency installation failed. See messages above.
    pause
    exit /b 1
)

REM Always FORCE the LATEST yt-dlp. TikTok/Instagram/YouTube change their
REM sites often; an outdated yt-dlp causes "Unable to extract universal data
REM for rehydration". We uninstall first so pip cannot say "already satisfied"
REM and skip the update, then install the newest release from PyPI.
echo [3a/4] Forcing the LATEST yt-dlp (fixes TikTok extraction errors)...
"%PY%" -m pip uninstall -y yt-dlp >nul 2>&1
"%PY%" -m pip install --upgrade --no-cache-dir --force-reinstall yt-dlp
echo Installed yt-dlp version:
"%PY%" -m yt_dlp --version



REM --- 3. Create the .env file with the token if it is missing --------
if not exist ".env" (
    echo [4/4] Creating .env file with your bot token...
    (
        echo BOT_TOKEN=8917400851:AAGBBmcgMPczZdVWJ4K0eAindldSm3nu_xU
        echo DEFAULT_LANGUAGE=ru
        echo MUSIC_SOURCES=ytmusic,youtube
        echo MAX_FILE_SIZE_MB=49
        echo MAX_SEARCH_RESULTS=24
        echo PAGE_SIZE=8
        echo DOWNLOAD_DIR=downloads
        echo DATABASE_PATH=data/bot.db
        echo LOG_LEVEL=INFO
    ) > .env
) else (
    echo [4/4] .env already exists. Keeping your settings.
)

echo.
echo ============================================
echo   Starting the bot... (press Ctrl+C to stop)
echo ============================================
echo.

REM --- 4. Run the bot -------------------------------------------------
"%PY%" -m bot.main

echo.
echo Bot stopped.
pause
