# Container image for the Melodix Telegram bot.
# Works on Fly.io, Railway, Render, or any Docker host.

FROM python:3.12-slim

# ffmpeg is required for downloading + trimming audio.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching).
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project.
COPY . .

# The database (playlists) lives here; on Fly this is a persistent volume.
# DATA_DIR is read by the app via the DATABASE_PATH env var.
RUN mkdir -p /data
ENV DATABASE_PATH=/data/bot.db
ENV DOWNLOAD_DIR=/tmp/downloads

# Long-polling bot: no ports to expose. Just run it.
CMD ["python", "-m", "bot.main"]
