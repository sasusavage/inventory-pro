"""
Telegram Bot — webhook-based, authorised to the owner's chat ID only.

Commands the admin can send from Telegram:
  /health   — full system health report (AI-generated)
  /stock    — stock status summary
  /sales    — sales performance summary
  /predict  — 7-day predictions
  /context  — raw business metrics snapshot
  /help     — list all commands

  Any other message is passed to the AI as a free-form question.

Setup:
  1. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env
  2. Deploy the app to a public HTTPS URL
  3. Call  POST /telegram/set-webhook?url=https://yourdomain.com
     to register the webhook with Telegram (one-time setup)
"""

import os
import json
from urllib import request as urllib_request, error as urllib_error

COMMANDS = {
    "/health":  "Full system health report",
    "/stock":   "Stock status & low-stock alerts",
    "/sales":   "Sales performance summary",
    "/predict": "7-day revenue & stockout predictions",
    "/context": "Raw business metrics snapshot",
    "/help":    "List all commands",
}

HELP_TEXT = (
    "🤖 *InventoryPro AI*\n\n"
    "Available commands:\n"
    + "\n".join(f"  {cmd} — {desc}" for cmd, desc in COMMANDS.items())
    + "\n\nOr just type any question and I'll answer it with your live business data."
)


# ── Low-level Telegram sender ─────────────────────────────────────────────────

def _send_message(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> None:
    """Send a message via the Bot API (synchronous, used inside Flask request)."""
    # Telegram message limit is 4096 chars
    if len(text) > 4000:
        text = text[:3990] + "\n…(truncated)"

    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": parse_mode,
    }).encode("utf-8")
    req = urllib_request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception:
        pass  # Never crash the webhook handler


def _send_typing(token: str, chat_id: str) -> None:
    """Show 'typing…' indicator while the AI thinks."""
    url     = f"https://api.telegram.org/bot{token}/sendChatAction"
    payload = json.dumps({"chat_id": chat_id, "action": "typing"}).encode("utf-8")
    req = urllib_request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=5) as r:
            r.read()
    except Exception:
        pass


# ── Command processor ─────────────────────────────────────────────────────────

def handle_message(token: str, chat_id: str, text: str) -> None:
    """
    Process one incoming message from the authorised admin.
    Runs synchronously inside a Flask app context.
    """
    text = (text or "").strip()
    cmd  = text.split()[0].lower() if text else ""

    _send_typing(token, chat_id)

    if cmd == "/help" or text == "":
        _send_message(token, chat_id, HELP_TEXT)
        return

    if cmd == "/context":
        from ai_engine import build_business_context
        ctx  = build_business_context()
        # Send a concise plain-text snapshot
        snap = (
            f"📊 <b>Business Snapshot</b> — {ctx['generated_at']}\n\n"
            f"<b>Sales (30d):</b> {ctx['sales']['last_30_days']['orders']} orders · "
            f"${ctx['sales']['last_30_days']['revenue']:,.2f} revenue\n"
            f"<b>Outstanding:</b> ${ctx['sales']['last_30_days']['outstanding']:,.2f}\n"
            f"<b>Gross Profit (30d):</b> ${ctx['finance']['gross_profit_30d']:,.2f} "
            f"({ctx['finance']['margin_30d_pct']}%)\n"
            f"<b>AR:</b> ${ctx['finance']['accounts_receivable']:,.2f} "
            f"from {ctx['finance']['debtors_count']} debtors\n"
            f"<b>Low Stock:</b> {ctx['stock']['low_stock_count']} products "
            f"({ctx['stock']['out_of_stock_count']} out)\n"
            f"<b>Stock Value:</b> ${ctx['stock']['total_stock_value']:,.2f}"
        )
        _send_message(token, chat_id, snap)
        return

    # AI-powered commands
    from ai_engine import (
        get_system_health, get_stock_summary,
        get_sales_summary, get_predictions, ask_ai,
    )

    dispatch = {
        "/health":  get_system_health,
        "/stock":   get_stock_summary,
        "/sales":   get_sales_summary,
        "/predict": get_predictions,
    }

    if cmd in dispatch:
        reply = dispatch[cmd]()
    else:
        # Free-form question
        reply = ask_ai(text, for_telegram=True)

    _send_message(token, chat_id, reply)


# ── Flask blueprint ───────────────────────────────────────────────────────────

from flask import Blueprint, request, jsonify, current_app

bot_bp = Blueprint("telegram_bot", __name__)


def _get_token_and_owner():
    token    = current_app.config.get("TELEGRAM_BOT_TOKEN", "").strip()
    owner_id = str(current_app.config.get("TELEGRAM_CHAT_ID", "")).strip()
    return token, owner_id


@bot_bp.route("/telegram/webhook", methods=["POST"])
def webhook():
    """Telegram pushes all updates here."""
    token, owner_id = _get_token_and_owner()
    if not token:
        return jsonify({"ok": False, "error": "Bot not configured"}), 400

    # Optional webhook secret verification
    secret = current_app.config.get("TELEGRAM_WEBHOOK_SECRET", "")
    if secret:
        incoming = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if incoming != secret:
            return jsonify({"ok": False}), 403

    data    = request.json or {}
    message = data.get("message") or data.get("edited_message") or {}
    chat_id = str(message.get("chat", {}).get("id", ""))
    text    = message.get("text", "").strip()

    # Only respond to the authorised owner
    if not chat_id or (owner_id and chat_id != owner_id):
        return jsonify({"ok": True})  # Silently ignore

    if not text:
        return jsonify({"ok": True})

    try:
        handle_message(token, chat_id, text)
    except Exception as e:
        _send_message(token, chat_id, f"⚠ Error: {e}")

    return jsonify({"ok": True})


@bot_bp.route("/telegram/set-webhook", methods=["POST"])
def set_webhook():
    """
    One-time setup: register this server as the webhook with Telegram.
    POST /telegram/set-webhook
    Body: { "url": "https://yourdomain.com" }
    """
    from decorators import login_required, admin_required  # noqa — used via decorator
    token, _ = _get_token_and_owner()
    if not token:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN not set in .env"}), 400

    data        = request.json or {}
    public_url  = (data.get("url") or "").rstrip("/")
    if not public_url:
        return jsonify({"error": "url is required (your public HTTPS domain)"}), 400

    webhook_url = f"{public_url}/telegram/webhook"
    secret      = current_app.config.get("TELEGRAM_WEBHOOK_SECRET", "")

    api_url = f"https://api.telegram.org/bot{token}/setWebhook"
    payload = {"url": webhook_url}
    if secret:
        payload["secret_token"] = secret

    req = urllib_request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=10) as r:
            result = json.loads(r.read().decode("utf-8"))
        if result.get("ok"):
            return jsonify({"message": f"Webhook registered: {webhook_url}"})
        return jsonify({"error": result.get("description", "Unknown error")}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bot_bp.route("/telegram/info", methods=["GET"])
def bot_info():
    """Returns current webhook info from Telegram (useful for debugging)."""
    token, _ = _get_token_and_owner()
    if not token:
        return jsonify({"error": "TELEGRAM_BOT_TOKEN not set"}), 400

    try:
        url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
        req = urllib_request.Request(url, method="GET")
        with urllib_request.urlopen(req, timeout=8) as r:
            return jsonify(json.loads(r.read().decode("utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
