"""FastAPI web server for EZ-Downloader.
"""

from __future__ import annotations
import os
import subprocess
import urllib.parse
import logging
from typing import Optional, List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from contextlib import asynccontextmanager
from .extractor import UnifiedExtractor
from .downloader import Downloader, sanitize_filename, DEFAULT_DOWNLOAD_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ez_downloader.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Optional embedded Telegram Bot when deployed (e.g. on Render Free Tier)
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    bot_app = None
    if token and token != "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        try:
            from bot import create_telegram_bot
            logger.info("Starting embedded Telegram Bot inside FastAPI...")
            bot_app = create_telegram_bot(token)
            await bot_app.initialize()
            await bot_app.start()
            await bot_app.updater.start_polling()
            logger.info("Telegram Bot is running and listening for messages!")
        except Exception as e:
            logger.warning(f"Could not start embedded Telegram Bot: {e}")

    yield

    if bot_app:
        try:
            logger.info("Stopping Telegram Bot...")
            await bot_app.updater.stop()
            await bot_app.stop()
            await bot_app.shutdown()
            logger.info("Telegram Bot stopped.")
        except Exception as e:
            logger.warning(f"Error stopping Telegram Bot: {e}")


app = FastAPI(
    title="EZ Downloader - TikTok & Douyin",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extractor = UnifiedExtractor()
downloader = Downloader(DEFAULT_DOWNLOAD_DIR)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class AnalyzeRequest(BaseModel):
    url: str
    cookie: Optional[str] = None


class LocalDownloadRequest(BaseModel):
    url: str
    filename: str
    folder: Optional[str] = ""
    referer: Optional[str] = None


class ZipRequest(BaseModel):
    images: List[str]
    title: str
    referer: Optional[str] = None


class LocalAlbumRequest(BaseModel):
    images: List[str]
    title: str
    referer: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>EZ-Downloader Backend Running</h1><p>UI loading...</p>")


@app.post("/api/analyze")
async def analyze_url(req: AnalyzeRequest):
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Please enter a TikTok or Douyin URL.")

    try:
        result = extractor.fetch(req.url, custom_cookie=req.cookie)
        return {"success": True, "data": result.to_dict()}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error analyzing URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/download")
async def download_file(
    url: str = Query(..., description="Remote media URL"),
    filename: str = Query("download.mp4", description="Saved filename"),
    referer: Optional[str] = Query(None, description="Optional referer")
):
    """Stream a remote video, audio, or image directly to the user's browser."""
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter required")

    safe_name = sanitize_filename(filename)
    encoded_filename = urllib.parse.quote(safe_name)

    # Determine media content-type
    ext = os.path.splitext(safe_name)[1].lower()
    content_type = "video/mp4"
    if ext in [".mp3", ".m4a", ".aac"]:
        content_type = "audio/mpeg"
    elif ext in [".jpg", ".jpeg"]:
        content_type = "image/jpeg"
    elif ext == ".png":
        content_type = "image/png"
    elif ext == ".webp":
        content_type = "image/webp"

    try:
        stream = downloader.stream_remote_file(url, referer=referer)
        headers = {
            "Content-Disposition": f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{encoded_filename}',
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
        return StreamingResponse(stream, media_type=content_type, headers=headers)
    except Exception as e:
        logger.error(f"Download streaming error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stream media: {e}")


@app.post("/api/download/local")
async def download_local(req: LocalDownloadRequest):
    """Download directly to the PC's local downloads folder."""
    try:
        saved_path, total_bytes = downloader.save_locally(
            url=req.url,
            filename=req.filename,
            folder_prefix=req.folder or "",
            referer=req.referer
        )
        return {
            "success": True,
            "filepath": saved_path,
            "filename": os.path.basename(saved_path),
            "size_bytes": total_bytes
        }
    except Exception as e:
        logger.error(f"Local download failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")


@app.post("/api/download/zip")
async def download_images_zip(req: ZipRequest):
    """Zip photo album images on the fly and stream as a single ZIP file."""
    if not req.images:
        raise HTTPException(status_code=400, detail="No images provided for zip archive.")

    try:
        zip_buf = downloader.create_images_zip(req.images, req.title, referer=req.referer)
        safe_title = sanitize_filename(req.title or "photo_album", max_len=50)
        zip_filename = f"{safe_title}_images.zip"
        encoded_filename = urllib.parse.quote(zip_filename)

        headers = {
            "Content-Disposition": f'attachment; filename="{zip_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        }
        return StreamingResponse(zip_buf, media_type="application/zip", headers=headers)
    except Exception as e:
        logger.error(f"ZIP creation error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create ZIP: {e}")


@app.post("/api/download/local-album")
async def download_local_album(req: LocalAlbumRequest):
    """Download all album images concurrently into a subfolder in PC downloads directory."""
    if not req.images:
        raise HTTPException(status_code=400, detail="No images provided for album download.")

    try:
        folder_path, total_bytes = downloader.save_images_locally(
            images_urls=req.images,
            album_name=req.title,
            referer=req.referer
        )
        return {
            "success": True,
            "folder_path": folder_path,
            "folder_name": os.path.basename(folder_path),
            "size_bytes": total_bytes,
            "count": len(req.images)
        }
    except Exception as e:
        logger.error(f"Local album save error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save album: {e}")


@app.post("/api/open-folder")
async def open_downloads_folder():
    """Open the downloads directory in Windows File Explorer."""
    path = DEFAULT_DOWNLOAD_DIR
    try:
        if os.name == "nt":
            os.startfile(path)
        else:
            subprocess.run(["xdg-open", path])
        return {"success": True, "path": path}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/downloads-path")
async def get_downloads_path():
    return {"path": DEFAULT_DOWNLOAD_DIR}
