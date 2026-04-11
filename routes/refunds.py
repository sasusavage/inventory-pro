from flask import Blueprint, render_template, request, jsonify, session
from models import db, Refund
from decorators import login_required, admin_required
from utils import log_stock_movement

refunds_bp = Blueprint('refunds', __name__)


@refunds_bp.route('/refunds-page')
@login_required
def refunds_page():
    return render_template('refunds.html', user_role=session.get('role'))


@refunds_bp.route('/refunds', methods=['GET'])
@login_required
def list_refunds():
    refunds = Refund.query.order_by(Refund.created_at.desc()).all()
    return jsonify([{
        'id': r.id,
        'sale_id': r.sale_id,
        'product_name': r.product.name,
        'quantity': r.quantity,
        'reason': r.reason,
        'status': r.status,
        'created_at': r.created_at.isoformat(),
    } for r in refunds])


@refunds_bp.route('/refunds/request', methods=['POST'])
@login_required
def request_refund():
    data = request.json or {}

    required = ['sale_id', 'product_id', 'quantity']
    missing = [f for f in required if data.get(f) is None]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

    try:
        qty = int(data['quantity'])
        if qty <= 0:
            return jsonify({'error': 'Quantity must be positive'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid quantity'}), 400

    try:
        refund = Refund(
            sale_id=data['sale_id'],
            product_id=data['product_id'],
            quantity=qty,
            reason=(data.get('reason') or '').strip() or None,
            status='Pending',
        )
        db.session.add(refund)
        db.session.commit()
        return jsonify({'message': 'Refund requested', 'id': refund.id}), 201
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to submit refund request'}), 500


@refunds_bp.route('/refunds/<int:refund_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_refund(refund_id):
    refund = Refund.query.get_or_404(refund_id)

    if refund.status != 'Pending':
        return jsonify({'error': 'Refund already processed'}), 400

    action = (request.json or {}).get('action', 'restock')

    try:
        refund.status = 'Approved'
        if action == 'restock':
            refund.product.quantity_in_stock += refund.quantity
            log_stock_movement(refund.product.id, refund.quantity, 'Refund Restock', ref_id=refund.id)
        else:
            refund.product.damaged_quantity += refund.quantity
            log_stock_movement(refund.product.id, 0, 'Refund to Damaged', ref_id=refund.id)

        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({'message': 'Refund approved'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to approve refund'}), 500


@refunds_bp.route('/refunds/<int:refund_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_refund(refund_id):
    refund = Refund.query.get_or_404(refund_id)

    if refund.status != 'Pending':
        return jsonify({'error': 'Refund already processed'}), 400

    try:
        refund.status = 'Rejected'
        db.session.commit()
        return jsonify({'message': 'Refund rejected'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to reject refund'}), 500
