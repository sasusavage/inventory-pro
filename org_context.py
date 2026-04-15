"""
org_context.py — Multi-tenant organisation context middleware.

Org resolution priority (first match wins):
  1. session['org_id']       — already authenticated user
  2. Custom domain            — e.g. pos.myshop.com (domain_verified=True)
  3. Subdomain                — e.g. shopname.inventorypro.app (matched by slug)
  4. Fall back to org 1       — local dev / direct IP access

Sets g.org_id, g.org, g.enabled_modules on every request.
Injects enabled_modules + convenience booleans into every Jinja2 template.
"""
import os
from flask import g, session, request
from functools import wraps

# The platform's own base domain, e.g. "inventorypro.app"
# Set PLATFORM_DOMAIN env var in production. Defaults to localhost for dev.
_PLATFORM_DOMAIN = os.environ.get('PLATFORM_DOMAIN', 'inventorypro.app').lower()


def _resolve_org_from_host(host: str):
    """
    Given a Host header value (without port), return the matching Organisation
    or None.

    Handles:
      shopname.inventorypro.app   → look up by slug='shopname'
      pos.myshop.com              → look up by custom_domain='pos.myshop.com'
      inventorypro.app            → platform root, no org
      localhost / 127.0.0.1       → no org (dev)
    """
    from models import Organisation

    host = host.lower().strip()

    # Strip port if present
    if ':' in host:
        host = host.split(':')[0]

    # Skip localhost / bare IP — dev mode
    if host in ('localhost', '127.0.0.1', '0.0.0.0') or host.startswith('192.168.'):
        return None

    # Check for subdomain of our platform domain
    # e.g. host = "shopname.inventorypro.app", _PLATFORM_DOMAIN = "inventorypro.app"
    if host.endswith('.' + _PLATFORM_DOMAIN):
        subdomain = host[: -(len(_PLATFORM_DOMAIN) + 1)]  # strip ".inventorypro.app"
        # Only one level of subdomain is meaningful (not "a.b.inventorypro.app")
        if subdomain and '.' not in subdomain:
            return Organisation.query.filter_by(slug=subdomain, is_active=True).first()
        return None

    # Platform root itself — no tenant
    if host == _PLATFORM_DOMAIN or host == 'www.' + _PLATFORM_DOMAIN:
        return None

    # Any other hostname → try as a verified custom domain
    return Organisation.query.filter_by(
        custom_domain=host, domain_verified=True, is_active=True
    ).first()


def init_org_context(app):
    """Register before_request + context_processor on the Flask app."""

    @app.before_request
    def _load_org():
        from models import Organisation, TenantModule

        org_id = session.get('org_id')

        # If no session org_id, try to resolve from Host header
        if not org_id:
            host = request.host or ''
            org = _resolve_org_from_host(host)
            if org:
                org_id = org.id

        g.org_id = org_id or 1  # fall back to org 1

        try:
            g.org = Organisation.query.get(g.org_id)
        except Exception:
            g.org = None

        try:
            g.enabled_modules = TenantModule.enabled_set(g.org_id)
        except Exception:
            from models import DEFAULT_MODULES
            g.enabled_modules = frozenset(DEFAULT_MODULES)

    @app.context_processor
    def _inject_org_context():
        enabled = getattr(g, 'enabled_modules', frozenset())
        org     = getattr(g, 'org', None)
        return {
            'enabled_modules':      enabled,
            'current_org':          org,
            'platform_domain':      _PLATFORM_DOMAIN,
            'mod_pos':              'pos'               in enabled,
            'mod_inventory':        'inventory'         in enabled,
            'mod_purchase_orders':  'purchase_orders'   in enabled,
            'mod_customers':        'customers'         in enabled,
            'mod_loyalty':          'loyalty'           in enabled,
            'mod_suppliers':        'suppliers'         in enabled,
            'mod_expenses':         'expenses'          in enabled,
            'mod_reports':          'reports'           in enabled,
            'mod_ai_analytics':     'ai_analytics'      in enabled,
            'mod_refunds':          'refunds'           in enabled,
            'mod_categories':       'categories'        in enabled,
            'mod_stock_adj':        'stock_adjustments' in enabled,
            'mod_telegram':         'telegram'          in enabled,
            'mod_activity_log':     'activity_log'      in enabled,
            'mod_multi_branch':     'multi_branch'      in enabled,
            'mod_pnl_report':       'pnl_report'        in enabled,
            'mod_top_customers':    'top_customers'     in enabled,
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
