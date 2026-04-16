from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ─────────────────────────────────────────────────────────────────────────────
# Module registry — every feature the platform supports.
# Super admin can toggle these on/off per organisation.
# ─────────────────────────────────────────────────────────────────────────────
AVAILABLE_MODULES = {
    'pos':               'Point of Sale',
    'inventory':         'Inventory Management',
    'purchase_orders':   'Purchase Orders',
    'customers':         'Customer Management',
    'loyalty':           'Loyalty Programme',
    'suppliers':         'Suppliers',
    'expenses':          'Expenses',
    'reports':           'Reports & Analytics',
    'ai_analytics':      'AI Analytics',
    'refunds':           'Refunds',
    'categories':        'Categories',
    'stock_adjustments': 'Stock Adjustments',
    'telegram':          'Telegram Notifications',
    'activity_log':      'Activity Log',
    'multi_branch':      'Multi-Branch',
    'pnl_report':        'P&L Report',
    'top_customers':     'Top Customers Leaderboard',
    'product_variants':  'Product Variants (size/colour)',
    'stock_transfers':   'Branch Stock Transfers',
    'sms_receipts':      'SMS Receipts',
    'eod_report':        'End-of-Day Cash Report',
}

# Modules enabled by default for every new organisation
DEFAULT_MODULES = [
    'pos', 'inventory', 'customers', 'suppliers',
    'purchase_orders', 'expenses', 'reports', 'refunds',
    'categories', 'activity_log',
]


# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM-LEVEL MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class Organisation(db.Model):
    """A single tenant / shop on the platform."""
    __tablename__ = 'organisations'
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(120), nullable=False)
    slug         = db.Column(db.String(80), unique=True, nullable=False, index=True)
    industry     = db.Column(db.String(60), nullable=True)   # retail, food, pharmacy …
    phone        = db.Column(db.String(20), nullable=True)
    email        = db.Column(db.String(100), nullable=True)
    address      = db.Column(db.String(255), nullable=True)
    logo_url     = db.Column(db.String(500), nullable=True)
    currency     = db.Column(db.String(5), default='GHS')
    country      = db.Column(db.String(60), nullable=True)
    timezone     = db.Column(db.String(60), default='Africa/Accra')
    is_active    = db.Column(db.Boolean, default=True)
    is_verified  = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # ── Domain / subdomain ────────────────────────────────────────────────────
    # Subdomain: {slug}.inventorypro.app  (auto-assigned, no action needed)
    # Custom domain: e.g. pos.myshop.com — tenant requests, super admin verifies
    custom_domain        = db.Column(db.String(255), unique=True, nullable=True, index=True)
    domain_verified      = db.Column(db.Boolean, default=False)
    domain_verified_at   = db.Column(db.DateTime, nullable=True)
    domain_requested_at  = db.Column(db.DateTime, nullable=True)  # when tenant submitted request

    branches      = db.relationship('Branch',       backref='organisation', lazy=True)
    subscriptions = db.relationship('Subscription', backref='organisation', lazy=True,
                                    order_by='Subscription.created_at.desc()')

    @property
    def current_subscription(self):
        return (Subscription.query
                .filter_by(organisation_id=self.id)
                .order_by(Subscription.created_at.desc())
                .first())

    @property
    def current_plan(self):
        sub = self.current_subscription
        return sub.plan if sub else None

    @property
    def default_branch(self):
        return (Branch.query
                .filter_by(organisation_id=self.id, is_default=True)
                .first())


