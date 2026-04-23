import os
import sys

# Add parent directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db

def fix():
    app = create_app()
    with app.app_context():
        print("--- Fixing app_settings constraints ---")
        try:
            # 1. Drop the incorrect unique index on 'key'
            # psycopg2/postgres specific
            db.session.execute(db.text("DROP INDEX IF EXISTS ix_app_settings_key"))
            
            # 2. Create a non-unique index on 'key' for performance
            db.session.execute(db.text("CREATE INDEX IF NOT EXISTS ix_app_settings_key ON app_settings (key)"))
            
            # 3. Ensure the multi-tenant unique constraint exists
            # We already have 'uq_appsetting_org_key' in models.py, but let's ensure it in DB
            db.session.execute(db.text("""
                ALTER TABLE app_settings 
                DROP CONSTRAINT IF EXISTS uq_appsetting_org_key,
                ADD CONSTRAINT uq_appsetting_org_key UNIQUE (organisation_id, key)
            """))
            
            db.session.commit()
            print("✅ Successfully refactored app_settings for multi-tenancy.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Failed to fix constraints: {e}")

if __name__ == "__main__":
    fix()
