from flask import Blueprint, render_template, request, jsonify, session
from models import db, User
from decorators import admin_required, login_required

users_bp = Blueprint('users', __name__)

PERMISSION_FIELDS = [
    'can_view_dashboard', 'can_view_pos', 'can_view_products',
    'can_view_sales', 'can_view_purchase_orders', 'can_view_customers',
    'can_view_suppliers', 'can_view_reports', 'can_manage_users',
]


@users_bp.route('/users-page')
@login_required
@admin_required
def users_page():
    return render_template('users.html')


@users_bp.route('/api/users', methods=['GET'])
@login_required
@admin_required
def get_users():
    users = User.query.order_by(User.username).all()
    return jsonify([_serialize_user(u) for u in users])


@users_bp.route('/api/users', methods=['POST'])
@login_required
@admin_required
def create_user():
    data = request.json or {}

    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    role = data.get('role', 'sales')

    if not username:
        return jsonify({'error': 'Username is required'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    if role not in ('admin', 'sales'):
        return jsonify({'error': 'Role must be admin or sales'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already taken'}), 409

    try:
        user = User(username=username, role=role)
        user.set_password(password)

        for perm in PERMISSION_FIELDS:
            if perm in data:
                setattr(user, perm, bool(data[perm]))

        db.session.add(user)
        db.session.commit()
        return jsonify({'message': 'User created', 'id': user.id}), 201
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to create user'}), 500


@users_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_user(user_id):
    if session.get('user_id') == user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    user = User.query.get_or_404(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({'message': 'User deleted'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete user'}), 500


@users_bp.route('/api/users/<int:user_id>/permissions', methods=['PUT'])
@login_required
@admin_required
def update_permissions(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json or {}

    try:
        for perm in PERMISSION_FIELDS:
            if perm in data:
                setattr(user, perm, bool(data[perm]))

        db.session.commit()
        return jsonify({'message': 'Permissions updated'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to update permissions'}), 500


@users_bp.route('/api/users/<int:user_id>/password', methods=['PUT'])
@login_required
@admin_required
def change_password(user_id):
    user = User.query.get_or_404(user_id)
    data = request.json or {}
    password = data.get('password', '')

    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400

    try:
        user.set_password(password)
        db.session.commit()
        return jsonify({'message': 'Password updated'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to update password'}), 500


def _serialize_user(u):
    return {
        'id': u.id,
        'username': u.username,
        'role': u.role,
        'permissions': {p: getattr(u, p, False) for p in PERMISSION_FIELDS},
    }
