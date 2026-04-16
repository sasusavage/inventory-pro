"""
Product Variants — size, colour, or any attribute per product.
Routes:
  GET  /api/products/<id>/variants      — list variants
  POST /api/products/<id>/variants      — create variant
  PUT  /api/products/<id>/variants/<vid>— update variant
  DELETE /api/products/<id>/variants/<vid> — delete variant
"""
from flask import Blueprint, request, jsonify, g
from models import db, Product, ProductVariant
from decorators import login_required, admin_required

variants_bp = Blueprint('variants', __name__)


@variants_bp.route('/api/products/<int:product_id>/variants', methods=['GET'])
@login_required
def list_variants(product_id):
    product = Product.query.filter_by(id=product_id, organisation_id=g.org_id).first_or_404()
    variants = ProductVariant.query.filter_by(
        product_id=product.id, organisation_id=g.org_id, is_active=True
    ).all()
    return jsonify([_v(v) for v in variants])


@variants_bp.route('/api/products/<int:product_id>/variants', methods=['POST'])
@login_required
@admin_required
def create_variant(product_id):
    product = Product.query.filter_by(id=product_id, organisation_id=g.org_id).first_or_404()
    data = request.json or {}

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Variant name is required'}), 400

    v = ProductVariant(
        organisation_id=g.org_id,
        product_id=product.id,
        name=name,
        attributes=data.get('attributes') or {},
        sku_suffix=(data.get('sku_suffix') or '').strip() or None,
        price_adjustment=float(data.get('price_adjustment', 0)),
        quantity_in_stock=int(data.get('quantity_in_stock', 0)),
    )
    db.session.add(v)
    db.session.commit()
    return jsonify(_v(v)), 201


@variants_bp.route('/api/products/<int:product_id>/variants/<int:vid>', methods=['PUT'])
@login_required
@admin_required
def update_variant(product_id, vid):
    v = ProductVariant.query.filter_by(
        id=vid, product_id=product_id, organisation_id=g.org_id
    ).first_or_404()
    data = request.json or {}

    if 'name' in data:
        v.name = data['name'].strip()
    if 'attributes' in data:
        v.attributes = data['attributes']
    if 'sku_suffix' in data:
        v.sku_suffix = (data['sku_suffix'] or '').strip() or None
    if 'price_adjustment' in data:
        v.price_adjustment = float(data['price_adjustment'])
    if 'quantity_in_stock' in data:
        v.quantity_in_stock = int(data['quantity_in_stock'])
    if 'is_active' in data:
        v.is_active = bool(data['is_active'])

    db.session.commit()
    return jsonify(_v(v))


@variants_bp.route('/api/products/<int:product_id>/variants/<int:vid>', methods=['DELETE'])
@login_required
@admin_required
def delete_variant(product_id, vid):
    v = ProductVariant.query.filter_by(
        id=vid, product_id=product_id, organisation_id=g.org_id
    ).first_or_404()
    v.is_active = False
    db.session.commit()
    return jsonify({'message': 'Variant removed'})


def _v(v):
    return {
        'id':               v.id,
        'product_id':       v.product_id,
        'name':             v.name,
        'attributes':       v.attributes or {},
        'sku_suffix':       v.sku_suffix,
        'price_adjustment': v.price_adjustment,
        'quantity_in_stock':v.quantity_in_stock,
        'is_active':        v.is_active,
    }
