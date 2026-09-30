"""Download and streaming utility with sanitize, chunking, and zip support.
"""

from __future__ import annotations
import os
import re
import io
import zipfile
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Generator, Optional, List, Tuple
from curl_cffi import requests

logger = logging.getLogger("ez_downloader.downloader")

DEFAULT_DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "downloads"))


def sanitize_filename(name: str, max_len: int = 80) -> str:
    """Clean string to be valid across Windows and UNIX filesystem."""
    clean = re.sub(r'[\\/*?:"<>|#\n\r\t]', "", name)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        clean = "media_download"
    return clean[:max_len].strip()


class Downloader:
    def __init__(self, download_dir: str = DEFAULT_DOWNLOAD_DIR):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

    def get_headers(self, referer: Optional[str] = None, target_url: Optional[str] = None) -> dict:
        """Infer proper referer and anti-bot headers for the given CDN URL."""
        headers = {"User-Agent": self.ua}
        if referer:
            headers["Referer"] = referer
        elif target_url:
            if "tikwm.com" in target_url:
                headers["Referer"] = "https://www.tikwm.com/"
            elif "ssstik.io" in target_url or "tikcdn.io" in target_url:
                headers["Referer"] = "https://ssstik.io/"
            elif any(d in target_url for d in ["tiktokcdn", "byteoversea", "ibytedtos", "tiktok.com"]):
                headers["Referer"] = "https://www.tiktok.com/"
            elif any(d in target_url for d in ["douyin", "snssdk", "zijieapi"]):
                headers["Referer"] = "https://www.douyin.com/"
            elif any(d in target_url for d in ["instagram", "cdninstagram"]):
                headers["Referer"] = "https://www.instagram.com/"
            elif any(d in target_url for d in ["facebook", "fbcdn", "fbsbx"]):
                headers["Referer"] = "https://www.facebook.com/"
            elif any(d in target_url for d in ["youtube", "googlevideo", "ytimg", "youtu.be"]):
                headers["Referer"] = "https://www.youtube.com/"
        return headers

    def stream_remote_file(self, url: str, referer: Optional[str] = None, chunk_size: int = 65536) -> Generator[bytes, None, None]:
        """Stream an external URL chunk by chunk to FastAPI StreamingResponse."""
        headers = self.get_headers(referer=referer, target_url=url)
        try:
            res = requests.get(url, headers=headers, stream=True, impersonate="chrome124", timeout=30)
            res.raise_for_status()
        except Exception as e:
            logger.warning(f"curl_cffi impersonate stream error, retrying without impersonate: {e}")
            res = requests.get(url, headers=headers, stream=True, timeout=30)
            res.raise_for_status()

        for chunk in res.iter_content(chunk_size=chunk_size):
            if chunk:
                yield chunk

    def save_locally(
        self,
        url: str,
        filename: str,
        folder_prefix: str = "",
        referer: Optional[str] = None
    ) -> Tuple[str, int]:
        """Download URL and save to local downloads directory."""
        target_dir = os.path.join(self.download_dir, folder_prefix) if folder_prefix else self.download_dir
        os.makedirs(target_dir, exist_ok=True)

        safe_name = sanitize_filename(filename)
        dest_path = os.path.join(target_dir, safe_name)

        # Avoid overwriting
        base_name, ext = os.path.splitext(safe_name)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(target_dir, f"{base_name}_{counter}{ext}")
            counter += 1

        headers = self.get_headers(referer=referer, target_url=url)
        res = requests.get(url, headers=headers, stream=True, impersonate="chrome124", timeout=30)
        res.raise_for_status()

        total_bytes = 0
        with open(dest_path, "wb") as f:
            for chunk in res.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    total_bytes += len(chunk)

        return dest_path, total_bytes

    def create_images_zip(
        self,
        images_urls: List[str],
        title: str,
        referer: Optional[str] = None
    ) -> io.BytesIO:
        """Download images concurrently and compile them into an in-memory ZIP archive."""
        zip_buffer = io.BytesIO()

        def fetch_image(idx: int, img_url: str) -> Tuple[int, Optional[str], Optional[bytes]]:
            try:
                headers = self.get_headers(referer=referer, target_url=img_url)
                r = requests.get(img_url, headers=headers, impersonate="chrome124", timeout=15)
                if r.status_code == 200:
                    ext = ".jpeg"
                    content_type = r.headers.get("Content-Type", "")
                    if "png" in content_type:
                        ext = ".png"
                    elif "webp" in content_type:
                        ext = ".webp"
                    return idx, ext, r.content
            except Exception as e:
                logger.warning(f"Failed to fetch image {idx} ({img_url}): {e}")
            return idx, None, None

        # Download up to 6 images in parallel
        results = []
        max_workers = min(6, max(len(images_urls), 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(fetch_image, i, url): i
                for i, url in enumerate(images_urls, 1)
            }
            for future in as_completed(future_to_idx):
                results.append(future.result())

        # Sort by original image index
        results.sort(key=lambda x: x[0])

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for idx, ext, content in results:
                if ext and content:
                    img_filename = f"image_{idx:02d}{ext}"
                    zip_file.writestr(img_filename, content)

        zip_buffer.seek(0)
        return zip_buffer

    def save_images_locally(
        self,
        images_urls: List[str],
        album_name: str,
        referer: Optional[str] = None
    ) -> Tuple[str, int]:
        """Download all images concurrently into a dedicated subfolder in the downloads directory."""
        safe_album = sanitize_filename(album_name or "photo_album", max_len=45)
        target_dir = os.path.join(self.download_dir, safe_album)
        os.makedirs(target_dir, exist_ok=True)

        total_saved = 0
        def fetch_and_save(idx: int, img_url: str):
            try:
                headers = self.get_headers(referer=referer, target_url=img_url)
                r = requests.get(img_url, headers=headers, impersonate="chrome124", timeout=15)
                if r.status_code == 200:
                    ext = ".jpeg"
                    content_type = r.headers.get("Content-Type", "")
                    if "png" in content_type:
                        ext = ".png"
                    elif "webp" in content_type:
                        ext = ".webp"
                    dest = os.path.join(target_dir, f"photo_{idx:02d}{ext}")
                    with open(dest, "wb") as f:
                        f.write(r.content)
                    return len(r.content)
            except Exception as e:
                logger.warning(f"Error saving image {idx} locally: {e}")
            return 0

        max_workers = min(6, max(len(images_urls), 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(fetch_and_save, i, url)
                for i, url in enumerate(images_urls, 1)
            ]
            for f in as_completed(futures):
                total_saved += f.result()

        return target_dir, total_saved

    def create_slideshow_video(
        self,
        images_urls: List[str],
        audio_url: Optional[str] = None,
        title: str = "slideshow",
        referer: Optional[str] = None,
        duration_per_image: float = 3.0,
        max_duration: float = 60.0
    ) -> io.BytesIO:
        """Render an MP4 vertical slideshow video (1080x1920) combining photo(s) and background audio using FFmpeg."""
        import tempfile
        import subprocess

        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            import shutil
            ffmpeg_exe = shutil.which("ffmpeg")

        if not ffmpeg_exe or not os.path.exists(ffmpeg_exe):
            raise RuntimeError("FFmpeg is not available to render slideshow videos.")

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Download images concurrently
            def fetch_single_img(idx: int, u: str):
                try:
                    headers = self.get_headers(referer=referer, target_url=u)
                    try:
                        r = requests.get(u, headers=headers, impersonate="chrome124", timeout=15)
                    except Exception:
                        r = requests.get(u, headers=headers, timeout=15)
                    if r.status_code == 200:
                        path = os.path.join(tmpdir, f"img_{idx:03d}.jpg")
                        with open(path, "wb") as f:
                            f.write(r.content)
                        return idx, path
                except Exception as e:
                    logger.warning(f"Error fetching image {idx} for video: {e}")
                return idx, None

            results = []
            with ThreadPoolExecutor(max_workers=min(6, max(len(images_urls), 1))) as pool:
                futures = {pool.submit(fetch_single_img, i, u): i for i, u in enumerate(images_urls)}
                for fut in as_completed(futures):
                    res = fut.result()
                    if res[1]:
                        results.append(res)

            results.sort(key=lambda x: x[0])
            valid_img_paths = [r[1] for r in results]
            if not valid_img_paths:
                raise RuntimeError("Failed to download images for slideshow video generation.")

            # 2. Download audio track if available
            audio_path = None
            if audio_url:
                try:
                    audio_headers = self.get_headers(referer=referer, target_url=audio_url)
                    try:
                        ar = requests.get(audio_url, headers=audio_headers, impersonate="chrome124", timeout=15)
                    except Exception:
                        ar = requests.get(audio_url, headers=audio_headers, timeout=15)
                    if ar.status_code == 200 and len(ar.content) > 500:
                        audio_path = os.path.join(tmpdir, "audio.mp3")
                        with open(audio_path, "wb") as f:
                            f.write(ar.content)
                except Exception as e:
                    logger.warning(f"Error fetching audio for slideshow video: {e}")

            # 3. Build FFmpeg command for vertical slideshow MP4 (optimized for cloud micro-instances)
            output_mp4 = os.path.join(tmpdir, "output.mp4")
            scale_filter = "scale=540:960:force_original_aspect_ratio=decrease,pad=540:960:(ow-iw)/2:(oh-ih)/2:black"

            if len(valid_img_paths) == 1:
                # Single photo: 15s clip at 5 fps
                clip_duration = min(15.0, max_duration)
                cmd = [
                    ffmpeg_exe, "-y", "-nostdin",
                    "-threads", "1",
                    "-loop", "1",
                    "-framerate", "5",
                    "-t", str(clip_duration),
                    "-i", valid_img_paths[0]
                ]
                if audio_path:
                    cmd.extend(["-ss", "0", "-t", str(clip_duration), "-i", audio_path])
                else:
                    cmd.extend(["-f", "lavfi", "-t", str(clip_duration), "-i", "anullsrc=r=44100:cl=stereo"])

                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "26",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-vf", scale_filter,
                    "-r", "5",
                    "-t", str(clip_duration),
                    output_mp4
                ])
            else:
                # Multiple photos: display sequentially at 5 fps
                concat_file = os.path.join(tmpdir, "input.txt")
                with open(concat_file, "w", encoding="utf-8") as f:
                    for p in valid_img_paths:
                        f.write(f"file '{p.replace(os.sep, '/')}'\n")
                        f.write(f"duration {duration_per_image}\n")
                    f.write(f"file '{valid_img_paths[-1].replace(os.sep, '/')}'\n")

                total_slides_duration = len(valid_img_paths) * duration_per_image
                clip_duration = min(total_slides_duration, max_duration, 30.0)

                cmd = [
                    ffmpeg_exe, "-y", "-nostdin",
                    "-threads", "1",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", concat_file
                ]
                if audio_path:
                    cmd.extend(["-ss", "0", "-t", str(clip_duration), "-i", audio_path])
                else:
                    cmd.extend(["-f", "lavfi", "-t", str(clip_duration), "-i", "anullsrc=r=44100:cl=stereo"])

                cmd.extend([
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-crf", "26",
                    "-c:a", "aac",
                    "-b:a", "128k",
                    "-pix_fmt", "yuv420p",
                    "-vf", scale_filter,
                    "-r", "5",
                    "-t", str(clip_duration),
                    output_mp4
                ])

            proc = subprocess.run(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=25
            )
            if proc.returncode != 0 or not os.path.exists(output_mp4):
                err_msg = proc.stderr.decode(errors="ignore") if proc.stderr else "Unknown ffmpeg error"
                logger.error(f"FFmpeg render error: {err_msg}")
                raise RuntimeError(f"FFmpeg failed to create slideshow video: {err_msg[:200]}")

            buf = io.BytesIO()
            with open(output_mp4, "rb") as f:
                buf.write(f.read())
            buf.seek(0)
            return buf

