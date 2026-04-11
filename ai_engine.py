"""
AI Engine — powered by Groq (openai/gpt-oss-120b).

Responsibilities:
  • Build rich business context from the live database
  • Answer free-form admin questions with that context
  • Generate insights, predictions, and health reports
  • Cache expensive context builds so the DB isn't hammered on every call

All functions are Flask-context-aware (call inside a request or app context).
"""

import os
import time
import json
from datetime import datetime, timedelta

# ── Simple in-memory cache ────────────────────────────────────────────────────
_context_cache: dict = {}   # key → {data, expires}
CONTEXT_TTL  = 10 * 60      # 10 minutes


def _cached(key: str, ttl: int, builder):
    now = time.time()
    if key in _context_cache and _context_cache[key]["expires"] > now:
        return _context_cache[key]["data"]
    data = builder()
    _context_cache[key] = {"data": data, "expires": now + ttl}
    return data


def invalidate_ai_cache():
    _context_cache.clear()


# ── Business context builder ──────────────────────────────────────────────────

def build_business_context() -> dict:
    """
    Pull live data from the database and return a structured dict.
    Result is cached for CONTEXT_TTL seconds.
    """
    return _cached("biz_context", CONTEXT_TTL, _fetch_context)


def _fetch_context() -> dict:
    from sqlalchemy import func
    from models import db, Product, Sale, SaleItem, Customer, Supplier, SupplierPayment, StockMovement

    now   = datetime.utcnow()
    d7    = now - timedelta(days=7)
    d30   = now - timedelta(days=30)
    d90   = now - timedelta(days=90)

    # ── Sales aggregates ──────────────────────────────────────────────
    def sales_agg(since):
        return db.session.query(
            func.count(Sale.id).label("count"),
            func.coalesce(func.sum(Sale.total_amount),  0).label("revenue"),
            func.coalesce(func.sum(Sale.amount_paid),   0).label("collected"),
            func.coalesce(func.sum(Sale.balance_due),   0).label("outstanding"),
        ).filter(Sale.sale_date >= since).one()

    agg7  = sales_agg(d7)
    agg30 = sales_agg(d30)
    agg90 = sales_agg(d90)

    # ── Top products by revenue (30d) ─────────────────────────────────
    top_products = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label("units_sold"),
        func.sum(SaleItem.subtotal).label("revenue"),
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale,     Sale.id == SaleItem.sale_id)\
     .filter(Sale.sale_date >= d30, SaleItem.status == "Active")\
     .group_by(Product.id, Product.name)\
     .order_by(func.sum(SaleItem.subtotal).desc())\
     .limit(10).all()

    # ── Slow movers (30d) — products with 0 sales ─────────────────────
    sold_ids = {r.product_id for r in
                db.session.query(SaleItem.product_id)
                           .join(Sale)
                           .filter(Sale.sale_date >= d30).all()}
    slow_movers = Product.query.filter(
        Product.id.notin_(sold_ids),
        Product.quantity_in_stock > 0
    ).order_by(Product.quantity_in_stock.desc()).limit(10).all()

    # ── Stock status ──────────────────────────────────────────────────
    low_stock = Product.query.filter(
        Product.quantity_in_stock <= Product.min_stock_level
    ).all()
    out_of_stock = [p for p in low_stock if p.quantity_in_stock <= 0]

    total_stock_value = db.session.query(
        func.coalesce(func.sum(Product.quantity_in_stock * Product.cost_price), 0)
    ).scalar()

    # ── Customer debts ────────────────────────────────────────────────
    total_ar = db.session.query(func.coalesce(func.sum(Sale.balance_due), 0)).scalar()
    debtors_count = db.session.query(func.count(func.distinct(Sale.customer_id)))\
                              .filter(Sale.balance_due > 0).scalar()

    # ── Profit (30d) ─────────────────────────────────────────────────
    profit_row = db.session.query(
        func.coalesce(func.sum(SaleItem.subtotal - SaleItem.cost_price_at_sale * SaleItem.quantity), 0).label("gp"),
        func.coalesce(func.sum(SaleItem.subtotal), 0).label("rev"),
    ).join(Sale).filter(Sale.sale_date >= d30, SaleItem.status == "Active").one()

    # ── Daily sales velocity (last 30 days, per product) ─────────────
    velocity = db.session.query(
        Product.name,
        func.sum(SaleItem.quantity).label("units"),
    ).join(SaleItem, SaleItem.product_id == Product.id)\
     .join(Sale,     Sale.id == SaleItem.sale_id)\
     .filter(Sale.sale_date >= d30, SaleItem.status == "Active")\
     .group_by(Product.id, Product.name).all()

    velocity_map = {r.name: round(r.units / 30, 2) for r in velocity}

    # ── Days-to-stockout for low-stock items ──────────────────────────
    stockout_risk = []
    for p in low_stock:
        daily = velocity_map.get(p.name, 0)
        days  = round(p.quantity_in_stock / daily, 1) if daily > 0 else None
        stockout_risk.append({
            "name": p.name,
            "stock": p.quantity_in_stock,
            "min": p.min_stock_level,
            "daily_velocity": daily,
            "days_to_stockout": days,
        })

    # ── Recent movement summary ───────────────────────────────────────
    movements = StockMovement.query.order_by(
        StockMovement.timestamp.desc()
    ).limit(20).all()

    # ── Total counts ─────────────────────────────────────────────────
    return {
        "generated_at": now.strftime("%Y-%m-%d %H:%M UTC"),
        "sales": {
            "last_7_days":  {"orders": agg7.count,  "revenue": round(float(agg7.revenue),  2), "collected": round(float(agg7.collected),  2), "outstanding": round(float(agg7.outstanding),  2)},
            "last_30_days": {"orders": agg30.count, "revenue": round(float(agg30.revenue), 2), "collected": round(float(agg30.collected), 2), "outstanding": round(float(agg30.outstanding), 2)},
            "last_90_days": {"orders": agg90.count, "revenue": round(float(agg90.revenue), 2), "collected": round(float(agg90.collected), 2), "outstanding": round(float(agg90.outstanding), 2)},
        },
        "top_products_30d": [
            {"name": r.name, "units_sold": int(r.units_sold), "revenue": round(float(r.revenue), 2)}
            for r in top_products
        ],
        "slow_movers_30d": [
            {"name": p.name, "stock": p.quantity_in_stock}
            for p in slow_movers
        ],
        "stock": {
            "low_stock_count": len(low_stock),
            "out_of_stock_count": len(out_of_stock),
            "total_stock_value": round(float(total_stock_value), 2),
            "at_risk": stockout_risk,
        },
        "finance": {
            "accounts_receivable": round(float(total_ar), 2),
            "debtors_count": debtors_count,
            "gross_profit_30d": round(float(profit_row.gp), 2),
            "revenue_30d": round(float(profit_row.rev), 2),
            "margin_30d_pct": round((profit_row.gp / profit_row.rev) * 100, 1) if profit_row.rev else 0,
        },
        "recent_movements": [
            {"product": m.product.name, "change": m.quantity_change, "reason": m.reason,
             "time": m.timestamp.strftime("%Y-%m-%d %H:%M")}
            for m in movements
        ],
    }


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are InventoryPro AI — a smart business intelligence assistant embedded in an inventory management system.

