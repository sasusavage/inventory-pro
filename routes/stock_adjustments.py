from flask import Blueprint, render_template, request, jsonify, session
from models import db, StockAdjustment, Product
from decorators import login_required, admin_required

stock_adj_bp = Blueprint('stock_adjustments', __name__)

ADJUSTMENT_REASONS = ['Damage', 'Theft', 'Correction', 'Recount', 'Expired', 'Returned to Supplier', 'Other']


@stock_adj_bp.route('/stock-adjustments-page')
@admin_required
def stock_adjustments_page():
    return render_template('stock_adjustments.html', reasons=ADJUSTMENT_REASONS)


@stock_adj_bp.route('/api/stock-adjustments', methods=['GET'])
@admin_required
def list_adjustments():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    pag = StockAdjustment.query.order_by(StockAdjustment.adjusted_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        'data': [{
            'id': a.id,
            'product_id': a.product_id,
            'product_name': a.product.name,
            'quantity_before': a.quantity_before,
            'quantity_after': a.quantity_after,
            'change': a.quantity_after - a.quantity_before,
            'reason': a.reason,
            'note': a.note,
            'adjusted_at': a.adjusted_at.strftime('%Y-%m-%d %H:%M'),
            'adjusted_by': a.user.username if a.user else 'System',
        } for a in pag.items],
        'pagination': {'page': pag.page, 'pages': pag.pages, 'total': pag.total},
    })


@stock_adj_bp.route('/api/stock-adjustments', methods=['POST'])
@admin_required
def create_adjustment():
    data = request.json or {}
    required = ['product_id', 'new_quantity', 'reason']
    if missing := [f for f in required if f not in data]:
        return jsonify({'error': f'Missing: {", ".join(missing)}'}), 400

    product = Product.query.get_or_404(data['product_id'])
    qty_before = product.quantity_in_stock
    qty_after = int(data['new_quantity'])

    if qty_after < 0:
        return jsonify({'error': 'Quantity cannot be negative'}), 400

    adj = StockAdjustment(
        product_id=product.id,
        user_id=session.get('user_id'),
        quantity_before=qty_before,
        quantity_after=qty_after,
        reason=data['reason'],
        note=data.get('note', '').strip() or None,
    )
    product.quantity_in_stock = qty_after
    db.session.add(adj)

    # Also log to StockMovement for AI context
    from utils import log_stock_movement
    change = qty_after - qty_before
    if change != 0:
        log_stock_movement(
            product_id=product.id,
            quantity_change=change,
            reason=f'adjustment_{data["reason"].lower().replace(" ", "_")}',
            reference_id=str(adj.id)
        )

    db.session.commit()
    return jsonify({
        'message': f'Stock adjusted: {qty_before} → {qty_after}',
        'product_name': product.name,
        'change': change,
    }), 201
