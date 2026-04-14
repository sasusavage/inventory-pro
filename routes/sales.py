from flask import Blueprint, render_template, request, jsonify, session, make_response
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from io import BytesIO
from models import db, Sale, SaleItem, Product, Customer, ActivityLog
from decorators import login_required
from utils import log_stock_movement

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

sales_bp = Blueprint('sales', __name__)


@sales_bp.route('/pos-page')
@login_required
def pos_page():
    return render_template('pos.html', user_role=session.get('role'))


@sales_bp.route('/sales-page')
@login_required
def sales_page():
    return render_template('sales.html', user_role=session.get('role'))


@sales_bp.route('/pos/lookup-customer', methods=['POST'])
@login_required
def pos_lookup_customer():
    data = request.json or {}
    term = (data.get('term') or '').strip()
    if not term:
        return jsonify([])

    customers = Customer.query.filter(
        or_(
            Customer.phone.ilike(f'%{term}%'),
            Customer.full_name.ilike(f'%{term}%'),
        )
    ).limit(5).all()

    return jsonify([{
        'id': c.id,
        'full_name': c.full_name,
        'phone': c.phone,
        'address': c.address,
        'total_debt': c.total_debt,
    } for c in customers])


@sales_bp.route('/sales', methods=['GET'])
@login_required
def list_sales():
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip().upper()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    if session.get('role') == 'admin':
        query = Sale.query.options(
            joinedload(Sale.customer),
            joinedload(Sale.items).joinedload(SaleItem.product),
        )
    else:
        query = Sale.query.filter_by(user_id=session.get('user_id')).options(
            joinedload(Sale.customer),
            joinedload(Sale.items).joinedload(SaleItem.product),
        )

    if search:
        query = query.join(Customer).filter(
            Customer.full_name.ilike(f'%{search}%')
        )

    if status_filter in ('PAID', 'PARTIAL', 'UNPAID'):
        query = query.filter(Sale.payment_status == status_filter)

    if date_from:
        try:
            from datetime import datetime
            query = query.filter(Sale.sale_date >= datetime.fromisoformat(date_from))
        except ValueError:
            pass

    if date_to:
        try:
            from datetime import datetime
            query = query.filter(Sale.sale_date <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    paginated = query.order_by(Sale.sale_date.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        'data': [{
            'id': s.id,
            'customer_name': s.customer.full_name,
            'total_amount': s.total_amount,
            'amount_paid': s.amount_paid,
            'balance_due': s.balance_due,
            'payment_status': s.payment_status,
            'sale_date': s.sale_date.isoformat(),
            'items': [{
                'product_name': item.product.name,
                'quantity': item.quantity,
                'price_at_sale': item.price_at_sale,
                'subtotal': item.subtotal,
                'status': item.status,
            } for item in s.items],
        } for s in paginated.items],
        'pagination': {
            'page': paginated.page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages,
        }
    })


