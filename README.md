# EZ-Downloader 🚀
### High-Definition Media Downloader for TikTok, Douyin (抖音), Instagram, Facebook & YouTube

**EZ-Downloader** is a Python-powered media downloader with a modern Web UI, CLI, and Telegram Bot. It allows you to paste links from **TikTok**, **Douyin (抖音)**, **Instagram** (Reels, Videos, Photos, Carousels), **Facebook** (Reels, Watch, Videos), or **YouTube** (Videos, Shorts, Music) and download original watermark-free HD videos, audio tracks (MP3), or full photo albums with one click.

---

## ✨ Features

- **Multi-Platform Support (TikTok, Douyin, Instagram, Facebook & YouTube)**:
  - Automatically identifies whether the link is from TikTok, Douyin, Instagram, Facebook, or YouTube.
  - Resolves short share links (`v.douyin.com`, `vm.tiktok.com`, `vt.tiktok.com`, `instagr.am`, `fb.watch`, `youtu.be`, `youtube.com/shorts/`, etc.) and messy copied share text with titles or hashtags.
- **YouTube Support**:
  - Download standard YouTube videos, YouTube Shorts, and music videos in progressive HD / MP4.
  - Extract high-quality original audio tracks directly into MP3 with full metadata (title, artist/creator, thumbnail).
  - Adaptive resolution fallback for legacy or high-framerate video clips.
- **Instagram Support**:
  - Download Instagram Reels and Videos in highest quality (1080p HD).
  - Download single photos and multi-image photo carousels (albums).
  - Multi-tier fallback (Embed contextJSON scraper, yt-dlp, and Private API).
- **Facebook Support**:
  - Download Facebook Reels, Watch videos, Page/Profile clips in HD and SD.
  - Multi-tier extraction (direct progressive CDN stream parsing and yt-dlp fallback).
- **Watermark-Free Video Downloads**:
  - Downloads highest quality original streams (1080p / 720p HD) without watermarks.
  - Option to download standard or alternative qualities if available.
- **Audio / Song Extraction**:
  - Extracts the original soundtrack or background music directly to MP3 where available.
  - Built-in audio player for instant playback in browser.
- **Photo Mode / Image Albums**:
  - Full support for TikTok Photo Mode, Douyin Image Notes, and Instagram Photo Carousels.
  - Interactive gallery carousel with thumbnail strip.
  - **1-Click "Download All as ZIP"** to package all high-res photos into a single archive.
  - Download individual full-resolution images or save all directly to PC downloads folder.
- **In-Browser Preview**:
  - Play videos and listen to music tracks directly inside the Web UI before downloading.
- **Fast Direct Streaming**:
  - Integrated local streaming proxy ensures zero CORS errors, no referrer blocking, and maximum download speeds.
- **Local Storage Management**:
  - Automatically organizes files in `./downloads/TikTok/`, `./downloads/Douyin/`, `./downloads/Instagram/`, `./downloads/Facebook/`, and `./downloads/YouTube/`.
  - Quick "Open Downloads Folder" button opens Windows File Explorer directly.
- **Settings & Cookie Manager**:
  - Built-in settings modal for custom cookies to effortlessly bypass platform risk control or access restricted media.

---

## 🚀 Quick Start (Web UI)

### Option 1: Double-click (Windows)
Double-click **`run.bat`** in the project folder. It will start the server and automatically open your default browser at:
```
http://127.0.0.1:5000
```

### Option 2: Command Line
1. Open PowerShell or Terminal in the project folder:
   ```bash
   python run.py
   ```
2. Your browser will automatically launch to the Web UI.

---

## 💻 CLI Usage (Command Line)

You can also download media directly from your terminal using `cli.py`:

```bash
# Download YouTube Video or Short
python cli.py "https://www.youtube.com/watch?v=jNQXAC9IVRw"
python cli.py "https://youtube.com/shorts/5O_R11aZ5t4"

# Download YouTube Audio (MP3) only
python cli.py "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --type audio

# Download Instagram Reel
python cli.py "https://www.instagram.com/reel/C8q43j-S_Wq/"

# Download Facebook Video
python cli.py "https://www.facebook.com/reel/123456789012345"

# Download TikTok / Douyin video
python cli.py "https://v.douyin.com/xxxxxx/"

# Download audio track (MP3) only from TikTok
python cli.py "https://www.tiktok.com/@user/video/1234567890" --type audio

# Download all images in an Instagram or Douyin album
python cli.py "https://www.instagram.com/p/DB123456789/" --type images

# Download everything (Video + Audio + Photos) to a custom folder
python cli.py "https://www.instagram.com/p/DB123456789/" --type all --dir "C:\MyDownloads"

# Use with custom browser cookie (for restricted or age-gated posts)
python cli.py "https://www.instagram.com/reel/xxxxxx/" --cookie "sessionid=..."
```

