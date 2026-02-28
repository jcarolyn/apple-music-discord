# Apple Music -> Discord Rich Presence

Display your currently playing Apple Music track as Discord Rich Presence on Windows.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

## How it works

1. Reads the currently playing track from Windows Media Session API (no scraping, no hacks)
2. Sends the song title, artist, and album to Discord via local Rich Presence RPC
3. Polls every 5 seconds and updates automatically when the track changes

## Setup

### 1. Create a Discord Application

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** and give it a name (e.g. "Apple Music")
3. Copy the **Application ID** from the General Information page
4. *(Optional)* Under **Rich Presence -> Art Assets**, upload an image named `apple_music` to use as the large icon

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

- **Use a Chromium-based browser (Edge, Chrome) for Apple Music.** Firefox does not send continuous playback position updates to the Windows Media Session API, so the elapsed time shown in Discord will be inaccurate. Edge and Chrome work correctly.
- **The Discord Rich Presence timer updates visually every ~15 seconds.** This is a Discord client limitation -- the underlying timestamp is accurate, but Discord only redraws the timer display periodically, not every second.
- **Album art is not shown.** Discord Rich Presence requires pre-uploaded images or external URLs. Dynamic album art from Apple Music is not currently supported.

## Troubleshooting

- **"Could not connect to Discord"** -- Make sure Discord is running (desktop app, not browser)
- **No track detected** -- Make sure Apple Music is actively playing a song
- **Rich Presence not showing** -- It can take a few seconds to appear. Discord doesn't show your own Rich Presence to you in all views -- check your profile popup or ask a friend
- **"The pipe was closed"** -- This happens when Discord is restarted. The app will automatically reconnect within a few seconds
