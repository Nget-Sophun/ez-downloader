"""Douyin (抖音) extractor module supporting videos, high-bitrate streams, and image notes.
"""

from __future__ import annotations
import re
import json
import time
import hashlib
import urllib.parse
import logging
from typing import Optional, List, Dict, Any
from curl_cffi import requests
from .base import MediaResult, AuthorInfo, VideoOption, MusicInfo
from .signing.abogus import ABogus

logger = logging.getLogger("ez_downloader.douyin")

SALT = "A96D855A08C0A9707F8BEF0D9A527E4E"


class DouyinExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        self.bogus = ABogus(user_agent=self.ua)
        self.ttwid: Optional[str] = None
        self._ensure_ttwid()

    def _ensure_ttwid(self):
        """Retrieve a fresh ttwid from ByteDance union registration endpoint."""
        try:
            data = json.dumps({
                "region": "cn",
                "aid": 1768,
                "needFid": False,
                "service": "www.ixigua.com",
                "migrate_info": {"ticket": "", "source": "node"},
                "cbUrlProtocol": "https",
                "union": True
            })
            r = self.session.post(
                "https://ttwid.bytedance.com/ttwid/union/register/",
                data=data,
                headers={"Content-Type": "application/json"},
                timeout=6
            )
            self.ttwid = r.cookies.get("ttwid")
        except Exception as e:
            logger.warning(f"Failed to auto-register Douyin ttwid: {e}")

    def extract_id(self, url: str) -> Optional[str]:
        patterns = [
            r"/video/(\d+)",
            r"/note/(\d+)",
            r"/slides/(\d+)",
            r"modal_id=(\d+)",
            r"/(\d{18,20})"
        ]
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return None

    def resolve_url(self, url: str) -> str:
        """Resolve short link v.douyin.com to full canonical URL."""
        if any(h in url for h in ["v.douyin.com", "iesdouyin.com"]):
            try:
                # Disable auto redirect to capture Location
                res = self.session.get(
                    url,
                    allow_redirects=False,
                    impersonate="chrome124",
                    headers={"User-Agent": self.ua},
                    timeout=8
                )
                loc = res.headers.get("Location")
                if loc:
                    return loc
            except Exception as e:
                logger.warning(f"Error resolving Douyin short URL: {e}")
        return url

    def fetch(self, url: str, custom_cookie: Optional[str] = None) -> MediaResult:
        resolved_url = self.resolve_url(url)
        item_id = self.extract_id(resolved_url)

        if not item_id:
            # Try following redirects fully
            try:
                full_r = self.session.get(resolved_url, allow_redirects=True, impersonate="chrome124", timeout=10)
                item_id = self.extract_id(full_r.url)
            except Exception:
                pass

        if not item_id:
            raise ValueError(f"Could not extract Douyin ID from URL: {url}")

        # Try Tier 1: Direct Web API
        result = self._fetch_api(item_id, resolved_url, custom_cookie)
        if result:
            return result

        # Try Tier 2: yt-dlp fallback
        result = self._fetch_ytdlp(resolved_url, item_id, custom_cookie)
        if result:
            return result

        raise RuntimeError(
            "Douyin blocked the request with risk control (ArgusSecurity / IP block). "
            "Please open Settings (⚙) and paste your Douyin browser Cookie to download watermark-free!"
        )

    def _fetch_api(self, aweme_id: str, original_url: str, custom_cookie: Optional[str]) -> Optional[MediaResult]:
        try:
            if not self.ttwid:
                self._ensure_ttwid()

            params = {
                "device_platform": "webapp",
                "aid": "6383",
                "channel": "channel_pc_web",
                "pc_client_type": "1",
                "version_code": "190500",
                "version_name": "19.5.0",
                "cookie_enabled": "true",
                "screen_width": "1920",
                "screen_height": "1080",
                "browser_language": "zh-CN",
                "browser_platform": "Win32",
                "browser_name": "Chrome",
                "browser_version": "130.0.0.0",
                "browser_online": "true",
                "engine_name": "Blink",
                "engine_version": "130.0.0.0",
                "os_name": "Windows",
                "os_version": "10",
                "cpu_core_num": "12",
                "device_memory": "8",
                "platform": "PC",
                "downlink": "10",
                "effective_type": "4g",
                "round_trip_time": "50",
                "aweme_id": aweme_id
            }

            query_str = urllib.parse.urlencode(params)
            sig = self.bogus.get_value(query_str)
            params["a_bogus"] = sig

            cookie_header = custom_cookie or (f"ttwid={self.ttwid}" if self.ttwid else "")
            headers = {
                "User-Agent": self.ua,
                "Referer": "https://www.douyin.com/",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cookie": cookie_header
            }

            api_url = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
            res = self.session.get(api_url, params=params, headers=headers, impersonate="chrome124", timeout=12)

            if res.status_code == 200:
                data = res.json()
                aweme = data.get("aweme_detail")
                if aweme:
                    return self._parse_aweme_detail(aweme, original_url)
            else:
                logger.warning(f"Douyin API returned status {res.status_code}: {res.text[:100]}")
        except Exception as e:
            logger.warning(f"Douyin API error: {e}")
        return None

    def _parse_aweme_detail(self, aweme: dict, original_url: str) -> MediaResult:
        aweme_id = aweme.get("aweme_id", "")
        desc = aweme.get("desc", "")
        author_data = aweme.get("author", {})

        author = AuthorInfo(
            nickname=author_data.get("nickname", "Douyin Creator"),
            unique_id=author_data.get("unique_id") or author_data.get("short_id", ""),
            avatar=(author_data.get("avatar_thumb", {}).get("url_list") or [""])[0],
            verified=bool(author_data.get("custom_verify"))
        )

        stats_data = aweme.get("statistics", {})
        stats = {
            "digg_count": stats_data.get("digg_count", 0),
            "comment_count": stats_data.get("comment_count", 0),
            "share_count": stats_data.get("share_count", 0),
            "play_count": stats_data.get("play_count", 0)
        }

        # Check for photo album (note/slides)
        raw_images = aweme.get("images") or []
        images: List[str] = []
        for img in raw_images:
            url_list = img.get("url_list") or []
            if url_list:
                images.append(url_list[-1])  # Usually highest quality is last

        # Videos
        videos: List[VideoOption] = []
        video_data = aweme.get("video", {})
        play_addr = video_data.get("play_addr", {})
        play_urls = play_addr.get("url_list") or []
        uri = play_addr.get("uri")

        if uri:
            # Original highest quality link
            orig_url = f"https://www.douyin.com/aweme/v1/play/?video_id={uri}&ratio=1080p"
            videos.append(VideoOption(
                label="Original 1080p (No Watermark)",
                quality="1080p",
                url=orig_url,
                has_watermark=False
            ))
            default_url = f"https://www.douyin.com/aweme/v1/play/?video_id={uri}&ratio=default"
            videos.append(VideoOption(
                label="HD Stream (No Watermark)",
                quality="HD",
                url=default_url,
                has_watermark=False
            ))
        elif play_urls:
            clean_url = play_urls[0].replace("playwm", "play")
            videos.append(VideoOption(
                label="HD No Watermark",
                quality="HD",
                url=clean_url,
                has_watermark=False
            ))

        # Check bitrate gears
        bit_rate_list = video_data.get("bit_rate") or []
        for gear in bit_rate_list:
            gear_play = gear.get("play_addr", {})
            gear_urls = gear_play.get("url_list") or []
            if gear_urls:
                gear_name = gear.get("gear_name", "HD")
                bit_rate = gear.get("bit_rate")
                videos.append(VideoOption(
                    label=f"Stream {gear_name.upper()}",
                    quality=gear_name,
                    url=gear_urls[0].replace("playwm", "play"),
                    size_bytes=gear_play.get("data_size"),
                    has_watermark=False
                ))

        # Watermarked fallback
        download_addr = video_data.get("download_addr", {})
        wm_urls = download_addr.get("url_list") or []
        if wm_urls:
            videos.append(VideoOption(
                label="With Watermark",
                quality="SD",
                url=wm_urls[0],
                size_bytes=download_addr.get("data_size"),
                has_watermark=True
            ))

        # Music
        music: Optional[MusicInfo] = None
        music_data = aweme.get("music")
        if music_data:
            music_play = music_data.get("play_url", {})
            m_urls = music_play.get("url_list") or []
            if m_urls:
                music = MusicInfo(
                    title=music_data.get("title", "Original Music"),
                    author=music_data.get("author", "Douyin Artist"),
                    play_url=m_urls[0],
                    duration=music_data.get("duration", 0),
                    cover=(music_data.get("cover_large", {}).get("url_list") or [""])[0]
                )

        cover_urls = video_data.get("cover", {}).get("url_list") or []
        cover = cover_urls[0] if cover_urls else ""

        is_photo = bool(images)

        return MediaResult(
            platform="douyin",
            id=aweme_id,
            url=original_url,
            title=desc or "Douyin Video",
            author=author,
            type="photo" if is_photo else "video",
            cover=cover,
            stats=stats,
            videos=videos,
            images=images,
            music=music,
            created_at=str(aweme.get("create_time", ""))
        )

    def _fetch_ytdlp(self, url: str, item_id: str, cookie: Optional[str]) -> Optional[MediaResult]:
        try:
            import yt_dlp
            from yt_dlp.networking.impersonate import ImpersonateTarget

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True
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
                for f in formats:
                    if f.get("url"):
                        videos.append(VideoOption(
                            label=f"Quality {f.get('height', 'HD')}p",
                            quality=str(f.get("height", "HD")),
                            url=f["url"],
                            size_bytes=f.get("filesize") or f.get("filesize_approx"),
                            has_watermark=False
                        ))

                author = AuthorInfo(
                    nickname=info.get("uploader", "Douyin Creator"),
                    unique_id=info.get("uploader_id", ""),
                    avatar=""
                )

                music: Optional[MusicInfo] = None
                if info.get("track"):
                    music = MusicInfo(
                        title=info.get("track"),
                        author=info.get("artist") or info.get("uploader") or "",
                        play_url="",
                        duration=int(info.get("duration") or 0)
                    )

                return MediaResult(
                    platform="douyin",
                    id=info.get("id") or item_id,
                    url=url,
                    title=info.get("title") or info.get("description") or "Douyin Media",
                    author=author,
                    type="video",
                    cover=info.get("thumbnail") or "",
                    videos=videos,
                    images=[],
                    music=music
                )
        except Exception as e:
            logger.warning(f"Douyin yt-dlp fallback error: {e}")
            return None
