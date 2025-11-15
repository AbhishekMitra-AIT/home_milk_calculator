"""
Migration script to transfer data from SQLite to PostgreSQL
Run this LOCALLY before deploying to Railway
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import os
from dotenv import load_dotenv

load_dotenv()

def migrate_sqlite_to_postgres():
    """Migrate all data from SQLite to PostgreSQL"""
    
    # SQLite connection
    sqlite_db = 'instance/milk-calculation.db'
    if not os.path.exists(sqlite_db):
        print(f"✗ SQLite database not found at {sqlite_db}")
        return False
    
    # PostgreSQL connection
    postgres_url = os.environ.get('DATABASE_URL')
    if not postgres_url:
        print("✗ DATABASE_URL environment variable not set")
        print("Get it from Railway dashboard → PostgreSQL → Connect → Connection URL")
        return False
    
    # Fix postgres:// to postgresql://
    if postgres_url.startswith('postgres://'):
        postgres_url = postgres_url.replace('postgres://', 'postgresql://', 1)
    
    print("="*60)
    print("SQLITE TO POSTGRESQL MIGRATION")
    print("="*60)
    
    try:
        # Connect to SQLite
        print("\n1. Connecting to SQLite...")
        sqlite_conn = sqlite3.connect(sqlite_db)
        sqlite_cursor = sqlite_conn.cursor()
        
        # Connect to PostgreSQL
        print("2. Connecting to PostgreSQL...")
        pg_conn = psycopg2.connect(postgres_url)
        pg_cursor = pg_conn.cursor()
        
        # Migrate Users
        print("\n3. Migrating Users table...")
        sqlite_cursor.execute("SELECT * FROM user")
        users = sqlite_cursor.fetchall()
        
        if users:
            # Get column names
            sqlite_cursor.execute("PRAGMA table_info(user)")
            user_columns = [col[1] for col in sqlite_cursor.fetchall()]
            
            print(f"   Found {len(users)} users")
            
            # Clear existing data in PostgreSQL (optional)
            response = input("   Clear existing PostgreSQL data first? (y/n): ").lower()
            if response == 'y':
                pg_cursor.execute("TRUNCATE TABLE milk, \"user\" RESTART IDENTITY CASCADE")
                pg_conn.commit()
                print("   ✓ Cleared existing data")
            
            # Insert users
            insert_query = f"""
                INSERT INTO "user" ({', '.join(user_columns)})
                VALUES %s
                ON CONFLICT (email) DO NOTHING
            """
            execute_values(pg_cursor, insert_query, users)
            pg_conn.commit()
            print(f"   ✓ Migrated {len(users)} users")
        else:
            print("   No users to migrate")
        
        # Migrate Milk records
        print("\n4. Migrating Milk table...")
        sqlite_cursor.execute("SELECT * FROM milk")
        milk_records = sqlite_cursor.fetchall()
        
        if milk_records:
            # Get column names
            sqlite_cursor.execute("PRAGMA table_info(milk)")
            milk_columns = [col[1] for col in sqlite_cursor.fetchall()]
            
            print(f"   Found {len(milk_records)} milk records")
            
            # Insert milk records
            insert_query = f"""
                INSERT INTO milk ({', '.join(milk_columns)})
                VALUES %s
            """
            execute_values(pg_cursor, insert_query, milk_records)
            pg_conn.commit()
            print(f"   ✓ Migrated {len(milk_records)} milk records")
        else:
            print("   No milk records to migrate")
        
        # Verify migration
        print("\n5. Verifying migration...")
        pg_cursor.execute("SELECT COUNT(*) FROM \"user\"")
        pg_user_count = pg_cursor.fetchone()[0]
        
        pg_cursor.execute("SELECT COUNT(*) FROM milk")
        pg_milk_count = pg_cursor.fetchone()[0]
        
        print(f"   PostgreSQL Users: {pg_user_count}")
        print(f"   PostgreSQL Milk Records: {pg_milk_count}")
        
        # Close connections
        sqlite_conn.close()
        pg_conn.close()
        
        print("\n" + "="*60)
        print("✓ MIGRATION COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nNext steps:")
        print("1. Commit and push your updated code to GitHub")
        print("2. Railway will automatically deploy with PostgreSQL")
        print("3. Test your application")
        print("4. Keep SQLite database as backup")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def export_sqlite_to_sql():
    """Export SQLite data to SQL file as backup"""
    sqlite_db = 'instance/milk-calculation.db'
    output_file = 'sqlite_backup.sql'
    
    if not os.path.exists(sqlite_db):
        print(f"✗ SQLite database not found at {sqlite_db}")
        return
    
    print(f"\nExporting SQLite to {output_file}...")
    
    conn = sqlite3.connect(sqlite_db)
    
    with open(output_file, 'w') as f:
        for line in conn.iterdump():
            f.write('%s\n' % line)
    
    conn.close()
    print(f"✓ Backup saved to {output_file}")


if __name__ == "__main__":
    print("\nIMPORTANT: Before running this script:")
    print("1. Make sure you have created a PostgreSQL database in Railway")
    print("2. Copy the DATABASE_URL from Railway and add it to your .env file")
    print("3. Install psycopg2: pip install psycopg2-binary")
    print("4. Backup your SQLite database first!")
    
    response = input("\nHave you completed the above steps? (y/n): ").lower()
    
    if response == 'y':
        # Create SQL backup
        export_sqlite_to_sql()
        
        # Run migration
        migrate_sqlite_to_postgres()
    else:
        print("\nPlease complete the preparation steps first.")
        print("\nTo get DATABASE_URL from Railway:")
        print("1. Go to Railway dashboard")
        print("2. Click on PostgreSQL service")
        print("3. Go to 'Connect' tab")
        print("4. Copy the 'Postgres Connection URL'")
        print("5. Add it to your .env file: DATABASE_URL=<copied_url>")