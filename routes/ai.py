"""
AI API routes — powers the analytics page chat and Telegram bot helpers.
"""
import time
from flask import Blueprint, request, jsonify, session
from decorators import login_required, admin_required

ai_bp = Blueprint('ai', __name__)

# Cache insights per-session for 10 min so rapid page refreshes don't re-call Groq
_insights_cache: dict = {}
INSIGHTS_TTL = 10 * 60


@ai_bp.route('/api/ai/insights', methods=['GET'])
@login_required
@admin_required
def get_insights():
    org_id = session.get('organisation_id')
    now = time.time()
    cache_key = f"insights_{org_id}"
    if cache_key in _insights_cache and _insights_cache[cache_key]['expires'] > now:
        return jsonify(_insights_cache[cache_key]['data'])

    try:
        from ai_engine import get_insights as _get_insights
        data = _get_insights(org_id)
        _insights_cache[cache_key] = {'data': data, 'expires': now + INSIGHTS_TTL}
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/context', methods=['GET'])
@login_required
@admin_required
def get_context():
    try:
        from ai_engine import build_business_context
        return jsonify(build_business_context(session.get('organisation_id')))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/ask', methods=['POST'])
@login_required
@admin_required
def ask():
    data = request.json or {}
    message = (data.get('message') or '').strip()
    org_id = session.get('organisation_id')
    if not message:
        return jsonify({'error': 'message is required'}), 400

    try:
        from ai_engine import ask_ai
        reply = ask_ai(org_id, message, for_telegram=False)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/health', methods=['GET'])
@login_required
@admin_required
def health_report():
    try:
        from ai_engine import get_system_health
        return jsonify({'report': get_system_health(session.get('organisation_id'))})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/predictions', methods=['GET'])
@login_required
@admin_required
def predictions():
    try:
        from ai_engine import get_predictions
        return jsonify({'predictions': get_predictions(session.get('organisation_id'))})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/invalidate-cache', methods=['POST'])
@login_required
@admin_required
def invalidate_cache():
    org_id = session.get('organisation_id')
    _insights_cache.pop(f"insights_{org_id}", None)
    from ai_engine import invalidate_ai_cache
    invalidate_ai_cache(org_id)
    return jsonify({'message': 'AI cache cleared'})
