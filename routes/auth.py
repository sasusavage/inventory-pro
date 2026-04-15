from flask import Blueprint, render_template, request, jsonify, session
from models import db, User, ActivityLog, TenantModule
from extensions import limiter

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login-page')
def login_page():
    return render_template('login.html')


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    data = request.json or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        session['user_id']  = user.id
        session['username'] = user.username
        session['role']     = user.role
        session['org_id']   = user.organisation_id or 1
        ActivityLog.log('LOGIN', entity='user', entity_id=user.id, summary=f'{user.username} signed in')
        db.session.commit()
        return jsonify({'message': 'Login successful', 'role': user.role})
    ActivityLog.log('LOGIN_FAILED', entity='user', summary=f'Failed login for "{username}"')
    db.session.commit()
    return jsonify({'error': 'Invalid credentials'}), 401


@auth_bp.route('/logout', methods=['POST'])
def logout():
    username = session.get('username') or session.get('user_id')
    if username:
        ActivityLog.log('LOGOUT', entity='user', summary=f'{username} signed out')
        db.session.commit()
    session.clear()
    return jsonify({'message': 'Logged out'})


@auth_bp.route('/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user:
            org_id = session.get('org_id', 1)
            enabled_modules = list(TenantModule.enabled_set(org_id))
            return jsonify({
                'authenticated': True,
                'role': user.role,
                'username': user.username,
                'org_id': org_id,
                'enabled_modules': enabled_modules,
                'permissions': {
                    'can_view_dashboard': user.can_view_dashboard,
                    'can_view_pos': user.can_view_pos,
                    'can_view_products': user.can_view_products,
                    'can_view_sales': user.can_view_sales,
                    'can_view_purchase_orders': user.can_view_purchase_orders,
                    'can_view_customers': user.can_view_customers,
                    'can_view_suppliers': user.can_view_suppliers,
                    'can_view_reports': user.can_view_reports,
                    'can_manage_users': user.can_manage_users,
                }
            })
    return jsonify({'authenticated': False}), 401
