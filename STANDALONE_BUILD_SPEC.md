# Standalone Inventory Management System — Build Spec

> **Purpose:** Strip out all SaaS/multi-tenancy/billing/superadmin logic. Rebuild every tenant-facing module as a standalone, single-organization inventory + POS system. Hand this doc to an agent to do the build.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11+ / Flask 3.0 (Blueprint pattern) |
| Database | PostgreSQL 14+ via SQLAlchemy 2.0 ORM |
| Frontend | HTML5 + Vanilla JS + CSS3 (no frameworks) |
| PDF | ReportLab 4.0+ |
| AI | Groq API (`groq>=0.11.0`) |
| Scheduling | APScheduler 3.10+ |
| SMS | Africa's Talking (optional) |
| Server | Gunicorn (production) |
| Auth | Flask session-based, Werkzeug password hashing |
| Charts | Chart.js via CDN |
| Icons | Lucide via CDN |
| PWA | Service Worker + manifest.json |

---

## Environment Variables (.env)

```env
# ── Core ──────────────────────────────────────────────
DATABASE_URL=postgresql://user:pass@localhost:5432/inventory_db
SECRET_KEY=replace-with-long-random-string
FLASK_ENV=production
FLASK_DEBUG=False

# ── AI (Groq) ─────────────────────────────────────────
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx

# ── Telegram Alerts (optional) ────────────────────────
TELEGRAM_BOT_TOKEN=1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=123456789
TELEGRAM_WEBHOOK_SECRET=random-secret

# ── Server ────────────────────────────────────────────
PORT=5000
```

> **Settings stored in DB** (AppSetting key/value table, editable from UI):
> `store_name`, `store_currency`, `store_address`, `store_phone`, `store_tagline`,
> `telegram_bot_token`, `telegram_chat_id`, `notify_on_sale`,
> `scheduler_daily_report`, `scheduler_report_hour`, `scheduler_weekly_report`,
> `loyalty_earn_rate`, `loyalty_redeem_rate`,
> `sms_enabled`, `sms_username`, `sms_api_key`, `sms_sender_id`

---

## Database Models

All models use SQLAlchemy. No `organisation_id` anywhere — single org, no tenancy.

### User
```
id, username, email, password_hash, role (owner|manager|admin|cashier|sales),
is_active, branch_id (FK),
can_view_sales, can_manage_products, can_view_reports,
can_manage_users, can_manage_purchases, can_manage_expenses,
can_view_analytics, can_manage_refunds, can_manage_transfers,
created_at
```

### Branch
```
id, name, address, phone, is_active, created_at
```

### Category
```
id, name, color, created_at
```

### Product
```
id, name, sku, barcode, description, category_id (FK),
cost_price, selling_price, quantity, damaged_quantity,
min_stock_level, image_filename, is_active,
branch_id (FK), created_at, updated_at
```

### ProductVariant
```
id, product_id (FK), name, sku_suffix, price_adjustment,
quantity, attributes (JSON), is_active, created_at
```

### Customer
```
id, name, phone, email, address,
loyalty_points, outstanding_balance, created_at
```

### Supplier
```
id, name, contact_person, phone, email, address,
total_owed, created_at
```

### Sale
```
id, customer_id (FK nullable), user_id (FK), branch_id (FK),
subtotal, discount_amount, total_amount, amount_paid, balance,
payment_method (cash|momo|card|transfer|split),
status (PAID|PARTIAL|UNPAID), notes,
loyalty_points_earned, loyalty_points_redeemed,
sale_date, created_at
```

### SaleItem
```
id, sale_id (FK), product_id (FK), variant_id (FK nullable),
quantity, unit_price, cost_price, discount_amount, total_price
```

### Refund
```
id, sale_id (FK), sale_item_id (FK), user_id (FK),
quantity, amount, reason, status (pending|approved|rejected),
notes, created_at
```

