from app import create_app

app = create_app()

# ── Safe startup migrations ──────────────────────────────────────────────────
def _run_migrations(flask_app):
    with flask_app.app_context():
        from models import db, DEFAULT_MODULES, AVAILABLE_MODULES
        from sqlalchemy import inspect, text

        # Drop SaaS infrastructure tables so they are recreated with the
        # correct schema. These hold only seed data, never real user data.
        # Use a raw connection with autocommit to avoid transaction conflicts.
        try:
            with db.engine.connect() as _conn:
                _conn.execute(text('SET session_replication_role = replica'))
                for _t in ('billing_records', 'subscriptions', 'tenant_modules', 'plans', 'branches'):
                    _conn.execute(text(f'DROP TABLE IF EXISTS {_t} CASCADE'))
                _conn.execute(text('SET session_replication_role = DEFAULT'))
                _conn.commit()
        except Exception:
            pass

        # Create all tables fresh (new ones) or leave existing ones untouched
        db.create_all()

        # Refresh inspector after drop/create
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

        # ── seed org #2: Platform Admin (super admin's own workspace) ──────────
        if 'organisations' in existing_tables:
            exists = db.session.execute(text('SELECT COUNT(*) FROM organisations WHERE id=2')).scalar()
            if not exists:
                db.session.execute(text("""
                    INSERT INTO organisations (id, name, slug, currency, country, timezone, is_active, created_at)
                    VALUES (2, 'Platform Admin', 'platform-admin', 'GHS', 'Ghana', 'Africa/Accra', TRUE, NOW())
                """))
                db.session.commit()

        # ── branches: seed default branch for org 1 + org 2 ─────────────────
        if 'branches' in existing_tables:
            if not db.session.execute(text('SELECT COUNT(*) FROM branches WHERE organisation_id=1')).scalar():
                db.session.execute(text("""
                    INSERT INTO branches (id, organisation_id, name, is_default, is_active, created_at)
                    VALUES (1, 1, 'Main Branch', TRUE, TRUE, NOW())
                """))
                db.session.commit()
            if not db.session.execute(text('SELECT COUNT(*) FROM branches WHERE organisation_id=2')).scalar():
                db.session.execute(text("""
                    INSERT INTO branches (organisation_id, name, is_default, is_active, created_at)
                    VALUES (2, 'Platform Branch', TRUE, TRUE, NOW())
                """))
                db.session.commit()

        # ── plans: seed default subscription plans ─────────────────────────────
        if 'plans' in existing_tables:
            result = db.session.execute(text('SELECT COUNT(*) FROM plans')).scalar()
            if result == 0:
                plans_data = [
                    # id, name, display_name,       price_mo, price_yr, max_br, max_staff, max_prod, trial, sort
                    (1, 'starter',    'Starter',     59.0,   590.0,  1,   2,   500,  14, 1),
                    (2, 'growth',     'Growth',     179.0,  1790.0,  3,  10,  5000,  14, 2),
                    (3, 'pro',        'Pro',         449.0,  4490.0, 10,  30, 50000,  14, 3),
                    (4, 'enterprise', 'Enterprise',    0.0,     0.0,-1,  -1,    -1,  30, 4),
                ]
                for p in plans_data:
                    db.session.execute(text("""
                        INSERT INTO plans (id, name, display_name, price_monthly, price_yearly,
                                          max_branches, max_staff, max_products, trial_days, sort_order, is_active)
                        VALUES (:id, :name, :dn, :pm, :py, :mb, :ms, :mp, :td, :so, TRUE)
                    """), {'id': p[0], 'name': p[1], 'dn': p[2], 'pm': p[3], 'py': p[4],
                           'mb': p[5], 'ms': p[6], 'mp': p[7], 'td': p[8], 'so': p[9]})
                db.session.commit()

        # ── subscriptions: seed an active Pro subscription for org 1 ──────────
        if 'subscriptions' in existing_tables:
            result = db.session.execute(text('SELECT COUNT(*) FROM subscriptions WHERE organisation_id=1')).scalar()
            if result == 0:
                db.session.execute(text("""
                    INSERT INTO subscriptions (organisation_id, plan_id, status,
                                              billing_cycle, started_at, expires_at)
                    VALUES (1, 3, 'active', 'monthly', NOW(), NOW() + INTERVAL '1 year')
                """))
                db.session.commit()

        # ── tenant_modules: seed modules for org 1 (defaults) + org 2 (all on) ─
        if 'tenant_modules' in existing_tables:
            for org_id, all_on in [(1, False), (2, True)]:
                result = db.session.execute(
                    text('SELECT COUNT(*) FROM tenant_modules WHERE organisation_id=:o'), {'o': org_id}
                ).scalar()
                if result == 0:
                    for module in AVAILABLE_MODULES:
                        enabled = True if all_on else (module in DEFAULT_MODULES)
                        db.session.execute(text("""
                            INSERT INTO tenant_modules (organisation_id, module, is_enabled)
                            VALUES (:oid, :mod, :en)
                            ON CONFLICT DO NOTHING
                        """), {'oid': org_id, 'mod': module, 'en': enabled})
            db.session.commit()

        # ── fix superadmin user: must belong to org 2, not org 1 ─────────────
        if 'users' in existing_tables and 'organisation_id' in cols('users'):
            safe_alter("""
                UPDATE users SET organisation_id=2
                WHERE username='superadmin' AND (organisation_id=1 OR organisation_id IS NULL)
            """)

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
