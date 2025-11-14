"""
Migration script to add user_id foreign key to Milk table
and handle existing data.

IMPORTANT: Run this BEFORE deploying the updated app.py
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, String, Float, text, Boolean, DateTime
import os

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create a temporary app for migration
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///milk-calculation.db"
db.init_app(app)

def migrate():
    with app.app_context():
        try:
            print("="*60)
            print("STEP 1: Checking existing database structure...")
            print("="*60)
            
            # Check current table structure
            result = db.session.execute(text("PRAGMA table_info(milk)"))
            milk_columns = [row[1] for row in result]
            print(f"Current Milk table columns: {milk_columns}")
            
            result = db.session.execute(text("PRAGMA table_info(user)"))
            user_columns = [row[1] for row in result]
            print(f"Current User table columns: {user_columns}")
            
            # Check if user_id already exists
            if 'user_id' in milk_columns:
                print("\n✓ Column 'user_id' already exists in Milk table.")
                print("Migration may have already been run.")
                response = input("Do you want to continue anyway? (y/n): ").lower()
                if response != 'y':
                    print("Migration cancelled.")
                    return False
            
            print("\n" + "="*60)
            print("STEP 2: Counting existing records...")
            print("="*60)
            
            # Count existing milk records
            result = db.session.execute(text("SELECT COUNT(*) FROM milk"))
            milk_count = result.scalar()
            print(f"Found {milk_count} milk records")
            
            # Count existing users
            result = db.session.execute(text("SELECT COUNT(*) FROM user"))
            user_count = result.scalar()
            print(f"Found {user_count} user accounts")
            
            if milk_count > 0 and user_count == 0:
                print("\n⚠ WARNING: You have milk records but no users!")
                print("You need to create at least one user account first.")
                print("Please run the app, register an account, then run this migration.")
                return False
            
            print("\n" + "="*60)
            print("STEP 3: Adding user_id column to Milk table...")
            print("="*60)
            
            if 'user_id' not in milk_columns:
                # Add the new column (nullable first)
                db.session.execute(text("ALTER TABLE milk ADD COLUMN user_id INTEGER"))
                db.session.commit()
                print("✓ Column 'user_id' added successfully!")
            
            print("\n" + "="*60)
            print("STEP 4: Handling existing milk records...")
            print("="*60)
            
            if milk_count > 0:
                # Get the first user (or let admin choose)
                result = db.session.execute(text("SELECT id, email, username FROM user ORDER BY id LIMIT 10"))
                users = result.fetchall()
                
                if not users:
                    print("No users found. Creating a default admin user...")
                    print("⚠ You should delete this and create your own account later!")
                    
                    # Create a temporary admin user
                    from werkzeug.security import generate_password_hash
                    admin_email = "admin@milkcalculator.com"
                    admin_password = generate_password_hash("admin123")
                    
                    db.session.execute(text(
                        "INSERT INTO user (email, username, password_hash, email_verified) "
                        "VALUES (:email, :username, :password, :verified)"
                    ), {
                        "email": admin_email,
                        "username": "Admin",
                        "password": admin_password,
                        "verified": True
                    })
                    db.session.commit()
                    
                    result = db.session.execute(text("SELECT id FROM user WHERE email = :email"), 
                                               {"email": admin_email})
                    default_user_id = result.scalar()
                    
                    print(f"✓ Created admin user (ID: {default_user_id})")
                    print(f"   Email: {admin_email}")
                    print(f"   Password: admin123")
                    print(f"   ⚠ CHANGE THIS PASSWORD IMMEDIATELY AFTER LOGGING IN!")
                else:
                    print("\nAvailable users:")
                    for user in users:
                        print(f"  ID: {user[0]} | Email: {user[1]} | Username: {user[2]}")
                    
                    print("\nWhich user should own the existing milk records?")
                    default_user_id = input("Enter user ID (or press Enter for first user): ").strip()
                    
                    if not default_user_id:
                        default_user_id = users[0][0]
                    else:
                        default_user_id = int(default_user_id)
                
                # Assign all existing records to the chosen user
                db.session.execute(
                    text("UPDATE milk SET user_id = :user_id WHERE user_id IS NULL"),
                    {"user_id": default_user_id}
                )
                db.session.commit()
                
                print(f"\n✓ Assigned {milk_count} milk records to user ID {default_user_id}")
            
            print("\n" + "="*60)
            print("STEP 5: Making user_id NOT NULL...")
            print("="*60)
            
            # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
            print("Creating new table structure...")
            
            db.session.execute(text("""
                CREATE TABLE milk_new (
                    id INTEGER PRIMARY KEY,
                    date VARCHAR(250),
                    milk_qty FLOAT,
                    cost FLOAT,
                    month_year VARCHAR(50),
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
            """))
            
            print("Copying data to new table...")
            db.session.execute(text("""
                INSERT INTO milk_new (id, date, milk_qty, cost, month_year, user_id)
                SELECT id, date, milk_qty, cost, month_year, user_id FROM milk
            """))
            
            print("Replacing old table...")
            db.session.execute(text("DROP TABLE milk"))
            db.session.execute(text("ALTER TABLE milk_new RENAME TO milk"))
            
            db.session.commit()
            print("✓ Table structure updated successfully!")
            
            # Verify
            result = db.session.execute(text("SELECT COUNT(*) FROM milk"))
            final_count = result.scalar()
            
            print("\n" + "="*60)
            print("MIGRATION SUMMARY")
            print("="*60)
            print(f"✓ Migration completed successfully!")
            print(f"✓ Total milk records: {final_count}")
            print(f"✓ All records now have user_id associations")
            print("\n✓ You can now run your updated app.py")
            print("="*60)
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            db.session.rollback()
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == "__main__":
    print("="*60)
    print("DATABASE MIGRATION: ADD USER_ID TO MILK TABLE")
    print("="*60)
    print("\nThis script will:")
    print("1. Add 'user_id' column to the milk table")
    print("2. Create a foreign key relationship to the user table")
    print("3. Assign existing milk records to a user")
    print("4. Make user_id a required field")
    print("\n⚠ IMPORTANT: Backup your database before proceeding!")
    print(f"Database location: instance/milk-calculation.db")
    
    # Check if database exists
    db_path = "instance/milk-calculation.db"
    if not os.path.exists(db_path):
        print(f"\n✗ Database not found at {db_path}")
        print("The database will be created when you run the app for the first time.")
        print("If you're starting fresh, you don't need to run this migration.")
    else:
        response = input("\nDo you want to proceed with the migration? (y/n): ").lower()
        
        if response == 'y':
            print("\nStarting migration...\n")
            success = migrate()
            if success:
                print("\n✅ All done! Your app is now ready with multi-user support.")
        else:
            print("\nMigration cancelled.")