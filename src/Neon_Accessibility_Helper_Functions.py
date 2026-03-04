import os
import psycopg2
import pandas as pd
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from psycopg2 import sql
from werkzeug.security import generate_password_hash, check_password_hash

# ==============================
# CONNECTION MANAGEMENT
# ==============================

def get_connection():
    """Create and return a Neon PostgreSQL connection."""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError("DATABASE_URL not found in .env")

    print("Connected to Neon Hosted Server!\n")
    return psycopg2.connect(database_url)


def close_connection(conn):
    """Safely close database connection."""
    if conn:
        print("\nThank you for being responsible! :)")
        conn.close()

#-------------------------------------------------------
# Example Function (if we wanted to return a row given name of dataset and index):
# Idea is to show how to code such helper functions:

def get_row_by_index(table_name, row_index, conn):
    """
    Fetch a single row ordered chronologically by date.
    """
    query = sql.SQL("""
        SELECT *
        FROM {table}
        ORDER BY date ASC
        OFFSET %s
        LIMIT 1;
    """).format(
        table=sql.Identifier(table_name)
    )

    # Convert SQL object to string
    query_str = query.as_string(conn)

    df = pd.read_sql(query_str, conn, params=(row_index,))

    return df
#-------------------------------------------------------


# ==============================
# USER MANAGEMENT FUNCTIONS
# ==============================

def get_user_by_email(email, conn):
    """
    Fetch user profile by email.
    Returns dict with user data or None if not found.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, first_name, last_name, email, department,
               sub_department, location, created_at, updated_at
        FROM users
        WHERE email = %s;
        """,
        (email,)
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return None

    return {
        'user_id': str(row[0]),
        'first_name': row[1],
        'last_name': row[2],
        'email': row[3],
        'department': row[4],
        'sub_department': row[5],
        'location': row[6],
        'created_at': row[7],
        'updated_at': row[8],
    }


def create_user(first_name, last_name, email, department, sub_department=None, location=None, conn=None):
    """
    Create a new user profile.
    Returns the created user's data or None if creation failed.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, department, sub_department, location)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id, first_name, last_name, email, department, sub_department, location, created_at, updated_at;
        """, (first_name, last_name, email, department, sub_department, location))
        
        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        
        if row:
            return {
                'user_id': str(row[0]),
                'first_name': row[1],
                'last_name': row[2],
                'email': row[3],
                'department': row[4],
                'sub_department': row[5],
                'location': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
        return None
        
    except Exception as e:
        print(f"Error creating user: {e}")
        conn.rollback()
        return None
    finally:
        if should_close:
            close_connection(conn)


def update_user(email, first_name=None, last_name=None, department=None, 
                sub_department=None, location=None, conn=None):
    """
    Update user profile fields.
    Returns True if successful, False otherwise.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        
        # Build dynamic update query
        updates = []
        params = []
        
        if first_name is not None:
            updates.append("first_name = %s")
            params.append(first_name)
        if last_name is not None:
            updates.append("last_name = %s")
            params.append(last_name)
        if department is not None:
            updates.append("department = %s")
            params.append(department)
        if sub_department is not None:
            updates.append("sub_department = %s")
            params.append(sub_department)
        if location is not None:
            updates.append("location = %s")
            params.append(location)
        
        if not updates:
            return True  # Nothing to update
        
        updates.append("updated_at = now()")
        params.append(email)
        
        query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE email = %s;
        """
        
        cursor.execute(query, params)
        conn.commit()
        cursor.close()
        return True
        
    except Exception as e:
        print(f"Error updating user: {e}")
        conn.rollback()
        return False
    finally:
        if should_close:
            close_connection(conn)


def get_departments(conn=None):
    """
    Get list of all departments.
    Returns list of dicts with department_code and department_name.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT department_code, department_name, parent_department_code
            FROM departments
            ORDER BY department_name;
            """
        )
        rows = cursor.fetchall()
        cursor.close()

        return [
            {
                'department_code': row[0],
                'department_name': row[1],
                'parent_department_code': row[2],
            }
            for row in rows
        ]
    finally:
        if should_close:
            close_connection(conn)


def update_password(email, old_password, new_password, conn):
    """
    Update a user's password.
    Returns True if successful, False otherwise.
    """
    # First, verify the old password
    if not authenticate_user(email, old_password, conn):
        return False
    
    # Hash the new password
    password_hash = hash_password(new_password)
    
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE users
            SET password_hash = %s, updated_at = now()
            WHERE email = %s;
        """, (password_hash, email))
        cursor.close()
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating password: {e}")
        conn.rollback()
        return False


# ==============================
# PASSWORD & AUTHENTICATION FUNCTIONS
# ==============================

def hash_password(password):
    """Hash a password using PBKDF2:SHA256."""
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password, password_hash):
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)


def create_user_with_password(first_name, last_name, email, password, department, sub_department=None, location=None, conn=None):
    """
    Create a new user with hashed password.
    Returns the created user's data or None if creation failed.
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    
    try:
        password_hash = hash_password(password)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (first_name, last_name, email, password_hash, department, sub_department, location)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING user_id, first_name, last_name, email, department, sub_department, location, created_at, updated_at;
        """, (first_name, last_name, email, password_hash, department, sub_department, location))
        
        row = cursor.fetchone()
        cursor.close()
        conn.commit()
        
        if row:
            return {
                'user_id': str(row[0]),
                'first_name': row[1],
                'last_name': row[2],
                'email': row[3],
                'department': row[4],
                'sub_department': row[5],
                'location': row[6],
                'created_at': row[7],
                'updated_at': row[8]
            }
        return None
    except Exception as e:
        conn.rollback()
        print(f"Error creating user with password: {e}")
        return None
    finally:
        if should_close:
            close_connection(conn)


def authenticate_user(email, password, conn):
    """
    Authenticate a user with email and password.
    Returns user data if authentication successful, None otherwise.
    """
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, first_name, last_name, email, department,
               sub_department, location, created_at, updated_at, password_hash
        FROM users
        WHERE email = %s;
        """,
        (email,)
    )
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return None

    password_hash = row[9]
    if not password_hash or not verify_password(password, password_hash):
        return None

    return {
        'user_id': str(row[0]),
        'first_name': row[1],
        'last_name': row[2],
        'email': row[3],
        'department': row[4],
        'sub_department': row[5],
        'location': row[6],
        'created_at': row[7],
        'updated_at': row[8],
    }
