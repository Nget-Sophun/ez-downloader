"""Launcher for EZ-Downloader Web Application.
Starts local server and opens browser automatically.
"""

import sys
import time
import threading
import webbrowser

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import uvicorn

HOST = "127.0.0.1"
PORT = 5000
APP_URL = f"http://{HOST}:{PORT}"


def open_browser():
    time.sleep(1.2)
    print(f"\n[+] Opening browser at {APP_URL} ...")
    webbrowser.open(APP_URL)


def main():
    print("=" * 60)
    print("       EZ-Downloader | TikTok & Douyin (抖音) HD Downloader")
    print(f"       Running at: {APP_URL}")
    print("=" * 60)

    # Launch browser in a background thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start Uvicorn ASGI server
    uvicorn.run("app.server:app", host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
