"""
Branch-to-Branch Stock Transfers.
Routes:
  GET  /stock-transfers-page    — UI page
  GET  /api/transfers           — list transfers
  POST /api/transfers           — create transfer request
  POST /api/transfers/<id>/complete  — complete (moves stock)
  POST /api/transfers/<id>/cancel    — cancel
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, session, g
from models import db, StockTransfer, Product, Branch, ActivityLog
from decorators import login_required, admin_required

transfers_bp = Blueprint('transfers', __name__)


@transfers_bp.route('/api/branches', methods=['GET'])
@login_required
def list_branches():
    branches = Branch.query.filter_by(organisation_id=g.org_id).order_by(Branch.name).all()
    return jsonify([{'id': b.id, 'name': b.name} for b in branches])


@transfers_bp.route('/stock-transfers-page')
@login_required
def transfers_page():
    return render_template('stock_transfers.html')


@transfers_bp.route('/api/transfers', methods=['GET'])
@login_required
def list_transfers():
    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    status   = request.args.get('status', '').strip()

    q = StockTransfer.query.filter_by(organisation_id=g.org_id)
    if status:
        q = q.filter_by(status=status)

    pag = q.order_by(StockTransfer.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return jsonify({
        'data': [_t(t) for t in pag.items],
        'pagination': {'page': pag.page, 'pages': pag.pages, 'total': pag.total},
    })


@transfers_bp.route('/api/transfers', methods=['POST'])
@login_required
@admin_required
def create_transfer():
    data = request.json or {}

    from_branch_id = data.get('from_branch_id')
    to_branch_id   = data.get('to_branch_id')
    product_id     = data.get('product_id')
    quantity       = int(data.get('quantity', 0))

    if not all([from_branch_id, to_branch_id, product_id, quantity > 0]):
        return jsonify({'error': 'from_branch_id, to_branch_id, product_id, and quantity > 0 are required'}), 400

    if from_branch_id == to_branch_id:
        return jsonify({'error': 'Source and destination branches must be different'}), 400

    # Validate branches belong to this org
    from_branch = Branch.query.filter_by(id=from_branch_id, organisation_id=g.org_id).first()
    to_branch   = Branch.query.filter_by(id=to_branch_id,   organisation_id=g.org_id).first()
    product     = Product.query.filter_by(id=product_id,    organisation_id=g.org_id).first()

    if not from_branch or not to_branch:
        return jsonify({'error': 'Invalid branch'}), 404
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    if product.quantity_in_stock < quantity:
        return jsonify({'error': f'Insufficient stock. Available: {product.quantity_in_stock}'}), 400

    transfer = StockTransfer(
        organisation_id=g.org_id,
        from_branch_id=from_branch_id,
        to_branch_id=to_branch_id,
        product_id=product_id,
        quantity=quantity,
        notes=(data.get('notes') or '').strip() or None,
        created_by=session.get('user_id'),
        status='pending',
    )
    db.session.add(transfer)
    db.session.commit()

    ActivityLog.log('TRANSFER_CREATED', entity='stock_transfer', entity_id=transfer.id,
                    summary=f'{quantity}x {product.name}: {from_branch.name} → {to_branch.name}')
    db.session.commit()

    return jsonify(_t(transfer)), 201


@transfers_bp.route('/api/transfers/<int:tid>/complete', methods=['POST'])
@login_required
@admin_required
def complete_transfer(tid):
    transfer = StockTransfer.query.filter_by(id=tid, organisation_id=g.org_id).first_or_404()

    if transfer.status != 'pending':
        return jsonify({'error': f'Transfer is already {transfer.status}'}), 400

    product = Product.query.get(transfer.product_id)
    if product.quantity_in_stock < transfer.quantity:
        return jsonify({'error': f'Insufficient stock. Available: {product.quantity_in_stock}'}), 400

    # Deduct from source (global stock — branch-level stock tracking is future scope)
    product.quantity_in_stock -= transfer.quantity
    transfer.status       = 'completed'
    transfer.completed_at = datetime.utcnow()
    db.session.commit()

    ActivityLog.log('TRANSFER_COMPLETED', entity='stock_transfer', entity_id=transfer.id,
                    summary=f'{transfer.quantity}x {product.name} transfer completed')
    db.session.commit()

    return jsonify({'message': 'Transfer completed', 'transfer': _t(transfer)})


@transfers_bp.route('/api/transfers/<int:tid>/cancel', methods=['POST'])
@login_required
@admin_required
def cancel_transfer(tid):
    transfer = StockTransfer.query.filter_by(id=tid, organisation_id=g.org_id).first_or_404()

    if transfer.status != 'pending':
        return jsonify({'error': f'Cannot cancel a {transfer.status} transfer'}), 400

    transfer.status = 'cancelled'
    db.session.commit()
    return jsonify({'message': 'Transfer cancelled'})


def _t(t):
    return {
        'id':             t.id,
        'from_branch':    t.from_branch.name  if t.from_branch  else '',
        'to_branch':      t.to_branch.name    if t.to_branch    else '',
        'from_branch_id': t.from_branch_id,
        'to_branch_id':   t.to_branch_id,
        'product':        t.product.name      if t.product      else '',
        'product_id':     t.product_id,
        'quantity':       t.quantity,
        'status':         t.status,
        'notes':          t.notes,
        'created_by':     t.created_by_user.username if t.created_by_user else '',
        'completed_at':   t.completed_at.isoformat() if t.completed_at else None,
        'created_at':     t.created_at.isoformat()   if t.created_at   else None,
    }