### Supplier Payment
```
id, supplier_id (FK), user_id (FK), amount, notes, created_at
```

### PurchaseOrder
```
id, supplier_id (FK), user_id (FK), branch_id (FK),
status (pending|partial|received|cancelled),
payment_type (cash|credit), total_amount,
notes, order_date, created_at
```

### PurchaseOrderItem
```
id, purchase_order_id (FK), product_id (FK),
quantity_ordered, quantity_received, unit_cost, total_cost
```

### StockAdjustment
```
id, product_id (FK), user_id (FK), branch_id (FK),
reason (damage|theft|correction|recount|expired|return_to_supplier|other),
quantity_before, quantity_after, quantity_change,
notes, created_at
```

### StockTransfer
```
id, from_branch_id (FK), to_branch_id (FK), user_id (FK),
status (pending|completed|cancelled), notes, created_at
```

### StockTransferItem
```
id, transfer_id (FK), product_id (FK), quantity
```

### StockMovement
```
id, product_id (FK), user_id (FK),
movement_type (sale|purchase|adjustment|transfer_in|transfer_out|refund),
quantity_change, quantity_before, quantity_after,
reference_id, reference_type, notes, created_at
```

### LoyaltyPoint
```
id, customer_id (FK), sale_id (FK nullable),
points, transaction_type (earn|redeem), notes, created_at
```

### Expense
```
id, user_id (FK), category, amount, description,
branch_id (FK nullable), expense_date, created_at
```

### ActivityLog
```
id, user_id (FK nullable), action, entity_type, entity_id,
details (JSON), ip_address, created_at
```

### AppSetting
```
id, key (unique), value, updated_at
```

---

## Flask Application Structure

```
app/
├── __init__.py          # App factory
├── config.py            # Load env vars
├── extensions.py        # db, limiter init
├── models.py            # All SQLAlchemy models
├── decorators.py        # login_required, admin_required, permission_required
├── utils.py             # log_stock_movement(), log_activity(), allowed_file()
├── ai_engine.py         # Groq AI context + insights + chat
├── notifications.py     # Telegram alert sender (daemon thread)
├── telegram_bot.py      # Telegram webhook handler
├── scheduler.py         # APScheduler daily/weekly AI reports, low-stock alerts
├── sms_helper.py        # Africa's Talking SMS receipts
├── org_context.py       # (remove or simplify — no multi-tenancy needed)
│
├── routes/
│   ├── auth.py
│   ├── dashboard.py
│   ├── products.py
│   ├── variants.py
│   ├── categories.py
│   ├── sales.py
│   ├── customers.py
│   ├── suppliers.py
│   ├── purchase_orders.py
│   ├── refunds.py
│   ├── stock_adjustments.py
│   ├── stock_transfers.py
│   ├── expenses.py
│   ├── loyalty.py
│   ├── reports.py
│   ├── analytics.py
│   ├── ai.py
│   ├── eod.py
│   ├── activity.py
│   ├── users.py
│   └── settings.py
│
├── templates/
│   ├── layout.html
│   ├── login.html
│   ├── dashboard.html
│   ├── pos.html
│   ├── products.html
│   ├── categories.html
│   ├── sales.html
│   ├── customers.html
│   ├── suppliers.html
│   ├── purchase_orders.html
│   ├── refunds.html
│   ├── stock_adjustments.html
│   ├── stock_transfers.html
│   ├── expenses.html
│   ├── loyalty.html
│   ├── reports.html
│   ├── analytics.html
│   ├── ai_chat.html
│   ├── eod_report.html
│   ├── activity.html
│   ├── users.html
│   ├── settings.html
│   ├── receipt.html
│   ├── product_label.html
│   ├── customer_statement.html
│   ├── pnl_report.html
│   └── errors/ (403.html, 404.html, 500.html)
│
└── static/
    ├── css/style.css
    ├── manifest.json
    ├── sw.js
    └── uploads/         # product images (auto-created)
```

