"""
Helpers to clean up messy track metadata.

Search sources (especially SoundCloud) often put the real artist inside the
title ("Buddy Holly - Weezer") while the `artist` field holds the uploader
("koreykeat"). These helpers try to recover a clean artist + title so that
lyrics lookups and "more from artist" searches work well.
"""

import re

# Junk commonly found in track titles that we strip before parsing.
_JUNK = re.compile(
    r"\b(official\s*(music\s*)?video|official\s*audio|lyrics?|lyric\s*video|"
    r"audio|hd|hq|4k|mv|m/v|visualizer|remaster(ed)?|explicit|full\s*album|"
    r"free\s*download|prod\.?.*)\b",
    re.IGNORECASE,
)
# Bracketed segments like (Official Video), [HD], {audio}.
_BRACKETS = re.compile(r"[\(\[\{][^\)\]\}]*[\)\]\}]")


def _clean(text: str) -> str:
    text = _BRACKETS.sub(" ", text or "")
    text = _JUNK.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" -–—|·•").strip()
    return text


def parse_artist_title(title: str, uploader: str = "") -> tuple[str, str]:
    """
    Best-effort extraction of (artist, title) from a track's display title.

    Handles common patterns:
      "Artist - Title"      -> ("Artist", "Title")
      "Title - Artist"      -> heuristics decide (uploader helps)
      "Artist – Title"      -> en dash / em dash too

    Falls back to (uploader, cleaned_title) when there is no separator.
    """
    raw = _clean(title)

    # Split on the first dash/en-dash/em-dash separator. Allow missing spaces
    # ("Title-Artist", "Title- Artist") which are common on SoundCloud, but
    # require at least one space on a side OR spaces around, to avoid splitting
    # hyphenated words like "hip-hop".
    parts = re.split(r"\s*[–—]\s*|\s+-\s*|\s*-\s+", raw, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        left, right = _clean(parts[0]), _clean(parts[1])
        # If the uploader name appears on one side, the OTHER side is the title,
        # and the uploader side is likely the artist.
        up = (uploader or "").lower()
        if up and up in right.lower():
            return right, left       # "Title - Artist(uploader)"
        if up and up in left.lower():
            return left, right       # "Artist(uploader) - Title"
        # Default: assume "Artist - Title" (most common on YouTube/SoundCloud).
        return left, right

    # No separator: use uploader as artist, cleaned title as title.
    return _clean(uploader), raw or title


def best_lyrics_queries(title: str, artist: str, uploader: str = "") -> list[tuple[str, str]]:
    """
    Return a list of (artist, title) pairs to TRY for lyrics, best first.
    Different sources store metadata differently, so we try several combos.
    """
    a2, t2 = parse_artist_title(title, uploader or artist)
    candidates = [
        (artist, title),      # as-is
        (a2, t2),             # parsed from title
        (t2, a2),             # swapped (we can't always tell which side is which)
        (a2, _clean(title)),  # parsed artist + cleaned original title
    ]
    # De-duplicate while keeping order; drop empty titles.
    seen, out = set(), []
    for a, t in candidates:
        a, t = (a or "").strip(), (t or "").strip()
        if not t:
            continue
        key = (a.lower(), t.lower())
        if key not in seen:
            seen.add(key)
            out.append((a, t))
    return out


def best_artist_name(title: str, artist: str, uploader: str = "") -> str:
    """
    Return the best guess for the real artist name, for 'more from artist'.
    Prefers a parsed artist over an uploader-style name.
    """
    a2, _ = parse_artist_title(title, uploader or artist)
    # If the given artist looks like a real name (has a space or matches parsed),
    # keep it; otherwise prefer the parsed one.
    if artist and (a2 == "" or artist.lower() == a2.lower()):
        return artist
    return a2 or artist
