#!/usr/bin/env bash
# ============================================================
#  One-command setup for the Melodix bot on a Linux server
#  (Oracle Cloud Free Tier, or any Ubuntu/Debian machine).
#
#  Run it from inside the telegram-music-bot folder:
#      bash deploy/setup.sh
#
#  It installs Python + ffmpeg, creates the virtualenv, installs
#  the Python packages, and installs a systemd service that keeps
#  the bot running 24/7 (auto-restart on crash / reboot).
# ============================================================
set -e

echo "==> Installing system packages (python, ffmpeg)..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg

# Resolve the project directory (the parent of this deploy/ folder).
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
echo "==> Project directory: $PROJECT_DIR"

echo "==> Creating virtual environment..."
python3 -m venv .venv

echo "==> Installing Python dependencies..."
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

# Create the .env file if it does not exist yet.
if [ ! -f .env ]; then
  echo "==> Creating .env (edit it and paste your BOT_TOKEN!)"
  cp .env.example .env
  echo ""
  echo "  !!! IMPORTANT: open .env and set BOT_TOKEN before starting. !!!"
  echo "      nano .env"
  echo ""
fi

# Install the systemd service, pointing it at THIS project + user.
echo "==> Installing systemd service..."
SERVICE_SRC="$PROJECT_DIR/deploy/melodix-bot.service"
SERVICE_DST="/etc/systemd/system/melodix-bot.service"

# Fill in the real user and path into the service file.
CURRENT_USER="$(whoami)"
sudo bash -c "sed \
  -e 's|^User=.*|User=$CURRENT_USER|' \
  -e 's|^WorkingDirectory=.*|WorkingDirectory=$PROJECT_DIR|' \
  -e 's|^ExecStart=.*|ExecStart=$PROJECT_DIR/.venv/bin/python -m bot.main|' \
  '$SERVICE_SRC' > '$SERVICE_DST'"

sudo systemctl daemon-reload
sudo systemctl enable melodix-bot

echo ""
echo "============================================================"
echo "  Setup done!"
echo ""
echo "  1) Put your token in .env :   nano .env"
echo "  2) Start the bot          :   sudo systemctl start melodix-bot"
echo "  3) Check it is running     :   sudo systemctl status melodix-bot"
echo "  4) See live logs          :   journalctl -u melodix-bot -f"
echo ""
echo "  The bot now starts automatically on every reboot and"
echo "  restarts itself if it ever crashes."
echo "============================================================"