---

## Module Specs

### 1. Auth (`routes/auth.py`)
- `GET/POST /login` — session login, rate limited (10/min), Werkzeug password check
- `GET /logout` — clear session
- `GET /` → redirect to `/dashboard` if logged in, else `/login`
- Session stores: `user_id`, `username`, `role`, `branch_id`
- On first run with no users: auto-create owner account or show setup wizard

---

### 2. Dashboard (`routes/dashboard.py`)
**Page:** `GET /dashboard`

**API endpoints:**
- `GET /api/dashboard/stats` → `{ total_sales_today, total_revenue_today, total_orders, low_stock_count, stock_value, total_customers, total_ar, total_ap, total_expenses_month }`
- `GET /api/dashboard/low-stock` → products where `quantity <= min_stock_level`
- `GET /api/dashboard/recent-sales` → last 10 sales with customer name, total, status
- `GET /api/dashboard/stock-movements` → last 20 stock movements

KPI cards visible to all. Financial metrics (AR, AP, expenses) visible to admin/owner only.

Cache stats for 5 minutes in memory (invalidate on any write).

---

### 3. Products (`routes/products.py`)
**Page:** `GET /products`

**API:**
- `GET /api/products` — list with search, category filter, branch filter, pagination (50/page)
- `POST /api/products` — create product
- `GET /api/products/<id>` — single product detail
- `PUT /api/products/<id>` — update product
- `DELETE /api/products/<id>` — soft delete (set `is_active=False`)
- `POST /api/products/<id>/image` — upload image (max 5MB, jpg/png/gif/webp only)
- `GET /api/products/search?q=` — quick search by name/SKU/barcode (for POS)
- `GET /api/products/export` — CSV export

Log `StockMovement` on any quantity change. Log `ActivityLog` on create/update/delete.

---

### 4. Product Variants (`routes/variants.py`)
**API:**
- `GET /api/products/<id>/variants` — list variants
- `POST /api/products/<id>/variants` — create variant (name, sku_suffix, price_adjustment, quantity, attributes JSON)
- `PUT /api/products/<id>/variants/<vid>` — update variant
- `DELETE /api/products/<id>/variants/<vid>` — delete variant

---

### 5. Categories (`routes/categories.py`)
**Page:** `GET /categories`

**API:**
- `GET /api/categories` — list all
- `POST /api/categories` — create (name, color)
- `PUT /api/categories/<id>` — update
- `DELETE /api/categories/<id>` — delete (block if products exist in category)

---

### 6. Point of Sale (`routes/sales.py`)
**Page:** `GET /pos`

**API:**
- `POST /api/pos/sale` — create sale
  - Body: `{ customer_id?, items: [{product_id, variant_id?, quantity, unit_price, discount_amount}], payment_method, amount_paid, discount_amount, loyalty_points_redeemed?, notes? }`
  - Decrements product/variant stock
  - Calculates balance, status (PAID/PARTIAL/UNPAID)
  - Awards loyalty points if customer set (rate from AppSetting `loyalty_earn_rate`)
  - Deducts loyalty points if redeemed
  - Updates `customer.outstanding_balance` if PARTIAL/UNPAID
  - Logs StockMovement for each item
  - Triggers Telegram sale notification if enabled
  - Triggers SMS receipt if enabled
  - Returns sale_id for receipt redirect
- `GET /api/pos/receipt/<sale_id>` — generate PDF receipt (ReportLab)
- `GET /api/pos/customer-lookup?q=` — search customers by name/phone

---

### 7. Sales (`routes/sales.py`)
**Page:** `GET /sales`

**API:**
- `GET /api/sales` — list with search, status filter, date range, payment method filter, pagination (50/page)
- `GET /api/sales/<id>` — sale detail with items
- `POST /api/sales/<id>/payment` — add payment to partial/unpaid sale (updates balance, status)
- `GET /api/sales/export` — CSV export
- `GET /api/sales/<id>/receipt` — PDF receipt

