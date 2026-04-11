import functools
from flask import session, redirect, url_for, jsonify, render_template


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login_page'))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login_page'))
        if session.get('role') != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


def permission_required(perm):
    def decorator(f):
        @functools.wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('auth.login_page'))
            from models import User
            user = db_get_user(session['user_id'])
            if not user:
                return redirect(url_for('auth.login_page'))
            if user.role == 'admin':
                return f(*args, **kwargs)
            if not getattr(user, perm, False):
                return render_template('dashboard.html',
                                       error="You do not have permission to access that section.")
            return f(*args, **kwargs)
        return decorated
    return decorator


def db_get_user(user_id):
    from models import User
    return User.query.get(user_id)
