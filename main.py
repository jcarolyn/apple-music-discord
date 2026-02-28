"""Apple Music -> Discord Rich Presence

Displays the currently playing Apple Music track as Discord Rich Presence
on Windows, including song title, artist, album, and album cover art.

How it works:
  1. Polls the Windows Media Session API every few seconds for the current
     track. Runs in a subprocess to isolate winrt COM crashes that can
     occur when the active media session changes.
  2. Looks up album cover art from the iTunes Search API, with Deezer as
     a fallback. Both sources validate the returned artist and title to
     avoid showing art from the wrong song. Results are cached in memory.
  3. Sends track info and cover art to Discord via local Rich Presence RPC.
  4. Auto-reconnects if Discord restarts or the connection drops.
     Clears the presence when nothing is playing.

Usage:
  Set DISCORD_APP_ID in .env, then: python main.py
"""

import json
import logging
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from dotenv import load_dotenv
from pypresence import Presence
from pypresence.types import ActivityType

# -- Configuration ----------------------------------------------------------- #

load_dotenv()

DISCORD_APP_ID = os.getenv("DISCORD_APP_ID")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "2"))

APPLE_MUSIC_ICON = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/"
    "Apple_Music_icon.svg/512px-Apple_Music_icon.svg.png"
)
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
DEEZER_SEARCH_URL = "https://api.deezer.com/search"
ART_CACHE_MAX = 256

# -- Logging ----------------------------------------------------------------- #

sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("apple-music-discord")

# -- Media detection --------------------------------------------------------- #
# Runs in a subprocess to isolate winrt COM access-violation crashes that
# can occur when the active media session changes during a poll.

_MEDIA_SCRIPT = r"""
import asyncio, json
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as Mgr,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
)
async def main():
    mgr = await Mgr.request_async()
    session = mgr.get_current_session()
    if not session:
        print("null")
        return
    info = session.get_playback_info()
    if not info or info.playback_status not in (Status.PLAYING, Status.PAUSED):
        print("null")
        return
    props = await session.try_get_media_properties_async()
    if not props or not props.title:
        print("null")
        return
    print(json.dumps({
        "title": props.title,
        "artist": props.artist or "Unknown Artist",
        "album": props.album_title or "",
        "paused": info.playback_status == Status.PAUSED,
    }))
asyncio.run(main())
"""


