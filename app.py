from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from config import Config
from models import db, Product, Customer, Supplier, Sale, SaleItem, SupplierPayment, User, Refund, PurchaseOrder, PurchaseOrderItem, StockMovement
from datetime import datetime, timedelta
from sqlalchemy import func
import os
from werkzeug.utils import secure_filename
import functools
from flask import make_response
from io import BytesIO
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except ImportError:
    pass # In case not installed yet

app = Flask(__name__)
app.config.from_object(Config)

# Configure simple upload
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db.init_app(app)

# Create tables on first run (if specific file db)
with app.app_context():
    db.create_all()
    # Create default admin if not exists
    if not User.query.filter_by(role='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    # Create default sales if not exists
    if not User.query.filter_by(role='sales').first():
        sales = User(username='sales', role='sales')
        sales.set_password('sales123')
        db.session.add(sales)
        db.session.commit()

# --- Auth Decorators ---
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_stock_movement(product_id, change, reason, ref_id=None):
    movement = StockMovement(
        product_id=product_id,
        quantity_change=change,
        reason=reason,
        reference_id=str(ref_id) if ref_id else None
    )
    db.session.add(movement)

# --- Routes ---

@app.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template('dashboard.html', user_role=session.get('role'))

@app.route('/login-page')
def login_page():
    return render_template('login.html')

@app.route('/pos-page')
@login_required
def pos_page():
    return render_template('pos.html', user_role=session.get('role'))

@app.route('/products-page')
@login_required
def products_page():
    return render_template('products.html', user_role=session.get('role'))

@app.route('/sales-page')
@login_required
def sales_page():
    return render_template('sales.html', user_role=session.get('role'))

@app.route('/customers-page')
@login_required
def customers_page():
    return render_template('customers.html', user_role=session.get('role'))

@app.route('/suppliers-page')
@login_required
def suppliers_page():
    return render_template('suppliers.html', user_role=session.get('role'))

@app.route('/refunds-page')
@login_required
def refunds_page():
    return render_template('refunds.html', user_role=session.get('role'))

@app.route('/purchase-orders-page')
@login_required
def purchase_orders_page():
    return render_template('purchase_orders.html', user_role=session.get('role'))

# --- API Routes ---

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.check_password(data.get('password')):
        session['user_id'] = user.id
        session['role'] = user.role
        return jsonify({'message': 'Login successful', 'role': user.role})
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out'})

@app.route('/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'role': session['role']})
    return jsonify({'authenticated': False}), 401

@app.route('/dashboard/stats')
@login_required
def get_dashboard_stats():
    # Basic Stats
    total_sales = db.session.query(func.sum(Sale.total_amount)).scalar() or 0
    total_orders = Sale.query.count()
    low_stock_count = Product.query.filter(Product.quantity_in_stock <= Product.min_stock_level).count()
    
    # Financials (Admin Only)
    if session.get('role') == 'admin':
        stock_value = db.session.query(func.sum(Product.quantity_in_stock * Product.cost_price)).scalar() or 0
        total_expenses = db.session.query(func.sum(SupplierPayment.amount_paid)).scalar() or 0
        
        # Debt Summary
        # AR: Outstanding Customer Debt
        accounts_receivable = db.session.query(func.sum(Sale.balance_due)).scalar() or 0
        
        # AP: Outstanding Supplier Debt (Calculated from POs - Payments)
        # Note: This is an approximation. Ideally we track supplier balance explicitly.
        # Here we assume total Credit POs - total Payments = AP.
        total_credit_pos = db.session.query(func.sum(PurchaseOrder.total_amount)).filter_by(payment_type='Credit').scalar() or 0
        accounts_payable = max(0, total_credit_pos - total_expenses) 

        return jsonify({
            'total_sales': total_sales,
            'total_orders': total_orders,
            'low_stock_count': low_stock_count,
            'stock_value': stock_value,
            'total_expenses': total_expenses,
            'accounts_receivable': accounts_receivable,
            'accounts_payable': accounts_payable
        })
    else:
        # Sales view
        my_sales = Sale.query.filter_by(payment_status='PAID').count() # Simplified
        return jsonify({
            'total_orders': total_orders,
            'low_stock_count': low_stock_count,
            'my_sales_count': my_sales
        })

@app.route('/dashboard/low-stock')
@login_required
def get_low_stock():
    products = Product.query.filter(Product.quantity_in_stock <= Product.min_stock_level).all()
    return jsonify([{
        'id': p.id, 'name': p.name, 'stock': p.quantity_in_stock, 'min': p.min_stock_level
    } for p in products])

@app.route('/dashboard/movements')
@login_required
def get_stock_movements():
    # Return last 50 movements
    logs = StockMovement.query.order_by(StockMovement.timestamp.desc()).limit(50).all()
    return jsonify([{
        'timestamp': log.timestamp.isoformat(),
        'product': log.product.name,
        'change': log.quantity_change,
        'reason': log.reason,
        'ref': log.reference_id
    } for log in logs])

# --- Product Routes ---
@app.route('/products', methods=['GET', 'POST'])
@login_required
def manage_products():
    if request.method == 'POST':
        if session.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        data = request.json
        new_product = Product(
            name=data['name'],
            sku=data['sku'],
            cost_price=data['cost_price'],
            selling_price=data['selling_price'],
            quantity_in_stock=data['quantity_in_stock'],
            min_stock_level=data.get('min_stock_level', 10),
            image_url=data.get('image_url')
        )
        db.session.add(new_product)
        db.session.flush() # Ensure ID is generated
        
        # Initial Stock Log
        if new_product.quantity_in_stock > 0:
            log_stock_movement(new_product.id, new_product.quantity_in_stock, 'Initial Stock')
            
        db.session.commit()
        return jsonify({'message': 'Product added successfully', 'id': new_product.id}), 201
    
    products = Product.query.all()
    return jsonify([{
        'id': p.id, 
        'name': p.name, 
        'sku': p.sku, 
        'cost_price': p.cost_price, 
        'selling_price': p.selling_price, 
        'quantity_in_stock': p.quantity_in_stock,
        'damaged_quantity': p.damaged_quantity,
        'min_stock_level': p.min_stock_level,
        'image_url': p.image_url,
        'image_filename': p.image_filename
    } for p in products])

@app.route('/check-product/<sku>', methods=['GET'])
def check_product(sku):
    product = Product.query.filter_by(sku=sku).first()
    return jsonify({'exists': product is not None})

@app.route('/products/upload-image', methods=['POST'])
@login_required
def upload_product_image():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    product_id = request.form.get('product_id')
    
    if file and allowed_file(file.filename):
        filename = secure_filename(f"prod_{product_id}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        product = Product.query.get(product_id)
        if product:
            product.image_filename = filename
            product.image_url = None # Prefer local if exists
            db.session.commit()
            return jsonify({'message': 'Image uploaded', 'filename': filename})
    
    return jsonify({'error': 'Invalid file'}), 400

# --- Sales Routes (POS) ---
@app.route('/pos/lookup-customer', methods=['POST'])
@login_required
def pos_lookup_customer():
    data = request.json
    term = data.get('term') # Phone or Name
    if not term:
        return jsonify([])
        
    # Predictive search (Phone or Name)
    # Using simple Python filter if basic, or SQL ILIKE
    # Since we imported models, we can use filter
    # Note: for advanced logic use sqlalchemy or_
    from sqlalchemy import or_
    
    customers = Customer.query.filter(
        or_(
            Customer.phone.ilike(f"%{term}%"),
            Customer.full_name.ilike(f"%{term}%")
        )
    ).limit(5).all()
    
    return jsonify([{
        'id': c.id,
        'full_name': c.full_name,
        'phone': c.phone,
        'address': c.address,
        'total_debt': c.total_debt
    } for c in customers])

@app.route('/sales', methods=['GET', 'POST'])
@login_required
def manage_sales():
    if request.method == 'POST':
        data = request.json
        
        # New: Check for Walk-in auto-create? 
        # Actually logic is mostly frontend driven (lookup/create). 
        # Here we expect a valid customer_id.
        
        new_sale = Sale(
            customer_id=data['customer_id'],
            user_id=session.get('user_id'),
            total_amount=0,
            amount_paid=data['amount_paid'],
            balance_due=0,
            payment_status='UNPAID' 
        )
        db.session.add(new_sale)
        db.session.flush()

        total = 0
        for item in data['items']:
            product = Product.query.get(item['product_id'])
            if product.quantity_in_stock < item['quantity']:
                return jsonify({'error': f'Insufficient stock for {product.name}'}), 400
            
            # Stock Logic: Reduce
            product.quantity_in_stock -= item['quantity']
            log_stock_movement(product.id, -item['quantity'], 'Sale', ref_id=new_sale.id)

            subtotal = product.selling_price * item['quantity']
            total += subtotal
            
            sale_item = SaleItem(
                sale_id=new_sale.id,
                product_id=product.id,
                quantity=item['quantity'],
                price_at_sale=product.selling_price,
                cost_price_at_sale=product.cost_price,
                subtotal=subtotal
            )
            db.session.add(sale_item)
        
        new_sale.total_amount = total
        new_sale.balance_due = max(0, total - data['amount_paid'])
        
        if new_sale.balance_due == 0:
            new_sale.payment_status = 'PAID'
        elif new_sale.amount_paid > 0:
            new_sale.payment_status = 'PARTIAL'
        else:
            new_sale.payment_status = 'UNPAID'

        db.session.commit()
        return jsonify({'message': 'Sale completed', 'sale_id': new_sale.id}), 201
    
    # GET: List sales
    if session.get('role') == 'admin':
        sales = Sale.query.order_by(Sale.sale_date.desc()).all()
    else:
        sales = Sale.query.filter_by(user_id=session.get('user_id')).order_by(Sale.sale_date.desc()).all()
    return jsonify([{
        'id': s.id,
        'customer_name': s.customer.full_name,
        'total_amount': s.total_amount,
        'amount_paid': s.amount_paid,
        'balance_due': s.balance_due,
        'payment_status': s.payment_status,
        'sale_date': s.sale_date.isoformat()
    } for s in sales])

@app.route('/sales/<int:id>/payment', methods=['POST'])
@login_required
def add_sale_payment(id):
    sale = Sale.query.get_or_404(id)
    data = request.json
    amount = float(data['additional_payment'])
    
    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400
        
    sale.amount_paid += amount
    sale.balance_due = max(0, sale.total_amount - sale.amount_paid)
    
    if sale.balance_due == 0:
        sale.payment_status = 'PAID'
    else:
        sale.payment_status = 'PARTIAL'
        
    db.session.commit()
    return jsonify({'message': 'Payment added', 'new_balance': sale.balance_due})

# --- Refund Routes ---
@app.route('/refunds/request', methods=['POST'])
@login_required
def request_refund():
    data = request.json
    refund = Refund(
        sale_id=data['sale_id'],
        product_id=data['product_id'],
        quantity=data['quantity'],
        reason=data.get('reason'),
        status='Pending'
    )
    db.session.add(refund)
    db.session.commit()
    return jsonify({'message': 'Refund requested'}), 201

@app.route('/refunds', methods=['GET'])
@login_required
def list_refunds():
    refunds = Refund.query.order_by(Refund.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'sale_id': r.sale_id,
        'product_name': r.product.name,
        'quantity': r.quantity,
        'reason': r.reason,
        'status': r.status
    } for r in refunds])

@app.route('/refunds/<int:id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_refund(id):
    refund = Refund.query.get_or_404(id)
    if refund.status != 'Pending':
        return jsonify({'error': 'Refund already processed'}), 400
    
    refund.status = 'Approved'
    action = request.json.get('action') # 'restock' or 'damage'

    if action == 'restock':
        refund.product.quantity_in_stock += refund.quantity
        log_stock_movement(refund.product.id, refund.quantity, 'Refund Restock', ref_id=refund.id)
    else:
        refund.product.damaged_quantity += refund.quantity
        # Note: Damaged stock isn't "StockMovement" in the sellable sense, but we audit it?
        # Let's log it as 0 change to sellable, but note 'Refund Damage'
        log_stock_movement(refund.product.id, 0, 'Refund to Damaged', ref_id=refund.id)

    db.session.commit()
    return jsonify({'message': 'Refund approved'})

# --- Purchase Order Routes (Supply Chain) ---
@app.route('/purchase-orders', methods=['GET', 'POST'])
@login_required
def manage_pos():
    if request.method == 'POST':
        if session.get('role') != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        data = request.json
        
        po = PurchaseOrder(
            supplier_id=data['supplier_id'],
            payment_type=data['payment_type'],
            status='Pending'
        )
        db.session.add(po)
        db.session.flush()
        
        total = 0
        for item in data['items']:
            cost = float(item['unit_cost'])
            qty = int(item['quantity'])
            total += (cost * qty)
            po_item = PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=item['product_id'],
                quantity=qty,
                unit_cost=cost
            )
            db.session.add(po_item)
        
        po.total_amount = total
        db.session.commit()
        return jsonify({'message': 'PO Created', 'id': po.id}), 201

    pos = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).all()
    return jsonify([{
        'id': p.id,
        'supplier': p.supplier.name,
        'status': p.status,
        'total': p.total_amount,
        'date': p.created_at.isoformat(),
        'items_count': len(p.items)
    } for p in pos])

