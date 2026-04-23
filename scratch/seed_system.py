import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Organisation, Branch, User, Product, Category, Sale, Customer, TenantModule, AppSetting, AVAILABLE_MODULES

def seed():
    app = create_app()
    with app.app_context():
        print("--- Starting Fresh Database Seed ---")
        
        # 1. Platform / Super Admin
        system_org = Organisation.query.filter_by(slug="system").first()
        if not system_org:
            system_org = Organisation(name="InventoryPro Platform", slug="system", is_active=True)
            db.session.add(system_org)
            db.session.flush()
        
        super_admin = User.query.filter_by(username="admin").first()
        if not super_admin:
            super_admin = User(
                username="admin", 
                full_name="Platform Administrator", 
                role="super_admin", 
                organisation_id=system_org.id,
                is_active=True
            )
            super_admin.set_password("admin123")
            db.session.add(super_admin)
            print("Created Super Admin: admin / admin123")
        
        # 2. Pharmacy Tenant
        pharm = Organisation.query.filter_by(slug="pharmacy").first()
        if not pharm:
            pharm = Organisation(name="The Modern Pharmacy", slug="pharmacy", currency="GHS", country="Ghana", is_active=True)
            db.session.add(pharm)
            db.session.flush()
            
            p_branch = Branch(organisation_id=pharm.id, name="Accra Mall Branch", is_default=True, is_active=True)
            db.session.add(p_branch)
            db.session.flush()

            p_owner = User(username="pharm_owner", full_name="Dr. Kwame", role="owner", organisation_id=pharm.id, branch_id=p_branch.id, is_active=True)
            p_owner.set_password("pharm123")
            db.session.add(p_owner)
            
            p_sales = User(username="sales", full_name="Sales Rep 1", role="staff", organisation_id=pharm.id, branch_id=p_branch.id, is_active=True)
            p_sales.set_password("sales123")
            db.session.add(p_sales)

            for mod in AVAILABLE_MODULES:
                if not TenantModule.query.filter_by(organisation_id=pharm.id, module=mod).first():
                    db.session.add(TenantModule(organisation_id=pharm.id, module=mod, is_enabled=True))
            
            # Using update logic for AppSetting
            def set_setting(org_id, key, val):
                s = AppSetting.query.filter_by(organisation_id=org_id, key=key).first()
                if s: s.value = val
                else: db.session.add(AppSetting(organisation_id=org_id, key=key, value=val))

            set_setting(pharm.id, "store_name", "The Modern Pharmacy")
            set_setting(pharm.id, "sms_enabled", "1")
            
            cat = Category.query.filter_by(organisation_id=pharm.id, name="Medicines").first()
            if not cat:
                cat = Category(organisation_id=pharm.id, name="Medicines")
                db.session.add(cat)
                db.session.flush()
            
            if not Product.query.filter_by(organisation_id=pharm.id, barcode="1001").first():
                p1 = Product(organisation_id=pharm.id, category_id=cat.id, name="Paracetamol", barcode="1001", sku="PARA001", quantity_in_stock=50, min_stock_level=10, cost_price=2.0, selling_price=5.0)
                db.session.add(p1)
            
            if not Product.query.filter_by(organisation_id=pharm.id, barcode="1002").first():
                p2 = Product(organisation_id=pharm.id, category_id=cat.id, name="Vitamin C", barcode="1002", sku="VITC001", quantity_in_stock=5, min_stock_level=10, cost_price=10.0, selling_price=25.0)
                db.session.add(p2)
            
            print("Created Demo Tenant 1: pharm_owner / pharm123")

        db.session.commit()
        print("--- Seeding Complete! ---")

if __name__ == "__main__":
    seed()
