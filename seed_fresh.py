"""
Inventory Management System - Fresh Database Seed Script (V2)
This script resets the database and seeds it with improved sample data.
"""

from app import app, db
from models import Product, Customer, Supplier, Sale, SaleItem, SupplierPayment, User, PurchaseOrder, PurchaseOrderItem, StockMovement
from datetime import datetime, timedelta
import random

def create_fresh_data():
    """
    Create fresh and improved sample data for the inventory management system.
    """
    with app.app_context():
        print("🚀 Starting fresh database setup...")
        
        # Drop all tables to ensure clean schema
        print("💥 Dropping existing tables (Resetting database)...")
        db.drop_all()
        
        # Create all tables
        print("📋 Creating database tables...")
        db.create_all()
        print("✅ Tables created successfully!")
        
        print("\n🔐 Creating new users...")
        # New Admin (All True by default)
        admin = User(username='admin_pro', role='admin')
        admin.set_password('adminPass2026')
        admin.can_manage_users = True
        # Explicitly set all permission flags to True for Admin
        admin.can_view_dashboard = True
        admin.can_view_pos = True
        admin.can_view_products = True
        admin.can_view_sales = True
        admin.can_view_purchase_orders = True
        admin.can_view_customers = True
        admin.can_view_suppliers = True
        admin.can_view_reports = True
        db.session.add(admin)
        
        # New Sales User (Limited Access)
        sales_user = User(username='sales_pro', role='sales')
        sales_user.set_password('salesPass2026')
        sales_user.can_view_sales = False # Explicitly limited as per request
        sales_user.can_view_reports = False
        db.session.add(sales_user)
        
        db.session.flush() # Get IDs
        admin_id = admin.id
        sales_id = sales_user.id
        db.session.commit()
        print(f"✅ Users Created: Admin (admin_pro), Sales (sales_pro)")

        print("\n📦 Adding improved products...")
        
        # Improved product list with Unsplash images
        products_data = [
            # Electronics
            {
                'name': 'MacBook Pro 14"',
                'sku': 'TECH-MBP14',
                'cost': 1400.0,
                'price': 1999.0,
                'stock': 12,
                'min': 3,
                'image': 'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=800'
            },
            {
                'name': 'iPhone 15 Pro',
                'sku': 'TECH-IP15P',
                'cost': 700.0,
                'price': 999.0,
                'stock': 25,
                'min': 5,
                'image': 'https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=800'
            },
            {
                'name': 'Sony WH-1000XM5',
                'sku': 'ACC-SNY-H',
                'cost': 220.0,
                'price': 349.0,
                'stock': 18,
                'min': 4,
                'image': 'https://images.unsplash.com/photo-1618366712010-f4ae9c647dcb?w=800'
            },
            {
                'name': 'Samsung 27" 4K Monitor',
                'sku': 'TECH-SAM27',
                'cost': 280.0,
                'price': 449.0,
                'stock': 8,
                'min': 2,
                'image': 'https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=800'
            },
            # Furniture
            {
                'name': 'Standing Desk Pro',
                'sku': 'FURN-SDP',
                'cost': 250.0,
                'price': 499.0,
                'stock': 5,
                'min': 2,
                'image': 'https://images.unsplash.com/photo-1595515106969-1ce29566ff1c?w=800'
            },
            {
                'name': 'Ergonomic Mesh Chair',
                'sku': 'FURN-EMC',
                'cost': 120.0,
                'price': 249.0,
                'stock': 2,  # Low Stock
                'min': 5,
                'image': 'https://images.unsplash.com/photo-1505843490538-5133c6c7d0e1?w=800'
            },
            # Accessories/Others
            {
                'name': 'USB-C Docking Station',
                'sku': 'ACC-DOCK',
                'cost': 45.0,
                'price': 89.0,
                'stock': 30,
                'min': 10,
                'image': 'https://images.unsplash.com/photo-1614624532983-4ce03382d63d?w=800'
            },
            {
                'name': 'Premium Spiral Notebook',
                'sku': 'STAT-NB-P',
                'cost': 4.0,
                'price': 12.0,
                'stock': 100,
                'min': 20,
                'image': 'https://images.unsplash.com/photo-1531346878377-a5be20888e57?w=800'
            }
        ]
        
        products = []
        for p in products_data:
            prod = Product(
                name=p['name'],
                sku=p['sku'],
                cost_price=p['cost'],
                selling_price=p['price'],
                quantity_in_stock=p['stock'],
                min_stock_level=p['min'],
                image_url=p['image']
            )
            db.session.add(prod)
            db.session.flush()
            products.append(prod)
            
            # Log initial seed stock
            log = StockMovement(
                product_id=prod.id,
                quantity_change=prod.quantity_in_stock,
                reason='Fresh Seed Reset',
                timestamp=datetime.utcnow() - timedelta(days=20)
            )
            db.session.add(log)
        
        db.session.commit()
        print(f"✅ Added {len(products)} products (Chair is low stock!)")
        
        print("\n👥 Adding premium customers...")
        
        customers_data = [
            {'name': 'James Miller', 'phone': '+1 (555) 123-4567', 'email': 'james.miller@email.com', 'address': '789 Oak Lane, Seattle, WA'},
            {'name': 'Emily Watson', 'phone': '+1 (555) 987-6543', 'email': 'emily.w@tech.co', 'address': '456 Tech Plaza, San Francisco, CA'},
            {'name': 'Marcus Davis', 'phone': '+44 7700 900077', 'email': 'marcus.d@agency.uk', 'address': '12 London Bridge St, London'},
            {'name': 'Sarah Zhang', 'phone': '+1 (555) 234-5678', 'email': 'sarah.z@design.com', 'address': '101 Studio Ave, New York, NY'},
            {'name': 'Robert Taylor', 'phone': '+1 (555) 345-6789', 'email': 'robert.t@builder.net', 'address': '321 Construction Road, Austin, TX'}
        ]
        
        customers = []
        for c in customers_data:
            cust = Customer(
                full_name=c['name'],
                phone=c['phone'],
                email=c['email'],
                address=c['address']
            )
            db.session.add(cust)
            customers.append(cust)
        
        db.session.commit()
        print(f"✅ Added {len(customers)} customers")
        
        print("\n🚚 Adding reliable suppliers...")
        
        suppliers_data = [
            {'name': 'Global Tech Distribution', 'phone': '1-800-TECH-GLOB'},
            {'name': 'Modern Office Solutions', 'phone': '1-888-MOD-OFFICE'},
            {'name': 'Furniture Factory Direct', 'phone': '1-877-FURN-FACT'}
        ]
        
        suppliers = []
        for s in suppliers_data:
            supp = Supplier(name=s['name'], phone=s['phone'])
            db.session.add(supp)
            suppliers.append(supp)
        
        db.session.commit()
        print(f"✅ Added {len(suppliers)} suppliers")

        print("\n📋 Creating sample business history...")
        
        # PO 1: Received
        po1 = PurchaseOrder(
            supplier_id=suppliers[0].id,
            status='Received',
            payment_type='Cash',
            total_amount=5000.0,
            created_at=datetime.utcnow() - timedelta(days=10)
        )
        db.session.add(po1)
        db.session.flush()
        
        # PO 1 Item: iPhone 15 Pro
        db.session.add(PurchaseOrderItem(purchase_order_id=po1.id, product_id=products[1].id, quantity=5, unit_cost=700.0))
        db.session.add(StockMovement(product_id=products[1].id, quantity_change=5, reason='PO Received', reference_id=str(po1.id)))

        # PO 2: Pending
        po2 = PurchaseOrder(
            supplier_id=suppliers[2].id,
            status='Pending',
            payment_type='Credit',
            total_amount=1200.0,
            created_at=datetime.utcnow() - timedelta(days=2)
        )
        db.session.add(po2)
        db.session.flush()
        db.session.add(PurchaseOrderItem(purchase_order_id=po2.id, product_id=products[5].id, quantity=10, unit_cost=120.0))

        # Sale 1: Fully Paid (By Admin)
        sale1 = Sale(
            customer_id=customers[1].id,
            user_id=admin_id,
            total_amount=2448.0,
            amount_paid=2448.0,
            balance_due=0,
            payment_status='PAID',
            sale_date=datetime.utcnow() - timedelta(days=5)
        )
        db.session.add(sale1)
        db.session.flush()
        
        db.session.add(SaleItem(sale_id=sale1.id, product_id=products[0].id, quantity=1, price_at_sale=1999.0, subtotal=1999.0)) # Correcting index to match products list
        db.session.add(SaleItem(sale_id=sale1.id, product_id=products[3].id, quantity=1, price_at_sale=449.0, subtotal=449.0))

        # Update stock after sale
        db.session.add(StockMovement(product_id=products[0].id, quantity_change=-1, reason='Sale', reference_id=str(sale1.id)))
        db.session.add(StockMovement(product_id=products[3].id, quantity_change=-1, reason='Sale', reference_id=str(sale1.id)))

        # Sale 2: Credit Sale (By Sales Person)
        sale2 = Sale(
            customer_id=customers[3].id,
            user_id=sales_id,
            total_amount=1011.0,
            amount_paid=500.0,
            balance_due=511.0,
            payment_status='PARTIAL',
            sale_date=datetime.utcnow() - timedelta(days=1)
        )
        db.session.add(sale2)
        db.session.flush()
        
        db.session.add(SaleItem(sale_id=sale2.id, product_id=products[1].id, quantity=1, price_at_sale=999.0, subtotal=999.0))
        db.session.add(SaleItem(sale_id=sale2.id, product_id=products[7].id, quantity=1, price_at_sale=12.0, subtotal=12.0))
        
        db.session.add(StockMovement(product_id=products[1].id, quantity_change=-1, reason='Sale', reference_id=str(sale2.id)))
        db.session.add(StockMovement(product_id=products[7].id, quantity_change=-1, reason='Sale', reference_id=str(sale2.id)))

        db.session.commit()
        print("✅ Added sample sales and purchase orders")
        
        print("\n" + "="*60)
        print("🎉 FRESH SYSTEM RESET & UPGRADED SEED COMPLETE!")
        print("="*60)
        print("\n🆕 NEW CREDENTIALS:")
        print("   🔑 ADMIN: admin_pro / adminPass2026")
        print("   🔑 SALES: sales_pro / salesPass2026")
        print("\n📈 DASHBOARD READY FOR TESTING!")
        print("============================================================")

if __name__ == '__main__':
    try:
        create_fresh_data()
    except Exception as e:
        print(f"\n❌ SEEDING FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
