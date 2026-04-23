"""
Platform-Wide SMS Utility — Vynfy Implementation.
This service uses a single, system-wide Vynfy account configured by the Super Admin.
Tenants (Organisations) do NOT need their own API keys; the platform handles it.

Environment Variables (to be set in .env):
  VYNFY_API_KEY  : Platform-wide API Key
  VYNFY_SENDER_ID: Platform-wide Sender ID (e.g., "InvPro")
"""
import os
import requests
import threading
import logging

logger = logging.getLogger(__name__)

def format_gh_number(number):
    """Formats a Ghanaian number to the 233XXXXXXXXX format required by Vynfy."""
    num = ''.join(filter(str.isdigit, str(number)))
    if num.startswith('0') and len(num) == 10:
        return '233' + num[1:]
    if num.startswith('233') and len(num) == 12:
        return num
    return num

def _send_vynfy_platform(org_id: int, phone: str, message: str):
    """
    Core Vynfy sender using Platform-wide credentials from Environment Variables.
    """
    try:
        from models import AppSetting, TenantModule
        
        # 1. Module & Toggle Check
        # Ensure the 'sms_receipts' module is enabled for this organisation
        if not TenantModule.is_enabled_for(org_id, 'sms_receipts'):
            return
            
        # Ensure the tenant has actually opted-in to sending receipts
        if AppSetting.get('sms_enabled', '0', org_id=org_id) != '1':
            return
            
        # 2. Load Platform Credentials
        api_key = os.environ.get('VYNFY_API_KEY')
        sender_id = os.environ.get('VYNFY_SENDER_ID', 'InvPro')
        
        if not api_key:
            logger.warning('SMS Platform Warning: VYNFY_API_KEY environment variable is missing!')
            return

        # 3. Message Personalisation
        # Get the specific store name for this organisation
        store_name = AppSetting.get('store_name', 'Your Shop', org_id=org_id)
        final_message = f"[{store_name}] {message}"
        
        # 4. Prepare Payload
        recipients = [format_gh_number(phone)]
        payload = {
            "message": final_message,
            "recipients": recipients,
            "sender": sender_id
        }
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }

        # 5. Dispatch
        requests.post("https://sms.vynfy.com/api/v1/send", json=payload, headers=headers, timeout=10)
        
    except Exception as e:
        logger.error('SMS Platform Error: %s', e)

def send_sms_receipt(org_id: int, phone: str, message: str):
    """Entry point for the POS to trigger an SMS receipt in the background."""
    threading.Thread(
        target=_send_vynfy_platform, 
        args=(org_id, phone, message),
        daemon=True
    ).start()
