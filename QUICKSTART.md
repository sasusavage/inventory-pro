# 🚀 QUICK START GUIDE
## Get Your Inventory System Running in 5 Minutes!

### Prerequisites Check ✓
- [ ] Python 3.8+ installed
- [ ] PostgreSQL installed and running
- [ ] Terminal/PowerShell access

---

## Step-by-Step Setup

### 1️⃣ Create PostgreSQL Database

Open **pgAdmin** or **psql** terminal and run:

```sql
CREATE DATABASE inventory_db;
```

### 2️⃣ Navigate to Project Folder

```powershell
cd c:\Users\DeLL\Downloads\inventort
```

### 3️⃣ Create Virtual Environment

```powershell
python -m venv venv
```

### 4️⃣ Activate Virtual Environment

```powershell
.\venv\Scripts\Activate
```

You should see `(venv)` in your terminal prompt.

### 5️⃣ Install Dependencies

```powershell
pip install -r requirements.txt
```

Wait for installation to complete (~1-2 minutes).

### 6️⃣ Configure Environment Variables

**Option A: Quick Setup (for testing)**

Create `.env` file:
```powershell
copy .env.example .env
notepad .env
```

Update the password in this line:
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD_HERE@localhost:5432/inventory_db
```

Save and close.

**Option B: Manual Creation**

Create a file named `.env` with this content:
```
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@localhost:5432/inventory_db
SECRET_KEY=my-super-secret-key-change-in-production
FLASK_ENV=development
FLASK_DEBUG=True
```

### 7️⃣ Initialize Database with Sample Data (Optional)

```powershell
python setup_database.py
```

This creates:
- 8 sample products
- 5 sample customers
- 3 sample suppliers
- 3 sample sales (paid, partial, unpaid)
- 4 supplier payments

### 8️⃣ Start the Application

```powershell
python app.py
```

You should see:
```
 * Running on http://127.0.0.1:5000
```

### 9️⃣ Open in Browser

Visit: **http://127.0.0.1:5000**

---

## 🎯 First Steps After Launch

1. **Explore the Dashboard**
   - View statistics
   - Check low stock alerts
   - See recent sales

2. **Add Your First Product**
   - Click "Products" in sidebar
   - Click "Add Product"
   - Fill in details and save

3. **Add a Customer**
   - Click "Customers" in sidebar
   - Click "Add Customer"
   - Enter customer details

4. **Make a Sale**
   - Click "Sales" in sidebar
   - Click "New Sale"
   - Select customer and products
   - Enter payment amount (can be partial!)
   - Complete sale

5. **Track Payments**
   - View sales with outstanding balance
   - Click "Add Payment" to record additional payments
   - Watch status auto-update!

---

## 🐛 Troubleshooting

### ❌ "ModuleNotFoundError: No module named 'flask'"
**Solution:** Virtual environment not activated or dependencies not installed
```powershell
.\venv\Scripts\Activate
pip install -r requirements.txt
```

### ❌ "could not connect to server"
**Solution:** PostgreSQL not running or wrong credentials
- Start PostgreSQL service
- Check DATABASE_URL in .env file
- Verify username/password

### ❌ "database 'inventory_db' does not exist"
**Solution:** Database not created
```sql
CREATE DATABASE inventory_db;
```

### ❌ "Port 5000 already in use"
**Solution:** Change port in app.py:
```python
app.run(debug=True, port=5001)
```

---

## 📱 Testing Checklist

After setup, verify these features work:

- [ ] Dashboard shows statistics
- [ ] Can add a new product
- [ ] Can edit a product
- [ ] Can create a sale with multiple items
- [ ] Stock decreases after sale
- [ ] Can add partial payment to sale
- [ ] Payment status updates (PAID/PARTIAL/UNPAID)
- [ ] Debtors report shows customers with balance
- [ ] Can add supplier and record payment
- [ ] Low stock alert appears for items < 10 qty

---

## 🔥 Pro Tips

1. **Use Sample Data**: Run `setup_database.py` to get started quickly with test data

2. **Test Partial Payments**: 
   - Create a sale for $100
   - Pay only $50
   - Status shows "PARTIAL"
   - Add another $50 payment
   - Status changes to "PAID"

3. **Check Stock Updates**:
   - Note product quantity before sale
   - Make a sale
   - Verify quantity decreased

4. **View Debtors**:
   - Make sales with partial/no payment
   - Go to Customers page
   - See "Outstanding Debts" section

---

## 📞 Need Help?

1. Check console for error messages
2. Verify PostgreSQL is running
3. Ensure .env file has correct credentials
4. Check browser console (F12) for JavaScript errors

---

## 🎨 Design Features

Your system includes:
- ✨ Modern gradient UI
- 🌙 Dark mode design
- 💫 Smooth animations
- 📱 Responsive layout
- ⚡ Fast performance

---

## Next Steps

Once comfortable with basics:

1. Customize product categories
2. Add more customers
3. Process real sales
4. Track actual supplier expenses
5. Monitor profit reports

**Enjoy your new Inventory Management System! 🎉**
