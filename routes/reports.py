import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify, session, Response
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from models import db, Sale, SaleItem, Customer, Product, StockMovement, Expense, AppSetting
from decorators import login_required

reports_bp = Blueprint('reports', __name__)


@reports_bp.route('/reports/debtors')
@login_required
def report_debtors():
    # Efficient aggregate query — no N+1 loop
    rows = (
        db.session.query(
            Customer.id,
            Customer.full_name,
            Customer.phone,
            Customer.email,
            func.sum(Sale.balance_due).label('total_debt'),
        )
        .join(Sale, Sale.customer_id == Customer.id)
        .filter(Sale.balance_due > 0)
        .group_by(Customer.id, Customer.full_name, Customer.phone, Customer.email)
        .having(func.sum(Sale.balance_due) > 0)
        .order_by(func.sum(Sale.balance_due).desc())
        .all()
    )
    return jsonify([{
        'full_name': r.full_name,
        'phone': r.phone,
        'email': r.email,
        'total_debt': float(r.total_debt),
    } for r in rows])


@reports_bp.route('/reports/profit')
@login_required
def report_profit():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    query = SaleItem.query.filter_by(status='Active').join(Sale)

    if date_from:
        try:
            query = query.filter(Sale.sale_date >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            query = query.filter(Sale.sale_date <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    result = db.session.query(
        func.sum(SaleItem.subtotal).label('total_rev'),
        func.sum(SaleItem.subtotal - SaleItem.cost_price_at_sale * SaleItem.quantity).label('gross_profit'),
    ).filter(SaleItem.status == 'Active').join(Sale)

    if date_from:
        try:
            result = result.filter(Sale.sale_date >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            result = result.filter(Sale.sale_date <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    row = result.one()
    total_rev = float(row.total_rev or 0)
    gross_profit = float(row.gross_profit or 0)

    return jsonify({
        'total_revenue': total_rev,
        'gross_profit': gross_profit,
        'margin_percentage': round((gross_profit / total_rev) * 100, 2) if total_rev > 0 else 0,
    })


@reports_bp.route('/top-customers-page')
@login_required
def top_customers_page():
    if session.get('role') != 'admin':
        return "Admins only", 403
    return render_template('top_customers.html', user_role=session.get('role'))


@reports_bp.route('/pnl-page')
@login_required
def pnl_page():
    if session.get('role') != 'admin':
        return "Admins only", 403
    return render_template('pnl_report.html', user_role=session.get('role'))


@reports_bp.route('/reports/pnl')
@login_required
def report_pnl():
    """Profit & Loss: revenue, COGS, gross profit, expenses, net profit."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    df = dt = None
    if date_from:
        try: df = datetime.fromisoformat(date_from)
        except ValueError: pass
    if date_to:
        try: dt = datetime.fromisoformat(date_to + 'T23:59:59')
        except ValueError: pass

    # Revenue + COGS from sale items
    sales_q = db.session.query(
        func.coalesce(func.sum(SaleItem.subtotal), 0).label('revenue'),
        func.coalesce(func.sum(SaleItem.cost_price_at_sale * SaleItem.quantity), 0).label('cogs'),
    ).join(Sale, Sale.id == SaleItem.sale_id).filter(SaleItem.status == 'Active')
    if df: sales_q = sales_q.filter(Sale.sale_date >= df)
    if dt: sales_q = sales_q.filter(Sale.sale_date <= dt)
    sr = sales_q.one()
    revenue = float(sr.revenue or 0)
    cogs = float(sr.cogs or 0)
    gross_profit = revenue - cogs

    # Expenses
    exp_q = db.session.query(
        Expense.category, func.sum(Expense.amount).label('amt')
    )
    if df: exp_q = exp_q.filter(Expense.expense_date >= df)
    if dt: exp_q = exp_q.filter(Expense.expense_date <= dt)
    exp_rows = exp_q.group_by(Expense.category).all()

    expenses_by_category = [
        {'category': r.category or 'Uncategorized', 'amount': float(r.amt or 0)}
        for r in exp_rows
    ]
    total_expenses = sum(e['amount'] for e in expenses_by_category)
    net_profit = gross_profit - total_expenses

    currency = AppSetting.get('store_currency') or AppSetting.get('currency', '$')

    return jsonify({
        'date_from': date_from or None,
        'date_to': date_to or None,
        'currency': currency,
        'revenue': revenue,
        'cogs': cogs,
        'gross_profit': gross_profit,
        'gross_margin_percent': round((gross_profit / revenue) * 100, 2) if revenue > 0 else 0,
        'expenses_by_category': sorted(expenses_by_category, key=lambda x: -x['amount']),
        'total_expenses': total_expenses,
        'net_profit': net_profit,
        'net_margin_percent': round((net_profit / revenue) * 100, 2) if revenue > 0 else 0,
    })


@reports_bp.route('/reports/top-customers')
@login_required
def report_top_customers():
    """Top customers ranked by total spend over the window."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    days = min(int(request.args.get('days', 90) or 90), 3650)
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.session.query(
            Customer.id,
            Customer.full_name,
            Customer.phone,
            func.count(Sale.id).label('order_count'),
            func.sum(Sale.total_amount).label('total_spent'),
            func.sum(Sale.balance_due).label('outstanding'),
        )
        .join(Sale, Sale.customer_id == Customer.id)
        .filter(Sale.sale_date >= since)
        .group_by(Customer.id, Customer.full_name, Customer.phone)
        .order_by(func.sum(Sale.total_amount).desc())
        .limit(20)
        .all()
    )

    return jsonify({
        'days': days,
        'customers': [{
            'customer_id': r.id,
            'name': r.full_name,
            'phone': r.phone,
            'order_count': int(r.order_count or 0),
            'total_spent': float(r.total_spent or 0),
            'outstanding': float(r.outstanding or 0),
        } for r in rows],
    })


@reports_bp.route('/reports/monthly-trends')
@login_required
def monthly_trends():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    six_months_ago = datetime.utcnow() - timedelta(days=180)
    sales = db.session.query(
        func.date_trunc('month', Sale.sale_date).label('month'),
        func.sum(Sale.total_amount).label('total'),
    ).filter(Sale.sale_date >= six_months_ago).group_by('month').order_by('month').all()

    return jsonify([{
        'month': row.month.strftime('%Y-%m'),
        'total_revenue': float(row.total),
    } for row in sales])


# ─── CSV Exports ────────────────────────────────────────────────────────────────

@reports_bp.route('/export/sales.csv')
@login_required
def export_sales_csv():
    if session.get('role') == 'admin':
        sales = Sale.query.options(
            joinedload(Sale.customer),
            joinedload(Sale.items).joinedload(SaleItem.product),
        ).order_by(Sale.sale_date.desc()).all()
    else:
        sales = Sale.query.filter_by(user_id=session.get('user_id')).options(
            joinedload(Sale.customer),
            joinedload(Sale.items).joinedload(SaleItem.product),
        ).order_by(Sale.sale_date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Sale ID', 'Date', 'Customer', 'Items', 'Total', 'Paid', 'Balance', 'Status'])

    for s in sales:
        items_str = '; '.join(f"{i.product.name} x{i.quantity}" for i in s.items)
        writer.writerow([
            s.id,
            s.sale_date.strftime('%Y-%m-%d %H:%M'),
            s.customer.full_name,
            items_str,
            f'{s.total_amount:.2f}',
            f'{s.amount_paid:.2f}',
            f'{s.balance_due:.2f}',
            s.payment_status,
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=sales_export.csv'},
    )


@reports_bp.route('/export/products.csv')
@login_required
def export_products_csv():
    products = Product.query.order_by(Product.name).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'SKU', 'Cost Price', 'Selling Price', 'Stock', 'Damaged', 'Min Stock', 'Status'])

    for p in products:
        status = 'Low Stock' if p.quantity_in_stock <= p.min_stock_level else 'In Stock'
        writer.writerow([
            p.id, p.name, p.sku,
            f'{p.cost_price:.2f}', f'{p.selling_price:.2f}',
            p.quantity_in_stock, p.damaged_quantity, p.min_stock_level,
            status,
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=products_export.csv'},
    )


@reports_bp.route('/export/customers.csv')
@login_required
def export_customers_csv():
    rows = (
        db.session.query(
            Customer.id,
            Customer.full_name,
            Customer.phone,
            Customer.email,
            Customer.address,
            Customer.created_at,
            func.coalesce(func.sum(Sale.balance_due), 0).label('total_debt'),
        )
        .outerjoin(Sale, Sale.customer_id == Customer.id)
        .group_by(Customer.id)
        .order_by(Customer.full_name)
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Phone', 'Email', 'Address', 'Joined', 'Outstanding Debt'])

    for r in rows:
        writer.writerow([
            r.id, r.full_name, r.phone, r.email or '', r.address or '',
            r.created_at.strftime('%Y-%m-%d'),
            f'{float(r.total_debt):.2f}',
        ])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=customers_export.csv'},
    )


@reports_bp.route('/export/debtors.csv')
@login_required
def export_debtors_csv():
    rows = (
        db.session.query(
            Customer.full_name,
            Customer.phone,
            Customer.email,
            func.sum(Sale.balance_due).label('total_debt'),
        )
        .join(Sale, Sale.customer_id == Customer.id)
        .filter(Sale.balance_due > 0)
        .group_by(Customer.id, Customer.full_name, Customer.phone, Customer.email)
        .having(func.sum(Sale.balance_due) > 0)
        .order_by(func.sum(Sale.balance_due).desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Customer', 'Phone', 'Email', 'Outstanding Debt'])

    for r in rows:
        writer.writerow([r.full_name, r.phone, r.email or '', f'{float(r.total_debt):.2f}'])

    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=debtors_export.csv'},
    )
