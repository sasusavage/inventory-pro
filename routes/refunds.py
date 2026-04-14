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
    from models import Sale
    refunds = (
        Refund.query
        .order_by(Refund.created_at.desc())
        .all()
    )
    result = []
    for r in refunds:
        sale = Sale.query.get(r.sale_id)
        result.append({
            'id': r.id,
            'sale_id': r.sale_id,
            'product_id': r.product_id,
            'product_name': r.product.name,
            'customer_name': sale.customer.full_name if sale and sale.customer else '—',
            'quantity': r.quantity,
            'unit_price': next((i.price_at_sale for i in (sale.items if sale else []) if i.product_id == r.product_id), 0),
            'reason': r.reason,
            'status': r.status,
            'created_at': r.created_at.isoformat(),
        })
    return jsonify(result)


@refunds_bp.route('/sales/<int:sale_id>/refundable-items', methods=['GET'])
@login_required
def refundable_items(sale_id):
    """Return items from a sale that can still be refunded (active, not already fully refunded)."""
    from models import Sale
    sale = Sale.query.get_or_404(sale_id)

    refunded_by_product = {}
    for r in Refund.query.filter_by(sale_id=sale_id).filter(Refund.status != 'Rejected').all():
        refunded_by_product[r.product_id] = refunded_by_product.get(r.product_id, 0) + r.quantity

    items = []
    for i in sale.items:
        if i.status == 'Returned':
            continue
        already = refunded_by_product.get(i.product_id, 0)
        remaining = max(0, i.quantity - already)
        if remaining <= 0:
            continue
        items.append({
            'product_id': i.product_id,
            'product_name': i.product.name,
            'sold_quantity': i.quantity,
            'refundable_quantity': remaining,
            'price_at_sale': i.price_at_sale,
        })
    return jsonify({
        'sale_id': sale_id,
        'customer_name': sale.customer.full_name,
        'sale_date': sale.sale_date.isoformat(),
        'items': items,
    })


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
    from models import Sale, SaleItem, ActivityLog
    refund = Refund.query.get_or_404(refund_id)

    if refund.status != 'Pending':
        return jsonify({'error': 'Refund already processed'}), 400

    action = (request.json or {}).get('action', 'restock')

    try:
        refund.status = 'Approved'

        # Restock or write off
        if action == 'restock':
            refund.product.quantity_in_stock += refund.quantity
            log_stock_movement(refund.product.id, refund.quantity, 'Refund Restock', ref_id=refund.id)
        else:
            refund.product.damaged_quantity += refund.quantity
            log_stock_movement(refund.product.id, 0, 'Refund to Damaged', ref_id=refund.id)

        # Reverse the sale side: reduce the SaleItem qty or mark it returned, and
        # adjust the sale's total/balance so the customer's debt reflects the refund.
        sale = Sale.query.get(refund.sale_id)
        refund_value = 0.0
        if sale:
            item = next((i for i in sale.items if i.product_id == refund.product_id and i.status == 'Active'), None)
            if item:
                unit_price = item.price_at_sale
                refund_value = unit_price * refund.quantity

                if refund.quantity >= item.quantity:
                    item.status = 'Returned'
                else:
                    item.quantity -= refund.quantity
                    item.subtotal = item.quantity * item.price_at_sale

                sale.total_amount = max(0, sale.total_amount - refund_value)

                # Reduce amount_paid if customer had paid — this becomes a cash-back owed
                # Simpler: recompute balance_due from the new total and existing amount_paid
                if sale.amount_paid > sale.total_amount:
                    # Customer is now owed change — treat the excess as refunded by setting paid = total
                    sale.amount_paid = sale.total_amount
                sale.balance_due = max(0, sale.total_amount - sale.amount_paid)

                if sale.total_amount == 0:
                    sale.payment_status = 'PAID'
                elif sale.balance_due == 0:
                    sale.payment_status = 'PAID'
                elif sale.amount_paid > 0:
                    sale.payment_status = 'PARTIAL'
                else:
                    sale.payment_status = 'UNPAID'

        ActivityLog.log(
            'REFUND_APPROVED', 'refund', refund.id,
            f'Refund #{refund.id} approved ({refund.quantity}× {refund.product.name}, {action})'
        )

        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({
            'message': 'Refund approved',
            'refund_value': round(refund_value, 2),
            'action': action,
        })
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
        from models import ActivityLog
        refund.status = 'Rejected'
        ActivityLog.log('REJECT_REFUND', entity='refund', entity_id=refund.id,
                        summary=f'Refund for sale #{refund.sale_id} rejected')
        db.session.commit()
        return jsonify({'message': 'Refund rejected'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to reject refund'}), 500
