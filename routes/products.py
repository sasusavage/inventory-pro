import os
from flask import Blueprint, render_template, request, jsonify, session, current_app
from werkzeug.utils import secure_filename
from models import db, Product, ActivityLog
from decorators import login_required
from utils import allowed_file, log_stock_movement, MAX_FILE_SIZE

products_bp = Blueprint('products', __name__)


@products_bp.route('/products-page')
@login_required
def products_page():
    return render_template('products.html', user_role=session.get('role'))


@products_bp.route('/products', methods=['GET'])
@login_required
def list_products():
    search = request.args.get('search', '').strip()
    category_id = request.args.get('category_id', type=int)
    query = Product.query

    if search:
        query = query.filter(Product.name.ilike(f'%{search}%') | Product.sku.ilike(f'%{search}%'))
    if category_id:
        query = query.filter(Product.category_id == category_id)

    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 100, type=int), 500)
    paginated = query.order_by(Product.name).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'data': [{
            'id': p.id,
            'name': p.name,
            'sku': p.sku,
            'cost_price': p.cost_price,
            'selling_price': p.selling_price,
            'quantity_in_stock': p.quantity_in_stock,
            'damaged_quantity': p.damaged_quantity,
            'min_stock_level': p.min_stock_level,
            'image_url': p.image_url,
            'image_filename': p.image_filename,
            'category_id': p.category_id,
            'category_name': p.category.name if p.category else None,
        } for p in paginated.items],
        'pagination': {
            'page': paginated.page,
            'per_page': per_page,
            'total': paginated.total,
            'pages': paginated.pages,
        }
    })