---

### 8. Customers (`routes/customers.py`)
**Page:** `GET /customers`

**API:**
- `GET /api/customers` — list with search, pagination
- `POST /api/customers` — create
- `GET /api/customers/<id>` — detail with sales history, loyalty points
- `PUT /api/customers/<id>` — update
- `DELETE /api/customers/<id>` — soft delete
- `POST /api/customers/<id>/pay-balance` — record payment reducing `outstanding_balance`
- `GET /api/customers/<id>/statement` — PDF statement (ReportLab)
- `GET /api/customers/export` — CSV export

---

### 9. Suppliers (`routes/suppliers.py`)
**Page:** `GET /suppliers`

**API:**
- `GET /api/suppliers` — list with search
- `POST /api/suppliers` — create
- `GET /api/suppliers/<id>` — detail with payment history
- `PUT /api/suppliers/<id>` — update
- `DELETE /api/suppliers/<id>` — soft delete
- `POST /api/suppliers/<id>/payment` — record payment (creates SupplierPayment, reduces `total_owed`)

---

### 10. Purchase Orders (`routes/purchase_orders.py`)
**Page:** `GET /purchase-orders`

**API:**
- `GET /api/purchase-orders` — list with status filter, search, pagination
- `POST /api/purchase-orders` — create PO with items
- `GET /api/purchase-orders/<id>` — detail with items
- `PUT /api/purchase-orders/<id>` — update (only if pending)
- `POST /api/purchase-orders/<id>/receive` — receive items (partial or full)
  - Body: `{ items: [{item_id, quantity_received}] }`
  - Increments product stock for each received item
  - Logs StockMovement
  - Updates PO status to `partial` or `received`
  - Updates supplier `total_owed` if credit payment
- `POST /api/purchase-orders/<id>/cancel` — cancel PO

---

### 11. Refunds (`routes/refunds.py`)
**Page:** `GET /refunds`

**API:**
- `GET /api/refunds` — list with status filter, pagination
- `POST /api/refunds` — create refund request (sale_id, sale_item_id, quantity, reason)
- `GET /api/refunds/<id>` — detail
- `POST /api/refunds/<id>/approve` — approve refund (restores stock, logs movement)
- `POST /api/refunds/<id>/reject` — reject refund with reason

---

### 12. Stock Adjustments (`routes/stock_adjustments.py`)
**Page:** `GET /stock-adjustments`

**API:**
- `GET /api/stock-adjustments` — list with reason filter, date range, pagination
- `POST /api/stock-adjustments` — create adjustment
  - Body: `{ product_id, reason, quantity_after, notes }`
  - Calculates `quantity_change = quantity_after - current_quantity`
  - Updates product quantity
  - Logs StockMovement
- `GET /api/stock-adjustments/export` — CSV export

---

### 13. Stock Transfers (`routes/stock_transfers.py`)
**Page:** `GET /stock-transfers`

**API:**
- `GET /api/transfers` — list with status filter, branch filter
- `POST /api/transfers` — create transfer request
  - Body: `{ from_branch_id, to_branch_id, items: [{product_id, quantity}], notes }`
  - Status starts as `pending`
- `GET /api/transfers/<id>` — detail
- `POST /api/transfers/<id>/complete` — complete transfer
  - Deducts stock from source branch products
  - Adds stock to destination branch products
  - Logs StockMovements (transfer_out, transfer_in)
- `POST /api/transfers/<id>/cancel` — cancel

---

### 14. Expenses (`routes/expenses.py`)
**Page:** `GET /expenses`

**API:**
- `GET /api/expenses` — list with category filter, date range, pagination
- `POST /api/expenses` — create
- `PUT /api/expenses/<id>` — update
- `DELETE /api/expenses/<id>` — delete
- `GET /api/expenses/export` — CSV export

