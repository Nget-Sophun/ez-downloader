"""Telegram Bot for EZ-Downloader.
Supports:
1. Direct link processing: User sends TikTok/Douyin link in chat -> receives Video/Photos + MP3 audio.
2. Telegram Mini App (Web App): Interactive button in chat or menu to open the Web App inside Telegram.
"""

from __future__ import annotations
import os
import sys
import io
import re
import urllib.parse
import logging
from typing import Optional, List
from dotenv import load_dotenv

# Ensure proper UTF-8 output on Windows consoles
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables from .env
load_dotenv()

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    InputMediaPhoto,
    constants
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

from app.extractor import UnifiedExtractor
from app.extractor.base import MediaResult
from app.downloader import Downloader, sanitize_filename
from curl_cffi import requests

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("ez_downloader.bot")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://ez-downloader.onrender.com").strip()

extractor = UnifiedExtractor()
downloader = Downloader()


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Build persistent or welcome inline keyboard with Web App button."""
    buttons = []
    if WEBAPP_URL and WEBAPP_URL.startswith("https://"):
        buttons.append([
            InlineKeyboardButton("🚀 Open Web App", web_app=WebAppInfo(url=WEBAPP_URL))
        ])
    elif WEBAPP_URL:
        # Non-https (local dev)
        buttons.append([
            InlineKeyboardButton("🌐 Open Web App (Browser)", url=WEBAPP_URL)
        ])
    return InlineKeyboardMarkup(buttons)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    first_name = user.first_name if user else "Friend"
    
    welcome_text = (
        f"👋 <b>Welcome, {first_name}!</b>\n\n"
        "⚡ <b>EZ-Downloader Bot</b> lets you download <b>TikTok</b> & <b>Douyin (抖音)</b> media without watermarks.\n\n"
        "✨ <b>What I can download:</b>\n"
        "• 🎬 <b>HD Videos</b> (Watermark-free, 1080p/HD)\n"
        "• 📸 <b>Photo Slideshows</b> (All images in high resolution)\n"
        "• 🎵 <b>Background Songs & Audio</b> (Direct MP3 track)\n\n"
        "📥 <b>How to use:</b>\n"
        "1. Just <b>paste any TikTok or Douyin link</b> here in the chat!\n"
        "2. Or click the button below to use the <b>Web App</b> interface."
    )

    await update.message.reply_text(
        welcome_text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "💡 <b>EZ-Downloader Help</b>\n\n"
        "<b>Supported Links:</b>\n"
        "• TikTok: <code>https://www.tiktok.com/@user/video/...</code>\n"
        "• TikTok Photos: <code>https://www.tiktok.com/@user/photo/...</code>\n"
        "• Short links: <code>https://vt.tiktok.com/...</code> or <code>vm.tiktok.com/...</code>\n"
        "• Douyin: <code>https://v.douyin.com/...</code> or <code>https://www.douyin.com/video/...</code>\n\n"
        "Simply send or forward the link to this chat!"
    )
    await update.message.reply_text(
        help_text,
        parse_mode=constants.ParseMode.HTML,
        reply_markup=get_main_keyboard()
    )


def extract_url_from_text(text: str) -> Optional[str]:
    """Find the first TikTok or Douyin URL in a message text."""
    url_pattern = r"(https?://[^\s]+)"
    matches = re.findall(url_pattern, text)
    for m in matches:
        if any(domain in m for domain in ["tiktok.com", "douyin.com", "iesdouyin.com"]):
            return m.strip("()[]<>.,!\"'")
    return None


async def send_media_to_chat(
    bot,
    chat_id: int | str,
    media: MediaResult,
    target_url: Optional[str] = None
) -> None:
    """Forward analyzed media (video or photo album + audio) directly to a Telegram chat."""
    platform_label = "Douyin (抖音)" if media.platform == "douyin" else "TikTok"
    author_name = media.author.nickname or "Creator"
    title_text = media.title or "No title"
    if len(title_text) > 100:
        title_text = title_text[:97] + "..."

    caption_header = (
        f"🎬 <b>{platform_label}</b> | 👤 <b>{author_name}</b>\n"
        f"📝 <i>{title_text}</i>\n"
    )

    buttons = []
    if WEBAPP_URL and WEBAPP_URL.startswith("https://"):
        launch_url = f"{WEBAPP_URL}?url={urllib.parse.quote(target_url)}" if target_url else WEBAPP_URL
        buttons.append([
            InlineKeyboardButton("🚀 Open in Web App", web_app=WebAppInfo(url=launch_url))
        ])

    # 1. PHOTO SLIDESHOW MODE
    if media.type == "photo" and media.images:
        headers = downloader.get_headers(target_url=media.images[0])
        batch_size = 10
        for start_idx in range(0, len(media.images), batch_size):
            chunk = media.images[start_idx : start_idx + batch_size]
            media_group = []
            for i, img_url in enumerate(chunk):
                try:
                    r = requests.get(img_url, headers=headers, impersonate="chrome124", timeout=15)
                    if r.status_code == 200:
                        photo_file = io.BytesIO(r.content)
                        photo_file.name = f"photo_{start_idx + i + 1}.jpg"
                        caption = caption_header if (start_idx == 0 and i == 0) else None
                        media_group.append(
                            InputMediaPhoto(
                                media=photo_file,
                                caption=caption,
                                parse_mode=constants.ParseMode.HTML if caption else None
                            )
                        )
                except Exception as e:
                    logger.warning(f"Error fetching photo for Telegram chat: {e}")

            if media_group:
                await bot.send_media_group(chat_id=chat_id, media=media_group)

        # Send Soundtrack
        if media.music and media.music.play_url:
            try:
                music_headers = downloader.get_headers(target_url=media.music.play_url)
                mr = requests.get(media.music.play_url, headers=music_headers, impersonate="chrome124", timeout=20)
                if mr.status_code == 200 and len(mr.content) > 500:
                    audio_file = io.BytesIO(mr.content)
                    audio_name = sanitize_filename(media.music.title or "audio") + ".mp3"
                    audio_file.name = audio_name
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=audio_file,
                        title=media.music.title or "Background Music",
                        performer=media.music.author or author_name,
                        caption=f"🎵 <b>Slideshow Soundtrack:</b> {media.music.title or 'Original Audio'}",
                        parse_mode=constants.ParseMode.HTML
                    )
            except Exception as e:
                logger.warning(f"Failed to send telegram audio: {e}")

        # Send Photo with Song (MP4 Video Slideshow)
        try:
            video_buf = downloader.create_slideshow_video(
                images_urls=media.images,
                audio_url=media.music.play_url if media.music else None,
                title=title_text
            )
            video_buf.name = f"{sanitize_filename(title_text)}_slideshow.mp4"
            await bot.send_video(
                chat_id=chat_id,
                video=video_buf,
                caption=(
                    f"🎬 <b>Photo with Song (MP4 Video)</b>\n"
                    f"{caption_header}\n"
                    f"✨ <i>Created from {len(media.images)} photo(s) + soundtrack</i>"
                ),
                parse_mode=constants.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )
        except Exception as e:
            logger.warning(f"Could not generate slideshow video for Telegram: {e}")

        return

    # 2. VIDEO MODE
    if media.videos:
        best_vid = media.videos[0]
        video_headers = downloader.get_headers(target_url=best_vid.url)
        vr = requests.get(best_vid.url, headers=video_headers, impersonate="chrome124", timeout=40)

        if vr.status_code == 200 and len(vr.content) > 1000:
            video_size_mb = len(vr.content) / (1024 * 1024)
            if video_size_mb < 49:
                video_file = io.BytesIO(vr.content)
                video_file.name = f"{sanitize_filename(title_text)}.mp4"
                caption = (
                    f"{caption_header}\n"
                    f"📊 ❤️ {media.stats.get('digg_count', 0):,} | 💬 {media.stats.get('comment_count', 0):,}\n"
                    f"✨ <i>Downloaded without watermark ({best_vid.quality})</i>"
                )
                await bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=caption,
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
                )
            else:
                buttons.append([
                    InlineKeyboardButton(f"📥 Download Video ({video_size_mb:.1f} MB)", url=best_vid.url)
                ])
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"{caption_header}\n⚠️ Video is large ({video_size_mb:.1f}MB). Click below to download directly:",
                    parse_mode=constants.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup(buttons)
                )
        else:
            buttons.append([
                InlineKeyboardButton("📥 Download HD Video", url=best_vid.url)
            ])
            await bot.send_message(
                chat_id=chat_id,
                text=f"{caption_header}\nClick below to download:",
                parse_mode=constants.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Send Audio track
        if media.music and media.music.play_url:
            try:
                music_headers = downloader.get_headers(target_url=media.music.play_url)
                mr = requests.get(media.music.play_url, headers=music_headers, impersonate="chrome124", timeout=20)
                if mr.status_code == 200 and len(mr.content) > 500:
                    audio_file = io.BytesIO(mr.content)
                    audio_file.name = f"{sanitize_filename(media.music.title or 'audio')}.mp3"
                    await bot.send_audio(
                        chat_id=chat_id,
                        audio=audio_file,
                        title=media.music.title or "Original Audio",
                        performer=media.music.author or author_name
                    )
            except Exception as e:
                logger.debug(f"Audio send skipped: {e}")
        return

    raise RuntimeError("No downloadable video or photo content found.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages and extract media links."""
    text = update.message.text
    if not text:
        return

    target_url = extract_url_from_text(text)
    if not target_url:
        # Not a valid link
        await update.message.reply_text(
            "⚠️ Please send a valid <b>TikTok</b> or <b>Douyin (抖音)</b> link.\n"
            "Example: <code>https://vt.tiktok.com/...</code> or <code>https://www.tiktok.com/@user/photo/...</code>",
            parse_mode=constants.ParseMode.HTML
        )
        return

    # Send status message
    status_msg = await update.message.reply_text(
        "🔍 <b>Analyzing link and retrieving media...</b>",
        parse_mode=constants.ParseMode.HTML
    )

    try:
        media = extractor.fetch(target_url)
        await status_msg.edit_text("⚡ <b>Downloading & sending media to chat...</b>", parse_mode=constants.ParseMode.HTML)
        await send_media_to_chat(context.bot, update.effective_chat.id, media, target_url=target_url)
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error handling Telegram link: {e}", exc_info=True)
        await status_msg.edit_text(
            f"❌ <b>Extraction Failed:</b> {str(e)}\n\n"
            "Please check if the video is public and try again.",
            parse_mode=constants.ParseMode.HTML
        )


