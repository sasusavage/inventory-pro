from flask import Blueprint, render_template, request, jsonify, session
from models import db, AppSetting
from decorators import admin_required, login_required
from notifications import notify_async

settings_bp = Blueprint('settings', __name__)

# Keys exposed in the settings UI
SETTING_KEYS = {
    'telegram_bot_token': 'Telegram Bot Token',
    'telegram_chat_id': 'Telegram Chat ID',
    'notify_on_sale': 'Notify on every sale (1 = yes, 0 = no)',
    'store_name': 'Store Name',
    'store_currency': 'Currency Symbol (e.g. $ or ₦)',
    'scheduler_daily_report': 'Daily AI report via Telegram (true/false)',
    'scheduler_report_hour': 'Report send hour (0-23, default 8)',
    'scheduler_weekly_report': 'Weekly AI report via Telegram (true/false)',
    'loyalty_earn_rate': 'Loyalty points earned per $1 spent (default 1)',
    'loyalty_redeem_rate': 'Points needed to redeem $1 discount (default 100)',
}


@settings_bp.route('/settings-page')
@login_required
@admin_required
def settings_page():
    return render_template('settings.html')


@settings_bp.route('/api/settings', methods=['GET'])
@login_required
@admin_required
def get_settings():
    data = {}
    for key in SETTING_KEYS:
        data[key] = AppSetting.get(key, '')
    # Never send the full token back to the browser — mask it
    token = data.get('telegram_bot_token', '')
    if token:
        data['telegram_bot_token'] = token[:6] + '…' + token[-4:] if len(token) > 10 else '••••••'
        data['telegram_configured'] = True
    else:
        data['telegram_configured'] = False
    return jsonify(data)


@settings_bp.route('/api/settings', methods=['POST'])
@login_required
@admin_required
def save_settings():
    data = request.json or {}
    saved = []

    for key in SETTING_KEYS:
        if key in data:
            value = str(data[key]).strip()
            # Don't overwrite token with the masked display value
            if key == 'telegram_bot_token' and ('…' in value or '••' in value):
                continue
            AppSetting.set(key, value)
            saved.append(key)

    return jsonify({'message': f'{len(saved)} setting(s) saved', 'saved': saved})


@settings_bp.route('/api/settings/test-telegram', methods=['POST'])
@login_required
@admin_required
def test_telegram():
    from models import AppSetting
    token = AppSetting.get('telegram_bot_token', '').strip()
    chat_id = AppSetting.get('telegram_chat_id', '').strip()

    if not token or not chat_id:
        return jsonify({'error': 'Telegram bot token and chat ID must be saved first'}), 400

    notify_async(
        "✅ <b>InventoryPro Test</b>\n\n"
        "Your Telegram notifications are working correctly!\n"
        "You'll receive low-stock and sale alerts here."
    )
    return jsonify({'message': 'Test message sent — check your Telegram chat'})
