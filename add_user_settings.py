"""
Add settings columns to existing User table
Run this after updating app.py with new User model
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def add_settings_columns():
    """Add milk_price_per_litre, currency, and currency_symbol to User table"""
    
    DATABASE_URL = os.environ.get("DATABASE_URL")
    
    if not DATABASE_URL:
        print("✗ DATABASE_URL not found")
        return False
    
    # Fix postgres:// to postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    print("="*60)
    print("ADDING USER SETTINGS COLUMNS")
    print("="*60)
    
    try:
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            print("\n1. Checking existing columns...")
            
            # Check if columns already exist
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'user'
            """))
            existing_columns = [row[0] for row in result]
            print(f"   Existing columns: {existing_columns}")
            
            # Add milk_price_per_litre
            if 'milk_price_per_litre' not in existing_columns:
                print("\n2. Adding milk_price_per_litre column...")
                conn.execute(text(
                    'ALTER TABLE "user" ADD COLUMN milk_price_per_litre FLOAT DEFAULT 50.0'
                ))
                conn.commit()
                print("   ✓ Added milk_price_per_litre")
            else:
                print("\n2. milk_price_per_litre already exists")
            
            # Add currency
            if 'currency' not in existing_columns:
                print("\n3. Adding currency column...")
                conn.execute(text(
                    "ALTER TABLE \"user\" ADD COLUMN currency VARCHAR(10) DEFAULT 'INR'"
                ))
                conn.commit()
                print("   ✓ Added currency")
            else:
                print("\n3. currency already exists")
            
            # Add currency_symbol
            if 'currency_symbol' not in existing_columns:
                print("\n4. Adding currency_symbol column...")
                conn.execute(text(
                    "ALTER TABLE \"user\" ADD COLUMN currency_symbol VARCHAR(5) DEFAULT '₹'"
                ))
                conn.commit()
                print("   ✓ Added currency_symbol")
            else:
                print("\n4. currency_symbol already exists")
            
            # Update existing users with defaults if needed
            print("\n5. Updating existing users with default values...")
            conn.execute(text("""
                UPDATE "user" 
                SET milk_price_per_litre = 50.0 
                WHERE milk_price_per_litre IS NULL
            """))
            conn.execute(text("""
                UPDATE "user" 
                SET currency = 'INR' 
                WHERE currency IS NULL
            """))
            conn.execute(text("""
                UPDATE "user" 
                SET currency_symbol = '₹' 
                WHERE currency_symbol IS NULL
            """))
            conn.commit()
            print("   ✓ Updated users with default values")
            
            # Verify
            print("\n6. Verifying changes...")
            result = conn.execute(text("""
                SELECT COUNT(*) FROM "user"
            """))
            user_count = result.scalar()
            print(f"   Total users: {user_count}")
            
            result = conn.execute(text("""
                SELECT email, milk_price_per_litre, currency, currency_symbol 
                FROM "user" 
                LIMIT 3
            """))
            users = result.fetchall()
            if users:
                print("\n   Sample users:")
                for user in users:
                    print(f"   - {user[0]}: {user[2]}{user[3]} {user[1]}/L")
            
            print("\n" + "="*60)
            print("✓ SETTINGS COLUMNS ADDED SUCCESSFULLY!")
            print("="*60)
            print("\nUsers can now configure:")
            print("  • Milk price per litre")
            print("  • Currency preference")
            print("  • Currency symbol")
            print("\nAccess via: /settings route")
            
            return True
            
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\nThis script adds settings columns to the User table")
    print("(milk_price_per_litre, currency, currency_symbol)\n")
    
    if not os.environ.get('DATABASE_URL'):
        print("✗ DATABASE_URL not found in environment")
        exit(1)
    
    response = input("Add settings columns now? (y/n): ").lower()
    
    if response == 'y':
        success = add_settings_columns()
        if success:
            print("\n✅ Ready! Users can now access /settings")
    else:
        print("\nOperation cancelled.")