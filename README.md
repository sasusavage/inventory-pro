# Inventory Management System (Premium Edition)

A full-featured, production-ready inventory management system built with **Python Flask**, **PostgreSQL**, and an ultra-premium **Glassmorphic Dark Mode UI**. 

This system is designed for modern SMEs, featuring predictive low-stock intelligence, beautiful raw CSS aesthetics (no bulky frameworks), PDF invoice generation, seamless refund logic, and partial debt-tracking for customers.

## 🎯 Features

### Product Management
- ✅ Add, edit, and delete products
- ✅ Track SKU, cost price, selling price, and stock levels
- ✅ Automatic stock updates when sales are made
- ✅ Low stock alerts (quantity < 10)
- ✅ Prevent selling more than available stock

### Sales Management
- ✅ Create sales with multiple products
- ✅ **Partial payment support** - customers can pay in installments
- ✅ Automatic calculation of total amount, balance due, and payment status
- ✅ Payment status auto-updates: `PAID`, `PARTIAL`, `UNPAID`
- ✅ Add additional payments to existing sales
- ✅ Stock automatically reduces on sale

### Customer Debt Tracking
- ✅ View all customers with outstanding balances
- ✅ Track payment history per customer
- ✅ Real-time debt calculations
- ✅ Add payments to reduce customer debt

### Supplier Expense Tracking
- ✅ Record payments made to suppliers
- ✅ View total expenses per supplier
- ✅ Complete payment history
- ✅ Monthly expense summaries

### Dashboard & Reports
- ✅ Real-time statistics dashboard
- ✅ Total sales, outstanding debts, stock value
- ✅ Recent sales overview
- ✅ Profit calculations
- ✅ Low stock alerts

## 🛠️ Tech Stack

- **Backend**: Python Flask 3.0
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy 2.0
- **Frontend**: Vanilla HTML5, CSS3, JavaScript (ES6+)
- **Environment**: python-dotenv for configuration
- **Styling**: Custom CSS with modern gradients and animations

## 📁 Project Structure

```
inventort/
├── app.py                 # Main Flask application with all routes
├── models.py              # SQLAlchemy database models
├── config.py              # Configuration and environment variables
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
├── .gitignore            # Git ignore file
│
├── templates/            # HTML templates
│   ├── dashboard.html    # Dashboard with stats
│   ├── products.html     # Product management
│   ├── sales.html        # Sales and payments
│   ├── customers.html    # Customers and debtors
│   └── suppliers.html    # Suppliers and expenses
│
└── static/
    └── css/
        └── style.css     # Complete styling system

```

## 🗄️ Database Schema

### Products Table
- `id` (PK)
- `name` - Product name
- `sku` - Stock Keeping Unit (unique)
- `cost_price` - Purchase price
- `selling_price` - Sale price
- `quantity_in_stock` - Current stock level
- `created_at` - Timestamp

### Customers Table
- `id` (PK)
- `full_name` - Customer name
- `phone` - Contact number
- `email` - Email (optional)
- `created_at` - Timestamp

### Suppliers Table
- `id` (PK)
- `name` - Supplier name
- `phone` - Contact number
- `created_at` - Timestamp

### Sales Table
- `id` (PK)
- `customer_id` (FK → customers)
- `total_amount` - Total sale amount
- `amount_paid` - Amount customer has paid
- `balance_due` - Remaining balance
- `payment_status` - `PAID`, `PARTIAL`, or `UNPAID`
- `sale_date` - Timestamp

### Sale_Items Table
- `id` (PK)
- `sale_id` (FK → sales)
- `product_id` (FK → products)
- `quantity` - Quantity sold
- `price_at_sale` - Price at time of sale
- `subtotal` - Line item total

### Supplier_Payments Table
- `id` (PK)
- `supplier_id` (FK → suppliers)
- `amount_paid` - Payment amount
- `description` - Payment notes
- `payment_date` - Timestamp

## 🚀 Installation & Setup

### Prerequisites

1. **Python 3.8+** installed
2. **PostgreSQL** installed and running
3. Basic knowledge of command line

### Step 1: Install PostgreSQL

