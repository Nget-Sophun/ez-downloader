"""Base definitions and data structures for EZ-Downloader extractors.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any


@dataclass
class AuthorInfo:
    nickname: str = ""
    unique_id: str = ""
    avatar: str = ""
    verified: bool = False


@dataclass
class VideoOption:
    label: str = ""
    quality: str = "HD"
    url: str = ""
    size_bytes: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    has_watermark: bool = False


@dataclass
class MusicInfo:
    title: str = ""
    author: str = ""
    play_url: str = ""
    duration: int = 0
    cover: str = ""


@dataclass
class MediaResult:
    platform: str
    id: str
    url: str
    title: str
    author: AuthorInfo
    type: str  # 'video' or 'photo'
    cover: str
    stats: Dict[str, int] = field(default_factory=dict)
    videos: List[VideoOption] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    music: Optional[MusicInfo] = None
    created_at: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
