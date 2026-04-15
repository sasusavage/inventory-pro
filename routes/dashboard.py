import time
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, session, redirect, url_for, g
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import db, Product, Sale, SaleItem, SupplierPayment, PurchaseOrder, StockMovement
from decorators import login_required

dashboard_bp = Blueprint('dashboard', __name__)

# Simple in-memory cache for admin stats (5-minute TTL)
_stats_cache = {}


@dashboard_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login_page'))
    return render_template('dashboard.html', user_role=session.get('role'))


@dashboard_bp.route('/dashboard/stats')
@login_required
def get_dashboard_stats():
    role = session.get('role')
    org_id = g.org_id
    cache_key = f'stats_{role}_{org_id}'
    now = time.time()

    if cache_key in _stats_cache and _stats_cache[cache_key]['expires'] > now:
        return jsonify(_stats_cache[cache_key]['data'])

    total_sales = db.session.query(func.sum(Sale.total_amount)).filter_by(organisation_id=org_id).scalar() or 0
    total_orders = Sale.query.filter_by(organisation_id=org_id).count()
    low_stock_count = Product.query.filter(
        Product.quantity_in_stock <= Product.min_stock_level,
        Product.organisation_id == org_id,
    ).count()

    if role == 'admin':
        stock_value = db.session.query(
            func.sum(Product.quantity_in_stock * Product.cost_price)
        ).filter(Product.organisation_id == org_id).scalar() or 0
        total_expenses = db.session.query(
            func.sum(SupplierPayment.amount_paid)
        ).filter_by(organisation_id=org_id).scalar() or 0
        accounts_receivable = db.session.query(
            func.sum(Sale.balance_due)
        ).filter_by(organisation_id=org_id).scalar() or 0
        total_credit_pos = db.session.query(
            func.sum(PurchaseOrder.total_amount)
        ).filter_by(payment_type='Credit', organisation_id=org_id).scalar() or 0
        accounts_payable = max(0, total_credit_pos - total_expenses)

        data = {
            'total_sales': float(total_sales),
            'total_orders': total_orders,
            'low_stock_count': low_stock_count,
            'stock_value': float(stock_value),
            'total_expenses': float(total_expenses),
            'accounts_receivable': float(accounts_receivable),
            'accounts_payable': float(accounts_payable),
        }
    else:
        my_sales = Sale.query.filter_by(payment_status='PAID', organisation_id=org_id).count()
        data = {
            'total_orders': total_orders,
            'low_stock_count': low_stock_count,
            'my_sales_count': my_sales,
        }

    _stats_cache[cache_key] = {'data': data, 'expires': now + 300}
    return jsonify(data)


def invalidate_stats_cache():
    _stats_cache.clear()


@dashboard_bp.route('/dashboard/low-stock')
@login_required
def get_low_stock():
    products = Product.query.filter(
        Product.quantity_in_stock <= Product.min_stock_level,
        Product.organisation_id == g.org_id,
    ).all()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'stock': p.quantity_in_stock,
        'min': p.min_stock_level,
    } for p in products])


@dashboard_bp.route('/dashboard/movements')
@login_required
def get_stock_movements():
    logs = (
        StockMovement.query
        .filter_by(organisation_id=g.org_id)
        .options(joinedload(StockMovement.product))
        .order_by(StockMovement.timestamp.desc())
        .limit(50)
        .all()
    )
    return jsonify([{
        'timestamp': log.timestamp.isoformat(),
        'product': log.product.name,
        'change': log.quantity_change,
        'reason': log.reason,
        'ref': log.reference_id,
    } for log in logs])


@dashboard_bp.route('/dashboard/stock-intelligence')
@login_required
def stock_intelligence():
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    sales_last_30 = db.session.query(
        SaleItem.product_id,
        func.sum(SaleItem.quantity).label('qty_sold')
    ).join(Sale).filter(
        Sale.sale_date >= thirty_days_ago,
        Sale.organisation_id == g.org_id,
        SaleItem.status == 'Active'
    ).group_by(SaleItem.product_id).all()

    sales_dict = {row.product_id: row.qty_sold for row in sales_last_30}
    intelligence = []

    for p in Product.query.filter(
        Product.quantity_in_stock <= Product.min_stock_level,
        Product.organisation_id == g.org_id,
    ).all():
        qty_sold_30 = sales_dict.get(p.id, 0)
        daily_rate = qty_sold_30 / 30.0
        days_remaining = (p.quantity_in_stock / daily_rate) if daily_rate > 0 else 999
        intelligence.append({
            'id': p.id,
            'name': p.name,
            'current_stock': p.quantity_in_stock,
            'min_stock': p.min_stock_level,
            'days_remaining': round(days_remaining) if days_remaining != 999 else '99+',
            'prediction_text': (
                'Sufficient' if days_remaining > 14 and days_remaining != 999
                else f"{round(days_remaining)} Days left"
            ),
        })
    return jsonify(intelligence)