**Windows:**
- Download from [postgresql.org](https://www.postgresql.org/download/windows/)
- During installation, remember your password for the `postgres` user
- Default port is `5432`

### Step 2: Create Database

Open **pgAdmin** or use **psql** command line:

```sql
CREATE DATABASE inventory_db;
```

### Step 3: Clone/Download Project

Navigate to the project folder:
```powershell
cd c:\Users\DeLL\Downloads\inventort
```

### Step 4: Create Virtual Environment

```powershell
python -m venv venv
```

Activate the virtual environment:
```powershell
.\venv\Scripts\Activate
```

### Step 5: Install Dependencies

```powershell
pip install -r requirements.txt
```

### Step 6: Configure Environment Variables

Create a `.env` file (copy from `.env.example`):

```powershell
copy .env.example .env
```

Edit `.env` file with your database credentials:

```env
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/inventory_db
SECRET_KEY=your-secret-key-change-this-to-something-random
FLASK_ENV=development
FLASK_DEBUG=True
```

**Important**: Replace `YOUR_PASSWORD` with your actual PostgreSQL password!

### Step 7: Run the Application

```powershell
python app.py
```

The application will:
1. Automatically create all database tables on first run
2. Start the Flask development server
3. Be accessible at: **http://127.0.0.1:5000**

## 📖 Usage Guide

### Adding Products

1. Navigate to **Products** page
2. Click **"Add Product"**
3. Fill in:
   - Product name
   - SKU (unique identifier)
   - Cost price (what you pay)
   - Selling price (what customers pay)
   - Initial stock quantity
4. Click **"Add Product"**

### Making a Sale

1. Navigate to **Sales** page
2. Click **"New Sale"**
3. Select customer (add customer first if needed)
4. Click **"Add Item"** for each product
5. Select product and quantity
6. Enter **Amount Paid** (can be partial)
7. Click **"Complete Sale"**

**The system automatically:**
- Calculates total amount
- Reduces stock
- Sets payment status (PAID/PARTIAL/UNPAID)
- Calculates balance due

### Adding Partial Payments

1. In **Sales** page, find sale with outstanding balance
2. Click **"Add Payment"** button
3. Enter additional payment amount
4. Click **"Add Payment"**

**The system automatically:**
- Updates amount paid
- Recalculates balance
- Updates payment status

### Viewing Debtors

1. Navigate to **Customers** page
2. Top section shows **Outstanding Debts**
3. Shows customers who owe money and total debt

### Tracking Supplier Expenses

1. Navigate to **Suppliers** page
2. Add suppliers first
3. Click **"Record Payment"** to track expenses
4. View total expenses per supplier
5. See complete payment history

## 🎨 Design Features

The system includes a **modern, premium UI** with:

- 🌈 Vibrant gradient colors
- 🌙 Dark mode optimized
- ✨ Smooth animations and transitions
- 💫 Glassmorphism effects
- 📱 Fully responsive design
- ⚡ Fast and intuitive

## 📊 API Endpoints

### Products
- `GET /products` - Get all products
- `POST /products` - Create product
- `GET /products/<id>` - Get single product
- `PUT /products/<id>` - Update product
- `DELETE /products/<id>` - Delete product

### Customers
- `GET /customers` - Get all customers
- `POST /customers` - Create customer

### Sales
- `GET /sales` - Get all sales
- `POST /sales` - Create sale
- `POST /sales/<id>/payment` - Add payment to sale

### Suppliers
- `GET /suppliers` - Get all suppliers
- `POST /suppliers` - Create supplier
- `GET /supplier-payments` - Get all payments
- `POST /supplier-payments` - Record payment

### Reports
- `GET /reports/dashboard` - Dashboard statistics
- `GET /reports/debtors` - Customers with debts
- `GET /reports/profit` - Profit calculations

## 🔒 Security Features

- ✅ Environment variables for sensitive data
- ✅ No hardcoded credentials
- ✅ SQL injection protection (SQLAlchemy ORM)
- ✅ Input validation on all forms
- ✅ CSRF protection ready (can add Flask-WTF)

## 🧪 Testing the System

### Test Workflow:

1. **Add Products**
   - Add 3-5 test products with different prices and stock

2. **Add Customers**
   - Create 2-3 test customers

3. **Create Sale with Partial Payment**
   - Select customer
   - Add multiple products
   - Enter partial payment (less than total)
   - Verify status shows "PARTIAL"

4. **Add Payment to Sale**
   - Find the sale with partial payment
   - Add more payment
   - Verify balance updates

5. **Check Debtors Report**
   - Navigate to Customers
   - Verify customer appears in debtors list

6. **Add Supplier and Expenses**
   - Add a supplier
   - Record payments
   - Verify total expenses

## 🐛 Troubleshooting

### Database Connection Error

**Error:** `could not connect to server`

**Solution:**
- Verify PostgreSQL is running
- Check DATABASE_URL in `.env` file
- Verify username, password, and database name

### Port Already in Use

**Error:** `Address already in use`

**Solution:**
- Change port in `app.py`: `app.run(debug=True, port=5001)`

### Module Not Found

**Error:** `ModuleNotFoundError: No module named 'flask'`

**Solution:**
- Ensure virtual environment is activated
- Run `pip install -r requirements.txt`

## 📝 Business Logic Rules

1. **Stock Management**
   - Stock decreases automatically after each sale
   - Cannot sell more than available stock
   - Low stock alert when quantity < 10

2. **Payment Status**
   - **PAID**: `balance_due = 0`
   - **PARTIAL**: `0 < balance_due < total_amount`
   - **UNPAID**: `balance_due = total_amount`
   - Status updates automatically on payment

3. **Product Deletion**
   - Cannot delete products referenced in sales
   - Maintains data integrity

4. **Price Tracking**
   - Sale items store `price_at_sale`
   - Historical accuracy if prices change

## 🚀 Future Enhancements (Phase 3)

- [x] User authentication and roles (Completed)
- [x] PDF invoice generation (Completed - ReportLab)
- [x] Advanced reporting and analytics (Completed - Profit Tracking, Monthly Trends)
- [ ] Email notifications for low stock
- [ ] Product categories
- [ ] Barcode scanning
- [ ] Export data to Excel/CSV
- [ ] Multi-currency support
- [ ] Export data to Excel/CSV
- [ ] Multi-currency support

## 📄 License

This project is open source and available for commercial use.

## 👨‍💻 Support

For issues or questions:
1. Check the troubleshooting section
2. Review the code comments
3. Verify database connection
4. Check browser console for JavaScript errors

---

**Built with ❤️ using Flask, PostgreSQL, and Vanilla JavaScript**
