# InventoryPro

A full-featured inventory management system built with Flask and PostgreSQL. Designed for small-to-medium retail businesses with real-time AI analytics, Telegram bot integration, granular role-based access control, and a clean modern UI.

---

## Features

### Core Modules
| Module | Description |
|---|---|
| **Dashboard** | KPI cards, revenue charts, low-stock widget (auto-refreshes every 60s) |
| **POS** | Point-of-sale terminal for quick sales entry |
| **Products** | CRUD with image upload, SKU, cost/selling price, min stock level |
| **Sales** | Paginated sales list, search, status filter, date range, CSV export |
| **Purchase Orders** | Supplier PO workflow with status tracking |
| **Customers** | Customer profiles, outstanding balance view, Pay Balance modal with installment support |
| **Suppliers** | Supplier directory linked to purchase orders |
| **Refunds** | Refund processing tied to sale items |
| **Reports** | Debtors report, stock report (CSV export) |
| **AI Analytics** | Groq-powered business intelligence dashboard with 6 charts and live chat |
| **User Permissions** | Granular RBAC — per-user toggles for every module |
| **Settings** | Telegram credentials, store name/currency, sale notification toggle |

### AI Intelligence Layer
- **Business context engine** — queries sales (7/30/90d), stock velocity, days-to-stockout, AR balances, gross profit, slow movers
- **Structured insights** — health rating (GREEN/AMBER/RED), top insights, urgent actions, 7-day revenue forecast
- **Live AI chat** — ask any business question in natural language; powered by Groq `openai/gpt-oss-120b`
- **10-minute context cache** — avoids hammering the DB on every AI request
- **Cache auto-invalidation** on any write operation

### Telegram Bot
- Responds only to your configured `TELEGRAM_CHAT_ID`
- Commands:
  - `/health` — system health report
  - `/stock` — low/out-of-stock summary
  - `/sales` — today's sales summary
  - `/predict` — 7-day revenue forecast
  - `/context` — raw business context snapshot
  - `/help` — command list
- Any other message → free-form AI Q&A about your business
- Webhook-based (no polling), registered via `POST /telegram/set-webhook`

### Notifications
- **Low-stock Telegram alerts** fire automatically whenever stock drops to/below `min_stock_level`
- **Sale summary alerts** (toggle on/off in Settings)
- All alerts are non-blocking (daemon thread) — never slow down a sale

### Security
- Session-based auth with `Flask-Limiter` (10 login attempts / minute)
- Granular RBAC: `can_view_sales`, `can_view_pos`, `can_view_products`, `can_view_reports`, `can_manage_products`, `can_manage_sales`
- `login_required` / `admin_required` / `permission_required` decorators on every route
- File upload size capped at 5 MB
- All secrets in environment variables — nothing hardcoded

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask 3.0 (Blueprint/app-factory pattern) |
| Database | PostgreSQL via SQLAlchemy 2.0 |
| AI | Groq API — `openai/gpt-oss-120b` |
| Telegram | Telegram Bot API (stdlib `urllib` only, no SDK) |
| Charts | Chart.js (CDN) |
| Icons | Lucide Icons (CDN) |
| Rate Limiting | Flask-Limiter |
| Production Server | Gunicorn via `wsgi.py` |
| Deployment | Coolify + Nixpacks |

---

## Project Structure

