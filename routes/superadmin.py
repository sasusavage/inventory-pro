"""
Super Admin blueprint — platform-level management.
Only accessible to users with role='super_admin'.
Routes:
  GET  /superadmin/             — dashboard (MRR, tenant count, plan dist)
  GET  /superadmin/tenants      — list all organisations
  GET  /superadmin/tenants/<id> — tenant detail + module toggles
  POST /superadmin/tenants/<id>/modules — update module enabled/disabled
  POST /superadmin/tenants/<id>/suspend — toggle is_active
  GET  /superadmin/plans        — list/edit plans
"""
from functools import wraps
from flask import Blueprint, render_template, request, jsonify, session
from models import db, Organisation, User, TenantModule, Plan, Subscription, AVAILABLE_MODULES, DEFAULT_MODULES

superadmin_bp = Blueprint('superadmin', __name__, url_prefix='/superadmin')


def super_admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'super_admin':
            if request.is_json or request.path.startswith('/superadmin/api'):
                return jsonify({'error': 'Super admin access required'}), 403
            return render_template('errors/403.html'), 403
        return f(*args, **kwargs)
    return wrapper


@superadmin_bp.route('/')
@super_admin_required
def dashboard():
    return render_template('superadmin/dashboard.html')


@superadmin_bp.route('/tenants')
@super_admin_required
def tenants_page():
    return render_template('superadmin/tenants.html')


@superadmin_bp.route('/tenants/<int:org_id>')
@super_admin_required
def tenant_detail(org_id):
    org = Organisation.query.get_or_404(org_id)
    return render_template('superadmin/tenant_detail.html', org=org,
                           available_modules=AVAILABLE_MODULES,
                           default_modules=DEFAULT_MODULES)


# ── API ───────────────────────────────────────────────────────────────────────

@superadmin_bp.route('/api/stats')
@super_admin_required
def api_stats():
    from sqlalchemy import func
    total_tenants  = Organisation.query.count()
    active_tenants = Organisation.query.filter_by(is_active=True).count()
    total_users    = User.query.count()

    plan_dist = (
        db.session.query(Plan.name, db.func.count(Subscription.id).label('cnt'))
        .join(Subscription, Subscription.plan_id == Plan.id)
        .filter(Subscription.status == 'active')
        .group_by(Plan.name)
        .all()
    )

    return jsonify({
        'total_tenants':  total_tenants,
        'active_tenants': active_tenants,
        'total_users':    total_users,
        'plan_distribution': [{'plan': r.name, 'count': r.cnt} for r in plan_dist],
    })


@superadmin_bp.route('/api/tenants')
@super_admin_required
def api_tenants():
    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    search   = request.args.get('search', '').strip()

    q = Organisation.query
    if search:
        q = q.filter(Organisation.name.ilike(f'%{search}%') | Organisation.slug.ilike(f'%{search}%'))

    pag = q.order_by(Organisation.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'data': [{
            'id':         org.id,
            'name':       org.name,
            'slug':       org.slug,
            'currency':   org.currency,
            'country':    org.country,
            'is_active':  org.is_active,
            'created_at': org.created_at.isoformat() if org.created_at else None,
            'user_count': User.query.filter_by(organisation_id=org.id).count(),
        } for org in pag.items],
        'pagination': {
            'page': pag.page, 'pages': pag.pages,
            'total': pag.total, 'per_page': per_page,
        }
    })


@superadmin_bp.route('/api/tenants/<int:org_id>')
@super_admin_required
def api_tenant_detail(org_id):
    org = Organisation.query.get_or_404(org_id)
    enabled = TenantModule.enabled_set(org_id)
    modules = {m: (m in enabled) for m in AVAILABLE_MODULES}
    users = User.query.filter_by(organisation_id=org_id).all()

    return jsonify({
        'id':         org.id,
        'name':       org.name,
        'slug':       org.slug,
        'currency':   org.currency,
        'country':    org.country,
        'is_active':  org.is_active,
        'created_at': org.created_at.isoformat() if org.created_at else None,
        'modules':    modules,
        'users': [{
            'id':       u.id,
            'username': u.username,
            'role':     u.role,
            'is_active': u.is_active,
        } for u in users],
    })


@superadmin_bp.route('/api/tenants/<int:org_id>/modules', methods=['POST'])
@super_admin_required
def api_update_modules(org_id):
    Organisation.query.get_or_404(org_id)
    data = request.json or {}
    # data = { "pos": true, "loyalty": false, ... }
    updated = []
    for module, enabled in data.items():
        if module in AVAILABLE_MODULES:
            TenantModule.set_module(org_id, module, bool(enabled))
            updated.append(module)
    db.session.commit()
    return jsonify({'message': f'Updated {len(updated)} module(s)', 'updated': updated})


@superadmin_bp.route('/api/tenants/<int:org_id>/suspend', methods=['POST'])
@super_admin_required
def api_suspend_tenant(org_id):
    org = Organisation.query.get_or_404(org_id)
    org.is_active = not org.is_active
    db.session.commit()
    state = 'activated' if org.is_active else 'suspended'
    return jsonify({'message': f'Tenant {state}', 'is_active': org.is_active})


@superadmin_bp.route('/api/plans')
@super_admin_required
def api_plans():
    plans = Plan.query.order_by(Plan.price_monthly).all()
    return jsonify([{
        'id':            p.id,
        'name':          p.name,
        'slug':          p.slug,
        'price_monthly': p.price_monthly,
        'max_branches':  p.max_branches,
        'max_users':     p.max_users,
        'max_products':  p.max_products,
        'max_customers': p.max_customers,
        'is_active':     p.is_active,
    } for p in plans])
