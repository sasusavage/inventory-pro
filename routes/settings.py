from flask import Blueprint, render_template, request, jsonify, session, g
from models import db, AppSetting, Organisation
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
    'store_address': 'Store Address (for receipts)',
    'store_phone': 'Store Phone (for receipts)',
    'store_tagline': 'Tagline shown on receipts',
    'scheduler_daily_report': 'Daily AI report via Telegram (true/false)',
    'scheduler_report_hour': 'Report send hour (0-23, default 8)',
    'scheduler_weekly_report': 'Weekly AI report via Telegram (true/false)',
    'loyalty_earn_rate': 'Loyalty points earned per $1 spent (default 1)',
    'loyalty_redeem_rate': 'Points needed to redeem $1 discount (default 100)',
    # SMS receipts (Platform-managed)
    'sms_enabled':    'Enable SMS receipts (1 = yes, 0 = no)',
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

    from flask import session
    notify_async(
        session.get('organisation_id'),
        "<b>Telegram Connection Test</b>\n\n"
        "Configured successfully! You will now receive alerts here."
    )
    return jsonify({'message': 'Test message sent — check your Telegram chat'})


# ── Domain / subdomain management ────────────────────────────────────────────

@settings_bp.route('/api/settings/domain', methods=['GET'])
@login_required
@admin_required
def get_domain_info():
    """Return current subdomain + custom domain status for this org."""
    import os
    org = Organisation.query.get(g.org_id)
    if not org:
        return jsonify({'error': 'Organisation not found'}), 404

    platform_domain = os.environ.get('PLATFORM_DOMAIN', 'inventorypro.app')
    return jsonify({
        'subdomain':           org.slug,
        'subdomain_url':       f'https://{org.slug}.{platform_domain}',
        'platform_domain':     platform_domain,
        'custom_domain':       org.custom_domain or '',
        'domain_verified':     org.domain_verified,
        'domain_requested_at': org.domain_requested_at.isoformat() if org.domain_requested_at else None,
        'domain_verified_at':  org.domain_verified_at.isoformat() if org.domain_verified_at else None,
        'cname_target':        platform_domain,   # what the tenant must CNAME to
    })


@settings_bp.route('/api/settings/domain', methods=['POST'])
@login_required
@admin_required
def request_custom_domain():
    """
    Tenant submits a custom domain request.
    They must already have pointed their domain's CNAME to our platform_domain
    before submitting — super admin then verifies DNS is correct.
    """
    from datetime import datetime
    data   = request.json or {}
    domain = (data.get('custom_domain') or '').strip().lower()

    if not domain:
        return jsonify({'error': 'custom_domain is required'}), 400

    # Basic format check — no protocol, no path
    if domain.startswith('http') or '/' in domain or ' ' in domain:
        return jsonify({'error': 'Enter just the domain name, e.g. pos.myshop.com'}), 400

    # Must have at least one dot
    if '.' not in domain:
        return jsonify({'error': 'Enter a valid domain name'}), 400

    # Check not already taken by another org
    existing = Organisation.query.filter(
        Organisation.custom_domain == domain,
        Organisation.id != g.org_id,
    ).first()
    if existing:
        return jsonify({'error': 'This domain is already in use by another account'}), 409

    org = Organisation.query.get(g.org_id)
    org.custom_domain        = domain
    org.domain_verified      = False          # reset — super admin must re-verify
    org.domain_verified_at   = None
    org.domain_requested_at  = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'message': 'Domain request submitted. A super admin will verify DNS and activate it.',
        'custom_domain': domain,
    })


@settings_bp.route('/api/settings/subdomain', methods=['POST'])
@login_required
@admin_required
def change_subdomain():
    """Tenant changes their slug (subdomain). Must be unique across all orgs."""
    import re
    data = request.json or {}
    new_slug = (data.get('slug') or '').strip().lower()

    if not new_slug:
        return jsonify({'error': 'slug is required'}), 400
    if not re.match(r'^[a-z0-9-]+$', new_slug) or len(new_slug) < 3:
        return jsonify({'error': 'Slug must be at least 3 chars, lowercase letters, numbers and hyphens only'}), 400

    existing = Organisation.query.filter(
        Organisation.slug == new_slug,
        Organisation.id != g.org_id,
    ).first()
    if existing:
        return jsonify({'error': 'This subdomain is already taken'}), 409

    org = Organisation.query.get(g.org_id)
    org.slug = new_slug
    db.session.commit()
    return jsonify({'message': f'Subdomain updated to {new_slug}', 'slug': new_slug})


@settings_bp.route('/api/settings/domain', methods=['DELETE'])
@login_required
@admin_required
def remove_custom_domain():
    """Remove the custom domain from this org."""
    org = Organisation.query.get(g.org_id)
    org.custom_domain       = None
    org.domain_verified     = False
    org.domain_verified_at  = None
    org.domain_requested_at = None
    db.session.commit()
    return jsonify({'message': 'Custom domain removed'})