@sales_bp.route('/sales', methods=['POST'])
@login_required
def create_sale():
    data = request.json or {}

    if 'customer_id' not in data:
        return jsonify({'error': 'customer_id is required'}), 400
    if not data.get('items'):
        return jsonify({'error': 'At least one item is required'}), 400

    try:
        amount_paid = float(data.get('amount_paid', 0))
        if amount_paid < 0:
            return jsonify({'error': 'amount_paid cannot be negative'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid amount_paid'}), 400

    try:
        new_sale = Sale(
            customer_id=data['customer_id'],
            user_id=session.get('user_id'),
            total_amount=0,
            amount_paid=amount_paid,
            balance_due=0,
            payment_status='UNPAID',
        )
        db.session.add(new_sale)
        db.session.flush()

        total = 0
        for item in data['items']:
            product = Product.query.get(item['product_id'])
            if not product:
                raise ValueError(f'Product {item["product_id"]} not found')

            qty = int(item['quantity'])
            if qty <= 0:
                raise ValueError(f'Quantity must be positive for {product.name}')
            if product.quantity_in_stock < qty:
                raise ValueError(f'Insufficient stock for {product.name} (have {product.quantity_in_stock}, need {qty})')

            product.quantity_in_stock -= qty
            log_stock_movement(product.id, -qty, 'Sale', ref_id=new_sale.id)

            subtotal = product.selling_price * qty
            total += subtotal

            sale_item = SaleItem(
                sale_id=new_sale.id,
                product_id=product.id,
                quantity=qty,
                price_at_sale=product.selling_price,
                cost_price_at_sale=product.cost_price,
                subtotal=subtotal,
            )
            db.session.add(sale_item)

        new_sale.total_amount = total
        new_sale.balance_due = max(0, total - amount_paid)

        if new_sale.balance_due == 0:
            new_sale.payment_status = 'PAID'
        elif amount_paid > 0:
            new_sale.payment_status = 'PARTIAL'
        else:
            new_sale.payment_status = 'UNPAID'

        ActivityLog.log('CREATE_SALE', entity='sale', entity_id=new_sale.id,
                        summary=f'Total {total:.2f}, paid {amount_paid:.2f}, status {new_sale.payment_status}')
        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()

        # Award loyalty points
        try:
            from routes.loyalty import award_points_for_sale
            award_points_for_sale(new_sale)
            db.session.commit()
        except Exception:
            pass  # loyalty failure must never break a sale

        # Optional per-sale Telegram alert (only if owner has enabled it)
        from models import AppSetting
        if AppSetting.get('notify_on_sale', '0') == '1':
            from notifications import sale_summary_alert
            sale_summary_alert(
                Customer.query.get(data['customer_id']).full_name,
                new_sale.total_amount,
                new_sale.payment_status,
            )

        # Return loyalty balance so POS can show it
        try:
            from models import LoyaltyPoint
            loyalty_balance = LoyaltyPoint.balance(new_sale.customer_id)
        except Exception:
            loyalty_balance = None

        return jsonify({
            'message': 'Sale completed',
            'id': new_sale.id,
            'sale_id': new_sale.id,
            'loyalty_points': loyalty_balance,
        }), 201

    except ValueError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to create sale'}), 500


@sales_bp.route('/sales/<int:sale_id>/payment', methods=['POST'])
@login_required
def add_sale_payment(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    data = request.json or {}

    try:
        amount = float(data['additional_payment'])
    except (KeyError, ValueError, TypeError):
        return jsonify({'error': 'Invalid payment amount'}), 400

    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400

    try:
        sale.amount_paid += amount
        sale.balance_due = max(0, sale.total_amount - sale.amount_paid)
        sale.payment_status = 'PAID' if sale.balance_due == 0 else 'PARTIAL'
        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({'message': 'Payment added', 'new_balance': sale.balance_due})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to record payment'}), 500


@sales_bp.route('/sales/<int:sale_id>/items/<int:item_id>/return', methods=['POST'])
@login_required
def return_sale_item(sale_id, item_id):
    item = SaleItem.query.get_or_404(item_id)
    if item.sale_id != sale_id:
        return jsonify({'error': 'Invalid item'}), 400
    if item.status == 'Returned':
        return jsonify({'error': 'Item already returned'}), 400

    try:
        item.status = 'Returned'
        item.product.quantity_in_stock += item.quantity
        log_stock_movement(item.product.id, item.quantity, 'Return Sale Item', ref_id=sale_id)
        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({'message': 'Item marked as returned and stock updated'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to process return'}), 500


@sales_bp.route('/sales/<int:sale_id>/invoice', methods=['GET'])
@login_required
def generate_invoice(sale_id):
    if not REPORTLAB_AVAILABLE:
        return jsonify({'error': 'PDF generation not available'}), 503

    sale = Sale.query.options(
        joinedload(Sale.customer),
        joinedload(Sale.items).joinedload(SaleItem.product),
    ).get_or_404(sale_id)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, f"Receipt / Invoice #{sale.id}")
    p.setFont("Helvetica", 12)
    p.drawString(100, 720, f"Customer: {sale.customer.full_name}")
    p.drawString(100, 700, f"Date: {sale.sale_date.strftime('%Y-%m-%d %H:%M')}")

    y = 650
    p.drawString(100, y, "Item")
    p.drawString(350, y, "Qty")
    p.drawString(450, y, "Price")
    y -= 20

    for item in sale.items:
        label = item.product.name + (' (Returned)' if item.status == 'Returned' else '')
        p.drawString(100, y, label)
        p.drawString(350, y, str(item.quantity))
        p.drawString(450, y, f"${item.price_at_sale:.2f}")
        y -= 25

    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y - 20, "Total:")
    p.drawString(450, y - 20, f"${sale.total_amount:.2f}")
    p.drawString(350, y - 40, "Paid:")
    p.drawString(450, y - 40, f"${sale.amount_paid:.2f}")
    p.drawString(350, y - 60, "Balance:")
    p.drawString(450, y - 60, f"${sale.balance_due:.2f}")

    p.showPage()
    p.save()
    buffer.seek(0)

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename=receipt_{sale.id}.pdf'
    return response


@sales_bp.route('/sales/<int:sale_id>/receipt', methods=['GET'])
@login_required
def html_receipt(sale_id):
    """Browser-printable HTML receipt — no external dependencies needed."""
    from flask import request as flask_req
    from models import AppSetting
    sale = Sale.query.options(
        joinedload(Sale.customer),
        joinedload(Sale.items).joinedload(SaleItem.product),
    ).get_or_404(sale_id)
    store_name = AppSetting.get('store_name', 'InventoryPro')
    currency = AppSetting.get('store_currency') or AppSetting.get('currency', '$')
    store_address = AppSetting.get('store_address', '')
    store_phone = AppSetting.get('store_phone', '')
    store_tagline = AppSetting.get('store_tagline', '')
    receipt_url = flask_req.url_root.rstrip('/') + f'/sales/{sale.id}/receipt'
    return render_template(
        'receipt.html',
        sale=sale,
        store_name=store_name,
        currency=currency,
        store_address=store_address,
        store_phone=store_phone,
        store_tagline=store_tagline,
        receipt_url=receipt_url,
    )
