"""
utils/telegram.py — Telegram Messaging Helper
==============================================
Handles sending messages and inline keyboards to the user.
"""

import os
import logging
import requests
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Load environment variables (if not already loaded in main)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def send_telegram(
    text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[Dict[str, Any]] = None,
    disable_web_page_preview: bool = False
) -> bool:
    """
    Send a message to the configured Telegram chat.
    
    Args:
        text: Message text (supports HTML if parse_mode='HTML')
        parse_mode: 'HTML' or 'Markdown'
        reply_markup: Optional inline keyboard dict (e.g., {"inline_keyboard": [[...]]})
        disable_web_page_preview: Whether to disable link previews
    
    Returns:
        True if sent successfully, False otherwise.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — cannot send message")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram message sent successfully")
        return True
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def send_telegram_buttons(
    text: str,
    buttons: List[Dict[str, str]],
    parse_mode: str = "HTML"
) -> bool:
    """
    Convenience function to send a message with inline keyboard buttons.
    
    Args:
        text: Message text
        buttons: List of button dicts, each with 'text' and 'callback_data' or 'url'
                 Example: [{"text": "Approve", "callback_data": "approve_123"}]
        parse_mode: 'HTML' or 'Markdown'
    
    Returns:
        True if sent, False otherwise.
    """
    keyboard = {"inline_keyboard": [[btn] for btn in buttons]}
    return send_telegram(text, parse_mode=parse_mode, reply_markup=keyboard)


def edit_telegram_message(
    message_id: int,
    new_text: str,
    parse_mode: str = "HTML",
    reply_markup: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Edit an existing Telegram message (e.g., to remove buttons after click).
    
    Args:
        message_id: ID of the message to edit
        new_text: New text content
        parse_mode: 'HTML' or 'Markdown'
        reply_markup: Optional new inline keyboard (or empty to remove)
    
    Returns:
        True if successful, False otherwise.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — cannot edit message")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "message_id": message_id,
        "text": new_text,
        "parse_mode": parse_mode,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        logger.info("Telegram message edited successfully")
        return True
    except Exception as e:
        logger.error(f"Telegram edit error: {e}")
        return False


def answer_callback_query(callback_query_id: str, text: str = "✅", show_alert: bool = False) -> bool:
    """
    Answer a callback query (when user clicks an inline button).
    
    Args:
        callback_query_id: ID from the callback query
        text: Notification text to show to user (optional)
        show_alert: If True, show as an alert instead of a toast
    
    Returns:
        True if successful, False otherwise.
    """
    if not TELEGRAM_BOT_TOKEN:
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
    payload = {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": show_alert,
    }

    try:
        resp = requests.post(url, json=payload, timeout=5)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Callback answer error: {e}")
        return False
