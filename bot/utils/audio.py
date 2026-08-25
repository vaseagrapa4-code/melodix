"""
Audio helpers: trimming with ffmpeg and reading duration.

ffmpeg must be installed on the system (see the tutorial). We call it as a
subprocess because it is the most reliable, fast way to cut audio without
re-encoding quality loss.
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_timecode(value: str) -> float | None:
    """
    Convert a timecode string into seconds.

    Supports: '00:01:15' (h:m:s), '01:15' (m:s), '75' (plain seconds),
    and decimals like '01:15.5'. Returns None if the string is invalid.
    """
    value = value.strip()
    if not value:
        return None
    parts = value.split(":")
    if len(parts) > 3:
        return None
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if any(n < 0 for n in nums):
        return None
    if len(nums) == 3:
        h, m, s = nums
    elif len(nums) == 2:
        h, m, s = 0.0, nums[0], nums[1]
    else:
        h, m, s = 0.0, 0.0, nums[0]
    return h * 3600 + m * 60 + s


async def cut_audio(
    src: Path, dst: Path, start: float, end: float
) -> bool:
    """
    Cut the segment [start, end] (in seconds) from `src` into `dst`.

    Returns True on success. Uses stream copy when possible for speed;
    falls back to re-encoding to mp3 to guarantee a valid output file.
    """
    duration = max(0.0, end - start)
    if duration <= 0:
        return False

    cmd = [
        "ffmpeg",
        "-y",                       # overwrite output
        "-ss", str(start),          # seek to start
        "-i", str(src),
        "-t", str(duration),        # length of the segment
        "-acodec", "libmp3lame",    # re-encode to mp3 for reliability
        "-q:a", "2",                # good quality VBR
        str(dst),
    ]
    logger.info("Cutting audio: %s -> %s (%.1fs to %.1fs)", src, dst, start, end)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        logger.error("ffmpeg failed: %s", stderr.decode(errors="ignore")[-500:])
        return False
    return dst.exists() and dst.stat().st_size > 0
