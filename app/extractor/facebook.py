"""Facebook video and reels extractor module.
Supports Facebook Reels, Watch videos, Page/Profile videos, and short links (fb.watch, facebook.com/share).
Features multi-tier fallback:
1. Direct Web Scraper (Extracts direct progressive HD & SD streams from Facebook HTML)
2. yt-dlp fallback (Handles complex video feeds and DASH formats)
"""

from __future__ import annotations
import re
import json
import logging
import html
import urllib.parse
from typing import Optional, List, Dict, Any
from curl_cffi import requests
from .base import MediaResult, AuthorInfo, VideoOption, MusicInfo

logger = logging.getLogger("ez_downloader.facebook")


class FacebookExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

    def clean_url(self, url: str) -> str:
        """Strip tracking query parameters while preserving video parameters like v=..."""
        try:
            parsed = urllib.parse.urlparse(url)
            query_params = urllib.parse.parse_qs(parsed.query)
            keep_params = {}
            if "v" in query_params:
                keep_params["v"] = query_params["v"][0]
            if "video_id" in query_params:
                keep_params["video_id"] = query_params["video_id"][0]
            if "story_fbid" in query_params:
                keep_params["story_fbid"] = query_params["story_fbid"][0]

            new_query = urllib.parse.urlencode(keep_params) if keep_params else ""
            clean = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                "",
                new_query,
                ""
            ))
            return clean.rstrip("/")
        except Exception:
            return url.split("?")[0]

    def extract_id(self, url: str) -> Optional[str]:
        """Extract Facebook Video or Reel ID from URL."""
        patterns = [
            r"/reel/(\d+)",
            r"/videos/(?:[^/]+/)?(\d+)",
            r"[?&]v=(\d+)",
            r"[?&]video_id=(\d+)",
            r"/watch/?\?v=(\d+)",
            r"facebook\.com/watch/(\d+)",
            r"fb\.watch/([A-Za-z0-9_-]+)",
            r"/share/r/([A-Za-z0-9_-]+)",
            r"/share/v/([A-Za-z0-9_-]+)",
            r"/(\d{15,20})"
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    def resolve_url(self, url: str) -> str:
        """Resolve short links (fb.watch, facebook.com/share/r/, etc.) to canonical URLs."""
        if any(h in url.lower() for h in ["fb.watch", "/share/r/", "/share/v/", "fb.gg"]):
            try:
                res = self.session.get(
                    url,
                    allow_redirects=True,
                    impersonate="chrome124",
                    headers={"User-Agent": self.ua},
                    timeout=10
                )
                if res.url:
                    return str(res.url)
            except Exception as e:
                logger.warning(f"Error resolving Facebook short URL: {e}")
        return url

    def fetch(self, url: str, cookie: Optional[str] = None) -> MediaResult:
        resolved_url = self.resolve_url(url.strip())
        clean = self.clean_url(resolved_url)
        item_id = self.extract_id(resolved_url) or self.extract_id(clean) or "video"

        logger.info(f"Extracting Facebook media: {resolved_url} (ID: {item_id})")

        # Tier 1: Direct HTML scraper with browser impersonation
        try:
            result = self._fetch_via_html(resolved_url, item_id, cookie)
            if result and result.videos:
                logger.info(f"Successfully extracted Facebook media via Direct HTML: {item_id}")
                return result
        except Exception as e:
            logger.debug(f"Direct HTML extraction failed: {e}")

        # Tier 2: yt-dlp fallback
        try:
            logger.info(f"Attempting yt-dlp fallback for Facebook: {resolved_url}")
            result = self._fetch_via_ytdlp(resolved_url, item_id, cookie)
            if result:
                return result
        except Exception as e:
            logger.debug(f"yt-dlp extraction failed: {e}")

        raise RuntimeError(
            "Could not extract Facebook video. The video may be private, age-restricted, "
            "or requires authentication. If this is a restricted video, please open Settings (⚙) "
            "and configure your Facebook cookie."
        )

    def _clean_fb_cdn_url(self, raw_url: str) -> str:
        """Clean escaped characters and entities commonly found in Facebook JSON/HTML strings."""
        if not raw_url:
            return ""
        clean = raw_url.replace(r"\/", "/").replace(r"\u0026", "&").replace("&amp;", "&")
        try:
            clean = html.unescape(clean)
        except Exception:
            pass
        return clean.strip()

    def _fetch_via_html(self, url: str, item_id: str, cookie: Optional[str] = None) -> Optional[MediaResult]:
        """Fetch Facebook page and extract playable video streams directly from JSON/script tags."""
        headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Dest": "document",
        }
        if cookie:
            headers["Cookie"] = cookie

        res = self.session.get(url, headers=headers, impersonate="chrome124", timeout=12)
        if res.status_code != 200 or not res.text:
            return None

        text = res.text

        # 1. Search for progressive MP4 video streams
        # HD patterns
        hd_patterns = [
            r'["\']playable_url_quality_hd["\']\s*:\s*["\']([^"\']+)["\']',
            r'["\']browser_native_hd_url["\']\s*:\s*["\']([^"\']+)["\']',
            r'["\']hd_src["\']\s*:\s*["\']([^"\']+)["\']',
            r'["\']hd_src_no_ratelimit["\']\s*:\s*["\']([^"\']+)["\']',
        ]
        # SD patterns
        sd_patterns = [
            r'["\']playable_url["\']\s*:\s*["\']([^"\']+)["\']',
            r'["\']browser_native_sd_url["\']\s*:\s*["\']([^"\']+)["\']',
            r'["\']sd_src["\']\s*:\s*["\']([^"\']+)["\']',
            r'["\']sd_src_no_ratelimit["\']\s*:\s*["\']([^"\']+)["\']',
        ]

        hd_url = None
        for p in hd_patterns:
            m = re.search(p, text)
            if m:
                hd_url = self._clean_fb_cdn_url(m.group(1))
                break

        sd_url = None
        for p in sd_patterns:
            m = re.search(p, text)
            if m:
                sd_url = self._clean_fb_cdn_url(m.group(1))
                break

        videos: List[VideoOption] = []
        if hd_url:
            videos.append(VideoOption(
                label="HD Video (High Definition)",
                quality="HD",
                url=hd_url,
                has_watermark=False
            ))
        if sd_url and sd_url != hd_url:
            videos.append(VideoOption(
                label="SD Video (Standard Quality)",
                quality="SD",
                url=sd_url,
                has_watermark=False
            ))

        if not videos:
            return None

        # 2. Extract Metadata (Title, Description, Author, Cover)
        og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]*)"', text) or re.search(r'<title>(.*?)</title>', text)
        title_str = og_title.group(1) if og_title else "Facebook Video"
        try:
            title_str = html.unescape(title_str).strip()
        except Exception:
            pass

        og_desc = re.search(r'<meta\s+property="og:description"\s+content="([^"]*)"', text)
        desc_str = og_desc.group(1) if og_desc else ""
        try:
            desc_str = html.unescape(desc_str).strip()
        except Exception:
            pass

        final_title = desc_str or title_str
        if len(final_title) > 120:
            final_title = final_title[:117] + "..."

        # Author / Creator
        author_name = "Facebook Creator"
        if title_str and " - " in title_str:
            author_name = title_str.split(" - ")[0].strip()
        elif title_str and " | " in title_str:
            author_name = title_str.split(" | ")[0].strip()

        # Cover thumbnail
        og_image = re.search(r'<meta\s+property="og:image"\s+content="([^"]*)"', text)
        cover_url = self._clean_fb_cdn_url(og_image.group(1)) if og_image else ""

        author = AuthorInfo(
            nickname=author_name,
            unique_id="",
            avatar=""
        )

        return MediaResult(
            platform="facebook",
            id=item_id,
            url=url,
            title=final_title or "Facebook Video",
            author=author,
            type="video",
            cover=cover_url,
            stats={"digg_count": 0, "comment_count": 0, "share_count": 0, "play_count": 0},
            videos=videos,
            images=[],
            music=None
        )

    def _fetch_via_ytdlp(self, url: str, item_id: str, cookie: Optional[str] = None) -> Optional[MediaResult]:
        """yt-dlp fallback for Facebook videos and reels."""
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
                info = ydl.extract_info(url, download=False)
                if not info:
                    return None

                videos: List[VideoOption] = []
                formats = info.get("formats", [])

                # Prefer progressive streams with both audio and video
                progressive = [
                    f for f in formats
                    if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none"
                ]

                target_formats = progressive if progressive else [f for f in formats if f.get("url") and f.get("vcodec") != "none"]

                if target_formats:
                    # Sort by height and bitrate descending
                    target_formats.sort(key=lambda x: (x.get("height") or 0, x.get("tbr") or 0), reverse=True)
                    best = target_formats[0]
                    videos.append(VideoOption(
                        label=f"HD Video ({best.get('height', '1080')}p)",
                        quality=f"{best.get('height', 'HD')}p" if best.get("height") else "HD",
                        url=best["url"],
                        size_bytes=best.get("filesize") or best.get("filesize_approx"),
                        width=best.get("width"),
                        height=best.get("height"),
                        has_watermark=False
                    ))
                    if len(target_formats) > 1:
                        second = target_formats[-1]
                        videos.append(VideoOption(
                            label=f"SD Video ({second.get('height', '720')}p)",
                            quality=f"{second.get('height', 'SD')}p" if second.get("height") else "SD",
                            url=second["url"],
                            size_bytes=second.get("filesize") or second.get("filesize_approx"),
                            width=second.get("width"),
                            height=second.get("height"),
                            has_watermark=False
                        ))
                elif info.get("url"):
                    videos.append(VideoOption(
                        label="Direct Video Stream",
                        quality="HD",
                        url=info["url"],
                        has_watermark=False
                    ))

                if not videos:
                    return None

                author = AuthorInfo(
                    nickname=info.get("uploader") or "Facebook Creator",
                    unique_id=info.get("uploader_id", ""),
                    avatar=""
                )

                music: Optional[MusicInfo] = None
                if info.get("track") or info.get("music"):
                    music = MusicInfo(
                        title=info.get("track") or info.get("music") or "Original Audio",
                        author=info.get("artist") or author.nickname,
                        play_url="",
                        duration=int(info.get("duration") or 0)
                    )

                return MediaResult(
                    platform="facebook",
                    id=info.get("id") or item_id,
                    url=url,
                    title=info.get("title") or info.get("description") or "Facebook Video",
                    author=author,
                    type="video",
                    cover=info.get("thumbnail") or "",
                    stats={
                        "digg_count": info.get("like_count", 0),
                        "comment_count": info.get("comment_count", 0),
                        "share_count": info.get("repost_count", 0),
                        "play_count": info.get("view_count", 0)
                    },
                    videos=videos,
                    images=[],
                    music=music
                )
        except Exception as e:
            logger.warning(f"Facebook yt-dlp error: {e}")
            return None
