"""
org_context.py — Multi-tenant organisation context middleware.

Sets g.org_id, g.org, g.enabled_modules on every request.
Injects `enabled_modules` into all Jinja2 templates automatically.
"""
from flask import g, session, request
from functools import wraps


def init_org_context(app):
    """Register before_request + context_processor on the Flask app."""

    @app.before_request
    def _load_org():
        """Resolve which organisation this request belongs to."""
        from models import Organisation, TenantModule

        # Super-admin requests carry org_id in session set at login
        org_id = session.get('org_id')

        # Future: resolve org by subdomain / custom domain
        # host = request.host.split(':')[0]
        # org = Organisation.query.filter_by(subdomain=host).first()
        # if org: org_id = org.id

        g.org_id = org_id or 1  # fall back to org 1 (existing shop)

        # Cache Organisation row
        try:
            g.org = Organisation.query.get(g.org_id)
        except Exception:
            g.org = None

        # Load enabled modules set (frozenset for O(1) lookup)
        try:
            g.enabled_modules = TenantModule.enabled_set(g.org_id)
        except Exception:
            from models import DEFAULT_MODULES
            g.enabled_modules = frozenset(DEFAULT_MODULES)

    @app.context_processor
    def _inject_org_context():
        """Make org info and module flags available in every template."""
        enabled = getattr(g, 'enabled_modules', frozenset())
        org = getattr(g, 'org', None)
        return {
            'enabled_modules': enabled,
            'current_org': org,
            # Convenience booleans for the most-used nav guards
            'mod_pos':              'pos'              in enabled,
            'mod_inventory':        'inventory'        in enabled,
            'mod_purchase_orders':  'purchase_orders'  in enabled,
            'mod_customers':        'customers'        in enabled,
            'mod_loyalty':          'loyalty'          in enabled,
            'mod_suppliers':        'suppliers'        in enabled,
            'mod_expenses':         'expenses'         in enabled,
            'mod_reports':          'reports'          in enabled,
            'mod_ai_analytics':     'ai_analytics'     in enabled,
            'mod_refunds':          'refunds'          in enabled,
            'mod_categories':       'categories'       in enabled,
            'mod_stock_adj':        'stock_adjustments' in enabled,
            'mod_telegram':         'telegram'         in enabled,
            'mod_activity_log':     'activity_log'     in enabled,
            'mod_multi_branch':     'multi_branch'     in enabled,
            'mod_pnl_report':       'pnl_report'       in enabled,
            'mod_top_customers':    'top_customers'    in enabled,
        }


def module_required(module_name):
    """Route decorator — returns 403 JSON if module is disabled for current org."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from flask import jsonify
            enabled = getattr(g, 'enabled_modules', frozenset())
            if module_name not in enabled:
                return jsonify({'error': f'Module "{module_name}" is not enabled for your account.'}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator
