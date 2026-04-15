import os
from flask import Flask, jsonify, render_template
from config import Config
from models import db
from extensions import limiter


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if config:
        app.config.update(config)

    # File upload settings
    app.config.setdefault('UPLOAD_FOLDER', os.path.join('static', 'uploads'))
    app.config.setdefault('MAX_CONTENT_LENGTH', 5 * 1024 * 1024)  # 5 MB limit
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    limiter.init_app(app)

    # Multi-tenant org context (sets g.org_id, g.enabled_modules on every request)
    from org_context import init_org_context
    init_org_context(app)

    # Register blueprints
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.products import products_bp
    from routes.sales import sales_bp
    from routes.customers import customers_bp
    from routes.suppliers import suppliers_bp
    from routes.purchase_orders import purchase_orders_bp
    from routes.refunds import refunds_bp
    from routes.reports import reports_bp
    from routes.users import users_bp
    from routes.settings import settings_bp
    from routes.ai import ai_bp
    from routes.analytics import analytics_bp
    from routes.categories import categories_bp
    from routes.expenses import expenses_bp
    from routes.stock_adjustments import stock_adj_bp
    from routes.loyalty import loyalty_bp
    from routes.activity import activity_bp
    from routes.onboarding import onboarding_bp
    from routes.superadmin import superadmin_bp
    from telegram_bot import bot_bp

    for bp in (
        auth_bp, dashboard_bp, products_bp, sales_bp,
        customers_bp, suppliers_bp, purchase_orders_bp,
        refunds_bp, reports_bp, users_bp, settings_bp,
        ai_bp, analytics_bp, categories_bp, expenses_bp,
        stock_adj_bp, loyalty_bp, activity_bp, onboarding_bp,
        superadmin_bp, bot_bp,
    ):
        app.register_blueprint(bp)

    # Start background scheduler (non-blocking)
    try:
        from scheduler import init_scheduler
        init_scheduler(app)
    except Exception as _sched_err:
        app.logger.warning(f"Scheduler not started: {_sched_err}")

    # ── PWA: serve sw.js with correct Service-Worker-Allowed scope header ────
    import os as _os
    from flask import send_from_directory, make_response as _mkr

    @app.route('/sw.js')
    def service_worker():
        resp = _mkr(send_from_directory(
            _os.path.join(app.root_path, 'static'), 'sw.js',
            mimetype='application/javascript'
        ))
        resp.headers['Service-Worker-Allowed'] = '/'
        resp.headers['Cache-Control'] = 'no-cache'
        return resp

    # ── Error handlers ───────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(_e):
        if _wants_json():
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(_e):
        if _wants_json():
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify({'error': 'File too large (max 5MB)'}), 413

    @app.errorhandler(429)
    def rate_limited(_e):
        return jsonify({'error': 'Too many requests — please slow down'}), 429

    return app


def _wants_json():
    from flask import request
    return request.path.startswith('/api') or request.path.startswith('/dashboard') \
        or request.is_json or 'application/json' in request.headers.get('Accept', '')


def _seed_default_users(app):
    from models import User
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin_pro').first():
            admin = User(username='admin_pro', role='admin')
            admin.set_password('adminPass2026')
            db.session.add(admin)
            db.session.commit()

        if not User.query.filter_by(username='sales_pro').first():
            sales = User(username='sales_pro', role='sales')
            sales.set_password('salesPass2026')
            db.session.add(sales)
            db.session.commit()


if __name__ == '__main__':
    app = create_app()
    _seed_default_users(app)
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
