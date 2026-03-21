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
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/inventory_db'
    )
    
    # Disable FSAModifications tracking (saves resources)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Flask environment
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', 'True') == 'True'