@app.route('/purchase-orders/<int:id>/receive', methods=['POST'])
@login_required
@admin_required
def receive_po(id):
    po = PurchaseOrder.query.get_or_404(id)
    if po.status != 'Pending':
        return jsonify({'error': 'PO already processed'}), 400
    
    po.status = 'Received'
    
    for item in po.items:
        item.product.quantity_in_stock += item.quantity
        # Update cost price? Optional, keeping simple (weighted average is complex)
        log_stock_movement(item.product.id, item.quantity, 'PO Received', ref_id=po.id)
    
    # Auto-create SupplierPayment if Cash?
    if po.payment_type == 'Cash':
        payment = SupplierPayment(
            supplier_id=po.supplier_id,
            amount_paid=po.total_amount,
            description=f'Auto-payment for PO #{po.id}'
        )
        db.session.add(payment)
        
    db.session.commit()
    return jsonify({'message': 'PO Received and Stock Updated'})

# --- Customer & Supplier Routes ---
@app.route('/customers', methods=['GET', 'POST'])
@login_required
def manage_customers():
    if request.method == 'POST':
        data = request.json
        new_customer = Customer(
            full_name=data['full_name'],
            phone=data['phone'],
            email=data.get('email'),
            address=data.get('address')
        )
        db.session.add(new_customer)
        db.session.commit()
        return jsonify({'message': 'Customer added', 'id': new_customer.id}), 201
    
    customers = Customer.query.all()
    return jsonify([{
        'id': c.id, 
        'full_name': c.full_name, 
        'phone': c.phone, 
        'email': c.email, 
        'created_at': c.created_at.isoformat()
    } for c in customers])

