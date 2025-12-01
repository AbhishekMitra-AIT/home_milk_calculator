"""
Migration script to add refresh_token column to User table
Run this once before using JWT authentication
"""

from app import app, db
from sqlalchemy import text, inspect

def add_refresh_token_column():
    """Add refresh_token column to User table"""
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('user')]
            
            if 'refresh_token' not in columns:
                print("Adding refresh_token column...")
                db.session.execute(text('ALTER TABLE "user" ADD COLUMN refresh_token VARCHAR(500)'))
                db.session.commit()
                print("✓ refresh_token column added successfully")
            else:
                print("✓ refresh_token column already exists")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    add_refresh_token_column()