class Branch(db.Model):
    """A physical location / branch under an organisation."""
    __tablename__ = 'branches'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=False, index=True)
    name            = db.Column(db.String(100), nullable=False)
    address         = db.Column(db.String(255), nullable=True)
    phone           = db.Column(db.String(20),  nullable=True)
    is_active       = db.Column(db.Boolean, default=True)
    is_default      = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class Plan(db.Model):
    """Subscription plan definition (managed by super admin)."""
    __tablename__ = 'plans'
    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(50),  nullable=False, unique=True)  # starter, growth, pro
    display_name    = db.Column(db.String(80),  nullable=False)
    price_monthly   = db.Column(db.Float, default=0.0)   # GHS
    price_yearly    = db.Column(db.Float, default=0.0)   # GHS (with discount)
    max_branches    = db.Column(db.Integer, default=1)   # -1 = unlimited
    max_staff       = db.Column(db.Integer, default=2)   # -1 = unlimited
    max_products    = db.Column(db.Integer, default=100) # -1 = unlimited
    trial_days      = db.Column(db.Integer, default=14)
    is_active       = db.Column(db.Boolean, default=True)
    sort_order      = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class Subscription(db.Model):
    """An organisation's current or past subscription."""
    __tablename__ = 'subscriptions'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=False, index=True)
    plan_id         = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    status          = db.Column(db.String(20), default='trial', index=True)
    # status values: trial | active | grace | expired | cancelled
    billing_cycle   = db.Column(db.String(10), default='monthly')   # monthly | yearly
    started_at      = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at      = db.Column(db.DateTime, nullable=True)
    trial_ends_at   = db.Column(db.DateTime, nullable=True)
    grace_ends_at   = db.Column(db.DateTime, nullable=True)
    paystack_sub_code = db.Column(db.String(100), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship('Plan')

    @property
    def is_access_allowed(self):
        now = datetime.utcnow()
        if self.status == 'trial':
            return bool(self.trial_ends_at and now < self.trial_ends_at)
        if self.status == 'grace':
            return bool(self.grace_ends_at and now < self.grace_ends_at)
        if self.status == 'active':
            return not self.expires_at or now < self.expires_at
        return False

    @property
    def days_remaining(self):
        now = datetime.utcnow()
        end = self.trial_ends_at if self.status == 'trial' else self.expires_at
        if not end:
            return None
        delta = (end - now).days
        return max(0, delta)


class BillingRecord(db.Model):
    """Payment history per organisation."""
    __tablename__ = 'billing_records'
    id                   = db.Column(db.Integer, primary_key=True)
    organisation_id      = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                     nullable=False, index=True)
    plan_id              = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=True)
    amount               = db.Column(db.Float, nullable=False)
    currency             = db.Column(db.String(5), default='GHS')
    payment_method       = db.Column(db.String(30), nullable=True)   # momo, card, manual
    paystack_reference   = db.Column(db.String(100), nullable=True)
    status               = db.Column(db.String(20), default='success')  # success | failed | pending
    billing_period_start = db.Column(db.DateTime, nullable=True)
    billing_period_end   = db.Column(db.DateTime, nullable=True)
    description          = db.Column(db.String(255), nullable=True)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    organisation = db.relationship('Organisation', backref=db.backref('billing_records', lazy=True))
    plan         = db.relationship('Plan')


class TenantModule(db.Model):
    """Which modules are enabled per organisation (super admin toggles these)."""
    __tablename__ = 'tenant_modules'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=False, index=True)
    module          = db.Column(db.String(60), nullable=False)
    is_enabled      = db.Column(db.Boolean, default=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organisation_id', 'module', name='uq_tenant_module'),
    )

    @classmethod
    def is_enabled_for(cls, org_id, module):
        """Returns True if module is enabled for the org (defaults to True if no row)."""
        row = cls.query.filter_by(organisation_id=org_id, module=module).first()
        return row.is_enabled if row else (module in DEFAULT_MODULES)

    @classmethod
    def enabled_set(cls, org_id):
        """Returns a set of enabled module keys for the given org."""
        rows = cls.query.filter_by(organisation_id=org_id).all()
        overrides = {r.module: r.is_enabled for r in rows}
        result = set()
        for m in AVAILABLE_MODULES:
            if overrides.get(m, m in DEFAULT_MODULES):
                result.add(m)
        return result

    @classmethod
    def set_module(cls, org_id, module, enabled):
        row = cls.query.filter_by(organisation_id=org_id, module=module).first()
        if row:
            row.is_enabled = enabled
        else:
            db.session.add(cls(organisation_id=org_id, module=module, is_enabled=enabled))


# ═══════════════════════════════════════════════════════════════════════════════
# TENANT-SCOPED MODELS  (all carry organisation_id)
# ═══════════════════════════════════════════════════════════════════════════════