@app.route('/suppliers', methods=['GET', 'POST'])
@login_required
def manage_suppliers():
    if request.method == 'POST':
        data = request.json
        new_supplier = Supplier(name=data['name'], phone=data['phone'])
        db.session.add(new_supplier)
        db.session.commit()
        return jsonify({'message': 'Supplier added'}), 201
    
    suppliers = Supplier.query.all()
    return jsonify([{'id': s.id, 'name': s.name, 'phone': s.phone} for s in suppliers])

@app.route('/supplier-payments', methods=['GET', 'POST'])
@login_required
def manage_supplier_payments():
    if request.method == 'POST':
        data = request.json
        payment = SupplierPayment(
            supplier_id=data['supplier_id'],
            amount_paid=data['amount_paid'],
            description=data.get('description')
        )
        db.session.add(payment)
        db.session.commit()
        return jsonify({'message': 'Payment recorded'}), 201
        
    payments = SupplierPayment.query.order_by(SupplierPayment.payment_date.desc()).all()
    return jsonify([{
        'id': p.id,
        'supplier_name': p.supplier.name,
        'amount_paid': p.amount_paid,
        'description': p.description,
        'payment_date': p.payment_date.isoformat()
    } for p in payments])
    
@app.route('/reports/debtors')
@login_required
def report_debtors():
    # Find customers with debts
    # Optimized: Filter in Python for simplicity or write complex Join
    debtors = []
    customers = Customer.query.all()
    for c in customers:
        debt = c.total_debt
        if debt > 0:
            debtors.append({
                'full_name': c.full_name,
                'phone': c.phone,
                'email': c.email,
                'total_debt': debt
            })
    return jsonify(debtors)

