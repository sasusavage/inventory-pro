# 🎯 GETTING STARTED - Your First 10 Minutes

Welcome to your new **Inventory Management System**! This guide will get you from zero to running in about 10 minutes.

---

## ⚡ Prerequisites (2 minutes)

Before we start, make sure you have:

- [ ] **Python 3.8+** installed
  - Check: `python --version`
  - Download: https://python.org

- [ ] **PostgreSQL** installed and running
  - Check: Open pgAdmin or run `psql --version`
  - Download: https://postgresql.org/download

- [ ] **PowerShell** or **Command Prompt** access

---

## 🚀 Step-by-Step Setup

### Step 1: Create Database (1 minute)

**Option A: Using pgAdmin (GUI)**
1. Open **pgAdmin**
2. Right-click on "Databases"
3. Click "Create" → "Database"
4. Name it: `inventory_db`
5. Click "Save"

**Option B: Using psql (Command Line)**
```powershell
# Open PowerShell and run:
psql -U postgres

# In psql prompt:
CREATE DATABASE inventory_db;
\q
```

✅ **Checkpoint**: Database `inventory_db` exists

---

### Step 2: Open Project Folder (30 seconds)

```powershell
cd c:\Users\DeLL\Downloads\inventort
```

---

### Step 3: Create Virtual Environment (1 minute)

```powershell
python -m venv venv
```

Wait for it to complete...

Then activate it:
```powershell
.\venv\Scripts\Activate
```

You should see `(venv)` appear in your prompt.

✅ **Checkpoint**: Virtual environment activated

---

### Step 4: Install Dependencies (2 minutes)

```powershell
pip install -r requirements.txt
```

This installs:
- Flask
- SQLAlchemy
- psycopg2 (PostgreSQL driver)
- python-dotenv

Wait for installation...

✅ **Checkpoint**: All packages installed

---

### Step 5: Configure Database Connection (1 minute)

The `.env` file already exists, but you need to update it with YOUR PostgreSQL password.

**Option A: Edit in Notepad**
```powershell
notepad .env
```

**Option B: Edit in VS Code**
```powershell
code .env
```

Find this line:
```
DATABASE_URL=postgresql://username:password@localhost:5432/inventory_db
```

Change it to (use YOUR password):
```
DATABASE_URL=postgresql://postgres:YOUR_ACTUAL_PASSWORD@localhost:5432/inventory_db
```

**Example:**
If your PostgreSQL password is `admin123`, change to:
```
DATABASE_URL=postgresql://postgres:admin123@localhost:5432/inventory_db
```

Save and close the file.

✅ **Checkpoint**: `.env` file configured

---

### Step 6: Add Sample Data (2 minutes) - OPTIONAL

This step is optional but recommended for testing.

```powershell
python setup_database.py
```

You should see:
```
🚀 Starting database setup...
📋 Creating database tables...
✅ Tables created successfully!
📦 Adding sample products...
✅ Added 8 products
👥 Adding sample customers...
✅ Added 5 customers
...
🎉 DATABASE SETUP COMPLETE!
```

This creates:
- 8 products (laptops, mice, chairs, etc.)
- 5 customers
- 3 suppliers
- 3 sample sales (1 paid, 1 partial, 1 unpaid)
- 4 supplier payments

**Skip this step** if you want to start with a blank database.

✅ **Checkpoint**: Sample data loaded OR skipped

---

### Step 7: Start the Application (30 seconds)

```powershell
python app.py
```

