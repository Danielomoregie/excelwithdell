"""
Delete all users from the users table in Neon PostgreSQL database.
"""
import sys
import os

# Add src directory to path to import helper functions
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from Neon_Accessibility_Helper_Functions import get_connection, close_connection

def delete_all_users():
    """Delete all records from the users table."""
    conn = None
    try:
        # Connect to database
        conn = get_connection()
        cursor = conn.cursor()
        
        # Count users before deletion
        cursor.execute("SELECT COUNT(*) FROM users;")
        count_before = cursor.fetchone()[0]
        print(f"Users in database before deletion: {count_before}")
        
        # Delete all users
        cursor.execute("DELETE FROM users;")
        conn.commit()
        
        # Count users after deletion
        cursor.execute("SELECT COUNT(*) FROM users;")
        count_after = cursor.fetchone()[0]
        print(f"Users in database after deletion: {count_after}")
        
        print(f"\n✅ Successfully deleted {count_before} user(s) from the users table!")
        
        cursor.close()
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Error deleting users: {e}")
        raise
    finally:
        if conn:
            close_connection(conn)

if __name__ == "__main__":
    print("=" * 60)
    print("DELETE ALL USERS FROM DATABASE")
    print("=" * 60)
    print("\n⚠️  WARNING: This will delete ALL users from the database!")
    confirmation = input("Type 'DELETE ALL' to confirm: ")
    
    if confirmation == "DELETE ALL":
        delete_all_users()
    else:
        print("\n❌ Deletion cancelled. No users were deleted.")
