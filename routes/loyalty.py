"""
Loyalty Points System.
Earn: 1 point per $1 spent (rounded down).
Redeem: 100 points = $1 discount.
Configured via AppSetting: loyalty_earn_rate (default 1), loyalty_redeem_rate (default 100).
"""
from flask import Blueprint, request, jsonify
from models import db, LoyaltyPoint, Customer, Sale, AppSetting
from decorators import login_required, admin_required

loyalty_bp = Blueprint('loyalty', __name__)

POINTS_PER_DOLLAR_DEFAULT = 1    # points earned per $ spent
REDEEM_POINTS_PER_DOLLAR_DEFAULT = 100  # points needed to get $1 discount


def _earn_rate():
    try:
        return float(AppSetting.get('loyalty_earn_rate', POINTS_PER_DOLLAR_DEFAULT))
    except (TypeError, ValueError):
        return POINTS_PER_DOLLAR_DEFAULT


def _redeem_rate():
    try:
        return float(AppSetting.get('loyalty_redeem_rate', REDEEM_POINTS_PER_DOLLAR_DEFAULT))
    except (TypeError, ValueError):
        return REDEEM_POINTS_PER_DOLLAR_DEFAULT


def award_points_for_sale(sale: Sale):
    """Call this after a successful sale to credit loyalty points."""
    if not sale.customer_id:
        return
    earn_rate = _earn_rate()
    points_earned = int(sale.total_amount * earn_rate)
    if points_earned <= 0:
        return
    lp = LoyaltyPoint(
        customer_id=sale.customer_id,
        points=points_earned,
        reason='sale',
        reference_id=sale.id,
    )
    db.session.add(lp)
    # Note: caller is responsible for db.session.commit()


@loyalty_bp.route('/api/loyalty/<int:customer_id>/balance', methods=['GET'])
@login_required
def get_balance(customer_id):
    Customer.query.get_or_404(customer_id)
    balance = LoyaltyPoint.balance(customer_id)
    redeem_rate = _redeem_rate()
    return jsonify({
        'customer_id': customer_id,
        'points': balance,
        'redeemable_value': round(balance / redeem_rate, 2) if balance >= redeem_rate else 0,
        'redeem_rate': redeem_rate,
        'earn_rate': _earn_rate(),
    })


@loyalty_bp.route('/api/loyalty/<int:customer_id>/history', methods=['GET'])
@login_required
def get_history(customer_id):
    Customer.query.get_or_404(customer_id)
    records = LoyaltyPoint.query.filter_by(customer_id=customer_id).order_by(
        LoyaltyPoint.created_at.desc()
    ).limit(50).all()
    return jsonify([{
        'id': r.id,
        'points': r.points,
        'reason': r.reason,
        'reference_id': r.reference_id,
        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M'),
    } for r in records])


@loyalty_bp.route('/api/loyalty/<int:customer_id>/redeem', methods=['POST'])
@login_required
def redeem_points(customer_id):
    """Redeem points as a discount on a sale. Returns discount amount."""
    data = request.json or {}
    points_to_redeem = int(data.get('points', 0))
    redeem_rate = _redeem_rate()

    if points_to_redeem <= 0:
        return jsonify({'error': 'Points must be > 0'}), 400

    balance = LoyaltyPoint.balance(customer_id)
    if points_to_redeem > balance:
        return jsonify({'error': f'Insufficient points. Balance: {balance}'}), 400

    # Must redeem in multiples of redeem_rate
    points_to_redeem = int(points_to_redeem // redeem_rate) * int(redeem_rate)
    if points_to_redeem <= 0:
        return jsonify({'error': f'Minimum redemption is {int(redeem_rate)} points'}), 400

    discount = round(points_to_redeem / redeem_rate, 2)
    lp = LoyaltyPoint(
        customer_id=customer_id,
        points=-points_to_redeem,
        reason='redemption',
        reference_id=data.get('sale_id'),
    )
    db.session.add(lp)
    db.session.commit()
    return jsonify({
        'points_redeemed': points_to_redeem,
        'discount_applied': discount,
        'new_balance': LoyaltyPoint.balance(customer_id),
    })


@loyalty_bp.route('/api/loyalty/settings', methods=['GET'])
@admin_required
def get_settings():
    return jsonify({'earn_rate': _earn_rate(), 'redeem_rate': _redeem_rate()})


@loyalty_bp.route('/api/loyalty/settings', methods=['POST'])
@admin_required
def update_settings():
    data = request.json or {}
    if 'earn_rate' in data:
        AppSetting.set('loyalty_earn_rate', str(float(data['earn_rate'])))
    if 'redeem_rate' in data:
        AppSetting.set('loyalty_redeem_rate', str(float(data['redeem_rate'])))
    return jsonify({'message': 'Settings updated'})
