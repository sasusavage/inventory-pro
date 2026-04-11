from flask import Blueprint, render_template, request, jsonify, session
from models import db, Supplier, SupplierPayment
from decorators import login_required

suppliers_bp = Blueprint('suppliers', __name__)


@suppliers_bp.route('/suppliers-page')
@login_required
def suppliers_page():
    return render_template('suppliers.html', user_role=session.get('role'))


@suppliers_bp.route('/suppliers', methods=['GET'])
@login_required
def list_suppliers():
    search = request.args.get('search', '').strip()
    query = Supplier.query

    if search:
        query = query.filter(
            Supplier.name.ilike(f'%{search}%') |
            Supplier.phone.ilike(f'%{search}%')
        )

    suppliers = query.order_by(Supplier.name).all()
    return jsonify([{'id': s.id, 'name': s.name, 'phone': s.phone} for s in suppliers])


@suppliers_bp.route('/suppliers', methods=['POST'])
@login_required
def create_supplier():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json or {}
    if not (data.get('name') or '').strip():
        return jsonify({'error': 'Supplier name is required'}), 400
    if not (data.get('phone') or '').strip():
        return jsonify({'error': 'Supplier phone is required'}), 400

    try:
        supplier = Supplier(
            name=data['name'].strip(),
            phone=data['phone'].strip(),
        )
        db.session.add(supplier)
        db.session.commit()
        return jsonify({'message': 'Supplier added', 'id': supplier.id}), 201
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to create supplier'}), 500


@suppliers_bp.route('/supplier-payments', methods=['GET'])
@login_required
def list_supplier_payments():
    payments = SupplierPayment.query.order_by(SupplierPayment.payment_date.desc()).all()
    return jsonify([{
        'id': p.id,
        'supplier_name': p.supplier.name,
        'amount_paid': p.amount_paid,
        'description': p.description,
        'payment_date': p.payment_date.isoformat(),
    } for p in payments])


@suppliers_bp.route('/supplier-payments', methods=['POST'])
@login_required
def create_supplier_payment():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json or {}

    if not data.get('supplier_id'):
        return jsonify({'error': 'supplier_id is required'}), 400

    try:
        amount = float(data['amount_paid'])
        if amount <= 0:
            return jsonify({'error': 'Amount must be positive'}), 400
    except (KeyError, ValueError, TypeError):
        return jsonify({'error': 'Invalid amount'}), 400

    try:
        payment = SupplierPayment(
            supplier_id=data['supplier_id'],
            amount_paid=amount,
            description=(data.get('description') or '').strip() or None,
        )
        db.session.add(payment)
        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({'message': 'Payment recorded'}), 201
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to record payment'}), 500
