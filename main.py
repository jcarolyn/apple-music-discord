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

load_dotenv()

DISCORD_APP_ID = os.getenv("DISCORD_APP_ID")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))

APPLE_MUSIC_ICON = (
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/"
    "Apple_Music_icon.svg/512px-Apple_Music_icon.svg.png"
)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(
            open(sys.stdout.fileno(), mode="w", encoding="utf-8", closefd=False)
        ),
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("apple-music-discord")


# -- Media detection (subprocess to isolate winrt COM crashes) --------------- #

_MEDIA_SCRIPT = r"""
import asyncio, json
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as M,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as S,
)
async def main():
    mgr = await M.request_async()
    session = mgr.get_current_session()
    if not session:
        print("null")
        return
    pb = session.get_playback_info()
    if not pb or pb.playback_status not in (S.PLAYING, S.PAUSED):
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
        "paused": pb.playback_status == S.PAUSED,
    }))
asyncio.run(main())
"""


def get_media_info() -> dict | None:
    """Run media detection in a subprocess to isolate winrt COM crashes."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", _MEDIA_SCRIPT],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        output = result.stdout.strip()
        if not output or output == "null":
            return None
        return json.loads(output)
    except subprocess.TimeoutExpired:
        log.warning("Media detection timed out")
        return None
    except Exception as exc:
        log.warning("Media detection error: %s", exc)
        return None


# -- Album art via iTunes Search API ----------------------------------------- #

_art_cache: dict[str, str] = {}


def get_album_art(title: str, artist: str) -> str | None:
    """Look up album cover URL from the iTunes Search API."""
    cache_key = f"{title}|{artist}"
    if cache_key in _art_cache:
        return _art_cache[cache_key]

    try:
        query = urllib.parse.urlencode({
            "term": f"{artist} {title}",
            "media": "music",
            "limit": "1",
        })
        url = f"{ITUNES_SEARCH_URL}?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "AppleMusicDiscord/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        if data.get("resultCount", 0) > 0:
            art_url = data["results"][0].get("artworkUrl100", "")
            # upscale to 600x600
            art_url = art_url.replace("100x100bb", "600x600bb")
            _art_cache[cache_key] = art_url
            return art_url
    except Exception as exc:
        log.debug("Album art lookup failed: %s", exc)

    return None


# -- Discord presence -------------------------------------------------------- #

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
            self.connected = False
            self.rpc = None

    def disconnect(self):
        try:
            if self.rpc:
                self.rpc.clear()
        except Exception:
            pass
        try:
            if self.rpc:
                self.rpc.close()
        except Exception:
            pass
        self.rpc = None
        self.connected = False
        self._last_track = None
        log.info("Disconnected from Discord (will reconnect)")

    def _needs_update(self, track: dict) -> bool:
        if self._last_track is None:
            return True
        if (track["title"] != self._last_track["title"]
                or track["artist"] != self._last_track["artist"]
                or track["album"] != self._last_track["album"]
                or track["paused"] != self._last_track["paused"]):
            return True
        return False

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
        state = "by " + track["artist"]
        if track["album"]:
            state += " on " + track["album"]
        state = state[:128]

        art_url = get_album_art(track["title"], track["artist"])
        large_image = art_url if art_url else APPLE_MUSIC_ICON
        large_text = track["album"] if track["album"] else "Apple Music"

        try:
            self.rpc.update(
                activity_type=ActivityType.LISTENING,
                details=details,
                state=state,
                large_image=large_image,
                large_text=large_text,
                small_image=APPLE_MUSIC_ICON,
                small_text="Paused" if track["paused"] else "Playing",
            )
            icon = "[Paused] " if track["paused"] else "[Playing] "
            log.info("%s%s - %s", icon, track["title"], track["artist"])
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
        try:
            if presence.rpc:
                presence.rpc.clear()
                presence.rpc.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
