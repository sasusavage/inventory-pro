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
from flask import Blueprint, render_template, request, jsonify, session, redirect
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


@superadmin_bp.route('/domains')
@super_admin_required
def domains_page():
    import os
    platform_domain = os.environ.get('PLATFORM_DOMAIN', 'inventorypro.app')
    return render_template('superadmin/domains.html', platform_domain=platform_domain)


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
    from datetime import datetime, timedelta

    # Exclude org 2 (Platform Admin / sandbox) from all tenant stats
    real_orgs = Organisation.query.filter(Organisation.id != 2)
    total_tenants  = real_orgs.count()
    active_tenants = real_orgs.filter_by(is_active=True).count()
    total_users    = User.query.filter(User.organisation_id != 2).count()

    # MRR from active subscriptions (real tenants only)
    mrr_row = (
        db.session.query(func.coalesce(func.sum(Plan.price_monthly), 0))
        .join(Subscription, Subscription.plan_id == Plan.id)
        .join(Organisation, Organisation.id == Subscription.organisation_id)
        .filter(Subscription.status == 'active', Organisation.id != 2)
        .scalar()
    )
    mrr = float(mrr_row or 0)

    plan_dist = (
        db.session.query(Plan.display_name, func.count(Subscription.id).label('cnt'))
        .join(Subscription, Subscription.plan_id == Plan.id)
        .join(Organisation, Organisation.id == Subscription.organisation_id)
        .filter(Subscription.status == 'active', Organisation.id != 2)
        .group_by(Plan.display_name)
        .all()
    )

    # New tenants in last 30 days
    thirty_ago = datetime.utcnow() - timedelta(days=30)
    new_tenants = real_orgs.filter(Organisation.created_at >= thirty_ago).count()

    # Recent 5 tenants
    recent = (real_orgs
              .order_by(Organisation.created_at.desc())
              .limit(5).all())

    return jsonify({
        'total_tenants':   total_tenants,
        'active_tenants':  active_tenants,
        'suspended_tenants': total_tenants - active_tenants,
        'total_users':     total_users,
        'mrr':             mrr,
        'new_last_30d':    new_tenants,
        'plan_distribution': [{'plan': r.display_name, 'count': r.cnt} for r in plan_dist],
        'recent_tenants': [{
            'id':        o.id,
            'name':      o.name,
            'slug':      o.slug,
            'is_active': o.is_active,
            'created_at': o.created_at.isoformat() if o.created_at else None,
        } for o in recent],
    })


@superadmin_bp.route('/api/tenants')
@super_admin_required
def api_tenants():
    page     = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 50, type=int), 200)
    search   = request.args.get('search', '').strip()

    q = Organisation.query.filter(Organisation.id != 2)  # exclude Platform Admin org
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


@superadmin_bp.route('/tenants/<int:org_id>/impersonate', methods=['POST'])
@super_admin_required
def impersonate_tenant(org_id):
    """Super admin enters a tenant's workspace. Saves original session so they can exit."""
    org = Organisation.query.get_or_404(org_id)
    # Save the super admin's real identity so we can restore it
    session['impersonating_org_id']    = org_id
    session['impersonating_org_name']  = org.name
    session['real_user_id']            = session.get('user_id')
    session['real_username']           = session.get('username')
    session['real_role']               = session.get('role')
    session['real_org_id']             = session.get('org_id')
    # Switch context to tenant's org
    session['org_id'] = org_id
    # Find an owner/admin user in that org to impersonate, or keep super_admin role
    tenant_admin = User.query.filter_by(organisation_id=org_id, role='owner').first() \
                or User.query.filter_by(organisation_id=org_id).first()
    if tenant_admin:
        session['user_id']  = tenant_admin.id
        session['username'] = tenant_admin.username
        session['role']     = tenant_admin.role
    else:
        session['role'] = 'admin'
    return jsonify({'message': f'Now viewing as {org.name}', 'redirect': '/'})