# --- Phase 2: Advanced Inventory & Reports ---
@app.route('/dashboard/stock-intelligence')
@login_required
def stock_intelligence():
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    sales_last_30 = db.session.query(
        SaleItem.product_id, 
        func.sum(SaleItem.quantity).label('qty_sold')
    ).join(Sale).filter(
        Sale.sale_date >= thirty_days_ago, 
        SaleItem.status == 'Active'
    ).group_by(SaleItem.product_id).all()
    
    sales_dict = {row.product_id: row.qty_sold for row in sales_last_30}
    intelligence = []
    
    for p in Product.query.filter(Product.quantity_in_stock <= Product.min_stock_level).all():
        qty_sold_30 = sales_dict.get(p.id, 0)
        daily_rate = qty_sold_30 / 30.0
        days_remaining = (p.quantity_in_stock / daily_rate) if daily_rate > 0 else 999 
        intelligence.append({
            'id': p.id,
            'name': p.name,
            'current_stock': p.quantity_in_stock,
            'days_remaining': round(days_remaining) if days_remaining != 999 else '99+',
            'prediction_text': 'Sufficient' if days_remaining > 14 and days_remaining != 999 else f"{round(days_remaining)} Days left"
        })
    return jsonify(intelligence)

@app.route('/products/bulk', methods=['POST'])
@login_required
def bulk_products():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    data = request.json
    action = data.get('action')
    product_ids = data.get('product_ids', [])
    
    if action == 'delete':
        Product.query.filter(Product.id.in_(product_ids)).delete(synchronize_session=False)
    elif action == 'update_price':
        new_price = float(data.get('new_selling_price'))
        Product.query.filter(Product.id.in_(product_ids)).update({Product.selling_price: new_price}, synchronize_session=False)
        
    db.session.commit()
    return jsonify({'message': 'Bulk action completed'})

