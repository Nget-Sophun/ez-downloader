"""Unified media extractor for TikTok and Douyin.
"""

from __future__ import annotations
import re
import logging
from typing import Optional, Dict, Any
from .base import MediaResult, VideoOption, MusicInfo, AuthorInfo
from .tiktok import TikTokExtractor
from .douyin import DouyinExtractor

logger = logging.getLogger("ez_downloader.extractor")


class UnifiedExtractor:
    def __init__(self):
        self.tiktok = TikTokExtractor()
        self.douyin = DouyinExtractor()

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
        return "unknown"

    def fetch(self, input_text: str, custom_cookie: Optional[str] = None) -> MediaResult:
        url = self.extract_url(input_text)
        if not url or not url.startswith("http"):
            raise ValueError("Please provide a valid TikTok or Douyin link.")

        # Platform check
        platform = self.identify_platform(url)

        # Expand short link if needed to clarify platform
        if any(h in url.lower() for h in ["v.douyin.com"]):
            platform = "douyin"
        elif any(h in url.lower() for h in ["vm.tiktok.com", "vt.tiktok.com"]):
            platform = "tiktok"

        if platform == "douyin":
            return self.douyin.fetch(url, custom_cookie=custom_cookie)
        elif platform == "tiktok":
            return self.tiktok.fetch(url, cookie=custom_cookie)
        else:
            # Try TikTok first, then Douyin
            try:
                return self.tiktok.fetch(url, cookie=custom_cookie)
            except Exception:
                return self.douyin.fetch(url, custom_cookie=custom_cookie)
