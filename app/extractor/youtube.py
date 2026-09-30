"""YouTube media extractor module supporting standard videos, YouTube Shorts, and audio extraction.
Powered by yt-dlp with support for progressive MP4 streams, high-definition streams, and audio-only tracks.
"""

from __future__ import annotations
import re
import logging
import urllib.parse
from typing import Optional, List, Dict, Any
from .base import MediaResult, AuthorInfo, VideoOption, MusicInfo

logger = logging.getLogger("ez_downloader.youtube")


class YouTubeExtractor:
    def __init__(self):
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

    def clean_url(self, url: str) -> str:
        """Strip tracking parameters while keeping the essential video ID parameter."""
        try:
            video_id = self.extract_id(url)
            if video_id:
                return f"https://www.youtube.com/watch?v={video_id}"
            return url.strip()
        except Exception:
            return url.strip()

    def extract_id(self, url: str) -> Optional[str]:
        """Extract 11-character YouTube video ID from watch, shorts, youtu.be, or embed links."""
        patterns = [
            r"(?:youtu\.be/|youtube\.com/(?:embed/|v/|shorts/|watch\?v=|watch\?.+&v=))([\w-]{11})",
            r"youtube\.com/live/([\w-]{11})",
            r"^([\w-]{11})$"
        ]
        for p in patterns:
            m = re.search(p, url.strip())
            if m:
                return m.group(1)
        return None

    def fetch(self, url: str, cookie: Optional[str] = None) -> MediaResult:
        video_id = self.extract_id(url)
        target_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else url.strip()

        logger.info(f"Extracting YouTube media: {target_url} (ID: {video_id})")

        try:
            import yt_dlp
            from yt_dlp.networking.impersonate import ImpersonateTarget

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": False,
            }
            try:
                ydl_opts["impersonate"] = ImpersonateTarget.from_str("chrome")
            except Exception:
                pass

            if cookie:
                ydl_opts["http_headers"] = {"Cookie": cookie}

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(target_url, download=False)
                if not info:
                    raise RuntimeError("Could not retrieve YouTube video metadata.")

                formats = info.get("formats", [])
                videos: List[VideoOption] = []

                # 1. Collect progressive MP4 formats (both video + audio included)
                progressive = [
                    f for f in formats
                    if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none"
                ]

                # Sort progressive by height and bitrate descending
                progressive.sort(key=lambda x: (x.get("height") or 0, x.get("tbr") or 0), reverse=True)

                for f in progressive:
                    height = f.get("height")
                    quality_label = f"{height}p" if height else "HD"
                    ext = f.get("ext", "mp4").upper()
                    label = f"HD Video ({quality_label} {ext})" if (height and height >= 720) else f"Video ({quality_label} {ext})"
                    videos.append(VideoOption(
                        label=label,
                        quality=quality_label,
                        url=f["url"],
                        size_bytes=f.get("filesize") or f.get("filesize_approx"),
                        width=f.get("width"),
                        height=f.get("height"),
                        has_watermark=False
                    ))

                # 2. Adaptive video streams
                video_only = [
                    f for f in formats
                    if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") == "none"
                ]
                video_only.sort(key=lambda x: (x.get("height") or 0, x.get("tbr") or 0), reverse=True)

                if not videos:
                    # If no progressive formats, add top video streams
                    seen_heights = set()
                    for f in video_only:
                        h = f.get("height") or 0
                        ext = f.get("ext", "mp4").upper()
                        if h not in seen_heights:
                            seen_heights.add(h)
                            q_label = f"{h}p" if h else "HD"
                            label = f"HD Video ({q_label} {ext})" if (h and h >= 720) else f"Video ({q_label} {ext})"
                            videos.append(VideoOption(
                                label=label,
                                quality=q_label,
                                url=f["url"],
                                size_bytes=f.get("filesize") or f.get("filesize_approx"),
                                width=f.get("width"),
                                height=f.get("height"),
                                has_watermark=False
                            ))
                            if len(videos) >= 4:
                                break
                else:
                    # Progressive formats exist; add any higher-resolution streams (e.g. 1080p, 1440p, 4K)
                    max_prog_height = max([v.height or 0 for v in videos], default=0)
                    seen_heights = set()
                    for f in video_only:
                        h = f.get("height") or 0
                        ext = f.get("ext", "mp4").upper()
                        if h > max_prog_height and h not in seen_heights:
                            seen_heights.add(h)
                            videos.append(VideoOption(
                                label=f"Ultra HD Stream ({h}p {ext})",
                                quality=f"{h}p",
                                url=f["url"],
                                size_bytes=f.get("filesize") or f.get("filesize_approx"),
                                width=f.get("width"),
                                height=f.get("height"),
                                has_watermark=False
                            ))
                            if len(videos) >= 5:
                                break

                # 3. Direct URL fallback if formats list didn't yield usable URLs
                if not videos and info.get("url"):
                    videos.append(VideoOption(
                        label="Direct HD Video",
                        quality="HD",
                        url=info["url"],
                        has_watermark=False
                    ))

                # 4. Extract Audio Track (Music/Soundtrack)
                music: Optional[MusicInfo] = None
                audio_formats = [
                    f for f in formats
                    if f.get("url") and f.get("vcodec") == "none" and f.get("acodec") != "none"
                ]
                if audio_formats:
                    # Sort by audio bitrate descending
                    audio_formats.sort(key=lambda x: x.get("abr") or 0, reverse=True)
                    best_audio = audio_formats[0]
                    music = MusicInfo(
                        title=info.get("track") or info.get("title") or "YouTube Audio Track",
                        author=info.get("artist") or info.get("uploader") or "YouTube Creator",
                        play_url=best_audio["url"],
                        duration=int(info.get("duration") or 0),
                        cover=info.get("thumbnail") or ""
                    )

                # Thumbnail / Cover
                cover_url = info.get("thumbnail") or ""
                if not cover_url and video_id:
                    cover_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

                author = AuthorInfo(
                    nickname=info.get("uploader") or info.get("channel") or "YouTube Creator",
                    unique_id=info.get("channel_id") or info.get("uploader_id") or "",
                    avatar=""
                )

                stats = {
                    "digg_count": info.get("like_count", 0),
                    "comment_count": info.get("comment_count", 0),
                    "share_count": 0,
                    "play_count": info.get("view_count", 0)
                }

                return MediaResult(
                    platform="youtube",
                    id=video_id or info.get("id") or "video",
                    url=target_url,
                    title=info.get("title") or "YouTube Video",
                    author=author,
                    type="video",
                    cover=cover_url,
                    stats=stats,
                    videos=videos,
                    images=[],
                    music=music,
                    created_at=str(info.get("upload_date") or "")
                )

        except Exception as e:
            logger.error(f"YouTube extraction error: {e}", exc_info=True)
            raise RuntimeError(
                f"Failed to extract YouTube video: {e}. "
                "Please verify the URL is public and accessible."
            )
