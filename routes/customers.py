from flask import Blueprint, render_template, request, jsonify, session
from models import db, Customer, Sale
from decorators import login_required

customers_bp = Blueprint('customers', __name__)


@customers_bp.route('/customers-page')
@login_required
def customers_page():
    return render_template('customers.html', user_role=session.get('role'))


@customers_bp.route('/customers', methods=['GET'])
@login_required
def list_customers():
    search = request.args.get('search', '').strip()
    query = Customer.query

    if search:
        query = query.filter(
            Customer.full_name.ilike(f'%{search}%') |
            Customer.phone.ilike(f'%{search}%') |
            Customer.email.ilike(f'%{search}%')
        )

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    paginated = query.order_by(Customer.full_name).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'data': [{
            'id': c.id,
            'full_name': c.full_name,
            'phone': c.phone,
            'email': c.email,
            'address': c.address,
            'created_at': c.created_at.isoformat(),
        } for c in paginated.items],
        'pagination': {
            'page': paginated.page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages,
        }
    })


@customers_bp.route('/customers', methods=['POST'])
@login_required
def create_customer():
    data = request.json or {}

    required = ['full_name', 'phone']
    missing = [f for f in required if not (data.get(f) or '').strip()]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

    phone = data['phone'].strip()
    if Customer.query.filter_by(phone=phone).first():
        return jsonify({'error': 'A customer with this phone number already exists'}), 409

    try:
        customer = Customer(
            full_name=data['full_name'].strip(),
            phone=phone,
            email=(data.get('email') or '').strip() or None,
            address=(data.get('address') or '').strip() or None,
        )
        db.session.add(customer)
        db.session.commit()
        return jsonify({'message': 'Customer added', 'id': customer.id}), 201
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to create customer'}), 500


@customers_bp.route('/customers/<int:customer_id>', methods=['PUT'])
@login_required
def update_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    data = request.json or {}

    try:
        if 'full_name' in data:
            customer.full_name = data['full_name'].strip()
        if 'phone' in data:
            phone = data['phone'].strip()
            existing = Customer.query.filter_by(phone=phone).first()
            if existing and existing.id != customer_id:
                return jsonify({'error': 'Phone number already in use'}), 409
            customer.phone = phone
        if 'email' in data:
            customer.email = data['email'].strip() or None
        if 'address' in data:
            customer.address = data['address'].strip() or None

        db.session.commit()
        return jsonify({'message': 'Customer updated'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to update customer'}), 500


@customers_bp.route('/customers/<int:customer_id>/outstanding-sales', methods=['GET'])
@login_required
def customer_outstanding_sales(customer_id):
    """Return all unpaid / partially-paid sales for a customer, used by the Pay Balance modal."""
    customer = Customer.query.get_or_404(customer_id)
    sales = (
        Sale.query
        .filter(Sale.customer_id == customer_id, Sale.balance_due > 0)
        .order_by(Sale.sale_date.desc())
        .all()
    )
    return jsonify({
        'customer': {'id': customer.id, 'full_name': customer.full_name, 'phone': customer.phone},
        'sales': [{
            'id': s.id,
            'sale_date': s.sale_date.strftime('%Y-%m-%d'),
            'total_amount': s.total_amount,
            'amount_paid': s.amount_paid,
            'balance_due': s.balance_due,
            'payment_status': s.payment_status,
            'items_summary': ', '.join(
                f"{i.product.name} x{i.quantity}" for i in s.items
            ),
        } for s in sales],
        'total_outstanding': sum(s.balance_due for s in sales),
    })
