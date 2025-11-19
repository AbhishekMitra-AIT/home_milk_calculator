"""
Fix PostgreSQL sequences after data migration
This resets the auto-increment counters to continue from the last imported ID
"""

import os
from dotenv import load_dotenv
from create_tables import app, db
from sqlalchemy import text

load_dotenv()

def fix_sequences():
    """Reset PostgreSQL sequences to match imported data"""
    
    print("="*60)
    print("FIXING POSTGRESQL SEQUENCES")
    print("="*60)
    
    try:
        with app.app_context():
            print("\n1. Checking current sequences...")
            
            # Get current max IDs
            result = db.session.execute(text("SELECT MAX(id) FROM \"user\""))
            max_user_id = result.scalar() or 0
            
            result = db.session.execute(text("SELECT MAX(id) FROM milk"))
            max_milk_id = result.scalar() or 0
            
            print(f"   Max User ID: {max_user_id}")
            print(f"   Max Milk ID: {max_milk_id}")
            
            # Reset User sequence
            print("\n2. Resetting User ID sequence...")
            if max_user_id > 0:
                db.session.execute(text(
                    f"SELECT setval('user_id_seq', {max_user_id}, true)"
                ))
                db.session.commit()
                print(f"   ✓ User sequence set to {max_user_id}")
            else:
                print("   ⊘ No users found, sequence unchanged")
            
            # Reset Milk sequence
            print("\n3. Resetting Milk ID sequence...")
            if max_milk_id > 0:
                db.session.execute(text(
                    f"SELECT setval('milk_id_seq', {max_milk_id}, true)"
                ))
                db.session.commit()
                print(f"   ✓ Milk sequence set to {max_milk_id}")
            else:
                print("   ⊘ No milk records found, sequence unchanged")
            
            # Verify sequences
            print("\n4. Verifying sequences...")
            result = db.session.execute(text("SELECT last_value FROM user_id_seq"))
            user_seq = result.scalar()
            
            result = db.session.execute(text("SELECT last_value FROM milk_id_seq"))
            milk_seq = result.scalar()
            
            print(f"   User sequence: {user_seq}")
            print(f"   Milk sequence: {milk_seq}")
            
            print("\n" + "="*60)
            print("✓ SEQUENCES FIXED SUCCESSFULLY!")
            print("="*60)
            print("\nNext IDs that will be assigned:")
            print(f"  - Next User ID: {user_seq + 1}")
            print(f"  - Next Milk ID: {milk_seq + 1}")
            print("\n✓ You can now add new records without conflicts!")
            
            return True
            
    except Exception as e:
        print(f"\n✗ Failed to fix sequences: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\nThis script will reset PostgreSQL auto-increment sequences")
    print("to continue from your migrated data.\n")
    
    if not os.environ.get('DATABASE_URL'):
        print("✗ DATABASE_URL not found in environment!")
        exit(1)
    
    response = input("Fix sequences now? (y/n): ").lower()
    
    if response == 'y':
        success = fix_sequences()
        if success:
            print("\n✅ Ready to add new records!")
            print("Try adding a new milk record now.")
    else:
        print("\nOperation cancelled.")