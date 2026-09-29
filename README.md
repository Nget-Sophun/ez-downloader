# EZ-Downloader 🚀
### High-Definition Media Downloader for TikTok & Douyin (抖音)

**EZ-Downloader** is a Python-powered media downloader with a modern Web UI and CLI. It allows you to paste links from **TikTok** or **Douyin (抖音)** and download original watermark-free HD videos, audio tracks (MP3), or full photo album slides with one click.

---

## ✨ Features

- **TikTok & Douyin (抖音) Support**:
  - Automatically identifies whether the link is from TikTok or Douyin.
  - Resolves short share links (`v.douyin.com`, `vm.tiktok.com`, `vt.tiktok.com`) and messy copied share text with titles or hashtags.
- **Watermark-Free Video Downloads**:
  - Downloads highest quality original streams (1080p / 720p HD) without watermarks.
  - Option to download standard or watermarked versions if desired.
- **Audio / Song Extraction**:
  - Extracts the original soundtrack or background music directly to MP3.
  - Built-in audio player for instant playback in browser.
- **Photo Mode / Image Albums**:
  - Full support for TikTok Photo Mode and Douyin Image Carousels (Notes / Slides).
  - Interactive gallery carousel with thumbnail strip.
  - **1-Click "Download All as ZIP"** to package all high-res photos into a single archive.
  - Download individual full-resolution images.
- **In-Browser Preview**:
  - Play videos and listen to music tracks directly inside the Web UI before downloading.
- **Fast Direct Streaming**:
  - Integrated local streaming proxy ensures zero CORS errors, no referrer blocking, and maximum download speeds.
- **Local Storage Management**:
  - Automatically organizes files in `./downloads/TikTok/` and `./downloads/Douyin/`.
  - Quick "Open Downloads Folder" button opens Windows File Explorer directly.
- **Settings & Cookie Manager**:
  - Built-in setting modal for custom cookies to effortlessly bypass platform risk control (ArgusSecurity).

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
# Download highest quality video (No Watermark)
python cli.py "https://v.douyin.com/xxxxxx/"

# Download audio track (MP3) only
python cli.py "https://www.tiktok.com/@user/video/1234567890" --type audio

# Download all images in a photo album
python cli.py "https://www.douyin.com/note/1234567890" --type images

# Download everything (Video + Audio + Photos) to a custom folder
python cli.py "https://v.douyin.com/xxxxxx/" --type all --dir "C:\MyDownloads"

# Use with custom browser cookie
python cli.py "https://v.douyin.com/xxxxxx/" --cookie "ttwid=...; sessionid=..."
```

---

## ⚙️ How to Add a Douyin / TikTok Cookie (If Needed)

For public TikTok videos, no login or cookies are needed.
If Douyin presents anti-bot verification (**ArgusSecurity**), you can supply your browser cookie once in the **Settings (⚙️)** modal:

1. Open [douyin.com](https://www.douyin.com) in Chrome or Edge.
2. Press `F12` to open Developer Tools &rarr; select the **Console** tab.
3. Type:
   ```javascript
   document.cookie
   ```
   and press Enter.
4. Copy the output string.
5. In EZ-Downloader, click the **Settings (⚙️)** button in the top right, paste the cookie, and click **Save Settings**.

---

## 📁 Project Structure

```
ez-downloader/
├── app/
│   ├── server.py              # FastAPI server & download streaming proxy
│   ├── downloader.py          # Chunked download engine & ZIP packager
│   ├── extractor/
│   │   ├── __init__.py        # Unified extractor routing
│   │   ├── base.py            # Media models & dataclasses
│   │   ├── douyin.py          # Douyin extractor (ttwid & a_bogus signing)
│   │   ├── tiktok.py          # TikTok extractor (TikWM & yt-dlp fallbacks)
│   │   └── signing/
│   │       ├── abogus.py      # Pure Python A-Bogus signing
│   │       └── sm3.py         # Pure Python SM3 cryptographic hash
│   └── static/
│       ├── index.html         # Responsive web application interface
│       ├── app.js             # Client-side UI & download handlers
│       ├── style.css          # Glassmorphic dark theme
│       └── avatar_default.svg # Default avatar placeholder
├── downloads/                 # Local directory where files are saved
├── cli.py                     # Command-line downloader tool
---

## 🤖 Telegram Bot & Telegram Mini App

EZ-Downloader can be deployed as a **Telegram Bot** and **Telegram Mini App (Web App)**!

### 🌟 What the Telegram Bot Does:
1. **Direct Link in Chat**: Users paste any TikTok or Douyin link into the chat:
   - 🎬 Sends the **watermark-free HD video** file directly to the chat!
   - 📸 Sends all **photo album images** as a Telegram photo carousel!
   - 🎵 Sends the **background music track (MP3)** with title and artist!
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

### 🌐 Setting Up the Telegram Mini App (Web App)

Telegram Web Apps require a secure **`https://`** URL to open inside Telegram.

#### Free Local Tunnel (for Testing & Local Hosting):
You can expose your local server (`http://127.0.0.1:5000`) with Cloudflare Tunnel or ngrok:

1. **Option A: Cloudflare Tunnel (Free, no account needed)**:
   ```bash
   # Download cloudflared or run:
   cloudflared tunnel --url http://127.0.0.1:5000
   ```
   Copy the generated `https://xxxx.trycloudflare.com` URL.

2. **Option B: ngrok**:
   ```bash
   ngrok http 5000
   ```
   Copy the generated `https://xxxx.ngrok-free.app` URL.

#### Add Web App to Telegram Menu Button:
1. Go back to **[@BotFather](https://t.me/BotFather)** on Telegram.
2. Send `/setmenubutton`.
3. Select your bot.
4. Paste your `https://...` URL and name the button (e.g. `🚀 Open Downloader`).
5. Now users will see a persistent **Menu** button at the bottom of the chat that opens the full Web App inside Telegram!

---

## 📁 Project Structure

```
ez-downloader/
├── app/
│   ├── server.py              # FastAPI server & streaming proxy
│   ├── downloader.py          # Multithreaded engine & ZIP packager
│   ├── extractor/
│   │   ├── __init__.py        # Unified extractor routing
│   │   ├── base.py            # Media models & dataclasses
│   │   ├── douyin.py          # Douyin extractor (ttwid & a_bogus signing)
│   │   ├── tiktok.py          # TikTok extractor (TikWM, SSSTik, yt-dlp)
│   │   └── signing/
│   │       ├── abogus.py      # Pure Python A-Bogus signing
│   │       └── sm3.py         # Pure Python SM3 cryptographic hash
│   └── static/
│       ├── index.html         # Responsive web UI with Telegram WebApp SDK
│       ├── app.js             # Telegram WebApp ready/expand & download logic
│       ├── style.css          # Glassmorphic dark theme
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