@app.route('/sales/<int:sale_id>/items/<int:item_id>/return', methods=['POST'])
@login_required
def return_sale_item(sale_id, item_id):
    item = SaleItem.query.get_or_404(item_id)
    if item.sale_id != sale_id: return jsonify({'error': 'Invalid item'}), 400
    if item.status == 'Returned': return jsonify({'error': 'Item already returned'}), 400
        
    item.status = 'Returned'
    item.product.quantity_in_stock += item.quantity
    log_stock_movement(item.product.id, item.quantity, 'Return Sale Item', ref_id=sale_id)
    db.session.commit()
    return jsonify({'message': 'Item marked as returned and stock updated'})

@app.route('/sales/<int:id>/invoice', methods=['GET'])
@login_required
def generate_invoice(id):
    sale = Sale.query.get_or_404(id)
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, f"Receipt / Invoice #{sale.id}")
    p.setFont("Helvetica", 12)
    p.drawString(100, 720, f"Customer: {sale.customer.full_name}")
    p.drawString(100, 700, f"Date: {sale.sale_date.strftime('%Y-%m-%d %H:%M')}")
    
    y = 650
    p.drawString(100, y, "Item")
    p.drawString(350, y, "Qty")
    p.drawString(450, y, "Price")
    y -= 20
    
    for item in sale.items:
        p.drawString(100, y, item.product.name + (' (Returned)' if item.status == 'Returned' else ''))
        p.drawString(350, y, str(item.quantity))
        p.drawString(450, y, f"${item.price_at_sale:.2f}")
        y -= 25
        
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y-20, "Total:")
    p.drawString(450, y-20, f"${sale.total_amount:.2f}")
    p.drawString(350, y-40, "Paid:")
    p.drawString(450, y-40, f"${sale.amount_paid:.2f}")
    p.drawString(350, y-60, "Balance:")
    p.drawString(450, y-60, f"${sale.balance_due:.2f}")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=receipt_{sale.id}.pdf'
    return response

@app.route('/reports/profit', methods=['GET'])
@login_required
def report_profit():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    items = SaleItem.query.filter_by(status='Active').all()
    
    total_rev = sum(i.subtotal for i in items)
    gross_profit = sum(i.subtotal - (i.cost_price_at_sale * i.quantity) for i in items)
    
    return jsonify({
        'total_revenue': total_rev,
        'gross_profit': gross_profit,
        'margin_percentage': round((gross_profit / total_rev) * 100, 2) if total_rev > 0 else 0
    })

@app.route('/reports/monthly-trends', methods=['GET'])
@login_required
def monthly_trends():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    sales = db.session.query(
        func.date_trunc('month', Sale.sale_date).label('month'),
        func.sum(Sale.total_amount).label('total')
    ).filter(Sale.sale_date >= six_months_ago).group_by('month').order_by('month').all()
    
    return jsonify([{
        'month': row.month.strftime('%Y-%m'), 
        'total_revenue': float(row.total)
    } for row in sales])

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
