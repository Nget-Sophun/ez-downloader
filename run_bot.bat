@echo off
title EZ-Downloader Telegram Bot
cd /d "%~dp0"

echo ============================================================
echo   Starting EZ-Downloader Telegram Bot
echo ============================================================
echo.

python bot.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] Bot exited or encountered an error.
    pause
)