@products_bp.route('/products', methods=['POST'])
@login_required
def create_product():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json or {}
    required = ['name', 'sku', 'cost_price', 'selling_price', 'quantity_in_stock']
    missing = [f for f in required if f not in data or data[f] == '' or data[f] is None]
    if missing:
        return jsonify({'error': f'Missing fields: {", ".join(missing)}'}), 400

    try:
        cost_price = float(data['cost_price'])
        selling_price = float(data['selling_price'])
        quantity = int(data['quantity_in_stock'])
        min_stock = int(data.get('min_stock_level', 10))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numeric values'}), 400

    if cost_price < 0 or selling_price < 0 or quantity < 0:
        return jsonify({'error': 'Prices and quantity must be non-negative'}), 400

    existing = Product.query.filter_by(sku=data['sku'].strip()).first()
    if existing:
        return jsonify({'error': 'SKU already exists'}), 409

    try:
        product = Product(
            name=data['name'].strip(),
            sku=data['sku'].strip(),
            cost_price=cost_price,
            selling_price=selling_price,
            quantity_in_stock=quantity,
            min_stock_level=min_stock,
            image_url=data.get('image_url') or None,
        )
        db.session.add(product)
        db.session.flush()

        if product.quantity_in_stock > 0:
            log_stock_movement(product.id, product.quantity_in_stock, 'Initial Stock')

        ActivityLog.log('CREATE_PRODUCT', entity='product', entity_id=product.id,
                        summary=f'{product.name} (SKU {product.sku}) qty {product.quantity_in_stock}')
        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({'message': 'Product added successfully', 'id': product.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create product'}), 500


@products_bp.route('/products/<int:product_id>', methods=['PUT'])
@login_required
def update_product(product_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    product = Product.query.get_or_404(product_id)
    data = request.json or {}

    try:
        if 'name' in data:
            product.name = data['name'].strip()
        if 'cost_price' in data:
            product.cost_price = float(data['cost_price'])
        if 'selling_price' in data:
            product.selling_price = float(data['selling_price'])
        if 'quantity_in_stock' in data:
            old_qty = product.quantity_in_stock
            new_qty = int(data['quantity_in_stock'])
            diff = new_qty - old_qty
            product.quantity_in_stock = new_qty
            if diff != 0:
                log_stock_movement(product.id, diff, 'Manual Adjustment')
        if 'min_stock_level' in data:
            product.min_stock_level = int(data['min_stock_level'])
        if 'image_url' in data:
            product.image_url = data['image_url'] or None

        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({'message': 'Product updated'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to update product'}), 500


@products_bp.route('/products/<int:product_id>', methods=['DELETE'])
@login_required
def delete_product(product_id):
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    product = Product.query.get_or_404(product_id)
    try:
        name_snapshot = product.name
        sku_snapshot = product.sku
        db.session.delete(product)
        ActivityLog.log('DELETE_PRODUCT', entity='product', entity_id=product_id,
                        summary=f'{name_snapshot} (SKU {sku_snapshot})')
        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({'message': 'Product deleted'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Cannot delete product — it may be referenced by sales'}), 409


@products_bp.route('/products/upload-image', methods=['POST'])
@login_required
def upload_product_image():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    product_id = request.form.get('product_id')

    if not product_id:
        return jsonify({'error': 'product_id required'}), 400

    # Check file size
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': 'File too large (max 5MB)'}), 413

    if file and allowed_file(file.filename):
        filename = secure_filename(f"prod_{product_id}_{file.filename}")
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)

        product = Product.query.get(product_id)
        if product:
            product.image_filename = filename
            product.image_url = None
            db.session.commit()
            return jsonify({'message': 'Image uploaded', 'filename': filename})

    return jsonify({'error': 'Invalid file type'}), 400


@products_bp.route('/products/bulk', methods=['POST'])
@login_required
def bulk_products():
    if session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json or {}
    action = data.get('action')
    product_ids = data.get('product_ids', [])

    if not product_ids:
        return jsonify({'error': 'No products selected'}), 400

    try:
        if action == 'delete':
            Product.query.filter(Product.id.in_(product_ids)).delete(synchronize_session=False)
        elif action == 'update_price':
            new_price = float(data.get('new_selling_price', 0))
            if new_price < 0:
                return jsonify({'error': 'Price must be non-negative'}), 400
            Product.query.filter(Product.id.in_(product_ids)).update(
                {Product.selling_price: new_price}, synchronize_session=False
            )
        else:
            return jsonify({'error': 'Unknown action'}), 400

        db.session.commit()
        from routes.dashboard import invalidate_stats_cache
        invalidate_stats_cache()
        return jsonify({'message': 'Bulk action completed'})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Bulk action failed'}), 500


@products_bp.route('/check-product/<sku>', methods=['GET'])
def check_product(sku):
    product = Product.query.filter_by(sku=sku).first()
    return jsonify({'exists': product is not None})


@products_bp.route('/products/<int:product_id>/label')
@login_required
def product_label(product_id):
    """Printable barcode label for a product."""
    from models import AppSetting
    product = Product.query.get_or_404(product_id)
    store_name = AppSetting.get('store_name', 'InventoryPro')
    currency = AppSetting.get('store_currency') or AppSetting.get('currency', '$')
    return render_template(
        'product_label.html',
        product=product,
        store_name=store_name,
        currency=currency,
    )


@products_bp.route('/products/top-profit', methods=['GET'])
@login_required
def top_profit_products():
    """Top products by total gross profit over the selected window (default 30d)."""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    from models import SaleItem, Sale

    days = min(int(request.args.get('days', 30) or 30), 365)
    since = datetime.utcnow() - timedelta(days=days)

    rows = (
        db.session.query(
            SaleItem.product_id,
            func.sum(SaleItem.quantity).label('units_sold'),
            func.sum(SaleItem.subtotal).label('revenue'),
            func.sum(SaleItem.subtotal - SaleItem.cost_price_at_sale * SaleItem.quantity).label('profit'),
        )
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(Sale.sale_date >= since, SaleItem.status == 'Active')
        .group_by(SaleItem.product_id)
        .order_by(func.sum(SaleItem.subtotal - SaleItem.cost_price_at_sale * SaleItem.quantity).desc())
        .limit(20)
        .all()
    )

    results = []
    for r in rows:
        product = Product.query.get(r.product_id)
        if not product:
            continue
        rev = float(r.revenue or 0)
        profit = float(r.profit or 0)
        results.append({
            'product_id': product.id,
            'name': product.name,
            'sku': product.sku,
            'units_sold': int(r.units_sold or 0),
            'revenue': rev,
            'profit': profit,
            'margin_percent': round((profit / rev) * 100, 1) if rev > 0 else 0,
        })
    return jsonify({'days': days, 'products': results})