---

### 15. Loyalty Program (`routes/loyalty.py`)
**Page:** `GET /loyalty`

**API:**
- `GET /api/loyalty` — list all customers with loyalty balance
- `GET /api/loyalty/transactions` — list all LoyaltyPoint records
- `GET /api/loyalty/customer/<id>` — customer loyalty history
- Earn/redeem logic lives in the POS sale endpoint (not a separate API)

Config (earn rate, redeem rate) stored in AppSetting, editable from settings page.

---

### 16. Reports (`routes/reports.py`)
**Page:** `GET /reports`

**Endpoints:**
- `GET /api/reports/debtors` — customers with outstanding_balance > 0, sorted desc
- `GET /api/reports/stock` — all products with quantity, value (qty × cost), low-stock flag
- `GET /api/reports/pnl?start=&end=` — P&L for date range: total revenue, total COGS, gross profit, total expenses, net profit
- `GET /api/reports/top-customers?limit=10` — customers by total spend
- `GET /api/reports/debtors/export` — CSV
- `GET /api/reports/stock/export` — CSV
- `GET /api/reports/pnl/export` — CSV
- `GET /reports/pnl` — printable P&L HTML page

---

### 17. Analytics (`routes/analytics.py`)
**Page:** `GET /analytics`

**API:**
- `GET /api/analytics/revenue-trend?days=30` — daily revenue for last N days
- `GET /api/analytics/top-products?limit=10` — by revenue and units sold
- `GET /api/analytics/payment-methods` — breakdown by payment method (count + value)
- `GET /api/analytics/stock-health` — count by status (healthy, low, out-of-stock)
- `GET /api/analytics/debt-aging` — AR grouped by age (0-30d, 31-60d, 61-90d, 90d+)
- `GET /api/analytics/activity-heatmap` — sale count by hour of day, day of week

---

### 18. AI Analytics (`routes/ai.py`)
**Page:** `GET /ai` (or embedded in analytics page)

**AI Engine (`ai_engine.py`):**
Build a context object with:
- Sales: today, 7d, 30d, 90d totals + counts
- Top 10 products by revenue (30d)
- Low stock items (below min level)
- AR total (outstanding_balance sum)
- AP total (supplier total_owed sum)
- Gross profit margin (30d)
- Expense total (30d)
- Recent stock adjustments (7d)

Cache context for 10 minutes in memory. Auto-invalidate on any DB write that affects it.

**API:**
- `GET /api/ai/insights` — structured response:
  ```json
  {
    "health_rating": "GREEN|AMBER|RED",
    "health_summary": "...",
    "urgent_actions": ["...", "..."],
    "opportunities": ["...", "..."],
    "revenue_forecast_7d": 12345.00,
    "generated_at": "2026-01-01T00:00:00"
  }
  ```
- `POST /api/ai/chat` — free-form chat with business context injected
  - Body: `{ message: "..." }`
  - Returns: `{ response: "..." }`
- `GET /api/ai/health-report` — full markdown business health report (used by scheduler)

Use Groq API with model: `llama-3.3-70b-versatile` (or latest available).

---

### 19. End-of-Day Report (`routes/eod.py`)
**Page:** `GET /eod`

**API:**
- `GET /api/eod/report?date=YYYY-MM-DD` — EOD data:
  - Total sales count and revenue
  - Breakdown by payment method
  - Discounts given total
  - Top 5 products sold
  - Cash expected vs actual (cashier enters actual)
  - Discrepancy
- `POST /api/eod/submit` — save actual cash count for the day

---

### 20. Activity Log (`routes/activity.py`)
**Page:** `GET /activity`

**API:**
- `GET /api/activity` — list with action filter, user filter, date range, pagination (100/page)

Every sensitive action across the system should call `log_activity(user_id, action, entity_type, entity_id, details, ip_address)`.

---

### 21. Users (`routes/users.py`)
**Page:** `GET /users` (admin/owner only)