You should see:
```
 * Serving Flask app 'app'
 * Debug mode: on
WARNING: This is a development server.
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

✅ **Checkpoint**: Server running

---

### Step 8: Open in Browser (10 seconds)

Open your web browser and go to:

```
http://127.0.0.1:5000
```

or

```
http://localhost:5000
```

🎉 **You should see the Dashboard!**

---

## 🎮 Your First Actions

### If You Used Sample Data:

1. **Explore the Dashboard**
   - See 8 stat cards with real numbers
   - Check "Low Stock Alert" (Keyboard has only 4 left)
   - View "Recent Sales" table

2. **View Products**
   - Click "Products" in sidebar
   - See 8 products with stock levels
   - Try editing one (click ✏️ Edit button)

3. **Check Debtors**
   - Click "Customers" in sidebar
   - See "Outstanding Debts" table
   - 2 customers owe money

4. **Add a Payment**
   - Click "Sales" in sidebar
   - Find a sale with "PARTIAL" or "UNPAID" status
   - Click "Add Payment" button
   - Enter an amount
   - Submit
   - Watch the status update! 🎉

### If You Started With Blank Database:

1. **Add Your First Product**
   - Click "Products"
   - Click "Add Product"
   - Fill in:
     - Name: "Test Product"
     - SKU: "TEST-001"
     - Cost Price: 10.00
     - Selling Price: 15.00
     - Quantity: 50
   - Click "Add Product"

2. **Add a Customer**
   - Click "Customers"
   - Click "Add Customer"
   - Fill in name and phone
   - Submit

3. **Make Your First Sale**
   - Click "Sales"
   - Click "New Sale"
   - Select the customer
   - Click "Add Item"
   - Select the product
   - Enter quantity
   - Enter amount paid (try partial: 5.00 instead of full 15.00)
   - Click "Complete Sale"
   - Status will show "PARTIAL"! 🎊

---

## 🐛 Troubleshooting

### Problem: "could not connect to server"

**Solution:**
1. Make sure PostgreSQL is running
2. Check your password in `.env` file
3. Verify database name is `inventory_db`

### Problem: "database 'inventory_db' does not exist"

**Solution:**
```sql
-- Run in psql or pgAdmin:
CREATE DATABASE inventory_db;
```

### Problem: "ModuleNotFoundError: No module named 'flask'"

**Solution:**
```powershell
# Make sure virtual environment is activated
.\venv\Scripts\Activate
# Reinstall dependencies
pip install -r requirements.txt
```

### Problem: "Port 5000 already in use"

**Solution:**
Edit `app.py`, change last line to:
```python
app.run(debug=True, port=5001)
```
Then use: http://127.0.0.1:5001

### Problem: Page looks broken or unstyled

**Solution:**
1. Check browser console (F12) for errors
2. Make sure `static/css/style.css` exists
3. Hard refresh the page (Ctrl+F5)

---

## 📝 Quick Reference

### Start Server
```powershell
cd c:\Users\DeLL\Downloads\inventort
.\venv\Scripts\Activate
python app.py
```

### Stop Server
Press `Ctrl+C` in the terminal

### Reset Database (Delete All Data)
```powershell
# In psql or pgAdmin:
DROP DATABASE inventory_db;
CREATE DATABASE inventory_db;
# Then run:
python setup_database.py
```

### View Database
```powershell
psql -U postgres -d inventory_db
\dt  # List tables
SELECT * FROM products;  # View products
\q  # Quit
```

---

## 🎯 What to Try Next

1. **Test Partial Payments**
   - Make a sale for $100
   - Pay only $30 → Status: PARTIAL
   - Add $40 payment → Status: PARTIAL
   - Add $30 payment → Status: PAID ✅

2. **Test Stock Updates**
   - Note product quantity
   - Make a sale
   - Check product again - quantity decreased ✅

3. **Test Low Stock Alert**
   - Edit a product
   - Set quantity to 5
   - Return to Dashboard
   - See it in "Low Stock Alert" table ✅

4. **Track Supplier Expenses**
   - Add a supplier
   - Record a payment to them
   - View total expenses ✅

5. **View Debtors**
   - Make sales with partial/no payment
   - Go to Customers page
   - See them in debtors list ✅

---

## 💡 Pro Tips

1. **Keep terminal open** while using the app to see request logs

2. **Use browser DevTools** (F12) to see API calls

3. **Check console** if something doesn't work - errors show there

4. **Sample data is great** for learning the system

5. **Try breaking it** - attempt to:
   - Sell more than stock (should fail)
   - Use duplicate SKU (should fail)
   - Delete product with sales (should fail)

---

## 📱 Interface Tour

### Sidebar Navigation
- 📊 Dashboard - Statistics overview
- 🏷️ Products - Inventory management
- 💰 Sales - Process sales & payments
- 👥 Customers - Customer & debt tracking
- 🚚 Suppliers - Supplier & expense tracking

### Color Coding
- 🟢 **Green badges**: Paid, Good stock
- 🟡 **Yellow badges**: Partial payment, Low stock
- 🔴 **Red badges**: Unpaid, Out of stock

### Interactive Elements
- Click stat cards to see details
- Hover over buttons for effects
- Modals close when clicking outside
- Forms validate before submission

---

## ✅ Success Checklist

After 10 minutes, you should have:

- [x] PostgreSQL database created
- [x] Virtual environment activated
- [x] Dependencies installed
- [x] `.env` file configured
- [x] Sample data loaded (optional)
- [x] Server running
- [x] Dashboard visible in browser
- [x] Able to navigate between pages
- [x] Can perform basic actions (add/edit)

---

## 🎉 Congratulations!

You now have a fully functional inventory management system!

**Next Steps:**
1. Explore all 5 pages
2. Test the partial payment feature
3. Try the sample workflows
4. Read README.md for advanced features
5. Customize for your business needs

**Need Help?**
- Check QUICKSTART.md for detailed setup
- Review PROJECT_CHECKLIST.md for features
- See DELIVERY_SUMMARY.md for overview

---

**Enjoy your new Inventory Management System! 🚀**

*Built with Flask, PostgreSQL, and Vanilla JavaScript*
