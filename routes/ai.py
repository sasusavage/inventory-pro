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
    """AI-generated insights for the analytics dashboard."""
    now = time.time()
    if 'insights' in _insights_cache and _insights_cache['insights']['expires'] > now:
        return jsonify(_insights_cache['insights']['data'])

    try:
        from ai_engine import get_insights as _get_insights
        data = _get_insights()
        _insights_cache['insights'] = {'data': data, 'expires': now + INSIGHTS_TTL}
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/context', methods=['GET'])
@login_required
@admin_required
def get_context():
    """Return the raw business context (useful for debugging / advanced use)."""
    try:
        from ai_engine import build_business_context
        return jsonify(build_business_context())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/ask', methods=['POST'])
@login_required
@admin_required
def ask():
    """
    General-purpose AI chat endpoint.
    Body: { "message": "..." }
    """
    data = request.json or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'message is required'}), 400

    try:
        from ai_engine import ask_ai, build_business_context
        context = build_business_context()
        reply = ask_ai(message, context=context, for_telegram=False)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/health', methods=['GET'])
@login_required
@admin_required
def health_report():
    """Full system health report (markdown)."""
    try:
        from ai_engine import get_system_health
        return jsonify({'report': get_system_health()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/predictions', methods=['GET'])
@login_required
@admin_required
def predictions():
    """7-day predictions."""
    try:
        from ai_engine import get_predictions
        return jsonify({'predictions': get_predictions()})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/invalidate-cache', methods=['POST'])
@login_required
@admin_required
def invalidate_cache():
    """Force-refresh the AI context and insights cache."""
    _insights_cache.clear()
    from ai_engine import invalidate_ai_cache
    invalidate_ai_cache()
    return jsonify({'message': 'AI cache cleared'})
