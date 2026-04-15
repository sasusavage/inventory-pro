from flask import Blueprint, render_template, request, jsonify, session, g
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
    paginated = PurchaseOrder.query.filter_by(organisation_id=g.org_id).order_by(PurchaseOrder.created_at.desc()).paginate(
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
            'items': [{
                'id': it.id,
                'product_id': it.product_id,
                'product_name': it.product.name,
                'quantity': it.quantity,
                'quantity_received': it.quantity_received or 0,
                'quantity_pending': it.quantity_pending,
                'unit_cost': it.unit_cost,
            } for it in po.items],
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
            organisation_id=g.org_id,
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
    """Receive a PO — either fully (no body) or partially with per-item receipts:
    { "receipts": [{ "item_id": 1, "quantity": 5 }, ...] }
    """
    from models import ActivityLog
    po = PurchaseOrder.query.filter_by(id=po_id, organisation_id=g.org_id).first_or_404()

    if po.status not in ('Pending', 'Partial'):
        return jsonify({'error': f'PO is {po.status} — cannot receive'}), 400

    data = request.json or {}
    receipts = data.get('receipts')  # optional: [{ item_id, quantity }]

    try:
        received_summary = []

        if receipts:
            # Partial receive — apply the provided quantities
            receipt_map = {int(r['item_id']): int(r['quantity']) for r in receipts if int(r.get('quantity', 0)) > 0}
            for item in po.items:
                qty_now = receipt_map.get(item.id, 0)
                if qty_now <= 0:
                    continue
                if qty_now > item.quantity_pending:
                    raise ValueError(f'Cannot receive {qty_now} of {item.product.name} — only {item.quantity_pending} pending')
                item.quantity_received = (item.quantity_received or 0) + qty_now
                item.product.quantity_in_stock += qty_now
                log_stock_movement(item.product.id, qty_now, 'PO Received', ref_id=po.id)
                received_summary.append(f"{item.product.name} +{qty_now}")
        else:
            # Full receive — top every pending item up to its ordered qty
            for item in po.items:
                pending = item.quantity_pending
                if pending <= 0:
                    continue
                item.quantity_received = item.quantity
                item.product.quantity_in_stock += pending
                log_stock_movement(item.product.id, pending, 'PO Received', ref_id=po.id)
                received_summary.append(f"{item.product.name} +{pending}")

        # Determine new status
        all_done = all((it.quantity_received or 0) >= it.quantity for it in po.items)
        any_done = any((it.quantity_received or 0) > 0 for it in po.items)

        if all_done:
            po.status = 'Received'
            # Create cash payment on full receipt (same behaviour as before)
            if po.payment_type == 'Cash':
                payment = SupplierPayment(
                    supplier_id=po.supplier_id,
                    amount_paid=po.total_amount,
                    description=f'Auto-payment for PO #{po.id}',
                )
                db.session.add(payment)
        elif any_done:
            po.status = 'Partial'

        ActivityLog.log(
            'PO_RECEIVED', 'purchase_order', po.id,
            f'PO #{po.id}: {", ".join(received_summary) or "no items"}'
        )

        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()

        # Telegram notification
        try:
            from notifications import notify_async
            notify_async(
                f"📦 <b>Purchase Order {'Fully' if all_done else 'Partially'} Received</b>\n\n"
                f"🏷️ <b>PO #{po.id}</b> from {po.supplier.name}\n"
                f"📋 <b>Items:</b> {', '.join(received_summary) or '—'}\n"
                f"📊 <b>Status:</b> {po.status}"
            )
        except Exception:
            pass

        return jsonify({
            'message': f'PO {"fully" if all_done else "partially"} received',
            'status': po.status,
            'received': received_summary,
        })
    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to receive PO'}), 500


@purchase_orders_bp.route('/purchase-orders/<int:po_id>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_po(po_id):
    po = PurchaseOrder.query.filter_by(id=po_id, organisation_id=g.org_id).first_or_404()

    if po.status != 'Pending':
        return jsonify({'error': 'Only pending POs can be cancelled'}), 400

    try:
        po.status = 'Cancelled'
        db.session.commit()
        return jsonify({'message': 'PO cancelled'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to cancel PO'}), 500


@purchase_orders_bp.route('/reorder/suggestions', methods=['GET'])
@login_required
def reorder_suggestions():
    """List products at or below min_stock_level with a suggested reorder qty."""
    from models import Product
    products = Product.query.filter(
        Product.quantity_in_stock <= Product.min_stock_level,
        Product.organisation_id == g.org_id,
    ).order_by(Product.name).all()

    results = []
    for p in products:
        min_lvl = p.min_stock_level or 10
        # Reorder to 2x min stock level (standard buffer), minimum 1 unit
        target = max(min_lvl * 2, min_lvl + 1)
        suggested = max(1, target - p.quantity_in_stock)
        results.append({
            'product_id': p.id,
            'name': p.name,
            'sku': p.sku,
            'current_stock': p.quantity_in_stock,
            'min_stock_level': min_lvl,
            'suggested_quantity': suggested,
            'unit_cost': p.cost_price,
        })
    return jsonify({'products': results, 'count': len(results)})


@purchase_orders_bp.route('/reorder/auto-draft', methods=['POST'])
@login_required
@admin_required
def auto_draft_po():
    """Create a draft PO from low-stock products.
    Body: { supplier_id: int, product_ids: [int]?  (optional — defaults to all low) }
    """
    from models import Product, ActivityLog
    data = request.json or {}
    supplier_id = data.get('supplier_id')
    if not supplier_id:
        return jsonify({'error': 'supplier_id is required'}), 400

    product_ids = data.get('product_ids') or []
    query = Product.query.filter(
        Product.quantity_in_stock <= Product.min_stock_level,
        Product.organisation_id == g.org_id,
    )
    if product_ids:
        query = query.filter(Product.id.in_(product_ids))
    products = query.all()

    if not products:
        return jsonify({'error': 'No low-stock products to reorder'}), 400

    try:
        po = PurchaseOrder(
            supplier_id=supplier_id,
            payment_type=data.get('payment_type', 'Credit'),
            status='Pending',
            organisation_id=g.org_id,
        )
        db.session.add(po)
        db.session.flush()

        total = 0.0
        for p in products:
            min_lvl = p.min_stock_level or 10
            target = max(min_lvl * 2, min_lvl + 1)
            qty = max(1, target - p.quantity_in_stock)
            cost = float(p.cost_price or 0)
            total += cost * qty
            db.session.add(PurchaseOrderItem(
                purchase_order_id=po.id,
                product_id=p.id,
                quantity=qty,
                unit_cost=cost,
            ))

        po.total_amount = total
        ActivityLog.log('AUTO_DRAFT_PO', 'purchase_order', po.id,
                        f'Auto-drafted from {len(products)} low-stock items, total {total:.2f}')
        db.session.commit()
        return jsonify({
            'message': f'Draft PO created with {len(products)} item(s)',
            'id': po.id,
            'total': total,
        }), 201
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to create draft PO'}), 500