```
inventort/
├── app.py                  # App factory — create_app(), _seed_default_users()
├── wsgi.py                 # Gunicorn entry point
├── config.py               # All config from env vars
├── models.py               # SQLAlchemy models + AppSetting key-value store
├── decorators.py           # login_required, admin_required, permission_required
├── extensions.py           # Flask-Limiter instance
├── notifications.py        # Telegram alert helpers (non-blocking)
├── ai_engine.py            # Groq AI brain — context builder, insights, chat
├── telegram_bot.py         # Telegram webhook Blueprint + command handlers
├── utils.py                # log_stock_movement(), low-stock trigger
├── Procfile                # web: gunicorn wsgi:app ...
├── requirements.txt
├── .env.example
│
├── routes/
│   ├── auth.py
│   ├── dashboard.py
│   ├── products.py
│   ├── sales.py
│   ├── customers.py
│   ├── suppliers.py
│   ├── purchase_orders.py
│   ├── refunds.py
│   ├── reports.py
│   ├── users.py
│   ├── settings.py
│   ├── ai.py               # /api/ai/* endpoints
│   └── analytics.py        # /api/analytics/* chart data endpoints
│
├── templates/
│   ├── layout.html         # Base template — sidebar, nav, mobile menu
│   ├── login.html
│   ├── dashboard.html
│   ├── pos.html
│   ├── products.html
│   ├── sales.html
│   ├── customers.html
│   ├── suppliers.html
│   ├── purchase_orders.html
│   ├── refunds.html
│   ├── analytics.html      # AI dashboard — health, charts, live chat
│   ├── users.html
│   ├── settings.html
│   └── errors/
│       ├── 404.html
│       └── 500.html
│
└── static/
    ├── css/style.css       # Clean white/light theme
    └── uploads/            # Product images (auto-created)
```

---

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/sasusavage/inventory-pro.git
cd inventory-pro
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/inventory_db
SECRET_KEY=your-long-random-secret-key
FLASK_ENV=production
FLASK_DEBUG=False
GROQ_API_KEY=gsk_...
TELEGRAM_BOT_TOKEN=1234567890:AA...
TELEGRAM_CHAT_ID=123456789
TELEGRAM_WEBHOOK_SECRET=your-random-secret
```

### 3. Run (Development)

```bash
python app.py
```

Seeds two default users on first run:
- **admin_pro** / `adminPass2026`
- **sales_pro** / `salesPass2026`

### 4. Run (Production)

```bash
gunicorn wsgi:app --bind 0.0.0.0:5000
```

---

## Deployment (Coolify)

1. Connect your GitHub repo to Coolify
2. Build pack: **Nixpacks** (auto-detected)
3. Add all env vars from `.env.example`
4. Set `FLASK_ENV=production`, `FLASK_DEBUG=False`
5. Deploy — Coolify runs `gunicorn wsgi:app` via `Procfile`

---

## Telegram Bot Setup

**Step 1 — Create the bot**
1. Message **@BotFather** on Telegram
2. Send `/newbot`, follow prompts, copy the token → `TELEGRAM_BOT_TOKEN`

**Step 2 — Get your chat ID**
1. Send `/start` to your bot
2. Visit `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Find `"chat"` → `"id"` → `TELEGRAM_CHAT_ID`

**Step 3 — Register webhook** (after deploying)
```bash
curl -X POST https://yourdomain.com/telegram/set-webhook \
  -H "Content-Type: application/json" \
  -d '{"url": "https://yourdomain.com"}'
```

---

## AI Analytics

The AI Analytics page (`/analytics-page`) includes:
- **Health banner** — GREEN / AMBER / RED rating with reason
- **KPI cards** — revenue (30d), orders, avg order value, AR balance
- **Top insights & urgent actions** — AI-generated bullet points
- **6 charts** — revenue trend, top products, payment breakdown, stock health, debt aging, activity heatmap
- **Live AI chat** — full business context, suggestion chips included

**Key endpoints:**
```
GET  /api/ai/insights              Structured insights (cached 10 min)
POST /api/ai/ask                   { "message": "..." } → AI response
GET  /api/analytics/revenue-trend  Daily revenue last 30 days
GET  /api/analytics/top-products   Top 10 products by revenue
GET  /api/analytics/stock-health   Healthy / low / out of stock counts
GET  /api/analytics/debt-aging     AR aged by time bucket
```

---

## Default Credentials

| Username | Password | Role |
|---|---|---|
| admin_pro | adminPass2026 | admin |
| sales_pro | salesPass2026 | sales |

> Change these immediately after first login via the User Permissions page.