**API:**
- `GET /api/users` — list all users
- `POST /api/users` — create user (username, email, password, role, branch_id, permissions)
- `GET /api/users/<id>` — detail
- `PUT /api/users/<id>` — update (including permission flags)
- `POST /api/users/<id>/toggle-active` — activate/deactivate
- `POST /api/users/<id>/reset-password` — admin password reset

Roles: `owner`, `manager`, `admin`, `cashier`, `sales`

Permission flags (boolean columns on User):
`can_view_sales`, `can_manage_products`, `can_view_reports`, `can_manage_users`,
`can_manage_purchases`, `can_manage_expenses`, `can_view_analytics`, `can_manage_refunds`,
`can_manage_transfers`

---

### 22. Settings (`routes/settings.py`)
**Page:** `GET /settings` (owner/admin only)

**Sections:**
1. Store Info — name, currency, address, phone, tagline (saves to AppSetting)
2. Telegram Integration — bot token, chat_id, enable/disable, test webhook button
3. SMS Receipts — Africa's Talking credentials, sender ID, enable/disable
4. Loyalty Config — earn rate (points per currency unit), redeem rate
5. AI Reports — enable daily report, report hour (0-23), enable weekly report
6. Branches — create/edit/activate/deactivate branches

**API:**
- `GET /api/settings` — all settings as JSON
- `POST /api/settings` — bulk update settings
- `POST /api/settings/test-telegram` — send test message to configured Telegram chat

---

## Telegram Notifications (`notifications.py`)

Run in daemon thread so it never blocks request handling.

Events to notify:
- New sale completed (if `notify_on_sale=1`)
- Low stock alert (when product drops below `min_stock_level`)
- Daily AI health report (scheduled)
- Weekly AI report (scheduled)

Message format: plain text with emoji, include store name, amounts, product names.

---

## Scheduler (`scheduler.py`)

Use APScheduler with `BackgroundScheduler`.

Jobs:
- **Daily AI Report** — runs at hour from `scheduler_report_hour` setting. Calls `ai_engine.get_health_report()` and sends via Telegram. Only if `scheduler_daily_report=1`.
- **Weekly AI Report** — runs Sunday at 8am. Only if `scheduler_weekly_report=1`.
- **Low Stock Check** — runs every 6 hours. Sends Telegram alert for any product below `min_stock_level`.

---

## PWA (`static/sw.js`, `static/manifest.json`)

Service worker caches shell (layout, CSS, icons). IndexedDB stores offline POS sales and syncs when connection restored.

Manifest: app name, short_name, icons, theme_color, background_color, display: standalone.

---

## PDF Generation (ReportLab)

### Sales Receipt (`/api/pos/receipt/<id>`)
- Store name + logo
- Date, sale ID, cashier name
- Line items table (product, qty, price, discount, subtotal)
- Totals (subtotal, discount, total, paid, balance)
- Payment method
- Loyalty points earned/redeemed
- "Thank you" footer with store contact

### Customer Statement (`/api/customers/<id>/statement`)
- Customer info header
- Table of all outstanding sales (date, sale_id, total, paid, balance)
- Grand total outstanding
- Generated date

### Product Labels (`/api/products/<id>/label`)
- Product name
- SKU / barcode
- Price
- Printable A4 grid layout (multiple labels per page)

---

## Auth & Permissions

### Decorators (`decorators.py`)

```python
@login_required      # redirect to /login if not in session
@admin_required      # role in (owner, manager, admin)
@permission_required('can_manage_products')  # check permission flag on user
```

### Route Permission Matrix

