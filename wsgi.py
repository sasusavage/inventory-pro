from app import create_app

app = create_app()

# ── Safe startup migrations ──────────────────────────────────────────────────
def _run_migrations(flask_app):
    with flask_app.app_context():
        from models import db, DEFAULT_MODULES, AVAILABLE_MODULES
        from sqlalchemy import inspect, text

        # Create any new tables (idempotent)
        db.create_all()

        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()

        def cols(table):
            if table not in existing_tables:
                return []
            return [c['name'] for c in inspector.get_columns(table)]

        def safe_alter(sql):
            try:
                db.session.execute(text(sql))
                db.session.commit()
            except Exception:
                db.session.rollback()

        # ── products ──────────────────────────────────────────────────────────
        prod_cols = cols('products')
        if 'category_id' not in prod_cols:
            safe_alter('ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id)')
        if 'barcode' not in prod_cols:
            safe_alter('ALTER TABLE products ADD COLUMN barcode VARCHAR(100)')
        if 'organisation_id' not in prod_cols:
            safe_alter('ALTER TABLE products ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── purchase_order_items ──────────────────────────────────────────────
        poi_cols = cols('purchase_order_items')
        if 'quantity_received' not in poi_cols:
            safe_alter('ALTER TABLE purchase_order_items ADD COLUMN quantity_received INTEGER DEFAULT 0')

        # ── users ─────────────────────────────────────────────────────────────
        user_cols = cols('users')
        if 'organisation_id' not in user_cols:
            safe_alter('ALTER TABLE users ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')
        if 'branch_id' not in user_cols:
            safe_alter('ALTER TABLE users ADD COLUMN branch_id INTEGER REFERENCES branches(id)')
        if 'full_name' not in user_cols:
            safe_alter("ALTER TABLE users ADD COLUMN full_name VARCHAR(120)")
        if 'email' not in user_cols:
            safe_alter("ALTER TABLE users ADD COLUMN email VARCHAR(120)")
        if 'phone' not in user_cols:
            safe_alter("ALTER TABLE users ADD COLUMN phone VARCHAR(30)")
        if 'is_active' not in user_cols:
            safe_alter("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE")

        # ── customers ────────────────────────────────────────────────────────
        cust_cols = cols('customers')
        if 'organisation_id' not in cust_cols:
            safe_alter('ALTER TABLE customers ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── categories ────────────────────────────────────────────────────────
        cat_cols = cols('categories')
        if 'organisation_id' not in cat_cols:
            safe_alter('ALTER TABLE categories ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── suppliers ────────────────────────────────────────────────────────
        sup_cols = cols('suppliers')
        if 'organisation_id' not in sup_cols:
            safe_alter('ALTER TABLE suppliers ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── purchase_orders ───────────────────────────────────────────────────
        po_cols = cols('purchase_orders')
        if 'organisation_id' not in po_cols:
            safe_alter('ALTER TABLE purchase_orders ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')
        if 'branch_id' not in po_cols:
            safe_alter('ALTER TABLE purchase_orders ADD COLUMN branch_id INTEGER REFERENCES branches(id)')

        # ── stock_movements ───────────────────────────────────────────────────
        sm_cols = cols('stock_movements')
        if 'organisation_id' not in sm_cols:
            safe_alter('ALTER TABLE stock_movements ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')
        if 'branch_id' not in sm_cols:
            safe_alter('ALTER TABLE stock_movements ADD COLUMN branch_id INTEGER REFERENCES branches(id)')

        # ── sales ─────────────────────────────────────────────────────────────
        sale_cols = cols('sales')
        if 'organisation_id' not in sale_cols:
            safe_alter('ALTER TABLE sales ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')
        if 'branch_id' not in sale_cols:
            safe_alter('ALTER TABLE sales ADD COLUMN branch_id INTEGER REFERENCES branches(id)')
        if 'discount_amount' not in sale_cols:
            safe_alter('ALTER TABLE sales ADD COLUMN discount_amount NUMERIC(12,2) DEFAULT 0')
        if 'payment_method' not in sale_cols:
            safe_alter("ALTER TABLE sales ADD COLUMN payment_method VARCHAR(30) DEFAULT 'cash'")
        if 'is_offline_sync' not in sale_cols:
            safe_alter('ALTER TABLE sales ADD COLUMN is_offline_sync BOOLEAN DEFAULT FALSE')

        # ── sale_items ────────────────────────────────────────────────────────
        si_cols = cols('sale_items')
        if 'discount_amount' not in si_cols:
            safe_alter('ALTER TABLE sale_items ADD COLUMN discount_amount NUMERIC(12,2) DEFAULT 0')

        # ── supplier_payments ─────────────────────────────────────────────────
        sp_cols = cols('supplier_payments')
        if 'organisation_id' not in sp_cols:
            safe_alter('ALTER TABLE supplier_payments ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── app_settings ──────────────────────────────────────────────────────
        as_cols = cols('app_settings')
        if 'organisation_id' not in as_cols:
            safe_alter('ALTER TABLE app_settings ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── refunds ───────────────────────────────────────────────────────────
        ref_cols = cols('refunds')
        if 'organisation_id' not in ref_cols:
            safe_alter('ALTER TABLE refunds ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── loyalty_points ────────────────────────────────────────────────────
        lp_cols = cols('loyalty_points')
        if 'organisation_id' not in lp_cols:
            safe_alter('ALTER TABLE loyalty_points ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── expenses ──────────────────────────────────────────────────────────
        exp_cols = cols('expenses')
        if 'organisation_id' not in exp_cols:
            safe_alter('ALTER TABLE expenses ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')
        if 'branch_id' not in exp_cols:
            safe_alter('ALTER TABLE expenses ADD COLUMN branch_id INTEGER REFERENCES branches(id)')

        # ── activity_logs ─────────────────────────────────────────────────────
        al_cols = cols('activity_logs')
        if 'organisation_id' not in al_cols:
            safe_alter('ALTER TABLE activity_logs ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── stock_adjustments ─────────────────────────────────────────────────
        sadj_cols = cols('stock_adjustments')
        if sadj_cols and 'organisation_id' not in sadj_cols:
            safe_alter('ALTER TABLE stock_adjustments ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')

        # ── branches: add columns before seeding ─────────────────────────────
        branch_cols = cols('branches')
        if branch_cols:
            if 'organisation_id' not in branch_cols:
                safe_alter('ALTER TABLE branches ADD COLUMN organisation_id INTEGER REFERENCES organisations(id)')
            if 'is_main' not in branch_cols:
                safe_alter('ALTER TABLE branches ADD COLUMN is_main BOOLEAN DEFAULT FALSE')
            if 'is_active' not in branch_cols:
                safe_alter('ALTER TABLE branches ADD COLUMN is_active BOOLEAN DEFAULT TRUE')
            if 'address' not in branch_cols:
                safe_alter('ALTER TABLE branches ADD COLUMN address TEXT')
            if 'phone' not in branch_cols:
                safe_alter('ALTER TABLE branches ADD COLUMN phone VARCHAR(30)')

        # ── organisations: add extra columns BEFORE seeding org #1 ──────────────
        if 'organisations' in existing_tables:
            org_cols_early = cols('organisations')
            if 'custom_domain' not in org_cols_early:
                safe_alter('ALTER TABLE organisations ADD COLUMN custom_domain VARCHAR(255) UNIQUE')
            if 'domain_verified' not in org_cols_early:
                safe_alter('ALTER TABLE organisations ADD COLUMN domain_verified BOOLEAN DEFAULT FALSE')
            if 'domain_verified_at' not in org_cols_early:
                safe_alter('ALTER TABLE organisations ADD COLUMN domain_verified_at TIMESTAMP')
            if 'domain_requested_at' not in org_cols_early:
                safe_alter('ALTER TABLE organisations ADD COLUMN domain_requested_at TIMESTAMP')
            if 'country' not in org_cols_early:
                safe_alter("ALTER TABLE organisations ADD COLUMN country VARCHAR(60)")
            if 'timezone' not in org_cols_early:
                safe_alter("ALTER TABLE organisations ADD COLUMN timezone VARCHAR(60) DEFAULT 'Africa/Accra'")

        # ═══════════════════════════════════════════════════════════════════════
        # Seed Tenant #1 — existing shop becomes the first organisation
        # ═══════════════════════════════════════════════════════════════════════
        if 'organisations' in existing_tables:
            result = db.session.execute(text('SELECT COUNT(*) FROM organisations')).scalar()
            if result == 0:
                db.session.execute(text("""
                    INSERT INTO organisations (id, name, slug, currency, country, timezone, is_active, created_at)
                    VALUES (1, 'My Store', 'my-store', 'GHS', 'Ghana', 'Africa/Accra', TRUE, NOW())
                """))
                db.session.commit()

            # Backfill all existing rows to org_id=1 where NULL
            for table in [
                'users', 'products', 'customers', 'categories', 'suppliers',
                'purchase_orders', 'stock_movements', 'sales', 'supplier_payments',
                'app_settings', 'refunds', 'loyalty_points', 'expenses',
                'activity_logs',
            ]:
                if table in existing_tables and 'organisation_id' in cols(table):
                    safe_alter(f'UPDATE {table} SET organisation_id=1 WHERE organisation_id IS NULL')

            if 'stock_adjustments' in existing_tables and 'organisation_id' in cols('stock_adjustments'):
                safe_alter('UPDATE stock_adjustments SET organisation_id=1 WHERE organisation_id IS NULL')

        # ── branches: seed default branch for org 1 ───────────────────────────
        if 'branches' in existing_tables:
            result = db.session.execute(text('SELECT COUNT(*) FROM branches')).scalar()
            if result == 0:
                db.session.execute(text("""
                    INSERT INTO branches (id, organisation_id, name, is_main, is_active, created_at)
                    VALUES (1, 1, 'Main Branch', TRUE, TRUE, NOW())
                """))
                db.session.commit()

        # ── plans: seed default subscription plans ─────────────────────────────
        if 'plans' in existing_tables:
            result = db.session.execute(text('SELECT COUNT(*) FROM plans')).scalar()
            if result == 0:
                plans = [
                    (1, 'Starter',    'starter',    9.99,  1,  1,   1000,  5),
                    (2, 'Growth',     'growth',    29.99,  3,  5,  10000, 20),
                    (3, 'Pro',        'pro',       79.99, 10, 20, 100000, 50),
                    (4, 'Enterprise', 'enterprise',199.99,999,999,9999999,999),
                ]
                for p in plans:
                    db.session.execute(text("""
                        INSERT INTO plans (id, name, slug, price_monthly, max_branches, max_users, max_products, max_customers, is_active)
                        VALUES (:id, :name, :slug, :price, :mb, :mu, :mp, :mc, TRUE)
                    """), {'id': p[0], 'name': p[1], 'slug': p[2], 'price': p[3],
                           'mb': p[4], 'mu': p[5], 'mp': p[6], 'mc': p[7]})
                db.session.commit()

        # ── subscriptions: seed a Pro subscription for org 1 ──────────────────
        if 'subscriptions' in existing_tables:
            result = db.session.execute(text('SELECT COUNT(*) FROM subscriptions WHERE organisation_id=1')).scalar()
            if result == 0:
                db.session.execute(text("""
                    INSERT INTO subscriptions (organisation_id, plan_id, status, current_period_start, current_period_end)
                    VALUES (1, 3, 'active', NOW(), NOW() + INTERVAL '1 year')
                """))
                db.session.commit()

        # ── tenant_modules: seed default enabled modules for org 1 ─────────────
        if 'tenant_modules' in existing_tables:
            result = db.session.execute(text('SELECT COUNT(*) FROM tenant_modules WHERE organisation_id=1')).scalar()
            if result == 0:
                for module in AVAILABLE_MODULES:
                    enabled = module in DEFAULT_MODULES
                    db.session.execute(text("""
                        INSERT INTO tenant_modules (organisation_id, module, is_enabled)
                        VALUES (:oid, :mod, :en)
                        ON CONFLICT DO NOTHING
                    """), {'oid': 1, 'mod': module, 'en': enabled})
                db.session.commit()

        # ── app_settings: ensure org 1 has a settings row ─────────────────────
        if 'app_settings' in existing_tables:
            # Migrate any settings without org_id to org 1
            safe_alter('UPDATE app_settings SET organisation_id=1 WHERE organisation_id IS NULL')

        # (organisations extra columns are added earlier, before seed)

        # ── unique constraint migrations (PostgreSQL only — skip on SQLite) ────
        try:
            dialect = db.engine.dialect.name
            if dialect == 'postgresql':
                # products: drop old sku unique, add composite
                existing = [r[0] for r in db.session.execute(
                    text("SELECT constraint_name FROM information_schema.table_constraints "
                         "WHERE table_name='products' AND constraint_type='UNIQUE'")
                ).fetchall()]
                if 'products_sku_key' in existing:
                    safe_alter('ALTER TABLE products DROP CONSTRAINT products_sku_key')
                if 'uq_product_org_sku' not in existing:
                    safe_alter('ALTER TABLE products ADD CONSTRAINT uq_product_org_sku UNIQUE (organisation_id, sku)')

                # customers: drop old phone unique, add composite
                existing = [r[0] for r in db.session.execute(
                    text("SELECT constraint_name FROM information_schema.table_constraints "
                         "WHERE table_name='customers' AND constraint_type='UNIQUE'")
                ).fetchall()]
                if 'customers_phone_key' in existing:
                    safe_alter('ALTER TABLE customers DROP CONSTRAINT customers_phone_key')
                if 'uq_customer_org_phone' not in existing:
                    safe_alter('ALTER TABLE customers ADD CONSTRAINT uq_customer_org_phone UNIQUE (organisation_id, phone)')

                # categories: drop old name unique, add composite
                existing = [r[0] for r in db.session.execute(
                    text("SELECT constraint_name FROM information_schema.table_constraints "
                         "WHERE table_name='categories' AND constraint_type='UNIQUE'")
                ).fetchall()]
                if 'categories_name_key' in existing:
                    safe_alter('ALTER TABLE categories DROP CONSTRAINT categories_name_key')
                if 'uq_category_org_name' not in existing:
                    safe_alter('ALTER TABLE categories ADD CONSTRAINT uq_category_org_name UNIQUE (organisation_id, name)')

                # users: drop old username unique, add composite
                existing = [r[0] for r in db.session.execute(
                    text("SELECT constraint_name FROM information_schema.table_constraints "
                         "WHERE table_name='users' AND constraint_type='UNIQUE'")
                ).fetchall()]
                if 'users_username_key' in existing:
                    safe_alter('ALTER TABLE users DROP CONSTRAINT users_username_key')
                if 'uq_user_org_username' not in existing:
                    safe_alter('ALTER TABLE users ADD CONSTRAINT uq_user_org_username UNIQUE (organisation_id, username)')

        except Exception:
            db.session.rollback()


_run_migrations(app)

# Seed default users only after migrations have run
from app import _seed_default_users
_seed_default_users(app)
