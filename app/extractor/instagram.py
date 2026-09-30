"""Instagram extractor module supporting Reels, Videos, Photos, and multi-slide Carousels.
Features multi-tier fallback:
1. Embed Page contextJSON Scraper (Extracts direct high-res MP4 video and photo carousel URLs without login)
2. yt-dlp fallback (Official-like scraper with direct stream formats and cookie support)
3. Instagram Mobile/Web API with App-ID and cookie support
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

logger = logging.getLogger("ez_downloader.instagram")

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"


def shortcode_to_media_id(shortcode: str) -> str:
    """Convert Instagram Base64 shortcode to numeric media ID."""
    media_id = 0
    for char in shortcode:
        try:
            media_id = media_id * 64 + ALPHABET.index(char)
        except ValueError:
            return ""
    return str(media_id)


class InstagramExtractor:
    def __init__(self):
        self.session = requests.Session()
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

    def clean_url(self, url: str) -> str:
        """Strip tracking query parameters while preserving canonical path."""
        try:
            if "/share/reel/" in url:
                url = url.replace("/share/reel/", "/reel/")
            elif "/share/p/" in url:
                url = url.replace("/share/p/", "/p/")

            parsed = urllib.parse.urlparse(url)
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            return clean.rstrip("/")
        except Exception:
            return url.split("?")[0]

    def extract_id(self, url: str) -> Optional[str]:
        """Extract Instagram shortcode (e.g. C8q43j-S_Wq)."""
        patterns = [
            r"/(?:reel|reels|p|tv|share/reel)/([A-Za-z0-9_-]+)",
            r"instagram\.com/(?:[^/]+/)?(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)",
            r"instagr\.am/p/([A-Za-z0-9_-]+)"
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    def resolve_url(self, url: str) -> str:
        """Resolve short or share links."""
        clean = self.clean_url(url.strip())
        if "instagr.am" in url or "/share/" in url:
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
                logger.warning(f"Error resolving Instagram short link: {e}")
        return clean

    def fetch(self, url: str, cookie: Optional[str] = None) -> MediaResult:
        resolved_url = self.resolve_url(url)
        shortcode = self.extract_id(resolved_url) or self.extract_id(url)
        if not shortcode:
            raise ValueError(f"Could not extract Instagram shortcode from URL: {url}")

        logger.info(f"Extracting Instagram post: {resolved_url} (Shortcode: {shortcode})")

        # Tier 1: Embed Page contextJSON Scraper
        try:
            result = self._fetch_via_embed(shortcode, resolved_url, cookie)
            if result and (result.videos or result.images):
                logger.info(f"Successfully extracted Instagram media via Embed contextJSON: {shortcode}")
                return result
        except Exception as e:
            logger.debug(f"Instagram Embed extraction failed: {e}")

        # Tier 2: yt-dlp fallback
        try:
            logger.info(f"Attempting yt-dlp fallback for Instagram: {resolved_url}")
            result = self._fetch_via_ytdlp(resolved_url, shortcode, cookie)
            if result and (result.videos or result.images):
                logger.info(f"Successfully extracted Instagram media via yt-dlp: {shortcode}")
                return result
        except Exception as e:
            logger.debug(f"Instagram yt-dlp extraction failed: {e}")

        # Tier 3: Instagram Private API endpoint
        try:
            logger.info(f"Attempting Instagram Private API for: {shortcode}")
            result = self._fetch_via_api(shortcode, resolved_url, cookie)
            if result and (result.videos or result.images):
                logger.info(f"Successfully extracted Instagram media via Private API: {shortcode}")
                return result
        except Exception as e:
            logger.debug(f"Instagram Private API extraction failed: {e}")

        raise RuntimeError(
            "Could not extract Instagram media. Instagram may have restricted this post or "
            "requires user authentication. If this is a restricted post, please open Settings (⚙) "
            "and paste your Instagram cookie (sessionid) to download."
        )

    def _fetch_via_embed(self, shortcode: str, original_url: str, cookie: Optional[str] = None) -> Optional[MediaResult]:
        """Extract media from Instagram embed page contextJSON or HTML tags."""
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
        headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.instagram.com/",
        }
        if cookie:
            headers["Cookie"] = cookie

        res = self.session.get(embed_url, headers=headers, impersonate="chrome124", timeout=12)
        if res.status_code != 200 or not res.text:
            return None

        text = res.text

        # 1. Parse contextJSON
        key = '"contextJSON":'
        index = text.find(key)
        media_data = None

        if index != -1:
            try:
                inner, _ = json.JSONDecoder().raw_decode(text, index + len(key))
                if isinstance(inner, str):
                    context = json.loads(inner)
                    media_data = (context.get("gql_data") or {}).get("shortcode_media")
            except Exception as e:
                logger.debug(f"contextJSON decode error: {e}")

        # 2. Check for __additionalDataLoaded
        if not media_data:
            match = re.search(r'window\.__additionalDataLoaded\s*\(\s*[^,]+,\s*({.+?})\s*\)', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    media_data = data.get("graphql", {}).get("shortcode_media") or data.get("shortcode_media")
                except Exception:
                    pass

        # 3. If structured data found, parse it
        if media_data:
            return self._parse_graphql_media(media_data, shortcode, original_url)

        # 4. Fallback: Parse direct video/image URLs in HTML
        video_matches = re.findall(r'<video[^>]+src=["\']([^"\']+)["\']', text) or re.findall(r'"video_url":"([^"]+)"', text)
        img_matches = re.findall(r'<img[^>]+class=["\'][^"\']*EmbeddedMediaImage[^"\']*["\'][^>]+src=["\']([^"\']+)["\']', text)

        if video_matches or img_matches:
            videos: List[VideoOption] = []
            if video_matches:
                v_url = html.unescape(video_matches[0].replace(r"\/", "/").replace(r"\u0026", "&"))
                videos.append(VideoOption(
                    label="HD Video (Highest Quality)",
                    quality="HD",
                    url=v_url,
                    has_watermark=False
                ))

            images: List[str] = []
            for img in img_matches:
                clean_img = html.unescape(img.replace(r"\/", "/").replace(r"\u0026", "&"))
                if clean_img not in images:
                    images.append(clean_img)

            caption_match = re.search(r'<div\s+class="Caption"[^>]*>(.*?)</div>', text, re.DOTALL)
            caption_text = ""
            if caption_match:
                caption_text = re.sub(r'<[^>]+>', '', caption_match.group(1)).strip()

            username_match = re.search(r'<a\s+class="UsernameText"[^>]*>(.*?)</a>', text)
            username = username_match.group(1).strip() if username_match else "Instagram User"

            is_photo = bool(images) and not videos

            return MediaResult(
                platform="instagram",
                id=shortcode,
                url=original_url,
                title=caption_text or f"Instagram post by @{username}",
                author=AuthorInfo(nickname=username, unique_id=username),
                type="photo" if is_photo else "video",
                cover=images[0] if images else "",
                stats={"digg_count": 0, "comment_count": 0, "share_count": 0, "play_count": 0},
                videos=videos,
                images=images,
                music=None
            )

        return None

    def _parse_graphql_media(self, media: dict, shortcode: str, original_url: str) -> MediaResult:
        """Parse Instagram GraphQL shortcode_media dictionary."""
        is_video = media.get("is_video", False)
        caption_edges = (media.get("edge_media_to_caption") or {}).get("edges", [])
        caption_text = caption_edges[0].get("node", {}).get("text", "") if caption_edges else ""

        owner = media.get("owner") or {}
        author = AuthorInfo(
            nickname=owner.get("full_name") or owner.get("username") or "Instagram User",
            unique_id=owner.get("username", ""),
            avatar=owner.get("profile_pic_url", ""),
            verified=bool(owner.get("is_verified"))
        )

        display_url = media.get("display_url") or ""

        # Check for multi-item carousel (photo/video slide album)
        children_edges = (media.get("edge_sidecar_to_children") or {}).get("edges", [])
        images: List[str] = []
        videos: List[VideoOption] = []

        if children_edges:
            for edge in children_edges:
                node = edge.get("node", {})
                if node.get("is_video") and node.get("video_url"):
                    videos.append(VideoOption(
                        label=f"Video Slide #{len(videos) + 1}",
                        quality="HD",
                        url=node["video_url"],
                        has_watermark=False
                    ))
                elif node.get("display_url"):
                    images.append(node["display_url"])
        else:
            if is_video and media.get("video_url"):
                videos.append(VideoOption(
                    label="HD Video (Highest Quality)",
                    quality="HD",
                    url=media["video_url"],
                    has_watermark=False
                ))
            elif display_url:
                images.append(display_url)

        is_photo = bool(images) and not videos

        stats = {
            "digg_count": (media.get("edge_media_preview_like") or {}).get("count", 0),
            "comment_count": (media.get("edge_media_to_parent_comment") or {}).get("count", 0),
            "play_count": media.get("video_view_count") or media.get("video_play_count") or 0
        }

        return MediaResult(
            platform="instagram",
            id=shortcode,
            url=original_url,
            title=caption_text or f"Instagram post by @{author.unique_id}",
            author=author,
            type="photo" if is_photo else "video",
            cover=display_url or (images[0] if images else ""),
            stats=stats,
            videos=videos,
            images=images,
            music=None
        )

    def _fetch_via_ytdlp(self, url: str, shortcode: str, cookie: Optional[str] = None) -> Optional[MediaResult]:
        """Extract Instagram post using yt-dlp."""
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
                images: List[str] = []

                # Handle multi-item Carousel post
                entries = info.get("entries")
                if entries:
                    for e in entries:
                        if not e:
                            continue
                        if e.get("vcodec") != "none" and (e.get("url") or e.get("formats")):
                            vid_url = e.get("url")
                            if not vid_url and e.get("formats"):
                                vid_url = e["formats"][-1].get("url")
                            if vid_url:
                                videos.append(VideoOption(
                                    label=f"Video Slide #{len(videos) + 1}",
                                    quality="HD",
                                    url=vid_url,
                                    has_watermark=False
                                ))
                        elif e.get("thumbnail") or e.get("url"):
                            img_url = e.get("url") or e.get("thumbnail")
                            if img_url and img_url not in images:
                                images.append(img_url)
                else:
                    # Single item (video or photo)
                    formats = info.get("formats", [])
                    progressive = [
                        f for f in formats
                        if f.get("url") and f.get("vcodec") != "none" and f.get("acodec") != "none"
                    ]
                    target_formats = progressive if progressive else [f for f in formats if f.get("url") and f.get("vcodec") != "none"]

                    if target_formats:
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
                    elif info.get("url") and info.get("ext") == "mp4":
                        videos.append(VideoOption(
                            label="Direct HD Video",
                            quality="HD",
                            url=info["url"],
                            has_watermark=False
                        ))

                    if not videos and (info.get("thumbnail") or info.get("url")):
                        images.append(info.get("url") or info.get("thumbnail"))

                if not videos and not images:
                    return None

                author = AuthorInfo(
                    nickname=info.get("uploader") or info.get("channel") or "Instagram Creator",
                    unique_id=info.get("uploader_id") or info.get("uploader") or "",
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

                is_photo = bool(images) and not videos

                return MediaResult(
                    platform="instagram",
                    id=info.get("id") or shortcode,
                    url=url,
                    title=info.get("title") or info.get("description") or f"Instagram media by @{author.unique_id}",
                    author=author,
                    type="photo" if is_photo else "video",
                    cover=info.get("thumbnail") or (images[0] if images else ""),
                    stats={
                        "digg_count": info.get("like_count", 0),
                        "comment_count": info.get("comment_count", 0),
                        "share_count": info.get("repost_count", 0),
                        "play_count": info.get("view_count", 0)
                    },
                    videos=videos,
                    images=images,
                    music=music
                )
        except Exception as e:
            logger.warning(f"Instagram yt-dlp error: {e}")
            return None

    def _fetch_via_api(self, shortcode: str, original_url: str, cookie: Optional[str] = None) -> Optional[MediaResult]:
        """Instagram Private API endpoint with X-IG-App-ID."""
        media_id = shortcode_to_media_id(shortcode)
        if not media_id:
            return None

        api_url = f"https://i.instagram.com/api/v1/media/{media_id}/info/"
        headers = {
            "User-Agent": self.ua,
            "X-IG-App-ID": "936619743392459",
            "Accept": "*/*",
            "Origin": "https://www.instagram.com",
            "Referer": "https://www.instagram.com/",
        }
        if cookie:
            headers["Cookie"] = cookie

        res = self.session.get(api_url, headers=headers, impersonate="chrome124", timeout=12)
        if res.status_code != 200 or not res.text:
            return None

        try:
            data = res.json()
            items = data.get("items", [])
            if not items:
                return None
            item = items[0]

            caption_obj = item.get("caption") or {}
            caption_text = caption_obj.get("text", "") if isinstance(caption_obj, dict) else ""

            user_obj = item.get("user") or {}
            author = AuthorInfo(
                nickname=user_obj.get("full_name") or user_obj.get("username") or "Instagram User",
                unique_id=user_obj.get("username", ""),
                avatar=user_obj.get("profile_pic_url", "")
            )

            videos: List[VideoOption] = []
            images: List[str] = []

            # Check carousel_media
            carousel = item.get("carousel_media") or []
            if carousel:
                for c in carousel:
                    v_versions = c.get("video_versions") or []
                    if v_versions:
                        videos.append(VideoOption(
                            label=f"Video Slide #{len(videos) + 1}",
                            quality="HD",
                            url=v_versions[0]["url"],
                            has_watermark=False
                        ))
                    else:
                        img_candidates = (c.get("image_versions2") or {}).get("candidates") or []
                        if img_candidates:
                            images.append(img_candidates[0]["url"])
            else:
                v_versions = item.get("video_versions") or []
                if v_versions:
                    for idx, v in enumerate(v_versions[:2]):
                        videos.append(VideoOption(
                            label="Original HD Video" if idx == 0 else "Standard Video",
                            quality="HD" if idx == 0 else "SD",
                            url=v["url"],
                            width=v.get("width"),
                            height=v.get("height"),
                            has_watermark=False
                        ))
                else:
                    img_candidates = (item.get("image_versions2") or {}).get("candidates") or []
                    if img_candidates:
                        images.append(img_candidates[0]["url"])

            if not videos and not images:
                return None

            is_photo = bool(images) and not videos

            return MediaResult(
                platform="instagram",
                id=shortcode,
                url=original_url,
                title=caption_text or f"Instagram media by @{author.unique_id}",
                author=author,
                type="photo" if is_photo else "video",
                cover=(item.get("image_versions2") or {}).get("candidates", [{}])[0].get("url", ""),
                stats={
                    "digg_count": item.get("like_count", 0),
                    "comment_count": item.get("comment_count", 0),
                    "play_count": item.get("play_count") or item.get("view_count") or 0
                },
                videos=videos,
                images=images,
                music=None
            )
        except Exception as e:
            logger.debug(f"Private API parse error: {e}")
            return None