| Route | Min Role / Permission |
|---|---|
| `/dashboard` | any logged-in |
| `/pos` | any logged-in |
| `/sales` | `can_view_sales` |
| `/products` | `can_manage_products` |
| `/customers` | any logged-in |
| `/suppliers` | `can_manage_purchases` |
| `/purchase-orders` | `can_manage_purchases` |
| `/refunds` | `can_manage_refunds` |
| `/stock-adjustments` | `can_manage_products` |
| `/stock-transfers` | `can_manage_transfers` |
| `/expenses` | `can_manage_expenses` |
| `/reports` | `can_view_reports` |
| `/analytics` | `can_view_analytics` |
| `/ai` | `can_view_analytics` |
| `/eod` | admin+ |
| `/activity` | admin+ |
| `/users` | `can_manage_users` |
| `/settings` | owner/admin |
| `/loyalty` | any logged-in |

---

## Sidebar Navigation

```
📊 Dashboard
🛒 Point of Sale
📦 Products
   └── Categories
🏷️ Variants
👥 Customers
🚚 Suppliers
📋 Purchase Orders
↩️ Refunds
🔧 Stock Adjustments
🔄 Stock Transfers
💰 Expenses
🌟 Loyalty
📈 Reports
📊 Analytics
🤖 AI Insights
🕐 End of Day
📜 Activity Log
👤 Users        (admin only)
⚙️ Settings     (admin only)
```

---

## What to EXCLUDE (do NOT build)

- ❌ Superadmin dashboard (`/superadmin/*`)
- ❌ Multi-tenancy (`organisation_id` on all models)
- ❌ Subdomain routing / custom domain logic
- ❌ `org_context.py` middleware
- ❌ Subscription billing module (`/billing/*`)
- ❌ Plan limits (max products, max staff, max branches enforcement)
- ❌ Onboarding/signup flow for new tenants (`/signup`)
- ❌ `Plan`, `Subscription`, `BillingRecord` models
- ❌ `TenantModule` model and per-tenant module toggles
- ❌ Platform admin user type (`super_admin` role)

---

## requirements.txt

```
Flask==3.0.0
Flask-SQLAlchemy==3.1.1
Flask-Limiter==3.5.0
psycopg2-binary>=2.9.10
python-dotenv==1.0.0
SQLAlchemy>=2.0.32
Werkzeug==3.0.1
gunicorn>=21.0.0
reportlab>=4.0.0
groq>=0.11.0
APScheduler>=3.10.0
```

---

## Procfile

```
web: gunicorn wsgi:app --workers 4 --bind 0.0.0.0:$PORT --timeout 120
```

---

## First Run / Seeding

On first startup (no users in DB):
1. Run `db.create_all()` to create all tables
2. Create a default Branch: `{ name: "Main Branch", address: "", phone: "" }`
3. Create a default owner user: `{ username: "admin", password: "admin123", role: "owner" }` — force password change on first login
4. Seed default Categories: `["Electronics", "Clothing", "Food & Beverage", "General"]`
5. Seed default AppSettings with sensible defaults

---

## Notes for the Build Agent

1. Keep all blueprint files thin — business logic goes in `utils.py` or dedicated service functions, not inline in routes.
2. Every endpoint that mutates data must call `log_activity()`.
3. Every stock quantity change must call `log_stock_movement()`.
4. Use `db.session.rollback()` in except blocks, never leave partial transactions.
5. All list endpoints need pagination. Default page size: 50.
6. CSV exports use Python's `csv` module + `io.StringIO` returned as `application/octet-stream`.
7. Image uploads: validate extension + size, save to `static/uploads/<uuid>.<ext>`.
8. Passwords: `generate_password_hash` / `check_password_hash` from `werkzeug.security`.
9. The `AppSetting` model is a simple key/value store. Helper functions `get_setting(key, default)` and `set_setting(key, value)` should live in `utils.py`.
10. Groq API calls should always have a try/except — if AI is unavailable, return a graceful fallback response, never crash the request.
11. No frontend framework — keep JS minimal. Use `fetch()` for all API calls, update DOM directly.
12. Chart.js loaded via CDN only on pages that need charts (analytics, dashboard).
