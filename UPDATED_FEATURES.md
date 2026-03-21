# 🚀 New Features & POS Expansion

I have successfully expanded your system into a full **Point of Sale (POS)** with **Role-Based Access Control (RBAC)**.

## 🔑 Default Credentials
Use these accounts to test the different roles:

| Role | Username | Password | Features Access |
|------|----------|----------|-----------------|
| **Admin** | `admin` | `admin123` | Full Access (Dashboard financials, Stock value, Refunds approval, User creation) |
| **Sales** | `sales` | `sales123` | Restricted (POS, Sales, View-only specific reports, Request refunds) |

---

## 🛠️ Setup Instructions (Important!)
Since we modified the database structure (added Users, Images, Refunds), you need to **reset your database** to apply the changes.

1. **Stop the running server** (Ctrl+C).
2. **Drop and recreate the database**:
   ```powershell
   dropdb inventory_db
   createdb inventory_db
   ```
   *(Or if using a file-based SQLite, delete `instance/inventory.db`)*
3. **Run the app** (this will auto-create tables and default users):
   ```powershell
   python app.py
   ```

---

## 📱 Key Features Delivered

### 1. 🛡️ Role-Based Access Control (RBAC)
- **Login System**: Secure login page protecting all resources.
- **Admin Dashboard**: See full financials (Profit, Stock Value).
- **Sales Dashboard**: Restricted view (Sales history, partial stats).
- **User Management**: Admin can create new users via Dashboard.

### 2. 🖥️ Touch-Friendly POS
- **New Page**: `/pos-page` (Accessible via sidebar "POS").
- **Visual Grid**: Product cards with images and stock badges.
- **Cart System**: One-click add, quantity toggle.
- **Customer Lookup**: Fast search by Phone or Name (or create new "Walk-in").
- **Payment**: Integrated Split/Partial payment workflow.

### 3. ↩️ Refund Workflow
- **Request**: Sales staff click "New Request" in Refunds page.
- **Approval**: Admin sees "Restock" or "Damage" buttons to approve.
- **Stock Logic**: Auto-updates inventory based on decision.

### 4. 📦 Inventory Enhancements
- **Images**: Add Image URLs to products for the POS grid.
- **Damaged Stock**: Separate tracking for damaged items (doesn't affect sellable stock).
- **Mark as Damaged**: Feature in Products page to write-off stock.

---

## 🧪 How to Test

1. **Login as Admin** (`admin`/`admin123`).
2. Go to **Products**, add a product with an **Image URL**.
3. **Logout**, then **Login as Sales** (`sales`/`sales123`).
4. Go to **POS**, search for your product, add to cart.
5. Click **Change** under Customer to find/create a customer.
6. Click **Pay Now**, enter a partial amount.
7. Go to **Refunds**, request a refund for a previous sale.
8. **Logout**, Login as **Admin**, go to Refunds and **Approve** it.

Enjoy your upgrades! 🚀
