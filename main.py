"""Entrypoint for Render / Cloud deployment.
Automatically reads PORT environment variable and starts FastAPI with embedded Telegram Bot.
"""

import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[*] Starting EZ-Downloader on 0.0.0.0:{port}...")
    uvicorn.run("app.server:app", host="0.0.0.0", port=port)
