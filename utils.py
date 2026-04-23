import os
from models import db, StockMovement

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def log_stock_movement(product_id, change, reason, ref_id=None):
    movement = StockMovement(
        product_id=product_id,
        quantity_change=change,
        reason=reason,
        reference_id=str(ref_id) if ref_id else None,
    )
    db.session.add(movement)

    # Fire a Telegram alert if this movement pushed stock to/below minimum.
    # We only alert on reductions (change < 0) or when stock is already critical.
    if change <= 0:
        _maybe_alert_low_stock(product_id)


def _maybe_alert_low_stock(product_id):
    """Check stock level after a reduction and send a Telegram alert if needed."""
    try:
        from models import Product
        product = Product.query.get(product_id)
        if product and product.quantity_in_stock <= product.min_stock_level:
            from notifications import low_stock_alert
            low_stock_alert(product.organisation_id, product.name, product.quantity_in_stock, product.min_stock_level)
    except Exception:
        pass  # Never let a notification failure break a transaction
