"""
SMS receipt helper — Africa's Talking integration.
Keys are stored in AppSetting per org:
  sms_enabled  : '1' to enable
  sms_username : AT username (use 'sandbox' for testing)
  sms_api_key  : AT API key
  sms_sender_id: optional sender ID

Usage:
    from sms_helper import send_sms_receipt
    send_sms_receipt(org_id, phone, message)   # fire and forget
"""
import threading
import logging

logger = logging.getLogger(__name__)


def _send(org_id: int, phone: str, message: str):
    try:
        from models import AppSetting
        enabled  = AppSetting.get('sms_enabled',   '0', org_id=org_id)
        if str(enabled).strip() != '1':
            return

        username = AppSetting.get('sms_username', '', org_id=org_id).strip()
        api_key  = AppSetting.get('sms_api_key',  '', org_id=org_id).strip()
        if not username or not api_key:
            logger.info('SMS skipped: keys not configured for org %s', org_id)
            return

        sender_id = AppSetting.get('sms_sender_id', None, org_id=org_id)
        sender_id = sender_id.strip() if sender_id else None

        import africastalking  # pip install africastalking
        africastalking.initialize(username, api_key)
        sms = africastalking.SMS

        # Africa's Talking expects E.164 numbers e.g. +233241234567
        # Attempt to normalise Ghanaian numbers
        p = phone.strip().replace(' ', '').replace('-', '')
        if p.startswith('0') and len(p) == 10:
            p = '+233' + p[1:]
        elif not p.startswith('+'):
            p = '+' + p

        resp = sms.send(message, [p], sender_id=sender_id)
        logger.info('SMS sent to %s: %s', p, resp)

    except ImportError:
        logger.warning('africastalking package not installed. Run: pip install africastalking')
    except Exception as e:
        logger.error('SMS send error: %s', e)


def send_sms_receipt(org_id: int, phone: str, message: str):
    """Non-blocking SMS dispatch. Never raises — failures are logged only."""
    t = threading.Thread(target=_send, args=(org_id, phone, message), daemon=True)
    t.start()