def create_telegram_bot(token: str):
    """Build and configure the Telegram bot application instance."""
    app = ApplicationBuilder().token(token).build()

    # Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    return app


def main():
    token = TELEGRAM_BOT_TOKEN
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("=" * 65)
        print("  [!] Telegram Bot Token Not Configured")
        print("=" * 65)
        print("\nPlease follow these simple steps to start your bot:")
        print("1. Open Telegram and search for @BotFather")
        print("2. Send /newbot and choose a name & username")
        print("3. Copy the HTTP API token provided by @BotFather")
        print("4. Paste the token below or save it in your .env file:\n")
        try:
            token = input("Enter your Telegram Bot Token: ").strip()
        except (KeyboardInterrupt, EOFError):
            sys.exit(0)

        if not token:
            print("\n[!] No token provided. Exiting.")
            sys.exit(1)

        # Save to .env for future convenience
        with open(".env", "a", encoding="utf-8") as f:
            f.write(f"\nTELEGRAM_BOT_TOKEN={token}\n")
        print("[✓] Saved token to .env file!\n")

    print("=" * 65)
    print("  🚀 Starting EZ-Downloader Telegram Bot...")
    print(f"  Web App URL: {WEBAPP_URL}")
    print("=" * 65)

    app = create_telegram_bot(token)

    print("\n[+] Bot is running and polling for messages! Press Ctrl+C to stop.")
    app.run_polling()


if __name__ == "__main__":
    import urllib.parse
    main()