class User(db.Model):
    __tablename__ = 'users'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)   # NULL = super_admin
    branch_id       = db.Column(db.Integer, db.ForeignKey('branches.id'),
                                nullable=True)               # optional branch assignment
    username        = db.Column(db.String(80), nullable=False, index=True)
    full_name       = db.Column(db.String(120), nullable=True)
    email           = db.Column(db.String(120), nullable=True)
    phone           = db.Column(db.String(20),  nullable=True)
    password_hash   = db.Column(db.String(256), nullable=False)
    role            = db.Column(db.String(20), nullable=False, default='cashier')
    # roles: super_admin | owner | manager | cashier
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    # Granular permission flags (used for cashier-level overrides)
    can_view_dashboard      = db.Column(db.Boolean, default=True)
    can_view_pos            = db.Column(db.Boolean, default=True)
    can_view_products       = db.Column(db.Boolean, default=True)
    can_view_sales          = db.Column(db.Boolean, default=True)
    can_view_purchase_orders= db.Column(db.Boolean, default=False)
    can_view_customers      = db.Column(db.Boolean, default=True)
    can_view_suppliers      = db.Column(db.Boolean, default=False)
    can_view_reports        = db.Column(db.Boolean, default=False)
    can_manage_users        = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint('organisation_id', 'username', name='uq_user_org_username'),
    )

    organisation = db.relationship('Organisation', backref=db.backref('users', lazy=True))
    branch       = db.relationship('Branch')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_owner_or_manager(self):
        return self.role in ('owner', 'manager', 'admin')


class Category(db.Model):
    """Product categories — scoped to organisation."""
    __tablename__ = 'categories'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    name            = db.Column(db.String(80), nullable=False)
    color           = db.Column(db.String(20), default='#4f46e5')
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship('Product', backref='category', lazy=True,
                               foreign_keys='Product.category_id')

    __table_args__ = (
        db.UniqueConstraint('organisation_id', 'name', name='uq_category_org_name'),
    )


class Product(db.Model):
    __tablename__ = 'products'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    name            = db.Column(db.String(100), nullable=False)
    sku             = db.Column(db.String(50),  nullable=False, index=True)
    barcode         = db.Column(db.String(100), nullable=True,  index=True)
    cost_price      = db.Column(db.Float, nullable=False)
    selling_price   = db.Column(db.Float, nullable=False)
    quantity_in_stock = db.Column(db.Integer, default=0)
    damaged_quantity  = db.Column(db.Integer, default=0)
    min_stock_level   = db.Column(db.Integer, default=10)
    image_url       = db.Column(db.String(500), nullable=True)
    image_filename  = db.Column(db.String(255), nullable=True)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)
    category_id     = db.Column(db.Integer, db.ForeignKey('categories.id'),
                                nullable=True, index=True)

    __table_args__ = (
        db.UniqueConstraint('organisation_id', 'sku', name='uq_product_org_sku'),
    )


class Customer(db.Model):
    __tablename__ = 'customers'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    full_name       = db.Column(db.String(100), nullable=False)
    phone           = db.Column(db.String(20),  nullable=False, index=True)
    email           = db.Column(db.String(100), nullable=True)
    address         = db.Column(db.String(255), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organisation_id', 'phone', name='uq_customer_org_phone'),
    )

    @property
    def total_debt(self):
        return sum(s.balance_due for s in self.sales)


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    name            = db.Column(db.String(100), nullable=False)
    phone           = db.Column(db.String(20),  nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    branch_id       = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    supplier_id     = db.Column(db.Integer, db.ForeignKey('suppliers.id'),
                                nullable=False, index=True)
    status          = db.Column(db.String(20), default='Pending')
    payment_type    = db.Column(db.String(20), default='Credit')
    total_amount    = db.Column(db.Float, default=0.0)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    supplier = db.relationship('Supplier', backref=db.backref('purchase_orders', lazy=True))
    items    = db.relationship('PurchaseOrderItem', backref='purchase_order',
                               lazy=True, cascade='all, delete-orphan')
    branch   = db.relationship('Branch')


class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    id                = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'),
                                  nullable=False, index=True)
    product_id        = db.Column(db.Integer, db.ForeignKey('products.id'),
                                  nullable=False, index=True)
    quantity          = db.Column(db.Integer, nullable=False)
    quantity_received = db.Column(db.Integer, default=0)
    unit_cost         = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')

    @property
    def quantity_pending(self):
        return max(0, (self.quantity or 0) - (self.quantity_received or 0))


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    product_id      = db.Column(db.Integer, db.ForeignKey('products.id'),
                                nullable=False, index=True)
    branch_id       = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    quantity_change = db.Column(db.Integer, nullable=False)
    reason          = db.Column(db.String(50), nullable=False)
    reference_id    = db.Column(db.String(50), nullable=True)
    timestamp       = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    product = db.relationship('Product')