@superadmin_bp.route('/test-features')
@super_admin_required
def test_features():
    """
    Enter the super-admin's own sandbox (org 2 — Platform Admin) as an admin
    so all modules are visible and testable without touching any real tenant data.
    """
    from flask import redirect, g as _g
    # Sandbox is org 2 (Platform Admin) — super admin's own isolated workspace
    sandbox_org_id = 2
    # Save real super-admin identity so we can exit
    session['impersonating_org_id']   = sandbox_org_id
    session['impersonating_org_name'] = '🧪 Sandbox (Test Mode)'
    session['real_user_id']           = session.get('user_id')
    session['real_username']          = session.get('username')
    session['real_role']              = session.get('role')
    session['real_org_id']            = session.get('org_id')
    # Switch to sandbox org — keep the super admin's own user_id & username
    # but change role to 'admin' so the tenant sidebar renders
    session['org_id'] = sandbox_org_id
    session['role']   = 'admin'
    return redirect('/')


@superadmin_bp.route('/stop-impersonating')
def stop_impersonating():
    """Restore the super admin's real session."""
    if session.get('real_role') == 'super_admin':
        session['user_id']  = session.pop('real_user_id', None)
        session['username'] = session.pop('real_username', None)
        session['role']     = session.pop('real_role', None)
        session['org_id']   = session.pop('real_org_id', None)
        session.pop('impersonating_org_id',   None)
        session.pop('impersonating_org_name', None)
    from flask import redirect
    return redirect('/superadmin/tenants')


@superadmin_bp.route('/api/domains')
@super_admin_required
def api_pending_domains():
    """List all orgs with a custom domain request (verified or pending)."""
    orgs = Organisation.query.filter(
        Organisation.custom_domain.isnot(None)
    ).order_by(Organisation.domain_requested_at.desc()).all()

    return jsonify([{
        'org_id':              o.id,
        'org_name':            o.name,
        'slug':                o.slug,
        'custom_domain':       o.custom_domain,
        'domain_verified':     o.domain_verified,
        'domain_requested_at': o.domain_requested_at.isoformat() if o.domain_requested_at else None,
        'domain_verified_at':  o.domain_verified_at.isoformat() if o.domain_verified_at else None,
    } for o in orgs])


@superadmin_bp.route('/api/domains/<int:org_id>/verify', methods=['POST'])
@super_admin_required
def api_verify_domain(org_id):
    """
    Super admin verifies that the tenant's custom domain CNAME is correct,
    then activates it so the middleware will start routing requests to that org.

    Optionally pass { "force": true } to skip the live DNS check (manual override).
    """
    import socket
    import os
    from datetime import datetime

    org = Organisation.query.get_or_404(org_id)
    if not org.custom_domain:
        return jsonify({'error': 'This org has no custom domain set'}), 400

    data  = request.json or {}
    force = bool(data.get('force', False))

    platform_domain = os.environ.get('PLATFORM_DOMAIN', 'inventorypro.app')
    domain = org.custom_domain

    dns_ok      = False
    dns_detail  = ''

    if not force:
        # Live DNS check: resolve the CNAME/A of the custom domain and compare
        try:
            resolved = socket.getaddrinfo(domain, None)
            platform_resolved = socket.getaddrinfo(platform_domain, None)

            domain_ips   = {r[4][0] for r in resolved}
            platform_ips = {r[4][0] for r in platform_resolved}

            if domain_ips & platform_ips:
                dns_ok     = True
                dns_detail = f'Resolved to {", ".join(domain_ips)} — matches platform'
            else:
                dns_detail = (
                    f'{domain} resolves to {", ".join(domain_ips)}, '
                    f'but platform is at {", ".join(platform_ips)}. '
                    f'DNS not propagated yet.'
                )
        except socket.gaierror as e:
            dns_detail = f'DNS lookup failed: {e}'
    else:
        dns_ok     = True
        dns_detail = 'Manually forced by super admin — DNS check skipped'

    if not dns_ok:
        return jsonify({
            'verified': False,
            'domain':   domain,
            'detail':   dns_detail,
            'hint':     f'Tenant must add a CNAME: {domain} → {platform_domain}',
        }), 422

    # Activate
    org.domain_verified    = True
    org.domain_verified_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'verified': True,
        'domain':   domain,
        'detail':   dns_detail,
        'message':  f'{domain} is now active for {org.name}',
    })


@superadmin_bp.route('/api/domains/<int:org_id>/revoke', methods=['POST'])
@super_admin_required
def api_revoke_domain(org_id):
    """Deactivate a custom domain (keeps the record but marks unverified)."""
    org = Organisation.query.get_or_404(org_id)
    org.domain_verified    = False
    org.domain_verified_at = None
    db.session.commit()
    return jsonify({'message': f'Custom domain {org.custom_domain} deactivated for {org.name}'})


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
