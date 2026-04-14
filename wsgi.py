from app import create_app, _seed_default_users

app = create_app()
_seed_default_users(app)

# ── Safe startup migrations ──────────────────────────────────────────────────
# db.create_all() is idempotent — it only creates tables that are missing.
# The ALTER TABLE calls add columns that may be missing on existing DBs
# (e.g. when deploying to a server that has the old schema).
def _run_migrations(flask_app):
    with flask_app.app_context():
        from models import db
        from sqlalchemy import inspect, text

        # Create any new tables
        db.create_all()

        inspector = inspect(db.engine)

        # products.category_id (added when Category model was introduced)
        prod_cols = [c['name'] for c in inspector.get_columns('products')]
        if 'category_id' not in prod_cols:
            db.session.execute(
                text('ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id)')
            )
            db.session.commit()

        # purchase_order_items.quantity_received (added for partial PO receiving)
        try:
            poi_cols = [c['name'] for c in inspector.get_columns('purchase_order_items')]
            if 'quantity_received' not in poi_cols:
                db.session.execute(
                    text('ALTER TABLE purchase_order_items ADD COLUMN quantity_received INTEGER DEFAULT 0')
                )
                db.session.commit()
        except Exception:
            db.session.rollback()

        # Any future safe ALTER TABLE migrations go here (add columns only — never drop)


_run_migrations(app)