---

## ⚙️ How to Add a Cookie (If Needed)

For most public videos, no login or cookies are needed.
If a platform (Douyin, Instagram, or Facebook) presents anti-bot verification or restricted access, you can supply your browser cookie once in the **Settings (⚙️)** modal:

1. Open the platform website ([instagram.com](https://www.instagram.com), [facebook.com](https://www.facebook.com), or [douyin.com](https://www.douyin.com)) in Chrome or Edge.
2. Press `F12` to open Developer Tools &rarr; select the **Console** tab.
3. Type:
   ```javascript
   document.cookie
   ```
   and press Enter.
4. Copy the output string.
5. In EZ-Downloader, click the **Settings (⚙️)** button in the top right, paste the cookie, and click **Save Settings**.

---

## 🤖 Telegram Bot & Telegram Mini App

EZ-Downloader can be run as a **Telegram Bot** and **Telegram Mini App (Web App)**!

### 🌟 What the Telegram Bot Does:
1. **Direct Link in Chat**: Users paste any TikTok, Douyin, Instagram, Facebook, or YouTube link into the chat:
   - 🎬 Sends the **HD video** file directly to the chat!
   - 📸 Sends **photo albums and carousels** as a Telegram photo album!
   - 🎵 Sends the **background music track (MP3)** with title and artist where available!
2. **Telegram Mini App Button**: Users can tap **"🚀 Open Web App"** to launch the interactive UI right inside Telegram!

---

### 🛠️ Setting Up Your Telegram Bot

#### Step 1: Create a Bot via `@BotFather`
1. Open Telegram and search for **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot` and choose a name and username (e.g. `MyEzDownloaderBot`).
3. Copy the **HTTP API Token** provided (looks like `123456789:ABCdefGhI...`).

#### Step 2: Configure the Token
In the `ez-downloader` folder, create a `.env` file (or copy from `.env.example`):
```ini
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhI_your_token_here
WEBAPP_URL=https://your-public-url.com
```

#### Step 3: Run the Telegram Bot
Double-click **`run_bot.bat`** or run in your terminal:
```bash
python bot.py
```
*(If you haven't set the token in `.env`, the script will prompt you to enter it once and save it automatically!)*

---

## 📁 Project Structure

```
ez-downloader/
├── app/
│   ├── server.py              # FastAPI server & streaming proxy
│   ├── downloader.py          # Multithreaded engine & ZIP packager
│   ├── extractor/
│   │   ├── __init__.py        # Unified extractor routing (TikTok, Douyin, Instagram, Facebook, YouTube)
│   │   ├── base.py            # Media models & dataclasses
│   │   ├── douyin.py          # Douyin extractor (ttwid & a_bogus signing)
│   │   ├── tiktok.py          # TikTok extractor (TikWM, SSSTik, yt-dlp)
│   │   ├── instagram.py       # Instagram extractor (contextJSON embed, yt-dlp, Private API)
│   │   ├── facebook.py        # Facebook extractor (Direct progressive stream scraper, yt-dlp)
│   │   ├── youtube.py         # YouTube extractor (Videos, Shorts & audio tracks via yt-dlp)
│   │   └── signing/
│   │       ├── abogus.py      # Pure Python A-Bogus signing
│   │       └── sm3.py         # Pure Python SM3 cryptographic hash
│   └── static/
│       ├── index.html         # Responsive web UI with Telegram WebApp SDK
│       ├── app.js             # Telegram WebApp ready/expand & download logic
│       ├── style.css          # Glassmorphic dark theme with platform badges
│       └── avatar_default.svg # Default avatar placeholder
├── downloads/                 # Local directory where files are saved
├── bot.py                     # Telegram Bot & Mini App launcher
├── run_bot.bat                # Windows 1-click Telegram Bot launcher
├── cli.py                     # Command-line downloader tool
├── run.py                     # Web app launcher
├── run.bat                    # Windows 1-click Web launcher
├── requirements.txt           # Python dependencies
├── .env.example               # Example configuration for Telegram Bot
└── README.md                  # Documentation
```

---

## 📜 Dependencies
- Python 3.10+
- `fastapi`, `uvicorn` (Web API Server)
- `curl-cffi` (Chrome TLS impersonation & anti-bot bypass)
- `requests`, `yt-dlp`, `lxml` (Stream extraction & fallback handlers)
- `python-telegram-bot` (Telegram Bot & Mini App integration)
- `python-dotenv` (Environment variable configuration)
- `pydantic` (Data schema validation)
- `imageio-ffmpeg` (FFmpeg binary for slideshow video generation)
