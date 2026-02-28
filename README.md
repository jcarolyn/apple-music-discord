# Apple Music → Discord Rich Presence

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
4. *(Optional)* Under **Rich Presence → Art Assets**, upload an image named `apple_music` to use as the large icon

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
00:47:21  Apple Music → Discord Rich Presence
00:47:21  Polling every 5s. Press Ctrl+C to stop.
00:47:21  Connected to Discord
00:47:22  ▶ Unisex — Foggieraw
```

Press `Ctrl+C` to stop.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DISCORD_APP_ID`    | *(required)* | Your Discord Application ID |
| `POLL_INTERVAL`     | `5`     | Seconds between track checks |

## Troubleshooting

- **"Could not connect to Discord"** — Make sure Discord is running and not in a browser
- **No track detected** — Make sure Apple Music (or iTunes) is actively playing a song
- **Rich Presence not showing** — It can take a few seconds to appear; also, Discord doesn't show your own Rich Presence to you in all views — ask a friend to check, or look at your profile popup
