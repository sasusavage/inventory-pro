"""
Multi-Tenant Telegram Notification Utility.

Hierarchy Logic:
  1. Priority: Organisation's specific Bot Token & Chat ID (from AppSetting DB)
     - This allows each tenant to have their own private bot.
  2. Fallback: Platform-wide Bot Token & Chat ID (from Environment Variables)
     - Used if the tenant hasn't configured their own bot.

This ensures data privacy and allows professional white-labeling for tenants.
"""

import os
import json
import threading
import logging
from urllib import request as urllib_request

logger = logging.getLogger(__name__)

def _get_credentials(org_id: int):
    """
    Strict isolation for Telegram credentials.
    - org_id > 0: USES ONLY Tenant-configured bot in AppSetting. No fallback.
    - org_id == 0: USES ONLY Platform Bot from .env (Super Admin only).
    """
    if not org_id or org_id == 0:
        # Platform/Super Admin Bot
        return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(), os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    # Tenant-Specific Bot
    try:
        from models import AppSetting
        token = AppSetting.get("telegram_bot_token", org_id=org_id)
        chat_id = AppSetting.get("telegram_chat_id", org_id=org_id)
        return (token or "").strip(), (chat_id or "").strip()
    except Exception:
        return "", ""


def _send_telegram(token: str, chat_id: str, text: str) -> None:
    if not token or not chat_id:
        return

    if len(text) > 4000:
        text = text[:3990] + "\n…(truncated)"

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }).encode("utf-8")

    req = urllib_request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    
    try:
        with urllib_request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        logger.error(f"Telegram API Send Error: {e}")


def notify_async(org_id: int, text: str) -> None:
    """Non-blocking background notification with Org isolation."""
    token, chat_id = _get_credentials(org_id)
    if not token or not chat_id:
        return

    threading.Thread(
        target=_send_telegram, 
        args=(token, chat_id, text), 
        daemon=True
    ).start()


def low_stock_alert(org_id: int, product_name: str, current_stock: int, min_stock: int) -> None:
    urgency = "🔴 <b>OUT OF STOCK</b>" if current_stock <= 0 else "🟠 <b>Low Stock Warning</b>"
    notify_async(
        org_id,
        f"{urgency}\n\n"
        f"📦 <b>Product:</b> {product_name}\n"
        f"📉 <b>Current Stock:</b> {current_stock} units\n"
        f"⚠️ <b>Minimum Level:</b> {min_stock} units\n\n"
        f"Please reorder soon."
    )


def sale_summary_alert(org_id: int, customer_name: str, total: float, payment_status: str) -> None:
    icon = "✅" if payment_status == "PAID" else "⏳"
    notify_async(
        org_id,
        f"{icon} <b>New Sale Notification</b>\n\n"
        f"👤 <b>Customer:</b> {customer_name}\n"
        f"💰 <b>Total:</b> ${total:.2f}\n"
        f"📋 <b>Status:</b> {payment_status}"
    )
