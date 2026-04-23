from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)
sms_webhook_bp = Blueprint('sms_webhook', __name__)

@sms_webhook_bp.route('/webhooks/vynfy', methods=['POST'])
def vynfy_callback():
    """
    Receives delivery reports from Vynfy.
    Expected payload structure:
    {
        "id": "sms_id",
        "recipient": "233...",
        "status": "delivered",
        "delivered_at": "...",
        "org_id": "optional_metadata"
    }
    """
    try:
        data = request.json or {}
        
        # Log the delivery status
        recipient = data.get('recipient')
        status = data.get('status')
        task_id = data.get('id')
        
        logger.info('SMS Delivery Report | Recipient: %s | Status: %s | ID: %s', recipient, status, task_id)
        
        # Here we could update a 'Sale' record or an 'SMSAudit' table if we had one.
        # For now, we simply acknowledge the receipt to Vynfy.
        
        return jsonify({"success": True}), 200
        
    except Exception as e:
        logger.error('Error processing Vynfy webhook: %s', e)
        return jsonify({"success": False, "error": str(e)}), 400
