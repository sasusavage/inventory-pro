from app import app, db
from models import User

def seed_admin():
    """
    Creates tables and seeds only the default admin user.
    Perfect for production initialization without dummy data.
    """
    with app.app_context():
        print("📋 Creating database tables if they don't exist...")
        db.create_all()
        
        # Check if admin already exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("🔐 Seeding default admin user...")
            admin = User(username='admin', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin user created successfully!")
            print("👉 Username: admin")
            print("👉 Password: admin123")
        else:
            print("✅ Admin user already exists. Skipping.")

if __name__ == '__main__':
    try:
        seed_admin()
    except Exception as e:
        print(f"❌ Error during admin seeding: {str(e)}")
