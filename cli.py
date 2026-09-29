"""Command Line Interface (CLI) for EZ-Downloader.
Usage:
    python cli.py <URL> [--type video|audio|images|all] [--dir ./downloads] [--cookie "<COOKIE>"]
"""

import os
import sys
import argparse

# Ensure proper UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app.extractor import UnifiedExtractor
from app.downloader import Downloader, sanitize_filename, DEFAULT_DOWNLOAD_DIR


def main():
    parser = argparse.ArgumentParser(
        description="EZ-Downloader CLI - Download TikTok & Douyin (抖音) videos, music, and photo albums."
    )
    parser.add_argument("url", help="TikTok or Douyin video/photo URL or copied share text")
    parser.add_argument(
        "--type",
        choices=["video", "audio", "images", "all"],
        default="video",
        help="Type of media to download (default: video)"
    )
    parser.add_argument(
        "--dir",
        default=DEFAULT_DOWNLOAD_DIR,
        help=f"Directory to save downloads (default: {DEFAULT_DOWNLOAD_DIR})"
    )
    parser.add_argument(
        "--cookie",
        default=None,
        help="Custom browser cookie string (optional, recommended for Douyin restricted videos)"
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("  EZ-Downloader CLI (TikTok & Douyin)")
    print("=" * 60)

    extractor = UnifiedExtractor()
    downloader = Downloader(args.dir)

    print(f"\n[*] Analyzing URL: {args.url[:70]}...")
    try:
        media = extractor.fetch(args.url, custom_cookie=args.cookie)
    except Exception as e:
        print(f"\n[!] Error during extraction: {e}")
        sys.exit(1)

    print(f"\n[+] Platform : {media.platform.upper()}")
    print(f"[+] Title    : {media.title}")
    print(f"[+] Creator  : {media.author.nickname} (@{media.author.unique_id})")
    print(f"[+] Type     : {media.type.upper()}")

    safe_title = sanitize_filename(media.title or media.id)
    folder_prefix = "Douyin" if media.platform == "douyin" else "TikTok"

    # If media is photo post and user kept default type, download both images and audio!
    is_photo_post = media.type == "photo"
    download_video = (args.type in ["video", "all"]) and bool(media.videos)
    download_audio = (args.type in ["audio", "all"]) or (is_photo_post and bool(media.music and media.music.play_url))
    download_images = (args.type in ["images", "all"]) or is_photo_post

    # Download Video
    if download_video and media.videos:
        best_vid = media.videos[0]
        vid_filename = f"{safe_title}_{best_vid.quality}.mp4"
        print(f"\n[*] Downloading Video ({best_vid.quality})...")
        try:
            path, size = downloader.save_locally(
                url=best_vid.url,
                filename=vid_filename,
                folder_prefix=folder_prefix
            )
            print(f"[✓] Saved Video: {path} ({size / (1024*1024):.2f} MB)")
        except Exception as e:
            print(f"[!] Failed to download video: {e}")

    # Download Audio
    if download_audio and media.music and media.music.play_url:
        audio_name = sanitize_filename(media.music.title or safe_title) + ".mp3"
        print(f"\n[*] Downloading Audio track: {media.music.title}...")
        try:
            path, size = downloader.save_locally(
                url=media.music.play_url,
                filename=audio_name,
                folder_prefix=folder_prefix
            )
            print(f"[✓] Saved Audio: {path} ({size / (1024*1024):.2f} MB)")
        except Exception as e:
            print(f"[!] Failed to download audio: {e}")

    # Download Images (Photo Mode)
    if download_images and media.images:
        print(f"\n[*] Downloading Photo Album ({len(media.images)} images)...")
        for idx, img_url in enumerate(media.images, 1):
            img_name = f"{safe_title}_img_{idx:02d}.jpg"
            try:
                path, size = downloader.save_locally(
                    url=img_url,
                    filename=img_name,
                    folder_prefix=os.path.join(folder_prefix, f"{safe_title}_photos")
                )
                print(f"  [✓] Image {idx}/{len(media.images)} saved: {os.path.basename(path)}")
            except Exception as e:
                print(f"  [!] Failed image {idx}: {e}")

    print("\n[+] Done! All requested media processed successfully.\n")


if __name__ == "__main__":
    main()
