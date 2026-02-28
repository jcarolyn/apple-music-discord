import asyncio
import logging
import os
import signal
import sys
import time

from dotenv import load_dotenv
from pypresence import Presence, exceptions as rpc_exceptions
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("apple-music-discord")

DISCORD_APP_ID = os.getenv("DISCORD_APP_ID")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))

# Apple Music's app user model ID on Windows (may vary; we also match by name)
APPLE_MUSIC_IDS = {"applemusic", "apple music", "itunes", "music"}


# -- Media detection --------------------------------------------------------- #

async def get_media_info() -> dict | None:
    """Return current track info from Apple Music, or None."""
    manager = await MediaManager.request_async()
    session = manager.get_current_session()
    if session is None:
        return None

    source = (session.source_app_user_model_id or "").lower()
    # Accept the session if it looks like Apple Music / iTunes
    if not any(name in source for name in APPLE_MUSIC_IDS):
        # If no match by ID, still accept — the user may have a non-standard ID
        # and Apple Music is the whole point of this tool
        pass

    playback = session.get_playback_info()
    if playback is None:
        return None

    status = playback.playback_status
    if status != PlaybackStatus.PLAYING and status != PlaybackStatus.PAUSED:
        return None

    props = await session.try_get_media_properties_async()
    if props is None or not props.title:
        return None

    return {
        "title": props.title,
        "artist": props.artist or "Unknown Artist",
        "album": props.album_title or "",
        "paused": status == PlaybackStatus.PAUSED,
        "source": session.source_app_user_model_id or "",
    }


# -- Discord presence -------------------------------------------------------- #

class DiscordPresence:
    def __init__(self, app_id: str):
        self.app_id = app_id
        self.rpc: Presence | None = None
        self._connected = False
        self._last_track: dict | None = None

    def connect(self) -> bool:
        try:
            self.rpc = Presence(self.app_id)
            self.rpc.connect()
            self._connected = True
            log.info("Connected to Discord")
            return True
        except Exception as exc:
            log.warning("Could not connect to Discord: %s", exc)
            self._connected = False
            return False

    def disconnect(self):
        if self.rpc and self._connected:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass
        self._connected = False
        self._last_track = None
        log.info("Disconnected from Discord")

    def update(self, track: dict | None):
        if not self._connected:
            return

        # Nothing playing → clear presence
        if track is None:
            if self._last_track is not None:
                try:
                    self.rpc.clear()
                    log.info("Cleared presence (nothing playing)")
                except Exception:
                    pass
                self._last_track = None
            return

        # Same track, same state → skip update
        if self._last_track == track:
            return

        state_parts = []
        if track["artist"]:
            state_parts.append(track["artist"])
        if track["album"]:
            state_parts.append(track["album"])

        details = track["title"]
        state = " — ".join(state_parts) if state_parts else None
        small_text = "Paused" if track["paused"] else "Playing"

        try:
            self.rpc.update(
                details=details,
                state=state,
                large_image="apple_music",
                large_text="Apple Music",
                small_text=small_text,
            )
            status = "⏸ " if track["paused"] else "▶ "
            log.info("%s%s — %s", status, track["title"], track["artist"])
            self._last_track = track.copy()
        except rpc_exceptions.InvalidID:
            log.error("Invalid Discord Application ID")
            self._connected = False
        except Exception as exc:
            log.warning("Failed to update presence: %s", exc)
            self._connected = False


# -- Main loop -------------------------------------------------------------- #

def main():
    if not DISCORD_APP_ID:
        log.error(
            "DISCORD_APP_ID not set. "
            "Create a Discord app at https://discord.com/developers/applications "
            "and add your Application ID to a .env file."
        )
        sys.exit(1)

    presence = DiscordPresence(DISCORD_APP_ID)

    # Graceful shutdown
    def shutdown(*_):
        log.info("Shutting down…")
        presence.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    log.info("Apple Music → Discord Rich Presence")
    log.info("Polling every %ds. Press Ctrl+C to stop.", POLL_INTERVAL)

    while True:
        # Ensure Discord connection
        if not presence._connected:
            if not presence.connect():
                time.sleep(POLL_INTERVAL)
                continue

        # Get current track and update presence
        track = asyncio.run(get_media_info())
        presence.update(track)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
