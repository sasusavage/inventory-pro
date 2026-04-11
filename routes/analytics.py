"""
Analytics page routes — chart data endpoints consumed by the analytics dashboard.
"""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, jsonify, session
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import db, Sale, SaleItem, Product, Customer, StockMovement
from decorators import login_required, admin_required

analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/analytics-page')
@login_required
@admin_required
def analytics_page():
    return render_template('analytics.html')


@analytics_bp.route('/api/analytics/revenue-trend', methods=['GET'])
@login_required
@admin_required
def revenue_trend():
    """Daily revenue for the last 30 days."""
    since = datetime.utcnow() - timedelta(days=30)
    rows = db.session.query(
        func.date_trunc('day', Sale.sale_date).label('day'),
        func.sum(Sale.total_amount).label('revenue'),
        func.sum(Sale.amount_paid).label('collected'),
        func.count(Sale.id).label('orders'),
    ).filter(Sale.sale_date >= since).group_by('day').order_by('day').all()

    return jsonify([{
        'date':      row.day.strftime('%Y-%m-%d'),
        'revenue':   round(float(row.revenue), 2),
        'collected': round(float(row.collected), 2),
        'orders':    int(row.orders),
    } for row in rows])


@analytics_bp.route('/api/analytics/top-products', methods=['GET'])
@login_required
@admin_required
def top_products():
    """Top 10 products by revenue and units, last 30 days."""
    since = datetime.utcnow() - timedelta(days=30)
    rows = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label('units'),
        func.sum(SaleItem.subtotal).label('revenue'),
        func.sum(
            SaleItem.subtotal - SaleItem.cost_price_at_sale * SaleItem.quantity
        ).label('profit'),
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale,     Sale.id == SaleItem.sale_id)\
     .filter(Sale.sale_date >= since, SaleItem.status == 'Active')\
     .group_by(Product.id, Product.name)\
     .order_by(func.sum(SaleItem.subtotal).desc())\
     .limit(10).all()

    return jsonify([{
        'name':    r.name,
        'units':   int(r.units),
        'revenue': round(float(r.revenue), 2),
        'profit':  round(float(r.profit),  2),
    } for r in rows])


@analytics_bp.route('/api/analytics/payment-status-breakdown', methods=['GET'])
@login_required
@admin_required
def payment_status_breakdown():
    """Count and value of PAID / PARTIAL / UNPAID sales, last 30 days."""
    since = datetime.utcnow() - timedelta(days=30)
    rows = db.session.query(
        Sale.payment_status,
        func.count(Sale.id).label('count'),
        func.sum(Sale.total_amount).label('value'),
    ).filter(Sale.sale_date >= since)\
     .group_by(Sale.payment_status).all()

    return jsonify([{
        'status': r.payment_status,
        'count':  int(r.count),
        'value':  round(float(r.value), 2),
    } for r in rows])


@analytics_bp.route('/api/analytics/stock-health', methods=['GET'])
@login_required
@admin_required
def stock_health():
    """Stock status breakdown for the pie chart."""
    total         = Product.query.count()
    out_of_stock  = Product.query.filter(Product.quantity_in_stock <= 0).count()
    low_stock     = Product.query.filter(
        Product.quantity_in_stock > 0,
        Product.quantity_in_stock <= Product.min_stock_level
    ).count()
    healthy       = total - out_of_stock - low_stock

    return jsonify({
        'total':        total,
        'out_of_stock': out_of_stock,
        'low_stock':    low_stock,
        'healthy':      healthy,
    })


@analytics_bp.route('/api/analytics/debt-aging', methods=['GET'])
@login_required
@admin_required
def debt_aging():
    """Customer debt bucketed by age: <30d / 30-60d / 60-90d / 90d+."""
    now  = datetime.utcnow()
    sales = Sale.query.filter(Sale.balance_due > 0)\
                      .options(joinedload(Sale.customer)).all()

    buckets = {'0-30': 0, '31-60': 0, '61-90': 0, '90+': 0}
    for s in sales:
        age = (now - s.sale_date).days
        if   age <= 30:  buckets['0-30']  += s.balance_due
        elif age <= 60:  buckets['31-60'] += s.balance_due
        elif age <= 90:  buckets['61-90'] += s.balance_due
        else:            buckets['90+']   += s.balance_due

    return jsonify([
        {'label': k, 'amount': round(v, 2)} for k, v in buckets.items()
    ])


@analytics_bp.route('/api/analytics/movement-heatmap', methods=['GET'])
@login_required
@admin_required
def movement_heatmap():
    """Stock movements per day for the last 30 days (for heatmap/bar chart)."""
    since = datetime.utcnow() - timedelta(days=30)
    rows = db.session.query(
        func.date_trunc('day', StockMovement.timestamp).label('day'),
        func.sum(
            func.abs(StockMovement.quantity_change)
        ).label('activity'),
    ).filter(StockMovement.timestamp >= since)\
     .group_by('day').order_by('day').all()

    return jsonify([{
        'date':     r.day.strftime('%Y-%m-%d'),
        'activity': int(r.activity),
    } for r in rows])
