from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='sales')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Granular permission flags
    can_view_dashboard = db.Column(db.Boolean, default=True)
    can_view_pos = db.Column(db.Boolean, default=True)
    can_view_products = db.Column(db.Boolean, default=True)
    can_view_sales = db.Column(db.Boolean, default=True)
    can_view_purchase_orders = db.Column(db.Boolean, default=True)
    can_view_customers = db.Column(db.Boolean, default=True)
    can_view_suppliers = db.Column(db.Boolean, default=True)
    can_view_reports = db.Column(db.Boolean, default=True)
    can_manage_users = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    cost_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    quantity_in_stock = db.Column(db.Integer, default=0)
    damaged_quantity = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=10)
    image_url = db.Column(db.String(500), nullable=True)
    image_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def total_debt(self):
        return sum(s.balance_due for s in self.sales)


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='Pending')
    payment_type = db.Column(db.String(20), default='Credit')
    total_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    supplier = db.relationship('Supplier', backref=db.backref('purchase_orders', lazy=True))
    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy=True,
                            cascade='all, delete-orphan')


class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')


class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity_change = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(50), nullable=False)
    reference_id = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    product = db.relationship('Product')


class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    total_amount = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    balance_due = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), default='PAID', index=True)
    sale_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    customer = db.relationship('Customer', backref=db.backref('sales', lazy=True))
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')


class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Float, nullable=False)
    cost_price_at_sale = db.Column(db.Float, default=0.0)
    subtotal = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Active')

    product = db.relationship('Product')


class SupplierPayment(db.Model):
    __tablename__ = 'supplier_payments'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False, index=True)
    amount_paid = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    supplier = db.relationship('Supplier', backref=db.backref('payments', lazy=True))


class AppSetting(db.Model):
    """Key-value store for runtime configuration (e.g. Telegram credentials)."""
    __tablename__ = 'app_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls, key, default=None):
        row = cls.query.filter_by(key=key).first()
        return row.value if row else default

    @classmethod
    def set(cls, key, value):
        row = cls.query.filter_by(key=key).first()
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            db.session.add(cls(key=key, value=value))
        db.session.commit()


class Refund(db.Model):
    __tablename__ = 'refunds'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Pending')
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sale = db.relationship('Sale')
    product = db.relationship('Product')


class Category(db.Model):
    """Product categories for grouping and POS filtering."""
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    color = db.Column(db.String(20), default='#4f46e5')  # hex colour for badge
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    products = db.relationship('Product', backref='category', lazy=True)


# Add category_id FK to Product
Product.category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True, index=True)


class LoyaltyPoint(db.Model):
    """Tracks loyalty point balance per customer. Points earned on every sale."""
    __tablename__ = 'loyalty_points'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False, index=True)
    points = db.Column(db.Integer, nullable=False)  # positive = earned, negative = redeemed
    reason = db.Column(db.String(120), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)  # sale_id
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    customer = db.relationship('Customer', backref=db.backref('loyalty_points', lazy=True))

    @classmethod
    def balance(cls, customer_id):
        from sqlalchemy import func
        result = db.session.query(func.coalesce(func.sum(cls.points), 0)).filter_by(customer_id=customer_id).scalar()
        return int(result)


class Expense(db.Model):
    """Business expense ledger."""
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(60), nullable=True)  # Rent, Salary, Utilities, etc.
    note = db.Column(db.Text, nullable=True)
    expense_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class StockAdjustment(db.Model):
    """Manual stock corrections with reason and audit trail."""
    __tablename__ = 'stock_adjustments'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(60), nullable=False)  # Damage, Theft, Correction, Recount
    note = db.Column(db.Text, nullable=True)
    adjusted_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    product = db.relationship('Product', backref=db.backref('adjustments', lazy=True))
    user = db.relationship('User')
