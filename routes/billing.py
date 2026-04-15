"""
Billing & Plan Management — tenant-facing.
Routes:
  GET  /billing          — current plan, usage, upgrade options
  POST /billing/upgrade  — record plan change (manual/Paystack webhook)
  GET  /billing/history  — payment history
"""
from flask import Blueprint, render_template, request, jsonify, session, g
from models import db, Organisation, Plan, Subscription, BillingRecord
from decorators import login_required

billing_bp = Blueprint('billing', __name__)


def _get_subscription(org_id):
    return (Subscription.query
            .filter_by(organisation_id=org_id)
            .order_by(Subscription.id.desc())
            .first())


def _get_usage(org_id):
    """Return current usage counts for the org."""
    from models import Product, User, Branch
    return {
        'products':  Product.query.filter_by(organisation_id=org_id).count(),
        'users':     User.query.filter_by(organisation_id=org_id).count(),
        'branches':  Branch.query.filter_by(organisation_id=org_id).count(),
    }


@billing_bp.route('/billing')
@login_required
def billing_page():
    if session.get('role') not in ('admin', 'owner', 'super_admin'):
        return "Owners only", 403
    return render_template('billing.html')


@billing_bp.route('/api/billing/status')
@login_required
def billing_status():
    org_id = g.org_id
    sub    = _get_subscription(org_id)
    plans  = Plan.query.filter_by(is_active=True).order_by(Plan.price_monthly).all()
    usage  = _get_usage(org_id)
    org    = Organisation.query.get(org_id)

    current_plan = None
    if sub and sub.plan:
        p = sub.plan
        current_plan = {
            'id':            p.id,
            'name':          p.display_name,
            'price_monthly': p.price_monthly,
            'max_branches':  p.max_branches,
            'max_staff':     p.max_staff,
            'max_products':  p.max_products,
        }

    return jsonify({
        'org':          {'id': org.id, 'name': org.name, 'currency': org.currency} if org else {},
        'subscription': {
            'status':      sub.status if sub else 'none',
            'expires_at':  sub.expires_at.isoformat() if sub and sub.expires_at else None,
            'trial_ends':  sub.trial_ends_at.isoformat() if sub and sub.trial_ends_at else None,
            'days_remaining': sub.days_remaining if sub else None,
        } if sub else {'status': 'none'},
        'current_plan': current_plan,
        'usage':        usage,
        'plans': [{
            'id':            p.id,
            'name':          p.display_name,
            'price_monthly': p.price_monthly,
            'max_branches':  p.max_branches,
            'max_staff':     p.max_staff,
            'max_products':  p.max_products,
            'trial_days':    p.trial_days,
            'sort_order':    p.sort_order,
            'is_active':     p.is_active,
        } for p in plans],
    })


@billing_bp.route('/api/billing/history')
@login_required
def billing_history():
    org_id = g.org_id
    records = (BillingRecord.query
               .filter_by(organisation_id=org_id)
               .order_by(BillingRecord.created_at.desc())
               .limit(50).all())
    return jsonify([{
        'id':             r.id,
        'amount':         r.amount,
        'currency':       r.currency,
        'status':         r.status,
        'payment_method': r.payment_method,
        'description':    r.description,
        'created_at':     r.created_at.isoformat(),
    } for r in records])


@billing_bp.route('/api/billing/upgrade', methods=['POST'])
@login_required
def upgrade_plan():
    """
    For now: manual plan switch by owner/admin.
    In production this would be triggered by a Paystack webhook.
    """
    if session.get('role') not in ('admin', 'owner', 'super_admin'):
        return jsonify({'error': 'Owners only'}), 403

    data    = request.json or {}
    plan_id = data.get('plan_id')
    if not plan_id:
        return jsonify({'error': 'plan_id required'}), 400

    plan = Plan.query.get_or_404(plan_id)
    org_id = g.org_id

    try:
        from datetime import datetime, timedelta
        sub = _get_subscription(org_id)
        if sub:
            sub.plan_id    = plan.id
            sub.status     = 'active'
            sub.started_at = datetime.utcnow()
            sub.expires_at = datetime.utcnow() + timedelta(days=30)
        else:
            sub = Subscription(
                organisation_id=org_id,
                plan_id=plan.id,
                status='active',
                billing_cycle='monthly',
                started_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
            db.session.add(sub)

        # Record the billing event
        db.session.add(BillingRecord(
            organisation_id=org_id,
            plan_id=plan.id,
            amount=plan.price_monthly,
            currency='GHS',
            status='success',
            payment_method='manual',
            description=f'Upgrade to {plan.display_name}',
        ))
        db.session.commit()
        return jsonify({'message': f'Upgraded to {plan.display_name}', 'plan': plan.display_name})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'Failed to upgrade plan'}), 500


# ── Plan limit enforcement helper ─────────────────────────────────────────────

def check_plan_limit(org_id, resource: str) -> tuple[bool, str]:
    """
    Returns (allowed: bool, error_message: str).
    Call before creating products, users, or branches.
    resource: 'products' | 'users' | 'branches' | 'customers'
    """
    sub = _get_subscription(org_id)
    if not sub or not sub.plan:
        # No subscription — use free tier defaults
        limits = {'products': 50, 'users': 2, 'branches': 1, 'customers': 200}
    else:
        p = sub.plan
        limits = {
            'products':  p.max_products,
            'users':     p.max_staff,
            'branches':  p.max_branches,
            'customers': 999999,  # no customer limit in current plan model
        }

    usage = _get_usage(org_id)
    limit = limits.get(resource, 999999)

    # 999 is the sentinel for "unlimited" (Enterprise)
    if limit >= 999:
        return True, ''

    current = usage.get(resource, 0)
    if current >= limit:
        return False, (
            f"You've reached your plan limit of {limit} {resource}. "
            f"Upgrade your plan to add more."
        )
    return True, ''
