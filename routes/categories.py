from flask import Blueprint, request, jsonify, session
from models import db, Category, Product
from decorators import login_required, admin_required

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('/categories-page')
@login_required
def categories_page():
    from flask import render_template
    return render_template('categories.html')


@categories_bp.route('/api/categories', methods=['GET'])
@login_required
def list_categories():
    cats = Category.query.order_by(Category.name).all()
    return jsonify([{
        'id': c.id,
        'name': c.name,
        'color': c.color,
        'product_count': len(c.products),
    } for c in cats])


@categories_bp.route('/api/categories', methods=['POST'])
@admin_required
def create_category():
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name required'}), 400
    if Category.query.filter_by(name=name).first():
        return jsonify({'error': 'Category already exists'}), 409
    cat = Category(name=name, color=data.get('color', '#4f46e5'))
    db.session.add(cat)
    db.session.commit()
    return jsonify({'id': cat.id, 'name': cat.name, 'color': cat.color}), 201


@categories_bp.route('/api/categories/<int:cat_id>', methods=['PUT'])
@admin_required
def update_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    data = request.json or {}
    if 'name' in data:
        cat.name = data['name'].strip()
    if 'color' in data:
        cat.color = data['color']
    db.session.commit()
    return jsonify({'message': 'Updated'})


@categories_bp.route('/api/categories/<int:cat_id>', methods=['DELETE'])
@admin_required
def delete_category(cat_id):
    cat = Category.query.get_or_404(cat_id)
    # Unlink products
    Product.query.filter_by(category_id=cat_id).update({'category_id': None})
    db.session.delete(cat)
    db.session.commit()
    return jsonify({'message': 'Deleted'})
