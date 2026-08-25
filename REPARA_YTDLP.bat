@echo off
REM ============================================================
REM  Fix the "Unable to extract universal data for rehydration"
REM  error. That error ALWAYS means yt-dlp is outdated.
REM  This script diagnoses which Python the bot uses and forces
REM  the newest yt-dlp into that exact environment.
REM ============================================================
setlocal
cd /d "%~dp0"

echo ============================================================
echo   yt-dlp repair tool
echo ============================================================
echo.

REM --- Find the venv python (the one the bot actually runs with) -------
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: .venv not found. Run run.bat first to create it.
    pause
    exit /b 1
)
set "PY=.venv\Scripts\python.exe"

echo [1] Python used by the bot:
"%PY%" -c "import sys; print('   ', sys.executable)"
echo.

echo [2] Current yt-dlp version (BEFORE):
"%PY%" -c "import yt_dlp; print('   ', yt_dlp.version.__version__)" 2>nul || echo    yt-dlp not installed
echo.

echo [3] Removing old yt-dlp completely...
"%PY%" -m pip uninstall -y yt-dlp >nul 2>&1

echo [4] Installing the LATEST yt-dlp (no cache, forced)...
"%PY%" -m pip install --upgrade --no-cache-dir --force-reinstall yt-dlp
echo.

echo [5] yt-dlp version (AFTER):
"%PY%" -c "import yt_dlp; print('   ', yt_dlp.version.__version__)"
echo.

echo [6] Quick self-test on a TikTok link...
"%PY%" -m yt_dlp --no-warnings --skip-download --print "%%(title)s" "https://www.tiktok.com/@tiktok/video/7106594312292453675" 2>nul && (
    echo.
    echo    SUCCESS: yt-dlp can read TikTok now.
) || (
    echo.
    echo    Still failing. Make sure you have internet and try once more.
)

echo.
echo ============================================================
echo   Done. Now start the bot again with run.bat
echo ============================================================
pause
