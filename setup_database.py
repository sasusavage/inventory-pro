"""
Inventory Management System - Setup and Database Initialization Script
This script helps set up the database with sample data for testing.
"""

from app import app, db
from models import Product, Customer, Supplier, Sale, SaleItem, SupplierPayment, User, PurchaseOrder, PurchaseOrderItem, StockMovement
from datetime import datetime, timedelta
import random

def create_sample_data():
    """
    Create sample data for testing the inventory management system.
    """
    with app.app_context():
        print("🚀 Starting database setup...")
        
        # Drop all tables to ensure clean schema (Handles model updates)
        print("💥 Dropping existing tables (Resetting database)...")
        db.drop_all()
        
        # Create all tables
        print("📋 Creating database tables...")
        db.create_all()
        print("✅ Tables created successfully!")
        
        print("\n🔐 Creating default users...")
        # Create Users
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        
        sales_user = User(username='sales', role='sales')
        sales_user.set_password('sales123')
        db.session.add(sales_user)
        db.session.flush() # Get IDs
        admin_id = admin.id
        sales_id = sales_user.id
        db.session.commit()
        print(f"✅ Users Created: Admin (ID {admin_id}), Sales (ID {sales_id})")

        print("\n📦 Adding sample products...")
        
        # Sample products
        products = [
            Product(
                name='Laptop Dell XPS 13',
                sku='TECH-001',
                cost_price=800.00,
                selling_price=1200.00,
                quantity_in_stock=15,
                min_stock_level=5,
                image_url='https://images.unsplash.com/photo-1593642632823-8f7856677741?w=500'
            ),
            Product(
                name='Wireless Mouse Logitech',
                sku='ACC-001',
                cost_price=15.00,
                selling_price=25.00,
                quantity_in_stock=50,
                min_stock_level=10,
                image_url='https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?w=500'
            ),
            Product(
                name='USB-C Cable 2m',
                sku='ACC-002',
                cost_price=5.00,
                selling_price=10.00,
                quantity_in_stock=100,
                min_stock_level=20
            ),
            Product(
                name='Office Chair Ergonomic',
                sku='FURN-001',
                cost_price=150.00,
                selling_price=250.00,
                quantity_in_stock=8,
                min_stock_level=5,
                image_url='https://images.unsplash.com/photo-1505843490538-5133c6c7d0e1?w=500'
            ),
            Product(
                name='Desk Lamp LED',
                sku='FURN-002',
                cost_price=20.00,
                selling_price=35.00,
                quantity_in_stock=25,
                min_stock_level=10
            ),
            Product(
                name='Mechanical Keyboard',
                sku='TECH-002',
                cost_price=60.00,
                selling_price=100.00,
                quantity_in_stock=3,  # LOW STOCK Trigger
                min_stock_level=5
            ),
            Product(
                name='Monitor 24 inch',
                sku='TECH-003',
                cost_price=180.00,
                selling_price=280.00,
                quantity_in_stock=12,
                min_stock_level=5,
                image_url='https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500'
            ),
            Product(
                name='Notebook A4 Pack',
                sku='STAT-001',
                cost_price=3.00,
                selling_price=7.00,
                quantity_in_stock=200,
                min_stock_level=50
            )
        ]
        
        for product in products:
            db.session.add(product)
            db.session.flush()
            # Log initial stock
            log = StockMovement(
                product_id=product.id,
                quantity_change=product.quantity_in_stock,
                reason='Initial Setup',
                timestamp=datetime.utcnow() - timedelta(days=30)
            )
            db.session.add(log)
        
        db.session.commit()
        print(f"✅ Added {len(products)} products (Keyboard is low stock!)")
        
        print("\n👥 Adding sample customers...")
        
        # Sample customers
        customers = [
            Customer(
                full_name='John Smith',
                phone='+1234567890',
                email='john.smith@example.com',
                address='123 Main St, New York, NY'
            ),
            Customer(
                full_name='Sarah Johnson',
                phone='+1234567891',
                email='sarah.johnson@example.com',
                address='456 Park Ave, Boston, MA'
            ),
            Customer(
                full_name='Michael Brown',
                phone='+1234567892',
                email=None  # Optional email
            ),
            Customer(
                full_name='Emily Davis',
                phone='+1234567893',
                email='emily.davis@example.com'
            ),
            Customer(
                full_name='James Wilson',
                phone='+1234567894',
                email='james.wilson@example.com'
            )
        ]
        
        for customer in customers:
            db.session.add(customer)
        
        db.session.commit()
        print(f"✅ Added {len(customers)} customers")
        
        print("\n🚚 Adding sample suppliers...")
        
        # Sample suppliers
        suppliers = [
            Supplier(
                name='Tech Wholesale Inc.',
                phone='+1111111111'
            ),
            Supplier(
                name='Office Supplies Co.',
                phone='+2222222222'
            ),
            Supplier(
                name='Furniture Direct',
                phone='+3333333333'
            )
        ]
        
        for supplier in suppliers:
            db.session.add(supplier)
        
        db.session.commit()
        print(f"✅ Added {len(suppliers)} suppliers")

        print("\n📋 Creating sample Purchase Orders...")
        # PO 1: Received (Cash)
        po1 = PurchaseOrder(
            supplier_id=1,
            status='Received',
            payment_type='Cash',
            total_amount=5000.00,
            created_at=datetime.utcnow() - timedelta(days=15)
        )
        db.session.add(po1)
        db.session.flush()
        
        po_item1 = PurchaseOrderItem(purchase_order_id=po1.id, product_id=1, quantity=5, unit_cost=800.00) # Laptops
        po_item2 = PurchaseOrderItem(purchase_order_id=po1.id, product_id=2, quantity=20, unit_cost=15.00) # Mice
        
        db.session.add(po_item1)
        db.session.add(po_item2)
        
        # Log movement for PO 1
        db.session.add(StockMovement(product_id=1, quantity_change=5, reason='PO Received', reference_id=str(po1.id)))
        db.session.add(StockMovement(product_id=2, quantity_change=20, reason='PO Received', reference_id=str(po1.id)))
        
        # PO 2: Pending (Credit)
        po2 = PurchaseOrder(
            supplier_id=3,
            status='Pending',
            payment_type='Credit',
            total_amount=1500.00,
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.session.add(po2)
        db.session.flush()
        
        po_item3 = PurchaseOrderItem(purchase_order_id=po2.id, product_id=4, quantity=10, unit_cost=150.00) # Chairs
        db.session.add(po_item3)
        
        db.session.commit()
        print("✅ Added 2 Purchase Orders (1 Received, 1 Pending)")
        
        print("\n💰 Creating sample sales...")
        
        # Sample sales
        # Sale 1: Fully paid (By Admin)
        sale1 = Sale(
            customer_id=1,
            user_id=admin_id,
            total_amount=1235.00,
            amount_paid=1235.00,
            balance_due=0,
            payment_status='PAID',
            sale_date=datetime.utcnow() - timedelta(days=5)
        )
        db.session.add(sale1)
        db.session.flush()
        
        db.session.add(SaleItem(sale_id=sale1.id, product_id=1, quantity=1, price_at_sale=1200.00, subtotal=1200.00))
        db.session.add(SaleItem(sale_id=sale1.id, product_id=2, quantity=1, price_at_sale=25.00, subtotal=25.00))
        
        db.session.add(StockMovement(product_id=1, quantity_change=-1, reason='Sale', reference_id=str(sale1.id)))
        db.session.add(StockMovement(product_id=2, quantity_change=-1, reason='Sale', reference_id=str(sale1.id)))
        
        # Sale 2: Partial payment (By Sales User)
        sale2 = Sale(
            customer_id=2,
            user_id=sales_id,
            total_amount=530.00,
            amount_paid=300.00,
            balance_due=230.00,
            payment_status='PARTIAL',
            sale_date=datetime.utcnow() - timedelta(days=3)
        )
        db.session.add(sale2)
        db.session.flush()
        
        db.session.add(SaleItem(sale_id=sale2.id, product_id=4, quantity=2, price_at_sale=250.00, subtotal=500.00))
        db.session.add(SaleItem(sale_id=sale2.id, product_id=5, quantity=1, price_at_sale=35.00, subtotal=35.00))
        
        db.session.add(StockMovement(product_id=4, quantity_change=-2, reason='Sale', reference_id=str(sale2.id)))
        db.session.add(StockMovement(product_id=5, quantity_change=-1, reason='Sale', reference_id=str(sale2.id)))
        
        # Sale 3: Unpaid (By Sales User)
        sale3 = Sale(
            customer_id=3,
            user_id=sales_id,
            total_amount=380.00,
            amount_paid=0,
            balance_due=380.00,
            payment_status='UNPAID',
            sale_date=datetime.utcnow() - timedelta(days=1)
        )
        db.session.add(sale3)
        db.session.flush()
        
        db.session.add(SaleItem(sale_id=sale3.id, product_id=7, quantity=1, price_at_sale=280.00, subtotal=280.00))
        db.session.add(SaleItem(sale_id=sale3.id, product_id=6, quantity=1, price_at_sale=100.00, subtotal=100.00))
        
        db.session.add(StockMovement(product_id=7, quantity_change=-1, reason='Sale', reference_id=str(sale3.id)))
        db.session.add(StockMovement(product_id=6, quantity_change=-1, reason='Sale', reference_id=str(sale3.id)))
        
        db.session.commit()
        print(f"✅ Added sales and movements")
        
        print("\n💸 Recording sample supplier payments...")
        
        # Sample supplier payments
        payments = [
            SupplierPayment(
                supplier_id=1,
                amount_paid=5000.00,
                description='Auto-payment for PO #1',
                payment_date=datetime.utcnow() - timedelta(days=15)
            )
        ]
        
        for payment in payments:
            db.session.add(payment)
        
        db.session.commit()
        print(f"✅ Added {len(payments)} supplier payments")
        
        print("\n" + "="*60)
        print("🎉 DATABASE UPGRADE & RESET COMPLETE!")
        print("="*60)
        print("\n📊 Check Dashboard for:")
        print("   • Low Stock Alert (Keyboard)")
        print("   • Accounts Receivable ($610 owed by customers)")
        print("   • Accounts Payable (Pending credit POs)")
        print("   • Stock Movement Logs")
        print("   • Sales History (Filtered by user)")
        print("\n🌐 Restart app and verify!")
        print("============================================================")

if __name__ == '__main__':
    try:
        create_sample_data()
    except Exception as e:
        print(f"\n❌ Error during setup: {str(e)}")
        print("\nPlease ensure:")
        print("1. PostgreSQL is running")
        print("2. Database 'inventory_db' exists")
        print("3. No other process is locking the database (Stop app.py first!)")
