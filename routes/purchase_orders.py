from flask import Blueprint, render_template, request, jsonify, session
from models import db, PurchaseOrder, PurchaseOrderItem, SupplierPayment
from decorators import login_required, admin_required
from utils import log_stock_movement

purchase_orders_bp = Blueprint('purchase_orders', __name__)


@purchase_orders_bp.route('/purchase-orders-page')
@login_required
def purchase_orders_page():
    return render_template('purchase_orders.html', user_role=session.get('role'))


@purchase_orders_bp.route('/purchase-orders', methods=['GET'])
@login_required
def list_purchase_orders():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    paginated = PurchaseOrder.query.order_by(PurchaseOrder.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'data': [{
            'id': po.id,
            'supplier': po.supplier.name,
            'status': po.status,
            'total': po.total_amount,
            'payment_type': po.payment_type,
            'date': po.created_at.isoformat(),
            'items_count': len(po.items),
        } for po in paginated.items],
        'pagination': {
            'page': paginated.page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages,
        }
    })


@purchase_orders_bp.route('/purchase-orders', methods=['POST'])
@login_required
@admin_required
def create_purchase_order():
    data = request.json or {}

    if not data.get('supplier_id'):
        return jsonify({'error': 'supplier_id is required'}), 400
    if not data.get('items'):
        return jsonify({'error': 'At least one item is required'}), 400

    try:
        po = PurchaseOrder(
            supplier_id=data['supplier_id'],
            payment_type=data.get('payment_type', 'Credit'),
            status='Pending',
        )
        db.session.add(po)
        db.session.flush()

        total = 0
        for item in data['items']:
            cost = float(item['unit_cost'])
            qty = int(item['quantity'])
            if cost < 0 or qty <= 0:
                raise ValueError('Invalid cost or quantity in items')
            total += cost * qty
            po_item = PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=item['product_id'],
                quantity=qty,
                unit_cost=cost,
            )
            db.session.add(po_item)

        po.total_amount = total
        db.session.commit()
        return jsonify({'message': 'PO Created', 'id': po.id}), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to create purchase order'}), 500


@purchase_orders_bp.route('/purchase-orders/<int:po_id>/receive', methods=['POST'])
@login_required
@admin_required
def receive_po(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    if po.status != 'Pending':
        return jsonify({'error': 'PO already processed'}), 400

    try:
        po.status = 'Received'
        for item in po.items:
            item.product.quantity_in_stock += item.quantity
            log_stock_movement(item.product.id, item.quantity, 'PO Received', ref_id=po.id)

        if po.payment_type == 'Cash':
            payment = SupplierPayment(
                supplier_id=po.supplier_id,
                amount_paid=po.total_amount,
                description=f'Auto-payment for PO #{po.id}',
            )
            db.session.add(payment)

        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()

        # Telegram notification
        try:
            from notifications import notify_async
            items_summary = ', '.join(
                f"{item.product.name} +{item.quantity}" for item in po.items
            )
            notify_async(
                f"📦 <b>Purchase Order Received</b>\n\n"
                f"🏷️ <b>PO #{po.id}</b> from {po.supplier.name}\n"
                f"📋 <b>Items restocked:</b> {items_summary}\n"
                f"💰 <b>Total:</b> ${po.total_amount:.2f}"
            )
        except Exception:
            pass

        return jsonify({'message': 'PO Received and stock updated'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to receive PO'}), 500


@purchase_orders_bp.route('/purchase-orders/<int:po_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_po(po_id):
    po = PurchaseOrder.query.get_or_404(po_id)

    if po.status != 'Pending':
        return jsonify({'error': 'Only pending POs can be cancelled'}), 400

    try:
        po.status = 'Cancelled'
        db.session.commit()
        return jsonify({'message': 'PO cancelled'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to cancel PO'}), 500
