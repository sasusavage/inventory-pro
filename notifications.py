"""
Telegram notification utility.

Priority for credentials:
  1. TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID environment variables  (recommended)
  2. app_settings DB table (legacy — set via /settings-page)

Falls back silently when not configured.
"""

import os
import json
import threading
from urllib import request as urllib_request


def _get_credentials():
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Fall back to DB settings if env not set
    if not token or not chat_id:
        try:
            from models import AppSetting
            token   = token   or AppSetting.get("telegram_bot_token", "").strip()
            chat_id = chat_id or AppSetting.get("telegram_chat_id",   "").strip()
        except Exception:
            pass

    return token, chat_id


def _send_telegram(token: str, chat_id: str, text: str) -> None:
    if len(text) > 4000:
        text = text[:3990] + "\n…(truncated)"

    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": "HTML",
    }).encode("utf-8")
    req = urllib_request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=8) as r:
            r.read()
    except Exception:
        pass


def notify_async(text: str) -> None:
    """Send a Telegram message in a background daemon thread (non-blocking)."""
    token, chat_id = _get_credentials()
    if not token or not chat_id:
        return

    t = threading.Thread(target=_send_telegram, args=(token, chat_id, text), daemon=True)
    t.start()


def low_stock_alert(product_name: str, current_stock: int, min_stock: int) -> None:
    urgency = "🔴 <b>OUT OF STOCK</b>" if current_stock <= 0 else "🟠 <b>Low Stock Warning</b>"
    notify_async(
        f"{urgency}\n\n"
        f"📦 <b>Product:</b> {product_name}\n"
        f"📉 <b>Current Stock:</b> {current_stock} units\n"
        f"⚠️ <b>Minimum Level:</b> {min_stock} units\n\n"
        f"Please reorder soon to avoid running out."
    )


def sale_summary_alert(customer_name: str, total: float, payment_status: str) -> None:
    icon = "✅" if payment_status == "PAID" else "⏳"
    notify_async(
        f"{icon} <b>New Sale</b>\n\n"
        f"👤 <b>Customer:</b> {customer_name}\n"
        f"💰 <b>Total:</b> ${total:.2f}\n"
        f"📋 <b>Status:</b> {payment_status}"
    )
