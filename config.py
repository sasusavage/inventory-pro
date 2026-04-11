import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """
    Application configuration class.
    Loads sensitive credentials from environment variables.
    """
    # Flask secret key for session management
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-this')
    
    # PostgreSQL database connection string
    # Format: postgresql://username:password@host:port/database_name
    _db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/inventory_db')
    if _db_url.startswith('postgres://'):
        _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
    
    SQLALCHEMY_DATABASE_URI = _db_url
    
    # Disable FSAModifications tracking (saves resources)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload limit (5 MB)
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    # Flask environment
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'

    # ── AI & Notifications ────────────────────────────────────────────
    GROQ_API_KEY          = os.getenv('GROQ_API_KEY', '')
    TELEGRAM_BOT_TOKEN    = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID      = os.getenv('TELEGRAM_CHAT_ID', '')
    # Optional: a random secret used to verify Telegram webhook calls
    TELEGRAM_WEBHOOK_SECRET = os.getenv('TELEGRAM_WEBHOOK_SECRET', '')
