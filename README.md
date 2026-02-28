# Apple Music -> Discord Rich Presence

Display your currently playing Apple Music track as Discord Rich Presence on Windows -- complete with album art, artist info, and playback status.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Real-time track display** -- Song title, artist, and album shown on your Discord profile
- **Dynamic album art** -- Automatically fetched from iTunes and Deezer APIs (no API keys required)
- **Listening activity** -- Shows "Listening to Apple Music" in your Discord status
- **Playback state** -- Indicates whether you are currently playing or paused
- **Auto-reconnect** -- Automatically reconnects if Discord restarts or the connection drops
- **Lightweight** -- Single Python script, polls every 2 seconds with minimal resource usage
- **No scraping or hacks** -- Uses the official Windows Media Session API for track detection

## Example

```
21:43:04  Apple Music -> Discord Rich Presence
21:43:04  Polling every 2s. Press Ctrl+C to stop.
21:43:04  Connected to Discord
21:43:05  [Playing] HUMBLE. - Kendrick Lamar
21:43:12  [Playing] LUST. - Kendrick Lamar
21:43:30  [Paused] LUST. - Kendrick Lamar
```

Your Discord profile will show:

- **Status line:** "Listening to Apple Music"
- **Rich Presence card** (click profile to see):
  - Album cover art (large image)
  - Song title
  - Artist and album name
  - Apple Music icon (small image)
  - Playing/Paused tooltip

<!-- Add a screenshot here if you have one: -->
<!-- ![Screenshot](assets/screenshot.png) -->

## How It Works

1. Reads the currently playing track from the Windows Media Session API
2. Looks up album cover art from the iTunes Search API, with Deezer as a fallback
3. Sends song title, artist, album, and cover art to Discord via local Rich Presence RPC
4. Polls every 2 seconds and updates automatically when the track changes

## Setup

### 1. Create a Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** and name it **Apple Music** (this name appears in your status)
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

Edit `.env` and paste your Discord Application ID.

### 4. Run

```bash
python main.py
```

Press `Ctrl+C` to stop.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DISCORD_APP_ID`    | *(required)* | Your Discord Application ID |
| `POLL_INTERVAL`     | `2`     | Seconds between track checks |

## Album Art

Album art is fetched dynamically using a multi-source search:

1. **iTunes Search API** -- song-level search by artist + title
2. **Deezer Search API** -- catches tracks not indexed in iTunes (e.g. demos, indie releases)

No API keys are required. Art URLs are cached in memory so the same song won't trigger repeated lookups.

If none of the sources find a match (e.g. unreleased demos, very obscure tracks), the Apple Music icon is shown instead.

## Known Limitations

### Elapsed Time

- **The elapsed timer is not the actual song position.** It counts from when the track was first detected, not the actual playback position. Apple Music's web player does not reliably report position data to the browser's Media Session API.
- **The timer resets when the app restarts**, not when the song restarts.
- **Seeking, rewinding, or restarting a song does not update the timer.**
- **Pausing does not stop the timer.** Discord continues counting elapsed time while paused. The tooltip will show "Paused" though.
- **The timer only redraws every ~15 seconds.** This is a Discord client-side limitation.

### Display

- **The member list only shows "Listening to Apple Music."** Song details are only visible when someone clicks your profile to see the Rich Presence card. This is a Discord limitation -- only Spotify has a native inline integration.
- **Album art may occasionally show the wrong cover.** The search APIs return the best match, which may not always be the exact version, remix, or deluxe edition you are listening to.

### General

- **Track detection has a ~2 second delay** due to the polling interval (configurable).
- **Requires an internet connection** for album art lookups. Track detection itself works offline.
- **Only detects the system's active media session.** If multiple media players are running, only the one Windows considers "current" will be shown.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Could not connect to Discord" | Make sure the Discord desktop app is running (not the browser version) |
| No track detected | Make sure Apple Music is actively playing in your browser (Edge or Chrome) |
| Rich Presence not showing | Check your profile popup or ask a friend -- Discord doesn't always show your own presence to you |
| "The pipe was closed" | Discord was restarted. The app will automatically reconnect within a few seconds |
| Album art not showing | The track may not be indexed in iTunes or Deezer. The Apple Music icon is used as a fallback |

## Roadmap

- [ ] Accurate song position timestamps (requires native Apple Music app from Microsoft Store instead of web player)
- [ ] Album art from the Windows Media Session thumbnail as a final fallback
- [ ] Support for macOS
- [ ] Optional system tray icon with minimize-to-tray
- [ ] Configurable presence format (customize what shows in details/state)
- [ ] Scrobbling to Last.fm

## License

MIT
