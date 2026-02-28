# Apple Music -> Discord Rich Presence

Display your currently playing Apple Music track as Discord Rich Presence on Windows.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## How it works

1. Reads the currently playing track from Windows Media Session API (no scraping, no hacks)
2. Looks up the album cover art via the iTunes Search API
3. Sends the song title, artist, album, and cover art to Discord via local Rich Presence RPC
4. Polls every 5 seconds and updates automatically when the track changes

## Setup

### 1. Create a Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** and give it a name (e.g. "Apple Music")
3. Copy the **Application ID** from the General Information page

### 2. Install

```bash
git clone https://github.com/your-username/apple-music-discord.git
cd apple-music-discord
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure

```bash
copy .env.example .env
```

Edit `.env` and replace `your_application_id_here` with your Discord Application ID.

### 4. Run

```bash
python main.py
```

You should see output like:

```
00:47:21  Apple Music -> Discord Rich Presence
00:47:21  Polling every 5s. Press Ctrl+C to stop.
00:47:21  Connected to Discord
00:47:22  [Playing] Unisex - Foggieraw
```

Press `Ctrl+C` to stop.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DISCORD_APP_ID`    | *(required)* | Your Discord Application ID |
| `POLL_INTERVAL`     | `5`     | Seconds between track checks |

## Known Limitations

### Elapsed Time / Timestamps

- **The elapsed timer is not the actual song position.** Discord shows a timer counting from when the track was first detected, not from where the song actually is. This is because Apple Music's web player does not reliably report song position or duration to the browser's Media Session API.
- **Seeking within a song does not update the timer.** If you skip ahead or rewind, the elapsed time keeps counting from when the track started playing.
- **Restarting the same song does not reset the timer.** The app only updates Discord when the track changes (different title or artist). Replaying the same song looks identical to continuing it.
- **Pausing does not stop the timer.** Discord continues counting elapsed time even while paused. The presence does update to show "Paused" in the tooltip.
- **The Discord timer only redraws every ~15 seconds.** This is a Discord client limitation that applies to all Rich Presence apps.

### Display

- **The member list only shows "Listening to Apple Music."** Song details (title, artist, album, cover art) are only visible when someone clicks your profile. This is a Discord limitation -- only Spotify has a native inline integration.
- **Album art may occasionally be wrong.** The iTunes Search API returns the best match for the song title + artist, which may not always be the exact version or remix you are listening to.

### General

- **Track detection has a ~5 second delay.** The app polls every 5 seconds (configurable via `POLL_INTERVAL`), so there is a short lag when switching songs.
- **Requires an internet connection** for album art lookups (the iTunes Search API). Track detection itself works offline.
- **Only detects the system's active media session.** If multiple media players are running, only the one Windows considers "current" will be shown.

## Troubleshooting

- **"Could not connect to Discord"** -- Make sure Discord is running (desktop app, not browser)
- **No track detected** -- Make sure Apple Music is actively playing a song
- **Rich Presence not showing** -- It can take a few seconds to appear. Discord doesn't show your own Rich Presence to you in all views -- check your profile popup or ask a friend
- **"The pipe was closed"** -- This happens when Discord is restarted. The app will automatically reconnect within a few seconds
