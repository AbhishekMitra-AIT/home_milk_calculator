"""
Create PostgreSQL tables before migrating data
Run this FIRST, then run migrate_sqlite_to_postgres.py
"""

import os
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import Integer, String, Float, Boolean, DateTime, ForeignKey
import datetime as dt

load_dotenv()

# Database setup
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "temp-key-for-migration"

# Get PostgreSQL URL
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("✗ DATABASE_URL not found in environment variables")
    print("Make sure you have it in your .env file")
    exit(1)

# Fix postgres:// to postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize db
db.init_app(app)

# Define models (must match your app.py)
class User(db.Model):
    __tablename__ = 'user'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(80), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=True)
    oauth_provider: Mapped[str] = mapped_column(String(20), nullable=True)
    oauth_id: Mapped[str] = mapped_column(String(200), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    
    milk_records = relationship('Milk', back_populates='user', cascade='all, delete-orphan')


class Milk(db.Model):
    __tablename__ = 'milk'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(String(250), nullable=True, index=True)
    milk_qty: Mapped[float] = mapped_column(Float, nullable=True)
    cost: Mapped[float] = mapped_column(Float, nullable=True)
    month_year: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('user.id'), nullable=False, index=True)
    
    user = relationship('User', back_populates='milk_records')


def create_tables():
    """Create all tables in PostgreSQL"""
    print("="*60)
    print("CREATING POSTGRESQL TABLES")
    print("="*60)
    
    try:
        with app.app_context():
            print("\n1. Connecting to PostgreSQL...")
            print(f"   Database: {DATABASE_URL.split('@')[1].split('/')[0] if '@' in DATABASE_URL else 'Unknown'}")
            
            print("\n2. Dropping existing tables (if any)...")
            db.drop_all()
            print("   ✓ Existing tables dropped")
            
            print("\n3. Creating tables...")
            db.create_all()
            print("   ✓ Tables created successfully!")
            
            print("\n4. Verifying tables...")
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            print(f"   Found {len(tables)} tables:")
            for table in tables:
                print(f"   - {table}")
                columns = inspector.get_columns(table)
                print(f"     Columns: {[col['name'] for col in columns]}")
            
            print("\n" + "="*60)
            print("✓ TABLES CREATED SUCCESSFULLY!")
            print("="*60)
            print("\nNext step: Run the migration script")
            print("Command: python migrate_sqlite_to_postgres.py")
            
            return True
            
    except Exception as e:
        print(f"\n✗ Failed to create tables: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\nThis script will:")
    print("1. Connect to your Railway PostgreSQL database")
    print("2. Drop existing tables (if any)")
    print("3. Create fresh tables for User and Milk")
    print("\n⚠️ This will DELETE any existing data in PostgreSQL!")
    
    response = input("\nDo you want to proceed? (y/n): ").lower()
    
    if response == 'y':
        success = create_tables()
        if success:
            print("\n✅ Ready for data migration!")
            print("\nRun: python migrate_sqlite_to_postgres.py")
    else:
        print("\nOperation cancelled.")