class Sale(db.Model):
    __tablename__ = 'sales'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    branch_id       = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'),
                                nullable=True, index=True)
    customer_id     = db.Column(db.Integer, db.ForeignKey('customers.id'),
                                nullable=False, index=True)
    total_amount    = db.Column(db.Float, nullable=False)
    discount_amount = db.Column(db.Float, default=0.0)
    amount_paid     = db.Column(db.Float, nullable=False)
    balance_due     = db.Column(db.Float, nullable=False)
    payment_status  = db.Column(db.String(20), default='PAID', index=True)
    payment_method  = db.Column(db.String(30), default='cash')  # cash | momo | card | transfer
    sale_date       = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_offline_sync = db.Column(db.Boolean, default=False)  # PWA offline sale

    customer = db.relationship('Customer', backref=db.backref('sales', lazy=True))
    items    = db.relationship('SaleItem', backref='sale', lazy=True,
                               cascade='all, delete-orphan')
    branch   = db.relationship('Branch')


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id                  = db.Column(db.Integer, primary_key=True)
    sale_id             = db.Column(db.Integer, db.ForeignKey('sales.id'),
                                    nullable=False, index=True)
    product_id          = db.Column(db.Integer, db.ForeignKey('products.id'),
                                    nullable=False, index=True)
    quantity            = db.Column(db.Integer, nullable=False)
    price_at_sale       = db.Column(db.Float, nullable=False)
    cost_price_at_sale  = db.Column(db.Float, default=0.0)
    subtotal            = db.Column(db.Float, nullable=False)
    discount_amount     = db.Column(db.Float, default=0.0)
    status              = db.Column(db.String(20), default='Active')

    product = db.relationship('Product')


class SupplierPayment(db.Model):
    __tablename__ = 'supplier_payments'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    supplier_id     = db.Column(db.Integer, db.ForeignKey('suppliers.id'),
                                nullable=False, index=True)
    amount_paid     = db.Column(db.Float, nullable=False)
    description     = db.Column(db.Text, nullable=True)
    payment_date    = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    supplier = db.relationship('Supplier', backref=db.backref('payments', lazy=True))


class AppSetting(db.Model):
    """Per-org key-value configuration store."""
    __tablename__ = 'app_settings'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    key             = db.Column(db.String(80), nullable=False, index=True)
    value           = db.Column(db.Text, nullable=True)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('organisation_id', 'key', name='uq_appsetting_org_key'),
    )

    @classmethod
    def _org_id(cls):
        """Auto-detect org_id from Flask session."""
        try:
            from flask import session, has_request_context
            if has_request_context():
                return session.get('org_id')
        except Exception:
            pass
        return None

    @classmethod
    def get(cls, key, default=None, org_id=None):
        oid = org_id if org_id is not None else cls._org_id()
        row = cls.query.filter_by(key=key, organisation_id=oid).first()
        return row.value if row else default

    @classmethod
    def set(cls, key, value, org_id=None):
        oid = org_id if org_id is not None else cls._org_id()
        row = cls.query.filter_by(key=key, organisation_id=oid).first()
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            db.session.add(cls(key=key, value=value, organisation_id=oid))
        db.session.commit()


