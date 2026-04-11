from flask import Blueprint, render_template, request, jsonify
from models import db, Expense
from decorators import login_required, admin_required
from datetime import datetime

expenses_bp = Blueprint('expenses', __name__)

EXPENSE_CATEGORIES = ['Rent', 'Salary', 'Utilities', 'Transport', 'Marketing',
                      'Supplies', 'Maintenance', 'Tax', 'Insurance', 'Other']


@expenses_bp.route('/expenses-page')
@admin_required
def expenses_page():
    return render_template('expenses.html', expense_categories=EXPENSE_CATEGORIES)


@expenses_bp.route('/api/expenses', methods=['GET'])
@admin_required
def list_expenses():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    category = request.args.get('category', '').strip()
    date_from = request.args.get('date_from', '').strip()
    date_to = request.args.get('date_to', '').strip()

    q = Expense.query
    if category:
        q = q.filter_by(category=category)
    if date_from:
        q = q.filter(Expense.expense_date >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        q = q.filter(Expense.expense_date <= datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))

    pag = q.order_by(Expense.expense_date.desc()).paginate(page=page, per_page=per_page, error_out=False)

    total_amount = sum(e.amount for e in q.all())

    return jsonify({
        'data': [{
            'id': e.id,
            'title': e.title,
            'amount': e.amount,
            'category': e.category,
            'note': e.note,
            'expense_date': e.expense_date.strftime('%Y-%m-%d'),
        } for e in pag.items],
        'pagination': {
            'page': pag.page, 'pages': pag.pages, 'total': pag.total, 'per_page': per_page,
        },
        'total_filtered': total_amount,
    })


@expenses_bp.route('/api/expenses', methods=['POST'])
@admin_required
def create_expense():
    data = request.json or {}
    required = ['title', 'amount']
    if missing := [f for f in required if not data.get(f)]:
        return jsonify({'error': f'Missing: {", ".join(missing)}'}), 400

    exp = Expense(
        title=data['title'].strip(),
        amount=float(data['amount']),
        category=data.get('category', 'Other'),
        note=data.get('note', '').strip() or None,
        expense_date=datetime.strptime(data['expense_date'], '%Y-%m-%d') if data.get('expense_date') else datetime.utcnow(),
    )
    db.session.add(exp)
    db.session.commit()
    return jsonify({'id': exp.id, 'message': 'Expense recorded'}), 201


@expenses_bp.route('/api/expenses/<int:exp_id>', methods=['PUT'])
@admin_required
def update_expense(exp_id):
    exp = Expense.query.get_or_404(exp_id)
    data = request.json or {}
    for field in ['title', 'amount', 'category', 'note']:
        if field in data:
            setattr(exp, field, data[field])
    if 'expense_date' in data:
        exp.expense_date = datetime.strptime(data['expense_date'], '%Y-%m-%d')
    db.session.commit()
    return jsonify({'message': 'Updated'})


@expenses_bp.route('/api/expenses/<int:exp_id>', methods=['DELETE'])
@admin_required
def delete_expense(exp_id):
    exp = Expense.query.get_or_404(exp_id)
    db.session.delete(exp)
    db.session.commit()
    return jsonify({'message': 'Deleted'})


@expenses_bp.route('/api/expenses/summary', methods=['GET'])
@admin_required
def expenses_summary():
    from sqlalchemy import func
    rows = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).group_by(Expense.category).all()

    total_all = sum(r.total for r in rows)
    return jsonify({
        'by_category': [{'category': r.category or 'Other', 'total': float(r.total)} for r in rows],
        'total': total_all,
    })
