"""Unified media extractor for TikTok, Douyin, Instagram, Facebook, and YouTube.
"""

from __future__ import annotations
import re
import logging
from typing import Optional, Dict, Any
from .base import MediaResult, VideoOption, MusicInfo, AuthorInfo
from .tiktok import TikTokExtractor
from .douyin import DouyinExtractor
from .instagram import InstagramExtractor
from .facebook import FacebookExtractor
from .youtube import YouTubeExtractor

logger = logging.getLogger("ez_downloader.extractor")


class UnifiedExtractor:
    def __init__(self):
        self.tiktok = TikTokExtractor()
        self.douyin = DouyinExtractor()
        self.instagram = InstagramExtractor()
        self.facebook = FacebookExtractor()
        self.youtube = YouTubeExtractor()

    def extract_url(self, text: str) -> str:
        """Extract first HTTP/HTTPS URL from user input string (handling messy share text)."""
        match = re.search(r'https?://[^\s]+', text)
        if match:
            url = match.group(0).rstrip(' ,;，。！!？”"’\'')
            return url
        return text.strip()

    def identify_platform(self, url: str) -> str:
        url_lower = url.lower()
        if any(h in url_lower for h in ["douyin.com", "iesdouyin.com", "amemv.com"]):
            return "douyin"
        if any(h in url_lower for h in ["tiktok.com", "tiktokv.com"]):
            return "tiktok"
        if any(h in url_lower for h in ["instagram.com", "instagr.am"]):
            return "instagram"
        if any(h in url_lower for h in ["facebook.com", "fb.watch", "fb.gg", "fb.com"]):
            return "facebook"
        if any(h in url_lower for h in ["youtube.com", "youtu.be"]):
            return "youtube"
        return "unknown"

    def fetch(self, input_text: str, custom_cookie: Optional[str] = None) -> MediaResult:
        url = self.extract_url(input_text)
        if not url or not url.startswith("http"):
            raise ValueError("Please provide a valid TikTok, Douyin, Instagram, Facebook, or YouTube link.")

        # Platform check
        platform = self.identify_platform(url)

        # Expand short links if needed to clarify platform
        url_lower = url.lower()
        if any(h in url_lower for h in ["v.douyin.com"]):
            platform = "douyin"
        elif any(h in url_lower for h in ["vm.tiktok.com", "vt.tiktok.com"]):
            platform = "tiktok"
        elif any(h in url_lower for h in ["instagr.am"]):
            platform = "instagram"
        elif any(h in url_lower for h in ["fb.watch", "fb.gg"]):
            platform = "facebook"
        elif any(h in url_lower for h in ["youtu.be"]):
            platform = "youtube"

        if platform == "douyin":
            return self.douyin.fetch(url, custom_cookie=custom_cookie)
        elif platform == "tiktok":
            return self.tiktok.fetch(url, cookie=custom_cookie)
        elif platform == "instagram":
            return self.instagram.fetch(url, cookie=custom_cookie)
        elif platform == "facebook":
            return self.facebook.fetch(url, cookie=custom_cookie)
        elif platform == "youtube":
            return self.youtube.fetch(url, cookie=custom_cookie)
        else:
            # Unknown domain: try extractors in sequence
            extractors = [
                ("youtube", lambda: self.youtube.fetch(url, cookie=custom_cookie)),
                ("tiktok", lambda: self.tiktok.fetch(url, cookie=custom_cookie)),
                ("instagram", lambda: self.instagram.fetch(url, cookie=custom_cookie)),
                ("facebook", lambda: self.facebook.fetch(url, cookie=custom_cookie)),
                ("douyin", lambda: self.douyin.fetch(url, custom_cookie=custom_cookie)),
            ]
            last_err = None
            for name, fn in extractors:
                try:
                    return fn()
                except Exception as e:
                    last_err = e

            raise ValueError(
                f"Could not identify or extract media from link. {last_err or ''}\n"
                "Please verify the URL is a supported TikTok, Douyin, Instagram, Facebook, or YouTube link."
            )