You have real-time access to the following business data (provided in each message):
• Sales trends (7d / 30d / 90d)
• Top-selling and slow-moving products
• Stock levels, low-stock alerts, and stockout risk
• Customer debt (accounts receivable) and debtor count
• Gross profit and margin
• Recent stock movements

Your role:
1. Answer questions about the business in plain, direct language
2. Spot patterns and flag risks the owner might miss
3. Give actionable recommendations (reorder, push promotions, chase debts)
4. When asked to predict, use velocity data + trends — be specific and honest about uncertainty
5. For system health, give a clear RED / AMBER / GREEN rating with reasons

Tone: concise, confident, like a smart CFO/ops advisor. No waffle.
Format for Telegram: plain text, use emoji sparingly.
Format for web: you may use markdown (bold, lists).
"""


# ── Groq call ─────────────────────────────────────────────────────────────────

def _groq_client():
    from groq import Groq
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in environment variables")
    return Groq(api_key=api_key)


def ask_ai(user_message: str, context: dict | None = None, for_telegram: bool = False) -> str:
    """
    Send a question to the AI with business context injected.
    Returns the full response as a string.
    """
    if context is None:
        context = build_business_context()

    fmt_note = "(Reply in plain text for Telegram — no markdown)" if for_telegram else "(You may use markdown.)"

    messages = [
        {
            "role": "system",
            "content": _SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                f"CURRENT BUSINESS DATA:\n```json\n{json.dumps(context, indent=2)}\n```\n\n"
                f"{fmt_note}\n\n"
                f"Question / Command: {user_message}"
            ),
        },
    ]

    try:
        client = _groq_client()
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            temperature=0.7,
            max_completion_tokens=1024,
            top_p=1,
            reasoning_effort="medium",
            stream=False,
            stop=None,
        )
        return completion.choices[0].message.content or "No response generated."
    except Exception as e:
        return f"AI unavailable: {e}"


# ── Pre-built report functions ────────────────────────────────────────────────

def get_insights(context: dict | None = None) -> dict:
    """Return a structured insights object for the analytics dashboard."""
    if context is None:
        context = build_business_context()

    prompt = """Analyse this business data and return a JSON object with EXACTLY these keys:
{
  "summary": "2-3 sentence executive summary of the business state right now",
  "health_rating": "GREEN | AMBER | RED",
  "health_reason": "one line explaining the rating",
  "top_insights": ["insight 1", "insight 2", "insight 3", "insight 4", "insight 5"],
  "urgent_actions": ["action 1", "action 2", "action 3"],
  "revenue_forecast_7d": <number — estimated revenue next 7 days based on trend>,
  "top_risk": "the single biggest risk to the business right now"
}
Return ONLY the JSON, no explanation."""

    raw = ask_ai(prompt, context=context)

    # Strip markdown fences if model wraps the JSON
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except Exception:
        # Fallback if model returns non-JSON
        return {
            "summary": raw[:300],
            "health_rating": "AMBER",
            "health_reason": "Could not parse structured response",
            "top_insights": [],
            "urgent_actions": [],
            "revenue_forecast_7d": 0,
            "top_risk": "Unknown",
        }


def get_system_health(context: dict | None = None) -> str:
    """Full health report — used by Telegram /health command."""
    if context is None:
        context = build_business_context()

    prompt = """Give a full SYSTEM HEALTH REPORT for this business. Cover:
