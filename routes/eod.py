"""
End-of-Day Cash Reconciliation Report.
Routes:
  GET  /eod-page              — UI page
  GET  /api/eod/summary       — JSON data for a given date
  POST /api/eod/reconcile     — save actual cash counted
"""
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, g
from sqlalchemy import func
from models import db, Sale, SaleItem, Product, AppSetting
from decorators import login_required, admin_required

eod_bp = Blueprint('eod', __name__)


@eod_bp.route('/eod-page')
@login_required
@admin_required
def eod_page():
    return render_template('eod_report.html')


@eod_bp.route('/api/eod/summary')
@login_required
@admin_required
def eod_summary():
    report_date_str = request.args.get('date', date.today().isoformat())
    try:
        report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

    day_start = datetime.combine(report_date, datetime.min.time())
    day_end   = datetime.combine(report_date + timedelta(days=1), datetime.min.time())
    org_id    = g.org_id

    # All sales for the day
    sales = Sale.query.filter(
        Sale.organisation_id == org_id,
        Sale.sale_date >= day_start,
        Sale.sale_date < day_end,
    ).all()

    # Breakdown by payment method
    method_totals = {}
    for s in sales:
        m = (s.payment_method or 'cash').lower()
        method_totals[m] = method_totals.get(m, 0) + float(s.total_amount or 0)

    # Top products sold today
    top_products = (
        db.session.query(
            Product.name,
            func.sum(SaleItem.quantity).label('qty'),
            func.sum(SaleItem.quantity * SaleItem.price_at_sale).label('revenue'),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .join(Product, SaleItem.product_id == Product.id)
        .filter(
            Sale.organisation_id == org_id,
            Sale.sale_date >= day_start,
            Sale.sale_date < day_end,
            SaleItem.status == 'Active',
        )
        .group_by(Product.name)
        .order_by(func.sum(SaleItem.quantity * SaleItem.price_at_sale).desc())
        .limit(10)
        .all()
    )

    # Retrieve saved actual cash count for this date (if admin already reconciled)
    key = f'eod_actual_cash_{report_date_str}'
    actual_cash_str = AppSetting.get(key, '')
    actual_cash = float(actual_cash_str) if actual_cash_str else None

    expected_cash = method_totals.get('cash', 0)
    variance = round(actual_cash - expected_cash, 2) if actual_cash is not None else None

    total_sales_amount = sum(float(s.total_amount or 0) for s in sales)
    total_transactions = len(sales)

    return jsonify({
        'date':               report_date_str,
        'total_transactions': total_transactions,
        'total_sales_amount': round(total_sales_amount, 2),
        'method_totals':      {k: round(v, 2) for k, v in method_totals.items()},
        'expected_cash':      round(expected_cash, 2),
        'actual_cash':        actual_cash,
        'variance':           variance,
        'top_products': [{
            'name':    r.name,
            'qty':     int(r.qty),
            'revenue': round(float(r.revenue), 2),
        } for r in top_products],
    })


@eod_bp.route('/api/eod/reconcile', methods=['POST'])
@login_required
@admin_required
def eod_reconcile():
    data        = request.json or {}
    report_date = data.get('date', date.today().isoformat())
    actual_cash = data.get('actual_cash')

    if actual_cash is None:
        return jsonify({'error': 'actual_cash is required'}), 400

    key = f'eod_actual_cash_{report_date}'
    AppSetting.set(key, str(float(actual_cash)), org_id=g.org_id)
    db.session.commit()

    return jsonify({'message': 'Cash count saved', 'date': report_date, 'actual_cash': actual_cash})