class Refund(db.Model):
    __tablename__ = 'refunds'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    sale_id         = db.Column(db.Integer, db.ForeignKey('sales.id'),
                                nullable=False, index=True)
    product_id      = db.Column(db.Integer, db.ForeignKey('products.id'),
                                nullable=False, index=True)
    quantity        = db.Column(db.Integer, nullable=False)
    status          = db.Column(db.String(20), default='Pending')
    reason          = db.Column(db.String(255), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    sale    = db.relationship('Sale')
    product = db.relationship('Product')


class LoyaltyPoint(db.Model):
    __tablename__ = 'loyalty_points'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    customer_id     = db.Column(db.Integer, db.ForeignKey('customers.id'),
                                nullable=False, index=True)
    points          = db.Column(db.Integer, nullable=False)
    reason          = db.Column(db.String(120), nullable=True)
    reference_id    = db.Column(db.Integer, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    customer = db.relationship('Customer', backref=db.backref('loyalty_points', lazy=True))

    @classmethod
    def balance(cls, customer_id, org_id=None):
        from sqlalchemy import func
        q = db.session.query(
            func.coalesce(func.sum(cls.points), 0)
        ).filter_by(customer_id=customer_id)
        if org_id:
            q = q.filter_by(organisation_id=org_id)
        return int(q.scalar())


class Expense(db.Model):
    __tablename__ = 'expenses'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    branch_id       = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=True)
    title           = db.Column(db.String(120), nullable=False)
    amount          = db.Column(db.Float, nullable=False)
    category        = db.Column(db.String(60), nullable=True)
    note            = db.Column(db.Text, nullable=True)
    expense_date    = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    branch = db.relationship('Branch')


class ActivityLog(db.Model):
    """Audit trail — scoped to organisation."""
    __tablename__ = 'activity_logs'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'),
                                nullable=True, index=True)
    username        = db.Column(db.String(80), nullable=True)
    action          = db.Column(db.String(60), nullable=False, index=True)
    entity          = db.Column(db.String(40), nullable=True)
    entity_id       = db.Column(db.Integer, nullable=True)
    summary         = db.Column(db.String(255), nullable=True)
    ip_address      = db.Column(db.String(45), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User')

    @classmethod
    def log(cls, action, entity=None, entity_id=None, summary=None):
        try:
            from flask import session, request, has_request_context
            user_id  = session.get('user_id')  if has_request_context() else None
            username = session.get('username') if has_request_context() else None
            org_id   = session.get('org_id')   if has_request_context() else None
            ip       = request.remote_addr     if has_request_context() else None
            db.session.add(cls(
                organisation_id=org_id,
                user_id=user_id,
                username=username,
                action=action,
                entity=entity,
                entity_id=entity_id,
                summary=(summary or '')[:255] or None,
                ip_address=ip,
            ))
        except Exception:
            pass


class StockAdjustment(db.Model):
    __tablename__ = 'stock_adjustments'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=True, index=True)
    product_id      = db.Column(db.Integer, db.ForeignKey('products.id'),
                                nullable=False, index=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_after  = db.Column(db.Integer, nullable=False)
    reason          = db.Column(db.String(60), nullable=False)
    note            = db.Column(db.Text, nullable=True)
    adjusted_at     = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    product = db.relationship('Product', backref=db.backref('adjustments', lazy=True))
    user    = db.relationship('User')


class ProductVariant(db.Model):
    """
    Size / colour / other variants for a product.
    Each variant has its own stock level and optional price adjustment.
    """
    __tablename__ = 'product_variants'
    id               = db.Column(db.Integer, primary_key=True)
    organisation_id  = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                 nullable=False, index=True)
    product_id       = db.Column(db.Integer, db.ForeignKey('products.id'),
                                 nullable=False, index=True)
    name             = db.Column(db.String(80), nullable=False)   # e.g. "M / Red"
    attributes       = db.Column(db.JSON, nullable=True)           # {"size":"M","color":"Red"}
    sku_suffix       = db.Column(db.String(40), nullable=True)     # appended to parent SKU
    price_adjustment = db.Column(db.Float, default=0.0)           # +/- from base price
    quantity_in_stock= db.Column(db.Integer, default=0)
    is_active        = db.Column(db.Boolean, default=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product', backref=db.backref('variants', lazy=True))


class StockTransfer(db.Model):
    """Transfer of stock between branches within an organisation."""
    __tablename__ = 'stock_transfers'
    id              = db.Column(db.Integer, primary_key=True)
    organisation_id = db.Column(db.Integer, db.ForeignKey('organisations.id'),
                                nullable=False, index=True)
    from_branch_id  = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=False)
    to_branch_id    = db.Column(db.Integer, db.ForeignKey('branches.id'), nullable=False)
    product_id      = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity        = db.Column(db.Integer, nullable=False)
    status          = db.Column(db.String(20), default='pending', index=True)
    # status: pending | completed | cancelled
    notes           = db.Column(db.Text, nullable=True)
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    completed_at    = db.Column(db.DateTime, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    from_branch  = db.relationship('Branch', foreign_keys=[from_branch_id])
    to_branch    = db.relationship('Branch', foreign_keys=[to_branch_id])
    product      = db.relationship('Product')
    created_by_user = db.relationship('User', foreign_keys=[created_by])
