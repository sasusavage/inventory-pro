from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    """
    User model for Role-Based Access Control (RBAC)
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='sales') # 'admin' or 'sales'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    sku = db.Column(db.String(50), unique=True, nullable=False)
    cost_price = db.Column(db.Float, nullable=False)
    selling_price = db.Column(db.Float, nullable=False)
    quantity_in_stock = db.Column(db.Integer, default=0)
    damaged_quantity = db.Column(db.Integer, default=0)
    min_stock_level = db.Column(db.Integer, default=10) # Alert trigger
    image_url = db.Column(db.String(500), nullable=True) # Remote URL support
    image_filename = db.Column(db.String(255), nullable=True) # Local upload support
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Customer(db.Model):
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    @property
    def total_debt(self):
        # Calculate total debt from partially paid or unpaid sales
        # This is a helper, though efficient queries should do this in bulk
        debt = 0
        for sale in self.sales:
            debt += sale.balance_due
        return debt

class Supplier(db.Model):
    __tablename__ = 'suppliers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_orders'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Received, Cancelled
    payment_type = db.Column(db.String(20), default='Credit') # Cash, Credit
    total_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    supplier = db.relationship('Supplier', backref=db.backref('purchase_orders', lazy=True))
    items = db.relationship('PurchaseOrderItem', backref='purchase_order', lazy=True, cascade="all, delete-orphan")

class PurchaseOrderItem(db.Model):
    __tablename__ = 'purchase_order_items'
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Float, nullable=False)
    
    product = db.relationship('Product')

class StockMovement(db.Model):
    __tablename__ = 'stock_movements'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False) # Positive (add) or Negative (remove)
    reason = db.Column(db.String(50), nullable=False) # Sale, PO Received, Refund, Adjustment
    reference_id = db.Column(db.String(50), nullable=True) # ID of Sale or PO
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    product = db.relationship('Product')

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Salesperson
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    balance_due = db.Column(db.Float, nullable=False) # Calculated
    payment_status = db.Column(db.String(20), default='PAID') # PAID, PARTIAL, UNPAID
    sale_date = db.Column(db.DateTime, default=datetime.utcnow)

    customer = db.relationship('Customer', backref=db.backref('sales', lazy=True))
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade="all, delete-orphan")

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_sale = db.Column(db.Float, nullable=False)
    cost_price_at_sale = db.Column(db.Float, default=0.0)
    subtotal = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Active')

    product = db.relationship('Product')

class SupplierPayment(db.Model):
    __tablename__ = 'supplier_payments'
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)

    supplier = db.relationship('Supplier', backref=db.backref('payments', lazy=True))

class Refund(db.Model):
    __tablename__ = 'refunds'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected
    reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sale = db.relationship('Sale')
    product = db.relationship('Product')
