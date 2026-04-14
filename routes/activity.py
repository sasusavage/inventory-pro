from flask import Blueprint, render_template, request, jsonify, session
from models import db, ActivityLog
from decorators import login_required

activity_bp = Blueprint('activity', __name__)


@activity_bp.route('/activity-page')
@login_required
def activity_page():
    if session.get('role') != 'admin':
        return "Admins only", 403
    return render_template('activity.html', user_role=session.get('role'))


@activity_bp.route('/activity', methods=['GET'])
@login_required
def list_activity():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    action = request.args.get('action', '').strip()
    entity = request.args.get('entity', '').strip()
    username = request.args.get('username', '').strip()

    query = ActivityLog.query
    if action:
        query = query.filter(ActivityLog.action.ilike(f'%{action}%'))
    if entity:
        query = query.filter(ActivityLog.entity == entity)
    if username:
        query = query.filter(ActivityLog.username.ilike(f'%{username}%'))

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    paginated = query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'data': [{
            'id': a.id,
            'username': a.username or '—',
            'action': a.action,
            'entity': a.entity,
            'entity_id': a.entity_id,
            'summary': a.summary,
            'ip_address': a.ip_address,
            'created_at': a.created_at.isoformat(),
        } for a in paginated.items],
        'pagination': {
            'page': paginated.page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages,
        }
    })
