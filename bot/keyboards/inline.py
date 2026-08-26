"""
Inline keyboard builders.

Callback data is kept short and prefixed so routers can tell which button was
pressed. Format: "<action>:<arg>[:<arg>]".

  lang:<code>              -> user picked a language
  pick:<index>            -> chose a search result (index into cached list)
  page:<n>                -> show page n of the current search results
  pick:cancel             -> cancel the current selection
  addpl:<index>           -> open "add this track to a playlist" menu
  pladd:<code>:<index>    -> add track <index> to playlist <code>
  cutpick:<index>         -> choose a recent track to trim
  plmenu:<action>         -> playlist menu action (create/my/open)
  plopen:<code>           -> open a playlist by code
  plpick:<code>:<i>       -> pick track i from playlist <code>
  pldel:<code>            -> delete a playlist
  topmenu:<which>         -> leaderboard menu (playlists/users)
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.services.sources.base import Track
from bot.utils.i18n import Translator


def language_keyboard(translator: Translator) -> InlineKeyboardMarkup:
    """One button per available language."""
    builder = InlineKeyboardBuilder()
    for code in translator.languages:
        builder.button(text=translator.language_name(code), callback_data=f"lang:{code}")
    builder.adjust(2)
    return builder.as_markup()


def results_keyboard(
    tracks: list[Track],
    page: int,
    page_size: int,
    more_label: str,
) -> InlineKeyboardMarkup:
    """
    Show one page of search results, plus a "More tracks" button if there are
    further pages. Buttons use absolute indexes so callbacks map to the full
    cached result list.
    """
    builder = InlineKeyboardBuilder()
    start = page * page_size
    end = start + page_size
    for index in range(start, min(end, len(tracks))):
        builder.button(text=tracks[index].label, callback_data=f"pick:{index}")
    builder.adjust(1)  # one result per row (matches the reference UI)

    # "More tracks" button when additional pages exist.
    if end < len(tracks):
        builder.row(InlineKeyboardButton(text=more_label, callback_data=f"page:{page + 1}"))
    return builder.as_markup()


def audio_actions_keyboard(
    index: int,
    add_label: str,
    lyrics_label: str | None = None,
    more_artist_label: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Buttons shown under a delivered audio.

    Always includes "Add to playlist". When we know the song's title/artist
    (e.g. after Shazam recognition or a normal search) we also show
    "Lyrics" and "More from artist" buttons, using the same recent-track index
    so the callbacks can look up the song.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text=add_label, callback_data=f"addpl:{index}")
    if lyrics_label:
        builder.button(text=lyrics_label, callback_data=f"lyrics:{index}")
    if more_artist_label:
        builder.button(text=more_artist_label, callback_data=f"artist:{index}")
    builder.adjust(1)
    return builder.as_markup()


def cut_pick_keyboard(tracks: list[dict]) -> InlineKeyboardMarkup:
    """Let the user choose which recently received song to trim."""
    builder = InlineKeyboardBuilder()
    for index, t in enumerate(tracks):
        title = t.get("title", "?")
        artist = t.get("artist", "")
        label = f"{title} — {artist}" if artist else title
        label = label[:58] + "…" if len(label) > 60 else label
        builder.button(text=label, callback_data=f"cutpick:{index}")
    builder.adjust(1)
    return builder.as_markup()


def playlist_menu_keyboard(translator: Translator, lang: str) -> InlineKeyboardMarkup:
    """Top-level playlist actions."""
    builder = InlineKeyboardBuilder()
    builder.button(text=translator.get(lang, "playlist_create_btn"), callback_data="plmenu:create")
    builder.button(text=translator.get(lang, "playlist_my_btn"), callback_data="plmenu:my")
    builder.button(text=translator.get(lang, "playlist_open_btn"), callback_data="plmenu:open")
    builder.adjust(1)
    return builder.as_markup()


def playlist_create_options_keyboard(
    translator: Translator, lang: str, is_private: bool, has_code: bool
) -> InlineKeyboardMarkup:
    """
    Options shown while creating a playlist: toggle private, set a custom code,
    or create it. The private/code state is kept in the FSM.
    """
    builder = InlineKeyboardBuilder()
    # Toggle private/public.
    priv_label = translator.get(
        lang, "playlist_opt_private_on" if is_private else "playlist_opt_private_off"
    )
    builder.button(text=priv_label, callback_data="plopt:toggle_private")
    # Set / change custom code.
    code_label = translator.get(
        lang, "playlist_opt_code_set" if has_code else "playlist_opt_code"
    )
    builder.button(text=code_label, callback_data="plopt:set_code")
    # Create.
    builder.button(text=translator.get(lang, "playlist_opt_create"), callback_data="plopt:create")
    builder.adjust(1)
    return builder.as_markup()


def playlist_target_keyboard(playlists: list[dict], track_index: int) -> InlineKeyboardMarkup:
    """Choose which playlist to add a track to."""
    builder = InlineKeyboardBuilder()
    for pl in playlists:
        builder.button(
            text=f"{pl['name']} ({pl['code']})",
            callback_data=f"pladd:{pl['code']}:{track_index}",
        )
    builder.adjust(1)
    return builder.as_markup()


def playlist_tracks_keyboard(code: str, tracks: list[dict]) -> InlineKeyboardMarkup:
    """List tracks inside an opened playlist for download."""
    builder = InlineKeyboardBuilder()
    for index, t in enumerate(tracks):
        title = t.get("title", "?")
        artist = t.get("artist", "")
        label = f"{title} — {artist}" if artist else title
        label = label[:58] + "…" if len(label) > 60 else label
        builder.button(text=label, callback_data=f"plpick:{code}:{index}")
    builder.adjust(1)
    return builder.as_markup()


def playlist_list_keyboard(
    playlists: list[dict], translator: Translator, lang: str
) -> InlineKeyboardMarkup:
    """User's own playlists: open, set photo, or delete each one."""
    builder = InlineKeyboardBuilder()
    for pl in playlists:
        builder.button(text=f"{pl['name']} ({pl['code']})", callback_data=f"plopen:{pl['code']}")
        builder.button(text=translator.get(lang, "playlist_photo_btn"), callback_data=f"plphoto:{pl['code']}")
        builder.button(text=translator.get(lang, "playlist_delete_btn"), callback_data=f"pldel:{pl['code']}")
    builder.adjust(3)  # [open][photo][delete] per row
    return builder.as_markup()


def top_menu_keyboard(translator: Translator, lang: str) -> InlineKeyboardMarkup:
    """Leaderboard selection."""
    builder = InlineKeyboardBuilder()
    builder.button(text=translator.get(lang, "top_playlists_btn"), callback_data="topmenu:playlists")
    builder.button(text=translator.get(lang, "top_users_btn"), callback_data="topmenu:users")
    builder.adjust(1)
    return builder.as_markup()
