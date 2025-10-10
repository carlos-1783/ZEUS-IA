import sqlite3
import sys

def list_tables(db_path):
    """List all tables in the database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("Tables in the database:")
        for table in tables:
            print(f"- {table[0]}")
            
            # Get table structure
            cursor.execute(f"PRAGMA table_info({table[0]})")
            columns = cursor.fetchall()
            print(f"  Columns: {', '.join([col[1] for col in columns])}")
            
            # Get sample data (first row)
            try:
                cursor.execute(f"SELECT * FROM {table[0]} LIMIT 1")
                row = cursor.fetchone()
                if row:
                    print(f"  Sample data: {row}")
            except sqlite3.Error as e:
                print(f"  Could not fetch sample data: {e}")
            
        conn.close()
        return tables
    except sqlite3.Error as e:
        print(f"Error accessing database: {e}")
        return []

def update_user_email(db_path, old_email, new_email):
    """Update user email in the database"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find the users table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%user%' OR name LIKE '%users%')")
        user_tables = cursor.fetchall()
        
        if not user_tables:
            print("No user table found in the database.")
            return False
            
        user_table = user_tables[0][0]
        print(f"Found user table: {user_table}")
        
        # Find email column
        cursor.execute(f"PRAGMA table_info({user_table})")
        columns = [col[1].lower() for col in cursor.fetchall()]
        
        email_columns = [col for col in columns if 'email' in col]
        if not email_columns:
            print("No email column found in the user table.")
            return False
            
        email_column = email_columns[0]
        
        # Check if user exists
        cursor.execute(f"SELECT id, {email_column} FROM {user_table} WHERE {email_column} LIKE ?", (f"%{old_email}%",))
        user = cursor.fetchone()
        
        if not user:
            print(f"User with email containing '{old_email}' not found.")
            return False
            
        print(f"Found user: ID={user[0]}, Email={user[1]}")
        
        # Update email
        cursor.execute(
            f"UPDATE {user_table} SET {email_column} = ? WHERE id = ?",
            (new_email, user[0])
        )
        
        conn.commit()
        print(f"Successfully updated email from '{user[1]}' to '{new_email}'")
        return True
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    db_path = "zeus.db"
    
    # List tables and their structure
    print("=== Database Structure ===")
    list_tables(db_path)
    
    # Update user email
    print("\n=== Updating User Email ===")
    old_email = "marketingdigital per,seo@gmail.com"
    new_email = "marketingdigitalperseo@gmail.com"
    
    if update_user_email(db_path, old_email, new_email):
        print("\nEmail updated successfully!")
        print("\n=== Updated User Data ===")
        list_tables(db_path)  # Show updated data
    else:
        print("\nFailed to update email.")
    
    input("\nPress Enter to exit...")
