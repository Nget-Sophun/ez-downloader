"""TikTok extractor module supporting both videos and photo mode albums.
Features multi-tier fallback:
1. TikWM API (High-speed metadata with direct HD video, album images & MP3 audio)
2. SSSTik Scraper (Resilient secondary provider for watermark-free videos, photo slides & MP3 audio)
3. yt-dlp fallback (Official-like scraper with direct stream formats)
"""

from __future__ import annotations
import re
import json
import logging
import urllib.parse
from typing import Optional, List, Dict, Any
from curl_cffi import requests
from lxml import html
from .base import MediaResult, AuthorInfo, VideoOption, MusicInfo

logger = logging.getLogger("ez_downloader.tiktok")

TIKWM_API = "https://www.tikwm.com/api/"


class TikTokExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

    def extract_id(self, url: str) -> Optional[str]:
        patterns = [
            r"/video/(\d+)",
            r"/photo/(\d+)",
            r"/slides/(\d+)",
            r"itemId=(\d+)",
            r"/v/(\d+)",
            r"item_id=(\d+)",
            r"/(\d{18,20})"
        ]
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return None

    def clean_url(self, url: str) -> str:
        """Strip tracking parameters while keeping canonical path."""
        try:
            parsed = urllib.parse.urlparse(url)
            # Retain scheme + netloc + path
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            return clean.rstrip("/")
        except Exception:
            return url.split("?")[0]

    def resolve_url(self, url: str) -> str:
        """Expand short URLs (vm.tiktok.com, vt.tiktok.com) to their canonical target."""
        if any(h in url for h in ["vm.tiktok.com", "vt.tiktok.com", "m.tiktok.com"]):
            try:
                # First attempt without auto-redirect to capture Location header directly
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

                # Fallback to allow_redirects
                res2 = self.session.get(
                    url,
                    allow_redirects=True,
                    impersonate="chrome124",
                    headers={"User-Agent": self.ua},
                    timeout=10
                )
                if res2.url:
                    return str(res2.url)
            except Exception as e:
                logger.warning(f"Error expanding TikTok short URL: {e}")
        return url

    def fetch(self, url: str, cookie: Optional[str] = None) -> MediaResult:
        resolved_url = self.resolve_url(url.strip())
        item_id = self.extract_id(resolved_url) or ""

        # Tier 1: TikWM API
        logger.info(f"Extracting TikTok via TikWM: {resolved_url} (ID: {item_id})")
        result = self._fetch_via_tikwm(resolved_url, item_id)
        if result:
            return result

        # Tier 2: SSSTik Scraper (Strong support for both photo slides and MP3 audio)
        logger.info(f"Extracting TikTok via SSSTik fallback: {resolved_url}")
        result = self._fetch_via_ssstik(resolved_url, item_id)
        if result:
            return result

        # Tier 3: yt-dlp fallback
        logger.info(f"Extracting TikTok via yt-dlp fallback: {resolved_url}")
        result = self._fetch_via_ytdlp(resolved_url, item_id, cookie)
        if result:
            return result

        raise RuntimeError(
            f"Unable to extract TikTok media from URL: {url}. "
            "The post may be private, deleted, or region-restricted."
        )

    def _fetch_via_tikwm(self, url: str, item_id: str) -> Optional[MediaResult]:
        clean = self.clean_url(url)
        # Formulate candidate query URLs to ensure TikWM matches
        candidates = [clean, url]
        if "/photo/" in clean:
            candidates.append(clean.replace("/photo/", "/video/"))
        if item_id:
            candidates.append(f"https://www.tiktok.com/@user/video/{item_id}")
            candidates.append(f"https://m.tiktok.com/v/{item_id}.html")

        headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }

        for candidate_url in candidates:
            try:
                payload = {"url": candidate_url, "hd": 1}
                res = self.session.post(TIKWM_API, data=payload, headers=headers, timeout=12)
                if res.status_code != 200:
                    continue

                data = res.json()
                if data.get("code") != 0 or not data.get("data"):
                    continue

                d = data["data"]
                base = "https://www.tikwm.com"

                def fix_url(u: Optional[str]) -> str:
                    if not u:
                        return ""
                    if u.startswith("http"):
                        return u
                    return base + u

                # Extract Images (Photo Slideshow Mode)
                images: List[str] = []
                raw_images = d.get("images") or []
                if not raw_images and isinstance(d.get("image_post_info"), dict):
                    raw_images = d.get("image_post_info", {}).get("images", [])

                for item in raw_images:
                    if isinstance(item, str) and item:
                        images.append(fix_url(item))
                    elif isinstance(item, dict):
                        # Could be { "url": "..." } or { "display_image": { "url_list": [...] } }
                        img_url = (
                            item.get("url")
                            or (item.get("display_image", {}).get("url_list") or [""])[0]
                            or (item.get("imageURL", {}).get("urlList") or [""])[0]
                            or item.get("download_url")
                        )
                        if img_url:
                            images.append(fix_url(img_url))

                # Extract Videos
                videos: List[VideoOption] = []
                hd_url = fix_url(d.get("hdplay"))
                play_url = fix_url(d.get("play"))
                wm_url = fix_url(d.get("wmplay"))

                if hd_url:
                    videos.append(VideoOption(
                        label="HD No Watermark (Highest Quality)",
                        quality="HD",
                        url=hd_url,
                        size_bytes=d.get("hd_size") or d.get("size"),
                        has_watermark=False
                    ))
                if play_url and play_url != hd_url:
                    videos.append(VideoOption(
                        label="Standard No Watermark",
                        quality="SD",
                        url=play_url,
                        size_bytes=d.get("size"),
                        has_watermark=False
                    ))
                if wm_url:
                    videos.append(VideoOption(
                        label="With Watermark",
                        quality="SD",
                        url=wm_url,
                        size_bytes=d.get("wm_size"),
                        has_watermark=True
                    ))

                # Extract Music / Audio (Guaranteed check across multiple fields)
                music: Optional[MusicInfo] = None
                music_info = d.get("music_info") or {}
                music_url = (
                    d.get("music")
                    or music_info.get("play")
                    or music_info.get("play_url")
                    or music_info.get("url")
                )
                if music_url:
                    music_url = fix_url(music_url)
                    music = MusicInfo(
                        title=music_info.get("title") or d.get("title") or "Original Sound",
                        author=music_info.get("author") or d.get("author", {}).get("nickname") or "TikTok Creator",
                        play_url=music_url,
                        duration=music_info.get("duration") or 0,
                        cover=fix_url(music_info.get("cover"))
                    )

                author_data = d.get("author") or {}
                author = AuthorInfo(
                    nickname=author_data.get("nickname", "TikTok User"),
                    unique_id=author_data.get("unique_id", ""),
                    avatar=fix_url(author_data.get("avatar", ""))
                )

                stats = {
                    "digg_count": d.get("digg_count", 0),
                    "comment_count": d.get("comment_count", 0),
                    "share_count": d.get("share_count", 0),
                    "play_count": d.get("play_count", 0)
                }

                is_photo = bool(images)

                return MediaResult(
                    platform="tiktok",
                    id=d.get("id") or item_id,
                    url=url,
                    title=d.get("title") or "TikTok Post",
                    author=author,
                    type="photo" if is_photo else "video",
                    cover=fix_url(d.get("cover")),
                    stats=stats,
                    videos=videos,
                    images=images,
                    music=music,
                    created_at=str(d.get("create_time", ""))
                )
            except Exception as e:
                logger.debug(f"TikWM attempt for {candidate_url} failed: {e}")

        return None

    def _fetch_via_ssstik(self, url: str, item_id: str) -> Optional[MediaResult]:
        """Fetch media using SSSTik with full support for photo albums and MP3 audio."""
        try:
            get_headers = {
                "User-Agent": self.ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            }
            home_res = self.session.get("https://ssstik.io/en", headers=get_headers, impersonate="chrome124", timeout=10)
            if home_res.status_code != 200:
                return None

            # Extract dynamic form token (s_tt or tt)
            m = re.search(r's_tt\s*=\s*[\'"]([^\'"]+)[\'"]', home_res.text) or re.search(r'tt:[\'"]([^\'"]+)[\'"]', home_res.text)
            if not m:
                return None
            token = m.group(1)

            post_headers = {
                "User-Agent": self.ua,
                "hx-current-url": "https://ssstik.io/en",
                "hx-request": "true",
                "hx-target": "target",
                "hx-trigger": "_gcaptcha_pt",
                "Origin": "https://ssstik.io",
                "Referer": "https://ssstik.io/en"
            }

            clean = self.clean_url(url)
            payload = {
                "id": clean,
                "locale": "en",
                "tt": token
            }

            post_res = self.session.post("https://ssstik.io/abc?url=dl", data=payload, headers=post_headers, impersonate="chrome124", timeout=12)
            if post_res.status_code != 200 or not post_res.text:
                return None

            tree = html.fromstring(post_res.text)

            # Check for error banners
            if "Video currently unavailable" in post_res.text or "not able to reach" in post_res.text:
                return None

            # Extract Title / Description
            title = ""
            maintext_el = tree.xpath("//p[contains(@class, 'maintext')]")
            if maintext_el:
                title = maintext_el[0].text_content().strip()

            # Extract Author
            avatar_url = ""
            author_img = tree.xpath("//img[contains(@class, 'result_author')]")
            if author_img:
                avatar_url = author_img[0].get("src", "")

            author = AuthorInfo(
                nickname="TikTok Creator",
                unique_id="",
                avatar=avatar_url
            )

            # Extract Images (Photo Slideshow mode)
            images: List[str] = []
            # Check for Splide carousel slides
            slide_links = tree.xpath("//div[contains(@class, 'splide')]//a") or tree.xpath("//ul[contains(@class, 'splide__list')]//a")
            for a in slide_links:
                href = a.get("href", "")
                if href and href.startswith("http") and "tiktok" in href or "tikcdn" in href:
                    if href not in images:
                        images.append(href)

            # Also check direct download image links
            if not images:
                for a in tree.xpath("//a[contains(@class, 'download_link')]"):
                    href = a.get("href", "")
                    classes = a.get("class", "")
                    text = a.text_content().strip().lower()
                    if "music" not in classes and "mp3" not in text and ("photo" in href or "image" in text or "tikcdn.io" in href):
                        if href and href not in images and not href.endswith(".mp4"):
                            images.append(href)

            # Extract Music / Audio
            music: Optional[MusicInfo] = None
            music_links = tree.xpath("//a[contains(@class, 'music')]") or tree.xpath("//a[contains(text(), 'MP3') or contains(@href, '.mp3')]")
            for a in music_links:
                href = a.get("href", "")
                if href and href.startswith("http"):
                    music = MusicInfo(
                        title=title[:40] if title else "Original Sound",
                        author=author.nickname,
                        play_url=href,
                        duration=0
                    )
                    break

            # Extract Videos
            videos: List[VideoOption] = []
            video_links = tree.xpath("//a[contains(@class, 'without_watermark')]")
            for i, a in enumerate(video_links):
                href = a.get("href", "")
                if href and href.startswith("http"):
                    is_hd = "hd" in a.get("class", "").lower() or "hd" in a.text_content().lower()
                    videos.append(VideoOption(
                        label="HD No Watermark" if is_hd else "Standard No Watermark",
                        quality="HD" if is_hd else "SD",
                        url=href,
                        has_watermark=False
                    ))

            if not videos and not images and not music:
                return None

            is_photo = bool(images)

            return MediaResult(
                platform="tiktok",
                id=item_id,
                url=url,
                title=title or "TikTok Post",
                author=author,
                type="photo" if is_photo else "video",
                cover=images[0] if images else "",
                stats={"digg_count": 0, "comment_count": 0, "share_count": 0, "play_count": 0},
                videos=videos,
                images=images,
                music=music
            )
        except Exception as e:
            logger.warning(f"SSSTik fallback error: {e}")
            return None

    def _fetch_via_ytdlp(self, url: str, item_id: str, cookie: Optional[str] = None) -> Optional[MediaResult]:
        try:
            import yt_dlp
            from yt_dlp.networking.impersonate import ImpersonateTarget

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "extract_flat": False,
                "skip_download": True,
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

                # Pick best mp4 formats
                video_formats = [f for f in formats if f.get("ext") == "mp4" and f.get("url")]
                if video_formats:
                    video_formats.sort(key=lambda x: (x.get("height") or 0, x.get("tbr") or 0), reverse=True)
                    best = video_formats[0]
                    videos.append(VideoOption(
                        label=f"Highest Quality ({best.get('height', '1080')}p)",
                        quality=f"{best.get('height', '1080')}p",
                        url=best["url"],
                        size_bytes=best.get("filesize") or best.get("filesize_approx"),
                        width=best.get("width"),
                        height=best.get("height"),
                        has_watermark=False
                    ))
                    if len(video_formats) > 1:
                        second = video_formats[-1]
                        videos.append(VideoOption(
                            label=f"Standard Quality ({second.get('height', '720')}p)",
                            quality=f"{second.get('height', '720')}p",
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

                author = AuthorInfo(
                    nickname=info.get("uploader", "TikTok Creator"),
                    unique_id=info.get("uploader_id", ""),
                    avatar=""
                )

                # Extract audio stream URL if present
                music: Optional[MusicInfo] = None
                audio_formats = [f for f in formats if f.get("vcodec") == "none" and f.get("url")]
                audio_url = audio_formats[0]["url"] if audio_formats else ""

                if info.get("track") or info.get("music") or audio_url:
                    music = MusicInfo(
                        title=info.get("track") or info.get("music") or "Original Sound",
                        author=info.get("artist") or info.get("uploader") or "",
                        play_url=audio_url,
                        duration=int(info.get("duration") or 0)
                    )

                # Thumbnails / images
                images: List[str] = []
                thumbnails = info.get("thumbnails", [])
                if len(thumbnails) > 1:
                    # In some slideshows, thumbnails contain all slide images
                    for t in thumbnails:
                        t_url = t.get("url")
                        if t_url and t_url not in images:
                            images.append(t_url)

                stats = {
                    "digg_count": info.get("like_count", 0),
                    "comment_count": info.get("comment_count", 0),
                    "share_count": info.get("repost_count", 0),
                    "play_count": info.get("view_count", 0)
                }

                is_photo = bool(images) and not videos

                return MediaResult(
                    platform="tiktok",
                    id=info.get("id") or item_id,
                    url=url,
                    title=info.get("title") or info.get("description") or "TikTok Post",
                    author=author,
                    type="photo" if is_photo else "video",
                    cover=info.get("thumbnail") or "",
                    stats=stats,
                    videos=videos,
                    images=images,
                    music=music
                )
        except Exception as e:
            logger.warning(f"yt-dlp TikTok fallback error: {e}")
            return None
