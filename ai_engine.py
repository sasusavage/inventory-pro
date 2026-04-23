"""
AI Engine — Segmented for Multi-Tenancy.
Powered by Groq.

Responsibilities:
  • Build rich, ISOLATED business context per organisation.
  • Generate insights and reports scoped only to the tenant's data.

Isolation Rule:
  Every query MUST be filtered by organisation_id. No tenant can see another's data.
"""

import os
import time
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ── Multi-tenant in-memory cache ──────────────────────────────────────────────
_context_cache: dict = {}   # key: "org_id:biz_context" → {data, expires}
CONTEXT_TTL  = 10 * 60      # 10 minutes


def _cached(org_id: int, key: str, ttl: int, builder):
    cache_key = f"{org_id}:{key}"
    now = time.time()
    if cache_key in _context_cache and _context_cache[cache_key]["expires"] > now:
        return _context_cache[cache_key]["data"]
    
    data = builder(org_id)
    _context_cache[cache_key] = {"data": data, "expires": now + ttl}
    return data


def invalidate_ai_cache(org_id: int = None):
    """Invalidate cache for a specific org or all if None."""
    if org_id:
        keys_to_del = [k for k in _context_cache if k.startswith(f"{org_id}:")]
        for k in keys_to_del: _context_cache.pop(k, None)
    else:
        _context_cache.clear()


# ── Segmented Business context builder ────────────────────────────────────────

def build_business_context(org_id: int) -> dict:
    """Pull live data for a specific organisation and return a structured dict."""
    return _cached(org_id, "biz_context", CONTEXT_TTL, _fetch_context)


def _fetch_context(org_id: int) -> dict:
    from sqlalchemy import func
    from models import db, Product, Sale, SaleItem, Customer, StockMovement

    now   = datetime.utcnow()
    d7    = now - timedelta(days=7)
    d30   = now - timedelta(days=30)

    # ── Sales aggregates (Filtered by org) ──────────────────────────────
    def sales_agg(since):
        return db.session.query(
            func.count(Sale.id).label("count"),
            func.coalesce(func.sum(Sale.total_amount),  0).label("revenue"),
            func.coalesce(func.sum(Sale.amount_paid),   0).label("collected"),
            func.coalesce(func.sum(Sale.balance_due),   0).label("outstanding"),
        ).filter(Sale.organisation_id == org_id, Sale.sale_date >= since).one()

    agg7  = sales_agg(d7)
    agg30 = sales_agg(d30)

    # ── Top products by revenue (Filtered by org) ──────────────────────
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label("units_sold"),
        func.sum(SaleItem.subtotal).label("revenue"),
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale,     Sale.id == SaleItem.sale_id)\
     .filter(Product.organisation_id == org_id, Sale.sale_date >= d30, SaleItem.status == "Active")\
     .group_by(Product.id, Product.name)\
     .order_by(func.sum(SaleItem.subtotal).desc())\
     .limit(10).all()

    # ── Low Stock (Filtered by org) ────────────────────────────────────
    low_stock = Product.query.filter(
        Product.organisation_id == org_id,
        Product.quantity_in_stock <= Product.min_stock_level
    ).all()

    # ── Days-to-stockout (Velocity calculated per org) ────────────────
    velocity = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label("units"),
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale,     Sale.id == SaleItem.sale_id)\
     .filter(Product.organisation_id == org_id, Sale.sale_date >= d30, SaleItem.status == "Active")\
     .group_by(Product.id, Product.name).all()

    velocity_map = {r.name: round(r.units / 30, 2) for r in velocity}
    stockout_risk = []
    for p in low_stock:
        daily = velocity_map.get(p.name, 0)
        days  = round(p.quantity_in_stock / daily, 1) if daily > 0 else None
        stockout_risk.append({"name": p.name, "stock": p.quantity_in_stock, "days": days})

    # ── AR & Debtors (Filtered by org) ────────────────────────────────
    total_ar = db.session.query(func.coalesce(func.sum(Sale.balance_due), 0))\
                 .filter(Sale.organisation_id == org_id).scalar()
    debtors_count = db.session.query(func.count(func.distinct(Sale.customer_id)))\
                              .filter(Sale.organisation_id == org_id, Sale.balance_due > 0).scalar()

    # ── Recent Movements (Filtered by org) ───────────────────────────
    movements = StockMovement.query.filter_by(organisation_id=org_id)\
                             .order_by(StockMovement.timestamp.desc()).limit(10).all()

    return {
        "org_id": org_id,
        "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "sales": {
            "last_7_days":  {"orders": agg7.count, "revenue": round(float(agg7.revenue), 2)},
            "last_30_days": {"orders": agg30.count, "revenue": round(float(agg30.revenue), 2)},
        },
        "top_products_30d": [{"name": r.name, "revenue": round(float(r.revenue), 2)} for r in top_products],
        "stock": {
            "low_stock_count": len(low_stock),
            "at_risk": stockout_risk,
        },
        "finance": {
            "accounts_receivable": round(float(total_ar), 2),
            "debtors_count": debtors_count,
        },
        "recent_movements": [
            {"product": m.product.name, "change": m.quantity_change, "reason": m.reason}
            for m in movements
        ],
    }


# ── AI Logic ──────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are InventoryPro AI — a CFO-level assistant.
You have real-time access to the JSON business data provided for this SPECIFIC organisation.
You must analyze ONLY the provided data.
Tone: concise, direct, helpful.
"""

def _groq_client():
    from groq import Groq
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key: raise RuntimeError("Missing GROQ_API_KEY")
    return Groq(api_key=api_key)


def ask_ai(org_id: int, user_message: str, context: dict | None = None, for_telegram: bool = False) -> str:
    """Send a query to the AI using the global Platform Key but Segmented Tenant Data."""
    if context is None:
        context = build_business_context(org_id)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"DATA: {json.dumps(context)}\n\nQuestion: {user_message}"}
    ]

    try:
        client = _groq_client()
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            temperature=0.7,
            max_completion_tokens=1024
        )
        return completion.choices[0].message.content or "No response."
    except Exception as e:
        return f"AI Error: {e}"


def get_insights(org_id: int) -> dict:
    """Generate structured dashboard insights for an organisation."""
    context = build_business_context(org_id)
    prompt = "Analyze this data and return JSON with keys: summary, health_rating, top_insights (list), urgent_actions (list)."
    raw = ask_ai(org_id, prompt, context=context)
    
    try:
        # Clean markdown if present
        if "```" in raw: raw = raw.split("```")[1].replace("json", "").strip()
        return json.loads(raw)
    except:
        return {"summary": "Analysis currently unavailable.", "health_rating": "AMBER", "top_insights": [], "urgent_actions": []}


def get_predictions(org_id: int) -> str:
    """Tenant-specific predictions."""
    return ask_ai(org_id, "Predict revenue and stockout risks for the next 7 days based on this data.", for_telegram=True)

def get_system_health(org_id: int) -> str:
    """Tenant-specific health report."""
    return ask_ai(org_id, "Give a concise RED/AMBER/GREEN health report for my shop.", for_telegram=True)