1. Overall rating: RED / AMBER / GREEN (with reason)
2. Sales health (trend up/down, collection rate)
3. Stock health (critical items, days to stockout)
4. Financial health (AR outstanding, profit margin)
5. Top 3 immediate actions the owner must take

Keep it tight — under 300 words. Plain text for Telegram."""
    return ask_ai(prompt, context=context, for_telegram=True)


def get_predictions(context: dict | None = None) -> str:
    """7-day predictions — used by Telegram /predict command."""
    if context is None:
        context = build_business_context()

    prompt = """Based on the sales velocity and trends in this data, predict:
1. Expected revenue for the next 7 days (give a range)
2. Which products will likely hit zero stock in the next 7–14 days (list with estimated date)
3. Which customers are most at risk of going further into debt
4. One opportunity the owner should act on this week

Be specific with numbers. Note uncertainty where data is thin. Plain text."""
    return ask_ai(prompt, context=context, for_telegram=True)


def get_stock_summary(context: dict | None = None) -> str:
    """Stock summary for Telegram /stock command."""
    if context is None:
        context = build_business_context()

    prompt = """Give a concise stock status update:
- How many products are low / out of stock
- Which are most urgent (days to stockout)
- Any slow movers with high stock that need attention
Plain text, under 200 words."""
    return ask_ai(prompt, context=context, for_telegram=True)


def get_sales_summary(context: dict | None = None) -> str:
    """Sales summary for Telegram /sales command."""
    if context is None:
        context = build_business_context()

    prompt = """Summarise recent sales performance:
- Revenue last 7 days vs 30-day average daily rate
- Collection rate (paid vs total)
- Outstanding customer debt
- Top-selling product this month
Plain text, under 200 words."""
    return ask_ai(prompt, context=context, for_telegram=True)
