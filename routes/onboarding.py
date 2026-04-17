"""
Tenant onboarding — public signup endpoint + page.
POST /signup creates: Organisation, Branch, owner User, default TenantModules, AppSettings.
"""
import re
from flask import Blueprint, render_template, request, jsonify, session
from models import db, Organisation, Branch, User, TenantModule, AppSetting, DEFAULT_MODULES, AVAILABLE_MODULES

onboarding_bp = Blueprint('onboarding', __name__)

_SLUG_RE = re.compile(r'[^a-z0-9-]')


def _make_slug(name: str) -> str:
    base = _SLUG_RE.sub('-', name.lower().strip()).strip('-')
    base = re.sub(r'-{2,}', '-', base) or 'shop'
    # Ensure uniqueness
    slug = base
    i = 2
    while Organisation.query.filter_by(slug=slug).first():
        slug = f'{base}-{i}'
        i += 1
    return slug


@onboarding_bp.route('/signup')
def signup_page():
    return render_template('signup.html')


@onboarding_bp.route('/signup', methods=['POST'])
def signup():
    data = request.json or {}

    store_name  = (data.get('store_name') or '').strip()
    owner_name  = (data.get('owner_name') or '').strip()
    username    = (data.get('username') or '').strip().lower()
    password    = data.get('password') or ''
    currency    = (data.get('currency') or 'GHS').strip().upper()
    country     = (data.get('country') or 'Ghana').strip()

    # Validation
    errors = {}
    if not store_name:
        errors['store_name'] = 'Store name is required'
    if not username or len(username) < 3:
        errors['username'] = 'Username must be at least 3 characters'
    if not re.match(r'^[a-z0-9_]+$', username):
        errors['username'] = 'Username: lowercase letters, numbers and _ only'
    if not password or len(password) < 6:
        errors['password'] = 'Password must be at least 6 characters'
    if errors:
        return jsonify({'errors': errors}), 422

    # Username globally unique (super_admin usernames live outside orgs)
    if User.query.filter_by(username=username).first():
        return jsonify({'errors': {'username': 'Username already taken'}}), 409

    try:
        # 1. Create Organisation
        slug = _make_slug(store_name)
        org = Organisation(
            name=store_name,
            slug=slug,
            currency=currency,
            country=country,
            is_active=True,
        )
        db.session.add(org)
        db.session.flush()  # get org.id

        # 2. Create default Branch
        branch = Branch(
            organisation_id=org.id,
            name='Main Branch',
            is_default=True,
            is_active=True,
        )
        db.session.add(branch)
        db.session.flush()

        # 3. Create owner User
        owner = User(
            username=username,
            full_name=owner_name or username,
            role='owner',
            organisation_id=org.id,
            branch_id=branch.id,
            is_active=True,
        )
        owner.set_password(password)
        db.session.add(owner)

        # 4. Enable default modules
        for module in AVAILABLE_MODULES:
            db.session.add(TenantModule(
                organisation_id=org.id,
                module=module,
                is_enabled=(module in DEFAULT_MODULES),
            ))

        # 5. Seed default AppSettings for this org
        defaults = {
            'store_name': store_name,
            'store_currency': currency,
            'store_country': country,
            'notify_on_sale': '0',
            'loyalty_earn_rate': '1',
            'loyalty_redeem_rate': '100',
        }
        for key, value in defaults.items():
            db.session.add(AppSetting(key=key, value=value, organisation_id=org.id))

        db.session.commit()

        # 6. Log them in automatically
        session['user_id']  = owner.id
        session['username'] = owner.username
        session['role']     = owner.role
        session['org_id']   = org.id

        return jsonify({
            'message': 'Account created successfully',
            'org_id': org.id,
            'redirect': '/',
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Registration failed. Please try again.'}), 500


@onboarding_bp.route('/api/demo-request', methods=['POST'])
def demo_request():
    """Public endpoint — store demo booking requests and optionally notify via Telegram."""
    data = request.json or {}
    name     = (data.get('name') or '').strip()
    phone    = (data.get('phone') or '').strip()
    biz_name = (data.get('business_name') or '').strip()
    if not name or not phone or not biz_name:
        return jsonify({'error': 'name, phone, and business_name are required'}), 400

    # Notify via Telegram if configured (org 2 = Platform Admin)
    try:
        from models import AppSetting
        biz_type = data.get('business_type', '—')
        branches = data.get('branches', '—')
        notes    = data.get('notes', '')
        msg = (
            f"📅 <b>New Demo Request</b>\n\n"
            f"👤 <b>{name}</b>\n"
            f"📞 {phone}\n"
            f"🏪 {biz_name} ({biz_type})\n"
            f"🏢 Branches: {branches}\n"
            + (f"📝 {notes}\n" if notes else "")
        )
        from notifications import notify_async
        notify_async(msg)
    except Exception:
        pass  # never block the response

    return jsonify({'message': 'Demo request received'}), 201
