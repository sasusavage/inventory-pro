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
    from telegram_bot import bot_bp

    for bp in (
        auth_bp, dashboard_bp, products_bp, sales_bp,
        customers_bp, suppliers_bp, purchase_orders_bp,
        refunds_bp, reports_bp, users_bp, settings_bp,
        ai_bp, analytics_bp, bot_bp,
    ):
        app.register_blueprint(bp)

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