def get_media_info() -> dict | None:
    """Detect the current media session via a subprocess."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", _MEDIA_SCRIPT],
            capture_output=True, text=True, timeout=10,
        )
        output = result.stdout.strip()
        if result.returncode != 0 or not output or output == "null":
            return None
        return json.loads(output)
    except subprocess.TimeoutExpired:
        log.warning("Media detection timed out")
    except Exception as exc:
        log.warning("Media detection error: %s", exc)
    return None


# -- Album art --------------------------------------------------------------- #

_art_cache: dict[str, str] = {}


def get_album_art(title: str, artist: str, album: str = "") -> str | None:
    """Look up album cover URL, trying iTunes then Deezer.

    Results are cached in memory. Lookup failures are not cached so they
    can be retried on the next poll.
    """
    cache_key = f"{title}|{artist}"
    if cache_key in _art_cache:
        return _art_cache[cache_key]

    art_url = (
        _itunes_search(artist, title)
        or _deezer_search(artist, title)
    )

    if art_url:
        if len(_art_cache) >= ART_CACHE_MAX:
            _art_cache.pop(next(iter(_art_cache)))
        _art_cache[cache_key] = art_url
    return art_url


def _itunes_search(artist: str, title: str) -> str | None:
    """Query the iTunes Search API and return the artwork URL if found."""
    try:
        query = urllib.parse.urlencode({
            "term": f"{artist} {title}",
            "media": "music",
            "entity": "song",
            "limit": "5",
        })
        url = f"{ITUNES_SEARCH_URL}?{query}"
        req = urllib.request.Request(
            url, headers={"User-Agent": "AppleMusicDiscord/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        for result in data.get("results", []):
            result_artist = result.get("artistName", "")
            result_title = result.get("trackName", "")
            if _fuzzy_match(artist, result_artist) and \
               _fuzzy_match(title, result_title):
                art_url = result.get("artworkUrl100", "")
                return art_url.replace("100x100bb", "600x600bb")
    except Exception as exc:
        log.debug("iTunes search failed: %s", exc)
    return None


def _deezer_search(artist: str, title: str) -> str | None:
    """Query the Deezer API as a fallback for album art."""
    try:
        term = f"{artist} {title}"
        url = f"{DEEZER_SEARCH_URL}?q={urllib.parse.quote(term)}&limit=5"
        req = urllib.request.Request(
            url, headers={"User-Agent": "AppleMusicDiscord/1.0"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        for result in data.get("data", []):
            result_artist = result.get("artist", {}).get("name", "")
            result_title = result.get("title", "")
            if _fuzzy_match(artist, result_artist) and \
               _fuzzy_match(title, result_title):
                return result.get("album", {}).get("cover_big", None)
    except Exception as exc:
        log.debug("Deezer search failed: %s", exc)
    return None


def _fuzzy_match(expected: str, actual: str) -> bool:
    """Check if two strings reasonably match.

    Matches are case/punctuation insensitive. Allows for minor suffixes
    like '(feat. X)' but rejects remixes, DJ mixes, and other variants
    unless the original title also contains those terms.
    """
    a = _normalize(expected)
    b = _normalize(actual)
    if a == b:
        return True
    # Allow 'feat' suffixes: "Song (feat. X)" matches "Song"
    if a.startswith(b) or b.startswith(a):
        longer, shorter = (a, b) if len(a) > len(b) else (b, a)
        suffix = longer[len(shorter):].strip()
        # Reject if the suffix indicates a remix/mix/version
        reject = ("remix", "mixed", "mix", "version", "edit", "live")
        if any(word in suffix for word in reject):
            return False
        return True
    return False


def _normalize(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    cleaned = "".join(c.lower() if c.isalnum() or c == " " else " " for c in s)
    return " ".join(cleaned.split())


# -- Discord presence -------------------------------------------------------- #

_TRACK_FIELDS = ("title", "artist", "album", "paused")


class DiscordPresence:
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.rpc: Presence | None = None
        self.connected = False
        self._last_track: dict | None = None

    def connect(self):
        try:
            self.rpc = Presence(self.app_id)
            self.rpc.connect()
            self.connected = True
            log.info("Connected to Discord")
        except Exception as exc:
            log.warning("Could not connect to Discord: %s", exc)
            self.rpc = None
            self.connected = False

    def disconnect(self):
        if self.rpc:
            for action in (self.rpc.clear, self.rpc.close):
                try:
                    action()
                except Exception:
                    pass
        self.rpc = None
        self.connected = False
        self._last_track = None
        log.info("Disconnected from Discord (will reconnect)")

    def _needs_update(self, track: dict) -> bool:
        if self._last_track is None:
            return True
        return any(
            track[k] != self._last_track[k] for k in _TRACK_FIELDS
        )

    def update(self, track: dict | None):
        if not self.connected or not self.rpc:
            return

        if track is None:
            if self._last_track is not None:
                try:
                    self.rpc.clear()
                    log.info("Cleared presence (nothing playing)")
                except Exception:
                    self.disconnect()
                    return
                self._last_track = None
            return

        if not self._needs_update(track):
            return

        details = track["title"][:128]
        state = f"by {track['artist']}"
        if track["album"]:
            state += f" on {track['album']}"
        state = state[:128]

        art_url = get_album_art(track["title"], track["artist"], track["album"])

        try:
            self.rpc.update(
                activity_type=ActivityType.LISTENING,
                details=details,
                state=state,
                large_image=art_url or APPLE_MUSIC_ICON,
                large_text=track["album"] if track["album"] else None,
                small_image=APPLE_MUSIC_ICON,
                small_text="Paused" if track["paused"] else "Playing",
            )
            status = "[Paused]" if track["paused"] else "[Playing]"
            log.info("%s %s - %s", status, track["title"], track["artist"])
            self._last_track = track.copy()
        except Exception as exc:
            log.warning("Failed to update presence: %s", exc)
            self.disconnect()


# -- Main -------------------------------------------------------------------- #

def main():
    if not DISCORD_APP_ID:
        log.error(
            "DISCORD_APP_ID not set. "
            "Create a Discord app at https://discord.com/developers/applications "
            "and add your Application ID to a .env file."
        )
        sys.exit(1)

    presence = DiscordPresence(DISCORD_APP_ID)

    log.info("Apple Music -> Discord Rich Presence")
    log.info("Polling every %ds. Press Ctrl+C to stop.", POLL_INTERVAL)

    try:
        while True:
            if not presence.connected:
                presence.connect()
                if not presence.connected:
                    time.sleep(POLL_INTERVAL)
                    continue

            try:
                track = get_media_info()
                presence.update(track)
            except Exception as exc:
                log.warning("Unexpected error (will retry): %s", exc)
                presence.disconnect()

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        pass
    finally:
        log.info("Shutting down...")
        presence.disconnect()


if __name__ == "__main__":
    main()
