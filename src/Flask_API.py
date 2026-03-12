import os
import pickle
import json
import pandas as pd
import re
import math
import time
import uuid
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from functools import wraps
from psycopg2 import sql

from Sentiment_Analyzer import analyze_sentiment, clean_review_text
from Theme_Extractor import classify_review_themes, COMPLAINT_CATEGORIES
from Risk_Score_Engine import _get_alert_level, compute_product_risk_scores, ALERT_THRESHOLDS
from Revenue_Impact_Calculator import (
    calculate_revenue_impact, calculate_portfolio_impact, format_currency
)
from Neon_Accessibility_Helper_Functions import (
    get_connection, close_connection, get_user_by_email, 
    create_user, update_user, get_departments,
    hash_password, verify_password, authenticate_user, create_user_with_password, update_password
)

# ==============================
# APP SETUP
# ==============================

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
)

# Secret key for session management
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
CURRENT_PRODUCTION_MODEL_PATH = os.path.join(MODELS_DIR, "current_production_model.pkl")
LEGACY_ARTIFACTS_PATH = os.path.join(MODELS_DIR, "Risk_Model_Artifacts.pkl")
ARTIFACTS_PATH = CURRENT_PRODUCTION_MODEL_PATH
MODEL_REGISTRY_PATH = os.path.join(MODELS_DIR, "model_registry.json")
BASELINE_METRICS_PATH = os.path.join(MODELS_DIR, "baseline_metrics.json")
VALIDATION_REPORT_PATH = os.path.join(MODELS_DIR, "Validation_Report.json")
EVALUATION_DATASET_PATH = os.path.join(MODELS_DIR, "evaluation_reviews.csv")

# Global artifacts (loaded on startup)
artifacts = None


def require_profile(f):
    """Decorator to require user profile before accessing route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


def require_dev_unlock(f):
    """Decorator to require developer mode unlock before accessing route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('dev_unlocked', False):
            return redirect(url_for('login_page') + '?tab=developer')
        return f(*args, **kwargs)
    return decorated_function


def get_current_user():
    """Get current logged-in user from session."""
    if 'user_email' not in session:
        return None
    
    conn = get_connection()
    user = get_user_by_email(session['user_email'], conn)
    close_connection(conn)
    return user


def filter_by_department(data, user):
    """Filter dashboard data by user's department (scaffolding for future use).
    
    TODO: Implement department-specific filtering:
    - Marketing: Focus on trends, summary metrics
    - Engineering: Product quality signals, technical issues
    - Finance: Revenue risk, KPI rollups
    - Customer Support: Complaint themes, response times
    
    For now, returns data unfiltered.
    """
    # Placeholder for department-specific logic
    return data


def load_artifacts():
    global artifacts
    path_to_load = ARTIFACTS_PATH if os.path.exists(ARTIFACTS_PATH) else LEGACY_ARTIFACTS_PATH
    if not os.path.exists(path_to_load):
        raise FileNotFoundError(
            f"Model artifacts not found at {path_to_load}. Run Train_Model.py first."
        )
    with open(path_to_load, "rb") as f:
        artifacts = pickle.load(f)
    print(f"Loaded model artifacts from {path_to_load} ({len(artifacts['risk_results'])} products)")


def get_model_metadata():
    """Return model metadata from artifacts when available."""
    if isinstance(artifacts, dict):
        metadata = artifacts.get("model_metadata", {})
        if isinstance(metadata, dict):
            return metadata
    return {}


def _load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


# ==============================
# ROUTES - DASHBOARD
# ==============================

@app.route("/")
@require_profile
def dashboard():
    user = get_current_user()
    return render_template("Dashboard.html", user=user)


@app.route("/raw-dataset")
@require_profile
def raw_dataset_page():
    user = get_current_user()
    return render_template("raw_dataset.html", user=user)


@app.route("/product-risk")
@require_profile
def product_risk_page():
    user = get_current_user()
    return render_template("Product_Risk.html", user=user)


@app.route("/dev-lock")
def dev_lock_page():
    user = get_current_user()
    return render_template("pattern_lock.html", user=user)


@app.route("/developer")
def developer_page():
    # Show developer page with passkey prompt (handled client-side)
    user = get_current_user()
    return render_template("developer.html", user=user)


@app.route("/developer/dell-infrastructure-fit")
@require_dev_unlock
def developer_dell_infrastructure_fit_page():
    user = get_current_user()
    return render_template("dell_infrastructure_fit.html", user=user)


@app.route("/developer/replay-analysis")
@require_dev_unlock
def developer_replay_analysis_page():
    user = get_current_user()
    return render_template("replay_analysis.html", user=user)


@app.route("/api/dev-unlock", methods=['POST'])
def dev_unlock():
    data = request.get_json() or {}
    passkey = data.get('passkey', '')
    
    # Verify passkey
    if passkey != 'a1b2c3d4':
        return jsonify({"status": "error", "message": "Invalid passkey"}), 403
    
    # Set session flag when passkey is correct
    session['dev_unlocked'] = True
    session.modified = True
    
    # Check if user is logged in
    if 'user_email' in session:
        return jsonify({"status": "success", "redirect": "/developer"})
    else:
        return jsonify({"status": "success", "redirect": "/developer"})


@app.route("/api/dev-check-unlock")
def dev_check_unlock():
    """Check if developer mode is already unlocked in session"""
    unlocked = session.get('dev_unlocked', False)
    return jsonify({"unlocked": unlocked})


RAW_DATASET_ALLOWED_TABLES = [
    "online_reviews",
]


def _list_public_tables(conn):
        cursor = conn.cursor()
        cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                ORDER BY table_name;
                """
        )
        tables = [str(row[0]) for row in cursor.fetchall()]
        cursor.close()
        return tables


@app.route("/api/raw-dataset/tables")
@require_profile
def raw_dataset_tables():
    conn = get_connection()
    try:
        available = set(_list_public_tables(conn))
        tables = [table for table in RAW_DATASET_ALLOWED_TABLES if table in available]
        return jsonify({
            "status": "success",
            "tables": tables,
        })
    finally:
        close_connection(conn)


@app.route("/api/raw-dataset/data")
@require_profile
def raw_dataset_data():
    table = (request.args.get("table") or "").strip()

    try:
        limit = int(request.args.get("limit", 100))
    except ValueError:
        limit = 100
    limit = max(1, min(limit, 500))

    try:
        offset = int(request.args.get("offset", 0))
    except ValueError:
        offset = 0
    offset = max(0, offset)

    if not table:
        return jsonify({"status": "error", "message": "table is required"}), 400

    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table):
        return jsonify({"status": "error", "message": "Invalid table name"}), 400

    if table not in RAW_DATASET_ALLOWED_TABLES:
        return jsonify({"status": "error", "message": "Only allowed datasets are available here"}), 403

    conn = get_connection()
    result_columns = []
    fetched_rows = []
    total_rows = 0
    try:
        available_tables = set(_list_public_tables(conn))
        if table not in available_tables:
            return jsonify({"status": "error", "message": "Table not found"}), 404

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
            """,
            (table,)
        )
        columns = [str(row[0]) for row in cursor.fetchall()]
        if not columns:
            cursor.close()
            return jsonify({
                "status": "success",
                "table": table,
                "columns": [],
                "rows": [],
                "total_rows": 0,
                "returned_rows": 0,
                "offset": offset,
                "limit": limit,
            })

        table_ident = sql.Identifier(table)
        where_conditions = []
        params = []

        # Process column-specific filters
        for key, value in request.args.items():
            if key.startswith('filter_') and value:
                # Extract column name from filter key
                filter_key = key[7:]  # Remove 'filter_' prefix
                
                if filter_key.endswith('_min'):
                    # Range filter minimum
                    col_name = filter_key[:-4]
                    if col_name in columns:
                        max_val = request.args.get(f'filter_{col_name}_max')
                        if max_val:
                            where_conditions.append(
                                sql.SQL("{col} >= %s AND {col} <= %s").format(col=sql.Identifier(col_name))
                            )
                            params.extend([float(value), float(max_val)])
                elif filter_key.endswith('_op'):
                    # Operator-based filter
                    continue  # Handled with the main filter
                elif filter_key.endswith('_max'):
                    # Skip, already handled with _min
                    continue
                else:
                    # Check if there's an operator
                    op = request.args.get(f'filter_{filter_key}_op', '')
                    if op and op in ['=', '>', '<', '>=', '<=']:
                        where_conditions.append(
                            sql.SQL("{col} " + op + " %s").format(col=sql.Identifier(filter_key))
                        )
                        params.append(float(value) if op != '=' else value)
                    elif filter_key in columns:
                        # Text search
                        where_conditions.append(
                            sql.SQL("CAST({col} AS TEXT) ILIKE %s").format(col=sql.Identifier(filter_key))
                        )
                        params.append(f"%{value}%")

        where_clause = sql.SQL("")
        if where_conditions:
            where_clause = sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_conditions)

        # Default sort by timestamp DESC
        order_clause = sql.SQL(" ORDER BY timestamp DESC") if 'timestamp' in columns else sql.SQL("")

        count_query = sql.SQL("SELECT COUNT(*) FROM {table}{where}").format(
            table=table_ident,
            where=where_clause,
        )
        cursor.execute(count_query, params)
        total_rows = cursor.fetchone()[0]

        data_query = sql.SQL("SELECT * FROM {table}{where}{order} LIMIT %s OFFSET %s").format(
            table=table_ident,
            where=where_clause,
            order=order_clause,
        )
        data_params = params + [limit, offset]
        cursor.execute(data_query, data_params)
        fetched_rows = cursor.fetchall()
        result_columns = [desc[0] for desc in cursor.description]
        cursor.close()
    except Exception as exc:
        return jsonify({"status": "error", "message": f"Failed to query table rows: {str(exc)}"}), 500
    finally:
        close_connection(conn)

    rows = []
    for row in fetched_rows:
        row_dict = {}
        for idx, col_name in enumerate(result_columns):
            value = row[idx]
            try:
                if pd.isna(value):
                    value = None
            except Exception:
                pass
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif isinstance(value, memoryview):
                value = value.tobytes().hex()
            elif isinstance(value, (bytes, bytearray)):
                value = value.hex()
            elif isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                value = None
            elif value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
                value = str(value)
            row_dict[col_name] = value
        rows.append(row_dict)

    return jsonify({
        "status": "success",
        "table": table,
        "columns": result_columns,
        "rows": rows,
        "total_rows": total_rows,
        "returned_rows": len(rows),
        "offset": offset,
        "limit": limit,
    })


# ==============================
# ROUTES - AUTHENTICATION & PROFILE
# ==============================

@app.route("/login")
def login_page():
    """Show login/registration page."""
    return render_template("login.html")


@app.route("/api/check_email", methods=["POST"])
def check_email():
    """Check if email exists. Does NOT log in - just returns exists status."""
    body = request.get_json()
    email = body.get("email", "").strip().lower()
    
    if not email:
        return jsonify({"status": "error", "message": "Email required"}), 400
    
    # Validate FusionTech domain
    if not email.endswith('@fusiontech.com'):
        return jsonify({"status": "error", "message": "Please use your FusionTech Systems company email."}), 400
    
    conn = get_connection()
    user = get_user_by_email(email, conn)
    close_connection(conn)
    
    if user:
        return jsonify({
            "status": "success",
            "exists": True
        })
    else:
        return jsonify({
            "status": "success",
            "exists": False
        })


@app.route("/api/login", methods=["POST"])
def login():
    """Authenticate user with email and password."""
    body = request.get_json()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    
    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password required"}), 400
    
    # Validate FusionTech domain
    if not email.endswith('@fusiontech.com'):
        return jsonify({"status": "error", "message": "Please use your FusionTech Systems company email."}), 400
    
    conn = get_connection()
    user = authenticate_user(email, password, conn)
    close_connection(conn)
    
    if user:
        # Authentication successful
        session['user_email'] = email
        return jsonify({
            "status": "success",
            "user": {
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "email": user['email'],
                "department": user['department'],
            }
        })
    else:
        # Authentication failed
        return jsonify({"status": "error", "message": "Invalid email or password"}), 401


@app.route("/api/register", methods=["POST"])
def register():
    """Register a new user profile with password."""
    body = request.get_json()
    
    required = ['email', 'first_name', 'last_name', 'department', 'password']
    for field in required:
        if not body.get(field):
            return jsonify({"status": "error", "message": f"{field} is required"}), 400
    
    email = body['email'].strip().lower()
    password = body['password']
    
    # Validate password strength
    if len(password) < 8:
        return jsonify({"status": "error", "message": "Password must be at least 8 characters"}), 400
    
    # Validate FusionTech domain
    if not email.endswith('@fusiontech.com'):
        return jsonify({"status": "error", "message": "Please use your FusionTech Systems company email."}), 400
    
    conn = get_connection()
    
    # Check if user already exists
    existing = get_user_by_email(email, conn)
    if existing:
        close_connection(conn)
        return jsonify({"status": "error", "message": "Email already registered"}), 400
    
    # Create user with password
    user = create_user_with_password(
        first_name=body['first_name'],
        last_name=body['last_name'],
        email=email,
        password=password,
        department=body['department'],
        sub_department=body.get('sub_department'),
        location=body.get('location'),
        conn=conn
    )
    
    close_connection(conn)
    
    if user:
        session['user_email'] = user['email']
        return jsonify({
            "status": "success",
            "user": {
                "first_name": user['first_name'],
                "last_name": user['last_name'],
                "email": user['email'],
                "department": user['department'],
            }
        })
    else:
        return jsonify({"status": "error", "message": "Failed to create user"}), 500


@app.route("/api/profile")
@require_profile
def get_profile():
    """Get current user's profile."""
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    return jsonify({
        "status": "success",
        "user": user
    })


@app.route("/api/profile", methods=["PUT"])
@require_profile
def update_profile():
    """Update current user's profile and optionally change password."""
    user = get_current_user()
    if not user:
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    body = request.get_json()
    
    conn = get_connection()
    
    # Handle password change if provided
    if body.get('new_password'):
        # Validate password change fields
        new_password = body.get('new_password', '').strip()
        current_password = body.get('current_password', '').strip()
        
        if not new_password or not current_password:
            close_connection(conn)
            return jsonify({"status": "error", "message": "Both current and new password required"}), 400
        
        if len(new_password) < 8:
            close_connection(conn)
            return jsonify({"status": "error", "message": "New password must be at least 8 characters"}), 400
        
        # Verify current password and update
        password_updated = update_password(user['email'], current_password, new_password, conn)
        
        if not password_updated:
            close_connection(conn)
            return jsonify({"status": "error", "message": "Invalid current password"}), 401
    
    # Update profile fields
    success = update_user(
        email=user['email'],
        first_name=body.get('first_name'),
        last_name=body.get('last_name'),
        department=body.get('department'),
        sub_department=body.get('sub_department'),
        location=body.get('location'),
        conn=conn
    )
    close_connection(conn)
    
    if success:
        return jsonify({"status": "success", "message": "Profile updated"})
    else:
        return jsonify({"status": "error", "message": "Update failed"}), 500


@app.route("/api/departments")
def list_departments():
    """Get list of available departments."""
    conn = get_connection()
    departments = get_departments(conn)
    close_connection(conn)

    metadata = get_model_metadata()
    ui_defaults = metadata.get("ui_defaults", {}) if isinstance(metadata.get("ui_defaults", {}), dict) else {}
    enabled_departments = set(ui_defaults.get("enabled_departments", ["Engineering & IT", "Marketing", "Sales"]))

    normalized_departments = []
    for dept in departments:
        row = dict(dept)
        row["is_enabled"] = row.get("department_name") in enabled_departments
        normalized_departments.append(row)
    
    return jsonify({
        "status": "success",
        "departments": normalized_departments
    })


def ensure_review_tables(conn):
    """Create review-related tables and seed product catalog from online_reviews."""
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS "FusionTech_Product" (
            product_id SERIAL PRIMARY KEY,
            title_y TEXT UNIQUE NOT NULL,
            asin TEXT,
            main_category TEXT,
            average_rating TEXT,
            rating_number TEXT,
            features TEXT,
            price TEXT,
            store TEXT,
            brand TEXT,
            default_os TEXT,
            default_color TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fusiontech_submitted_reviews (
            review_id BIGSERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES "FusionTech_Product"(product_id),
            rating INTEGER NOT NULL,
            title_x TEXT NOT NULL,
            text TEXT NOT NULL,
            asin TEXT,
            user_id TEXT,
            timestamp BIGINT NOT NULL,
            helpful_vote INTEGER NULL,
            main_category TEXT,
            title_y TEXT,
            average_rating TEXT,
            rating_number TEXT,
            features TEXT,
            price TEXT,
            store TEXT,
            os TEXT,
            color TEXT,
            brand TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_submitted_reviews_product_id
        ON fusiontech_submitted_reviews(product_id);
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_submitted_reviews_timestamp
        ON fusiontech_submitted_reviews(timestamp DESC);
        """
    )

    # Seed the product catalog from online_reviews when available.
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'online_reviews'
        );
        """
    )
    has_online_reviews = cursor.fetchone()[0]

    if has_online_reviews:
        cursor.execute(
            """
            INSERT INTO "FusionTech_Product"
                (title_y, asin, main_category, average_rating, rating_number, features, price, store, brand, default_os, default_color)
            SELECT DISTINCT ON (title_y)
                title_y,
                asin,
                main_category,
                average_rating,
                rating_number,
                features,
                price,
                store,
                brand,
                os,
                color
            FROM online_reviews
            WHERE title_y IS NOT NULL AND TRIM(title_y) <> ''
            ORDER BY title_y, COALESCE(rating_number::TEXT, '') DESC, COALESCE(asin, '') ASC
            ON CONFLICT (title_y) DO UPDATE SET
                asin = EXCLUDED.asin,
                main_category = EXCLUDED.main_category,
                average_rating = EXCLUDED.average_rating,
                rating_number = EXCLUDED.rating_number,
                features = EXCLUDED.features,
                price = EXCLUDED.price,
                store = EXCLUDED.store,
                brand = EXCLUDED.brand,
                default_os = EXCLUDED.default_os,
                default_color = EXCLUDED.default_color;
            """
        )

    cursor.close()


@app.route("/api/review-products")
def list_review_products():
    """Return products available for review selection."""
    conn = get_connection()
    try:
        ensure_review_tables(conn)
        conn.commit()

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT product_id, title_y, asin, main_category, average_rating, rating_number,
                   features, price, store, brand, default_os, default_color
            FROM "FusionTech_Product"
            ORDER BY title_y ASC;
            """
        )
        rows = cursor.fetchall()
        cursor.close()

        products = [
            {
                "product_id": row[0],
                "title_y": row[1],
                "asin": row[2],
                "main_category": row[3],
                "average_rating": row[4],
                "rating_number": row[5],
                "features": row[6],
                "price": row[7],
                "store": row[8],
                "brand": row[9],
                "default_os": row[10],
                "default_color": row[11],
            }
            for row in rows
        ]

        return jsonify({"status": "success", "products": products})
    except Exception as exc:
        conn.rollback()
        return jsonify({"status": "error", "message": f"Failed to load review products: {str(exc)}"}), 500
    finally:
        close_connection(conn)


@app.route("/api/submit_review", methods=["POST"])
def submit_review():
    """Persist customer review and infer metadata from selected product."""
    body = request.get_json() or {}

    product_id = body.get("product_id")
    rating = body.get("rating")
    title = (body.get("title") or "").strip()
    text = (body.get("text") or "").strip()
    os_value = (body.get("os") or "").strip() or None
    color_value = (body.get("color") or "").strip() or None
    price_value = (body.get("price") or "").strip() or None

    if not product_id:
        return jsonify({"status": "error", "message": "Product is required"}), 400
    if rating is None:
        return jsonify({"status": "error", "message": "Rating is required"}), 400
    if not title:
        return jsonify({"status": "error", "message": "Review title is required"}), 400
    if not text:
        return jsonify({"status": "error", "message": "Review text is required"}), 400

    try:
        product_id = int(product_id)
        rating = int(rating)
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "Invalid product or rating value"}), 400

    if rating < 1 or rating > 5:
        return jsonify({"status": "error", "message": "Rating must be between 1 and 5"}), 400

    conn = get_connection()
    try:
        ensure_review_tables(conn)

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT product_id, title_y, asin, main_category, average_rating, rating_number,
                   features, price, store, brand, default_os, default_color
            FROM "FusionTech_Product"
            WHERE product_id = %s;
            """,
            (product_id,)
        )
        product_row = cursor.fetchone()

        if not product_row:
            cursor.close()
            conn.rollback()
            return jsonify({"status": "error", "message": "Selected product was not found"}), 404

        resolved_user_id = session.get("user_email") or f"guest_{uuid.uuid4().hex[:16]}"
        review_timestamp = int(time.time())

        if not os_value:
            os_value = product_row[10]
        if not color_value:
            color_value = product_row[11]
        if not price_value:
            price_value = product_row[7]

        cursor.execute(
            """
            INSERT INTO fusiontech_submitted_reviews
                (product_id, rating, title_x, text, asin, user_id, timestamp, helpful_vote,
                 main_category, title_y, average_rating, rating_number, features, price,
                 store, os, color, brand)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING review_id;
            """,
            (
                product_row[0],
                rating,
                title,
                text,
                product_row[2],
                resolved_user_id,
                review_timestamp,
                product_row[3],
                product_row[1],
                product_row[4],
                price_value,
                product_row[6],
                product_row[7],
                product_row[8],
                os_value,
                color_value,
                product_row[9],
            )
        )
        review_id = cursor.fetchone()[0]
        cursor.close()
        conn.commit()

        return jsonify(
            {
                "status": "success",
                "message": "Review submitted successfully",
                "review_id": review_id,
                "inferred": {
                    "asin": product_row[2],
                    "user_id": resolved_user_id,
                    "timestamp": review_timestamp,
                    "helpful_vote": None,
                    "main_category": product_row[3],
                    "average_rating": product_row[4],
                    "rating_number": product_row[5],
                    "features": product_row[6],
                    "price": price_value,
                    "store": product_row[8],
                    "title_y": product_row[1],
                    "brand": product_row[9],
                    "os": os_value,
                    "color": color_value,
                },
            }
        )
    except Exception as exc:
        conn.rollback()
        return jsonify({"status": "error", "message": f"Failed to submit review: {str(exc)}"}), 500
    finally:
        close_connection(conn)


@app.route("/logout")
def logout():
    """Log out current user."""
    return_to = request.args.get('return', '')
    session.clear()
    
    if return_to == 'developer':
        return redirect(url_for('login_page') + '?tab=developer')
    return redirect(url_for('login_page'))


# ==============================
# ROUTES - API
# ==============================

@app.route("/api/dashboard")
@require_profile
def api_dashboard():
    user = get_current_user()
    metadata = get_model_metadata()
    ui_defaults = metadata.get("ui_defaults", {}) if isinstance(metadata.get("ui_defaults", {}), dict) else {}
    risk_thresholds = metadata.get("risk_thresholds", {}) if isinstance(metadata.get("risk_thresholds", {}), dict) else {}
    dashboard_alert_limit = int(ui_defaults.get("dashboard_alert_limit", 10))
    
    risk = artifacts['risk_results']
    portfolio = artifacts['portfolio_impact']
    alerts = artifacts['alerts']

    # TODO: Apply department-specific filtering here
    # risk = filter_by_department(risk, user)
    
    scored = [r for r in risk.values() if r['risk_score'] is not None]
    critical = sum(1 for r in scored if r['alert_level'] == 'CRITICAL')
    high = sum(1 for r in scored if r['alert_level'] == 'HIGH')

    enriched_df = artifacts['enriched_df']
    total_reviews = len(enriched_df)

    return jsonify({
        "status": "success",
        "summary": {
            "total_products": len(risk),
            "products_scored": len(scored),
            "critical_alerts": critical,
            "high_alerts": high,
            "total_reviews_analyzed": total_reviews,
            "total_monthly_revenue_at_risk": portfolio['total_monthly_revenue_at_risk'],
            "total_monthly_revenue_at_risk_formatted": format_currency(
                portfolio['total_monthly_revenue_at_risk']
            ),
            "avg_risk_score": round(
                sum(r['risk_score'] for r in scored) / len(scored), 1
            ) if scored else 0,
        },
        "alerts": alerts[:dashboard_alert_limit],
        "ui_defaults": {
            "dashboard_table_limit": int(ui_defaults.get("dashboard_table_limit", 10)),
            "dashboard_alert_limit": dashboard_alert_limit,
            "dashboard_alert_preview_limit": int(ui_defaults.get("dashboard_alert_preview_limit", 5)),
        },
        "risk_thresholds": {
            "critical": float(risk_thresholds.get("critical", 75)),
            "high": float(risk_thresholds.get("high", 50)),
            "moderate": float(risk_thresholds.get("moderate", 25)),
        },
    })


@app.route("/api/products")
def api_products():
    risk = artifacts['risk_results']
    products = []
    for asin, data in risk.items():
        products.append({
            "asin": data['asin'],
            "product_name": data['product_name'],
            "risk_score": data['risk_score'],
            "alert_level": data['alert_level'],
            "sub_scores": data.get('sub_scores', {}),
            "top_themes": [t[0] for t in data.get('top_themes', [])[:3]],
            "review_count": data['review_count'],
            "average_rating": data.get('average_rating'),
            "price": data.get('price'),
            "revenue_impact": data.get('revenue_impact', {}),
        })

    # Sort by risk score descending (None scores at end)
    products.sort(key=lambda x: x['risk_score'] if x['risk_score'] is not None else -1, reverse=True)

    return jsonify({
        "status": "success",
        "count": len(products),
        "products": products,
    })


@app.route("/api/products/<asin>")
def api_product_detail(asin):
    risk = artifacts['risk_results']
    enriched_df = artifacts['enriched_df']

    if asin not in risk:
        return jsonify({"status": "error", "message": "Product not found"}), 404

    data = risk[asin]
    product_reviews = enriched_df[enriched_df['asin'] == asin].copy()

    # Sentiment timeline
    timeline = []
    if 'date' in product_reviews.columns and not product_reviews.empty:
        product_reviews['year_month'] = product_reviews['date'].dt.to_period('M')
        for period, group in product_reviews.groupby('year_month'):
            timeline.append({
                "month": str(period),
                "avg_sentiment": round(group['combined_sentiment'].mean(), 4),
                "review_count": len(group),
                "avg_rating": round(group['rating'].astype(float).mean(), 2),
            })
        timeline.sort(key=lambda x: x['month'])

    # Rating distribution
    rating_dist = {}
    for r in range(1, 6):
        rating_dist[str(r)] = int((product_reviews['rating'].astype(int) == r).sum())

    # Recent negative reviews
    neg_reviews = product_reviews[product_reviews['sentiment_label'] == 'negative'].sort_values(
        'date', ascending=False
    ).head(5)
    recent_negatives = []
    for _, row in neg_reviews.iterrows():
        recent_negatives.append({
            "date": str(row['date'].date()) if pd.notna(row['date']) else "",
            "title": str(row['title_x'])[:100],
            "rating": int(row['rating']),
            "sentiment": round(row['combined_sentiment'], 3),
            "helpful_votes": int(row['helpful_vote']) if pd.notna(row['helpful_vote']) else 0,
        })

    # Theme detail with example counts
    themes_detail = []
    for theme_name, freq in data.get('top_themes', []):
        themes_detail.append({
            "theme": theme_name,
            "frequency": freq,
        })

    return jsonify({
        "status": "success",
        "product": {
            "asin": data['asin'],
            "product_name": data['product_name'],
            "risk_score": data['risk_score'],
            "alert_level": data['alert_level'],
            "sub_scores": data.get('sub_scores', {}),
            "top_themes": themes_detail,
            "sentiment_timeline": timeline,
            "rating_distribution": rating_dist,
            "revenue_impact": data.get('revenue_impact', {}),
            "recent_negative_reviews": recent_negatives,
            "review_count": data['review_count'],
            "average_rating": data.get('average_rating'),
            "price": data.get('price'),
        }
    })


@app.route("/api/trends")
def api_trends():
    risk_trends = artifacts['risk_trends']
    global_themes = artifacts['global_themes']

    return jsonify({
        "status": "success",
        "trends": {
            "sentiment_over_time": risk_trends,
            "global_themes": global_themes,
        }
    })


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Analyze a single new review in real-time."""
    body = request.get_json()
    if not body:
        return jsonify({"status": "error", "message": "JSON body required"}), 400

    text = body.get("text", "")
    title = body.get("title", "")
    rating = body.get("rating")
    asin = body.get("asin", "")

    # Build a single-row DataFrame and run sentiment
    review_df = pd.DataFrame([{
        "text": text,
        "title_x": title,
        "rating": rating,
        "asin": asin,
    }])
    analyzed = analyze_sentiment(review_df)
    row = analyzed.iloc[0]

    # Detect themes
    themes = classify_review_themes(clean_review_text(text))

    # Look up current product risk
    risk_data = artifacts['risk_results'].get(asin, {})
    current_score = risk_data.get('risk_score')

    return jsonify({
        "status": "success",
        "analysis": {
            "sentiment_score": round(row['combined_sentiment'], 4),
            "sentiment_label": row['sentiment_label'],
            "detected_themes": themes,
            "current_product_risk_score": current_score,
            "product_alert_level": risk_data.get('alert_level', 'UNKNOWN'),
        }
    })


@app.route("/api/chatbot")
def api_chatbot():
    """Template-based chatbot for product progression summaries."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"status": "error", "message": "Query parameter 'q' required"}), 400

    # Find matching product by keyword search in product names
    risk = artifacts['risk_results']
    query_lower = query.lower()
    matches = []

    for asin, data in risk.items():
        name = data['product_name'].lower()
        # Score by how many query words match the product name
        words = query_lower.split()
        score = sum(1 for w in words if w in name and len(w) > 2)
        if score > 0:
            matches.append((asin, data, score))

    if not matches:
        # Try matching by ASIN directly
        for asin, data in risk.items():
            if query_lower in asin.lower():
                matches.append((asin, data, 10))

    if not matches:
        return jsonify({
            "status": "success",
            "response": f"I couldn't find a product matching '{query}'. "
                        "Try using the product name or ASIN code.",
            "product_matched": None,
        })

    # Pick best match
    matches.sort(key=lambda x: x[2], reverse=True)
    asin, data, _ = matches[0]

    # Build response
    risk_score = data['risk_score']
    alert = data['alert_level']
    metadata = get_model_metadata()
    chatbot_thresholds = metadata.get("chatbot_response_thresholds", {}) if isinstance(metadata.get("chatbot_response_thresholds", {}), dict) else {}
    critical_threshold = float(chatbot_thresholds.get("critical", 75))
    high_threshold = float(chatbot_thresholds.get("high", 50))
    moderate_threshold = float(chatbot_thresholds.get("moderate", 25))

    themes = [t[0] for t in data.get('top_themes', [])][:3]
    themes_str = ", ".join(themes) if themes else "none detected"
    impact = data.get('revenue_impact', {})
    monthly_risk = format_currency(impact.get('monthly_revenue_at_risk', 0))
    review_count = data['review_count']
    avg_rating = data.get('average_rating', 'N/A')

    if risk_score is None:
        response = (
            f"The {data['product_name']} has insufficient review data for risk scoring "
            f"({review_count} reviews found). More data is needed for reliable analysis."
        )
    elif risk_score >= critical_threshold:
        response = (
            f"CRITICAL ALERT: The {data['product_name']} currently has a risk score of "
            f"{risk_score}/100 ({alert}). This product requires immediate attention. "
            f"Top complaint themes: {themes_str}. Average rating: {avg_rating}. "
            f"Estimated monthly revenue at risk: {monthly_risk}. "
            f"Based on {review_count} reviews analyzed. "
            f"Recommended action: Escalate to product team immediately."
        )
    elif risk_score >= high_threshold:
        response = (
            f"The {data['product_name']} has a risk score of {risk_score}/100 ({alert}). "
            f"Top complaint themes: {themes_str}. Average rating: {avg_rating}. "
            f"Estimated monthly revenue at risk: {monthly_risk}. "
            f"Based on {review_count} reviews analyzed. "
            f"Recommended action: Investigate top complaint themes and monitor trends."
        )
    elif risk_score >= moderate_threshold:
        response = (
            f"The {data['product_name']} has a moderate risk score of {risk_score}/100 ({alert}). "
            f"Some complaint themes detected: {themes_str}. Average rating: {avg_rating}. "
            f"Based on {review_count} reviews. No immediate action required but keep monitoring."
        )
    else:
        response = (
            f"The {data['product_name']} is performing well with a low risk score of "
            f"{risk_score}/100 ({alert}). Average rating: {avg_rating}. "
            f"Based on {review_count} reviews. No concerns detected."
        )

    return jsonify({
        "status": "success",
        "response": response,
        "product_matched": asin,
        "risk_score": risk_score,
        "alert_level": alert,
    })


@app.route("/api/developer/dell-infrastructure-fit")
@require_dev_unlock
def api_developer_dell_infrastructure_fit():
    """Return enterprise-scaled requirements + Dell infrastructure baseline capabilities."""
    metadata = get_model_metadata()
    dev_infra = metadata.get("dev_infrastructure", {}) if isinstance(metadata.get("dev_infrastructure", {}), dict) else {}
    assumptions = dev_infra.get("assumptions", {}) if isinstance(dev_infra.get("assumptions", {}), dict) else {}

    # Model-configured assumptions first; defaults are fallback for older artifacts.
    employees = int(assumptions.get("employees", 15000))
    avg_reviews_per_employee_per_year = int(assumptions.get("avg_reviews_per_employee_per_year", 20))
    default_avg_review_size_bytes = int(assumptions.get("default_avg_review_size_bytes", 2048))
    model_inference_time_ms = float(assumptions.get("model_inference_time_ms", 200))
    avg_daily_dashboard_queries = int(assumptions.get("avg_daily_dashboard_queries", 20000))
    dataset_growth_rate = float(assumptions.get("dataset_growth_rate", 0.15))
    retention_years = int(assumptions.get("retention_years", 5))

    # Pull dynamic signals from model artifacts when available
    artifact_stats_available = False
    total_reviews_analyzed = 0
    products_scored = 0
    detected_avg_review_size_bytes = default_avg_review_size_bytes

    if artifacts and isinstance(artifacts, dict):
        enriched_df = artifacts.get("enriched_df")
        risk_results = artifacts.get("risk_results", {})
        products_scored = len(risk_results) if isinstance(risk_results, dict) else 0

        if isinstance(enriched_df, pd.DataFrame) and not enriched_df.empty:
            artifact_stats_available = True
            total_reviews_analyzed = len(enriched_df)

            text_col = None
            if "text" in enriched_df.columns:
                text_col = "text"
            elif "clean_text" in enriched_df.columns:
                text_col = "clean_text"

            title_col = "title_x" if "title_x" in enriched_df.columns else None

            if text_col:
                text_lengths = enriched_df[text_col].fillna("").astype(str).str.len()
                title_lengths = (
                    enriched_df[title_col].fillna("").astype(str).str.len()
                    if title_col else 0
                )
                avg_chars = float((text_lengths + title_lengths).mean())
                # Approximate byte size using UTF-8 typical 1.2x overhead for mixed chars.
                detected_avg_review_size_bytes = max(
                    256,
                    int(avg_chars * 1.2)
                )

    # Enterprise-scaled requirements (reviews + chatbot + ops storage)
    annual_reviews = employees * avg_reviews_per_employee_per_year
    review_dataset_size_bytes = annual_reviews * detected_avg_review_size_bytes

    # Chatbot workload assumptions for enterprise usage
    active_chat_user_ratio = float(assumptions.get("active_chat_user_ratio", 0.30))
    chat_sessions_per_active_user_per_day = float(assumptions.get("chat_sessions_per_active_user_per_day", 1.2))
    avg_turns_per_session = float(assumptions.get("avg_turns_per_session", 3.5))
    avg_chat_prompt_tokens = int(assumptions.get("avg_chat_prompt_tokens", 900))
    avg_chat_completion_tokens = int(assumptions.get("avg_chat_completion_tokens", 300))
    avg_chars_per_token = float(assumptions.get("avg_chars_per_token", 4))
    chat_inference_time_ms = float(assumptions.get("chat_inference_time_ms", 900))

    daily_active_chat_users = int(round(employees * active_chat_user_ratio))
    daily_chat_turns = int(round(
        daily_active_chat_users * chat_sessions_per_active_user_per_day * avg_turns_per_session
    ))

    tokens_per_chat_turn = avg_chat_prompt_tokens + avg_chat_completion_tokens
    daily_chat_tokens = daily_chat_turns * tokens_per_chat_turn
    annual_chat_tokens = daily_chat_tokens * 365

    # Approximate payload size for each chatbot turn (prompt + response + metadata envelope)
    avg_chat_payload_bytes_per_turn = int(tokens_per_chat_turn * avg_chars_per_token * 1.15)
    annual_chat_log_size_bytes = daily_chat_turns * avg_chat_payload_bytes_per_turn * 365

    # Additional platform storage components
    feature_engineering_overhead_bytes = int(
        review_dataset_size_bytes * float(assumptions.get("feature_engineering_overhead_ratio", 0.35))
    )
    vector_index_bytes = int(
        annual_chat_log_size_bytes * float(assumptions.get("vector_index_ratio", 0.25))
    )
    model_artifacts_bytes = int(assumptions.get("model_artifacts_bytes", 8 * 1024**3))
    observability_and_monitoring_bytes = int(
        assumptions.get("observability_and_monitoring_bytes", 25 * 1024**3)
    )

    year1_total_dataset_size_bytes = (
        review_dataset_size_bytes
        + annual_chat_log_size_bytes
        + feature_engineering_overhead_bytes
        + vector_index_bytes
        + model_artifacts_bytes
        + observability_and_monitoring_bytes
    )

    # 5-year retained storage with annual growth compounding
    growth_multiplier = (
        (((1 + dataset_growth_rate) ** retention_years) - 1) / dataset_growth_rate
        if dataset_growth_rate > 0 else retention_years
    )
    storage_required_bytes = int(year1_total_dataset_size_bytes * growth_multiplier)

    daily_total_requests = avg_daily_dashboard_queries + daily_chat_turns
    queries_per_second = daily_total_requests / (24 * 3600)

    weighted_payload_bytes = (
        (avg_daily_dashboard_queries * detected_avg_review_size_bytes)
        + (daily_chat_turns * avg_chat_payload_bytes_per_turn)
    ) / max(daily_total_requests, 1)
    throughput_needed_bytes_per_second = queries_per_second * weighted_payload_bytes

    weighted_inference_time_ms = (
        (avg_daily_dashboard_queries * model_inference_time_ms)
        + (daily_chat_turns * chat_inference_time_ms)
    ) / max(daily_total_requests, 1)

    # Little's Law style concurrency approximation for API + chatbot mix
    estimated_concurrent_inference = queries_per_second * (weighted_inference_time_ms / 1000)
    estimated_vcpu_needed = max(8, int(math.ceil(estimated_concurrent_inference * 10)))
    compute_required_index = max(1, estimated_vcpu_needed * 12)

    # Cost estimates (transparent assumptions; update rates when vendor prices change)
    llm_cost_per_million_tokens = assumptions.get("llm_cost_per_million_tokens", {
        "economy": 0.80,
        "balanced": 2.50,
        "premium": 8.00,
    })
    monthly_chat_tokens = annual_chat_tokens / 12
    monthly_llm_cost = {
        k: round((monthly_chat_tokens / 1_000_000) * v, 2)
        for k, v in llm_cost_per_million_tokens.items()
    }
    yearly_llm_cost = {
        k: round((annual_chat_tokens / 1_000_000) * v, 2)
        for k, v in llm_cost_per_million_tokens.items()
    }

    training_runs_per_year = float(assumptions.get("training_runs_per_year", 52))
    cpu_hours_per_run = float(assumptions.get("cpu_hours_per_run", 3.0))
    gpu_hours_per_run = float(assumptions.get("gpu_hours_per_run", 0.8))
    cpu_cost_per_hour = float(assumptions.get("cpu_cost_per_hour", 1.40))
    gpu_cost_per_hour = float(assumptions.get("gpu_cost_per_hour", 4.50))
    training_compute_cost_yearly = training_runs_per_year * (
        cpu_hours_per_run * cpu_cost_per_hour
        + gpu_hours_per_run * gpu_cost_per_hour
    )
    mlops_overhead_pct = float(assumptions.get("mlops_overhead_pct", 0.35))
    training_total_cost_yearly = round(training_compute_cost_yearly * (1 + mlops_overhead_pct), 2)
    total_ai_ops_cost_yearly_balanced = round(
        yearly_llm_cost["balanced"] + training_total_cost_yearly,
        2
    )

    # Dell baseline capability objects (values normalized for scoring calculations)
    infrastructures = [
        {
            "name": "PowerEdge",
            "primary_type": "Compute / Servers",
            "compute_capacity": {
                "max_cpus": 2,
                "max_cores_per_cpu": 144,
                "max_ram_tb": 8,
                "max_gpu": 8,
                "compute_index": 1000,
            },
            "storage_capacity": {
                "internal_nvme_tb": 245,
                "cluster_capacity_bytes": 245 * 1024**4,
            },
            "throughput": {
                "note": "Optimized for compute-heavy workloads",
                "throughput_bytes_per_second": 12 * 1024**3,
            },
            "scalability": {
                "max_nodes": 1000,
                "scalability_index": 98,
            },
            "best_for": [
                "AI/ML inference",
                "virtualization",
                "containerized applications",
                "compute-heavy workloads",
            ],
            "efficiency_hint": 88,
        },
        {
            "name": "PowerStore",
            "primary_type": "Block Storage Array",
            "compute_capacity": {
                "compute_index": 230,
                "max_cpus": None,
                "max_cores_per_cpu": None,
                "max_ram_tb": None,
                "max_gpu": None,
            },
            "storage_capacity": {
                "cluster_capacity_pb": 8,
                "cluster_capacity_bytes": 8 * 1024**5,
                "typical_data_reduction": "4:1",
            },
            "throughput": {
                "max_iops": 4_000_000,
                "latency": "sub-ms",
                "throughput_bytes_per_second": 8 * 1024**3,
            },
            "scalability": {
                "max_nodes": 64,
                "scalability_index": 82,
            },
            "best_for": [
                "databases",
                "virtual machines",
                "transactional systems",
            ],
            "efficiency_hint": 76,
        },
        {
            "name": "PowerScale",
            "primary_type": "Scale-Out NAS",
            "compute_capacity": {
                "compute_index": 340,
                "max_cpus": None,
                "max_cores_per_cpu": None,
                "max_ram_tb": None,
                "max_gpu": None,
            },
            "storage_capacity": {
                "max_nodes": 252,
                "cluster_capacity_pb": 186,
                "cluster_capacity_bytes": 186 * 1024**5,
            },
            "throughput": {
                "max_throughput_gbps": 945,
                "max_iops": 15_800_000,
                "throughput_bytes_per_second": 945 * 1024**3,
            },
            "scalability": {
                "max_nodes": 252,
                "scalability_index": 95,
            },
            "best_for": [
                "AI datasets",
                "unstructured data",
                "analytics pipelines",
                "large file repositories",
            ],
            "efficiency_hint": 92,
        },
        {
            "name": "PowerProtect",
            "primary_type": "Backup / Cyber Recovery",
            "compute_capacity": {
                "compute_index": 160,
                "max_cpus": None,
                "max_cores_per_cpu": None,
                "max_ram_tb": None,
                "max_gpu": None,
            },
            "storage_capacity": {
                "logical_capacity_pb": 50,
                "cluster_capacity_bytes": 50 * 1024**5,
                "dedupe": "up to 65:1",
            },
            "throughput": {
                "backup_tb_per_hour": 94,
                "throughput_bytes_per_second": (94 * 1024**4) / 3600,
            },
            "scalability": {
                "max_nodes": 80,
                "scalability_index": 74,
            },
            "best_for": [
                "backup",
                "ransomware protection",
                "archival storage",
            ],
            "efficiency_hint": 55,
        },
    ]

    metadata_infrastructures = dev_infra.get("infrastructures") if isinstance(dev_infra.get("infrastructures"), list) else None
    if metadata_infrastructures:
        infrastructures = metadata_infrastructures

    metadata_weights = dev_infra.get("weights", {}) if isinstance(dev_infra.get("weights", {}), dict) else {}

    return jsonify({
        "status": "success",
        "requirements": {
            "employees": employees,
            "annual_reviews": annual_reviews,
            "avg_review_size_bytes": detected_avg_review_size_bytes,
            "retention_years": retention_years,
            "dataset_size_bytes": year1_total_dataset_size_bytes,
            "review_dataset_size_bytes": review_dataset_size_bytes,
            "chatbot_dataset_size_bytes": annual_chat_log_size_bytes,
            "feature_engineering_overhead_bytes": feature_engineering_overhead_bytes,
            "vector_index_bytes": vector_index_bytes,
            "observability_and_monitoring_bytes": observability_and_monitoring_bytes,
            "storage_required_bytes": storage_required_bytes,
            "avg_daily_dashboard_queries": avg_daily_dashboard_queries,
            "daily_chat_turns": daily_chat_turns,
            "daily_total_requests": daily_total_requests,
            "queries_per_second": queries_per_second,
            "throughput_needed_bytes_per_second": throughput_needed_bytes_per_second,
            "model_inference_time_ms": model_inference_time_ms,
            "chat_inference_time_ms": chat_inference_time_ms,
            "weighted_inference_time_ms": round(weighted_inference_time_ms, 1),
            "estimated_vcpu_needed": estimated_vcpu_needed,
            "compute_required_index": compute_required_index,
            "dataset_growth_rate": dataset_growth_rate,
            "annual_chat_tokens": annual_chat_tokens,
            "monthly_chat_tokens": int(monthly_chat_tokens),
            "monthly_llm_cost": monthly_llm_cost,
            "yearly_llm_cost": yearly_llm_cost,
            "training_total_cost_yearly": training_total_cost_yearly,
            "total_ai_ops_cost_yearly_balanced": total_ai_ops_cost_yearly_balanced,
        },
        "weights": {
            "compute_weight": float(metadata_weights.get("compute_weight", 0.30)),
            "storage_weight": float(metadata_weights.get("storage_weight", 0.25)),
            "throughput_weight": float(metadata_weights.get("throughput_weight", 0.20)),
            "scalability_weight": float(metadata_weights.get("scalability_weight", 0.15)),
            "efficiency_weight": float(metadata_weights.get("efficiency_weight", 0.10)),
        },
        "dynamic_model_stats": {
            "artifact_stats_available": artifact_stats_available,
            "total_reviews_analyzed": total_reviews_analyzed,
            "products_scored": products_scored,
        },
        "assumptions": {
            "active_chat_user_ratio": active_chat_user_ratio,
            "chat_sessions_per_active_user_per_day": chat_sessions_per_active_user_per_day,
            "avg_turns_per_session": avg_turns_per_session,
            "avg_chat_prompt_tokens": avg_chat_prompt_tokens,
            "avg_chat_completion_tokens": avg_chat_completion_tokens,
            "llm_cost_per_million_tokens": llm_cost_per_million_tokens,
            "training_runs_per_year": training_runs_per_year,
            "cpu_hours_per_run": cpu_hours_per_run,
            "gpu_hours_per_run": gpu_hours_per_run,
            "cpu_cost_per_hour": cpu_cost_per_hour,
            "gpu_cost_per_hour": gpu_cost_per_hour,
            "mlops_overhead_pct": mlops_overhead_pct,
        },
        "infrastructures": infrastructures,
    })


@app.route("/api/developer/model-training-results")
@require_dev_unlock
def api_developer_model_training_results():
    registry = _load_json_file(MODEL_REGISTRY_PATH, [])
    baseline = _load_json_file(BASELINE_METRICS_PATH, {})
    validation = _load_json_file(VALIDATION_REPORT_PATH, {})

    if not isinstance(registry, list):
        registry = []

    latest = registry[-1] if registry else None
    latest_deployed = next((r for r in reversed(registry) if r.get("deployed")), None)

    version_rows = []
    for row in registry:
        metrics = row.get("metrics", {}) if isinstance(row.get("metrics", {}), dict) else {}
        optimal_metrics = row.get("optimal_threshold_metrics", {}) if isinstance(row.get("optimal_threshold_metrics", {}), dict) else {}
        operating_threshold = row.get("operating_high_risk_threshold")
        if operating_threshold is None:
            operating_threshold = optimal_metrics.get("optimal_threshold", row.get("high_risk_threshold"))

        operating_recall = optimal_metrics.get("optimal_recall", metrics.get("high_risk_recall"))
        operating_precision = optimal_metrics.get("optimal_precision", metrics.get("high_risk_precision"))
        operating_f1 = optimal_metrics.get("optimal_f1_score", metrics.get("optimal_f1_score"))
        operating_roc_auc = optimal_metrics.get("roc_auc_score", metrics.get("roc_auc"))

        version_rows.append(
            {
                "run_id": row.get("run_id"),
                "run_number": row.get("run_number"),
                "candidate_model_version": row.get("candidate_model_version"),
                "deployed_model_version": row.get("deployed_model_version"),
                "deployed": bool(row.get("deployed")),
                "timestamp": row.get("timestamp"),
                "high_risk_threshold": row.get("high_risk_threshold"),
                "operating_high_risk_threshold": operating_threshold,
                "pearson_correlation": metrics.get("pearson_correlation"),
                "directional_accuracy": metrics.get("directional_accuracy"),
                "high_risk_recall": metrics.get("high_risk_recall"),
                "high_risk_precision": metrics.get("high_risk_precision"),
                "mae": metrics.get("mae"),
                "roc_auc": metrics.get("roc_auc"),
                "optimal_f1": optimal_metrics.get("optimal_f1_score", metrics.get("optimal_f1_score")),
                "optimal_threshold": optimal_metrics.get("optimal_threshold", metrics.get("optimal_threshold")),
                "optimal_recall": optimal_metrics.get("optimal_recall", metrics.get("optimal_recall")),
                "optimal_precision": optimal_metrics.get("optimal_precision", metrics.get("optimal_precision")),
                "operating_recall": operating_recall,
                "operating_precision": operating_precision,
                "operating_f1": operating_f1,
                "operating_roc_auc": operating_roc_auc,
                "composite_score": row.get("composite_score"),
            }
        )

    progression = {
        "labels": [f"Run {r.get('run_number')}" for r in version_rows],
        "pearson": [r.get("pearson_correlation") for r in version_rows],
        "directional_accuracy": [r.get("directional_accuracy") for r in version_rows],
        "high_risk_recall": [r.get("high_risk_recall") for r in version_rows],
        "high_risk_precision": [r.get("high_risk_precision") for r in version_rows],
        "operating_recall": [r.get("operating_recall") for r in version_rows],
        "operating_precision": [r.get("operating_precision") for r in version_rows],
        "mae": [r.get("mae") for r in version_rows],
        "optimal_f1": [r.get("optimal_f1") for r in version_rows],
        "roc_auc": [r.get("roc_auc") for r in version_rows],
    }

    baseline_metrics = baseline.get("metrics", {}) if isinstance(baseline.get("metrics", {}), dict) else {}
    latest_metrics = latest.get("metrics", {}) if latest and isinstance(latest.get("metrics", {}), dict) else {}

    improvements = {}
    for metric in ["pearson_correlation", "directional_accuracy", "high_risk_recall", "high_risk_precision"]:
        b = baseline_metrics.get(metric)
        l = latest_metrics.get(metric)
        if b is not None and l is not None:
            improvements[metric] = round(float(l) - float(b), 4)

    eval_dataset_rows = 0
    if os.path.exists(EVALUATION_DATASET_PATH):
        try:
            eval_dataset_rows = int(len(pd.read_csv(EVALUATION_DATASET_PATH)))
        except Exception:
            eval_dataset_rows = 0

    # Extract operating metrics for latest_run if it exists
    if latest:
        latest_optimal = latest.get("optimal_threshold_metrics", {}) if isinstance(latest.get("optimal_threshold_metrics", {}), dict) else {}
        latest_metrics_dict = latest.get("metrics", {}) if isinstance(latest.get("metrics", {}), dict) else {}
        latest["operating_high_risk_threshold"] = latest.get("operating_high_risk_threshold") or latest_optimal.get("optimal_threshold") or latest.get("high_risk_threshold")
        latest["operating_recall"] = latest_optimal.get("optimal_recall") or latest_metrics_dict.get("high_risk_recall")
        latest["operating_precision"] = latest_optimal.get("optimal_precision") or latest_metrics_dict.get("high_risk_precision")
        latest["operating_f1"] = latest_optimal.get("optimal_f1_score") or latest_metrics_dict.get("optimal_f1_score")
        latest["operating_roc_auc"] = latest_optimal.get("roc_auc_score") or latest_metrics_dict.get("roc_auc")

    # Extract operating metrics for latest_deployed_run if it exists
    if latest_deployed:
        deployed_optimal = latest_deployed.get("optimal_threshold_metrics", {}) if isinstance(latest_deployed.get("optimal_threshold_metrics", {}), dict) else {}
        deployed_metrics_dict = latest_deployed.get("metrics", {}) if isinstance(latest_deployed.get("metrics", {}), dict) else {}
        latest_deployed["operating_high_risk_threshold"] = latest_deployed.get("operating_high_risk_threshold") or deployed_optimal.get("optimal_threshold") or latest_deployed.get("high_risk_threshold")
        latest_deployed["operating_recall"] = deployed_optimal.get("optimal_recall") or deployed_metrics_dict.get("high_risk_recall")
        latest_deployed["operating_precision"] = deployed_optimal.get("optimal_precision") or deployed_metrics_dict.get("high_risk_precision")
        latest_deployed["operating_f1"] = deployed_optimal.get("optimal_f1_score") or deployed_metrics_dict.get("optimal_f1_score")
        latest_deployed["operating_roc_auc"] = deployed_optimal.get("roc_auc_score") or deployed_metrics_dict.get("roc_auc")

    return jsonify(
        {
            "status": "success",
            "current_production_model_path": CURRENT_PRODUCTION_MODEL_PATH,
            "latest_validation": validation,
            "latest_run": latest,
            "latest_deployed_run": latest_deployed,
            "baseline": baseline,
            "improvements_vs_baseline": improvements,
            "version_table": version_rows,
            "progression": progression,
            "distribution": validation.get("distribution", {}),
            "evaluation_dataset": {
                "path": EVALUATION_DATASET_PATH,
                "rows": eval_dataset_rows,
            },
        }
    )


@app.route("/api/developer/replay-analysis")
@require_dev_unlock
def api_developer_replay_analysis():
    enriched_df = artifacts.get("enriched_df") if artifacts else None
    if enriched_df is None or (hasattr(enriched_df, "empty") and enriched_df.empty):
        return jsonify({"status": "error", "message": "Enriched dataset not available. Train the model first."})

    df = enriched_df.copy()
    if "date" not in df.columns or "asin" not in df.columns or "rating" not in df.columns:
        return jsonify({"status": "error", "message": "Required columns missing (date, asin, rating)."})

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "asin", "rating"])

    registry = _load_json_file(MODEL_REGISTRY_PATH, [])
    validation = _load_json_file(VALIDATION_REPORT_PATH, {})

    latest_deployed = None
    if isinstance(registry, list) and registry:
        latest_deployed = next((r for r in reversed(registry) if r.get("deployed")), None)
    latest_record = registry[-1] if isinstance(registry, list) and registry else {}

    operating_threshold = None
    for rec in [latest_deployed, latest_record]:
        if not isinstance(rec, dict):
            continue
        operating_threshold = rec.get("operating_high_risk_threshold")
        if operating_threshold is None and isinstance(rec.get("optimal_threshold_metrics"), dict):
            operating_threshold = rec.get("optimal_threshold_metrics", {}).get("optimal_threshold")
        if operating_threshold is not None:
            break
    if operating_threshold is None and isinstance(validation, dict) and isinstance(validation.get("optimal_threshold_metrics"), dict):
        operating_threshold = validation.get("optimal_threshold_metrics", {}).get("optimal_threshold")

    high_threshold = float(operating_threshold if operating_threshold is not None else ALERT_THRESHOLDS.get("high", 50))

    ROLLING_WINDOW = 3
    CRISIS_DROP_THRESHOLD = 0.3
    CRISIS_RECOVERY_EPS = 0.1
    MIN_REVIEWS = 8
    MIN_MONTHS = 6
    MAX_MODEL_LEAD_MONTHS = 4

    replay_shift = df["date"].max() - df["date"].min()
    replay_shift_years = round(replay_shift.days / 365.25, 2)

    def _format_period_exact(idx_exact, month_list):
        if idx_exact is None or not month_list:
            return None
        idx_exact = max(0.0, min(float(idx_exact), float(len(month_list) - 1)))
        base = int(math.floor(idx_exact))
        frac = idx_exact - base
        extra_days = int(round(frac * 30))
        base_period = month_list[base]
        return str(base_period) if extra_days <= 0 else f"{base_period} +{extra_days}d"

    def _interp_value(values, idx_exact):
        if not values:
            return None
        idx_exact = max(0.0, min(float(idx_exact), float(len(values) - 1)))
        lo = int(math.floor(idx_exact))
        hi = int(math.ceil(idx_exact))
        if lo == hi:
            return float(values[lo])
        frac = idx_exact - lo
        return float(values[lo]) + frac * (float(values[hi]) - float(values[lo]))

    df["replay_date"] = df["date"] + replay_shift
    df["replay_month"] = df["replay_date"].dt.to_period("M")

    all_asins = sorted(df["asin"].dropna().astype(str).unique())
    results = []

    for asin in all_asins:
        asin_df = df[df["asin"].astype(str) == asin].copy()
        if len(asin_df) < MIN_REVIEWS:
            continue

        product_name = "Unknown"
        for col in ["title_y", "title", "product_title", "name"]:
            if col in asin_df.columns:
                values = asin_df[col].dropna()
                if not values.empty:
                    product_name = str(values.iloc[0])
                    break

        monthly = (
            asin_df.groupby("replay_month")
            .agg(avg_rating=("rating", "mean"), review_count=("rating", "count"))
            .sort_index()
        )
        if monthly.empty:
            continue

        # Standardize to monthly bins and fill missing months by carry-forward.
        full_index = pd.period_range(monthly.index.min(), monthly.index.max(), freq="M")
        monthly = monthly.reindex(full_index)
        monthly["review_count"] = monthly["review_count"].fillna(0).astype(int)
        monthly["avg_rating"] = monthly["avg_rating"].ffill().bfill()

        months = list(monthly.index)
        avg_ratings = [float(v) for v in monthly["avg_rating"].tolist()]
        n = len(months)
        if n < MIN_MONTHS:
            continue

        rolling_ratings = []
        for i in range(n):
            s = max(0, i - ROLLING_WINDOW + 1)
            w = avg_ratings[s:i + 1]
            rolling_ratings.append(sum(w) / len(w))

        baseline_end = max(3, min(n // 5, 6))
        baseline = sum(rolling_ratings[:baseline_end]) / baseline_end

        # Crisis start: first sustained decline (2 steps) plus drop from baseline.
        t1_idx = None
        t1_idx_exact = None
        for i in range(max(baseline_end, 2), n):
            downtrend = rolling_ratings[i] < rolling_ratings[i - 1] and rolling_ratings[i - 1] < rolling_ratings[i - 2]
            dropped = rolling_ratings[i] <= (baseline - CRISIS_DROP_THRESHOLD)
            if downtrend and dropped:
                t1_idx = i - 1
                target_drop = baseline - CRISIS_DROP_THRESHOLD
                prev_val = float(rolling_ratings[i - 1])
                curr_val = float(rolling_ratings[i])
                if prev_val > target_drop and curr_val <= target_drop and curr_val != prev_val:
                    frac = (target_drop - prev_val) / (curr_val - prev_val)
                    frac = max(0.0, min(1.0, float(frac)))
                    t1_idx_exact = (i - 1) + frac
                else:
                    t1_idx_exact = float(i - 1)
                break
        if t1_idx is None:
            results.append({"asin": asin, "product_name": product_name, "has_crisis": False})
            continue

        # Crisis bottom and manual detection per deterministic rule.
        sub = rolling_ratings[t1_idx:]
        t3_idx = t1_idx + sub.index(min(sub))
        if t3_idx <= 0:
            results.append({"asin": asin, "product_name": product_name, "has_crisis": False})
            continue

        t3_idx_exact = float(t3_idx)
        if 1 <= t3_idx <= (n - 2):
            y_prev = float(rolling_ratings[t3_idx - 1])
            y_mid = float(rolling_ratings[t3_idx])
            y_next = float(rolling_ratings[t3_idx + 1])
            denom = (y_prev - (2.0 * y_mid) + y_next)
            if abs(denom) > 1e-9:
                delta = 0.5 * (y_prev - y_next) / denom
                delta = max(-0.5, min(0.5, float(delta)))
                t3_idx_exact = float(t3_idx + delta)

        # Manual detection is fixed exactly 1 month before exact crisis bottom.
        t2_idx_exact = max(0.0, t3_idx_exact - 1.0)
        t2_idx = int(math.floor(t2_idx_exact))

        # Recovery is computed after T_model is known.
        t4_idx = None

        # Model detection from replayed monthly cumulative history.
        replay_asin_df = asin_df.copy()
        replay_asin_df["date"] = replay_asin_df["replay_date"]
        replay_asin_df["replay_month"] = replay_asin_df["date"].dt.to_period("M")

        risk_scores = [None] * n
        crossing_events = []
        for i, period in enumerate(months):
            cumulative = replay_asin_df[replay_asin_df["replay_month"] <= period]
            if len(cumulative) < 3:
                continue
            try:
                scores = compute_product_risk_scores(cumulative)
                obj = scores.get(asin) or scores.get(str(asin))
                if isinstance(obj, dict) and obj.get("risk_score") is not None:
                    score = round(float(obj.get("risk_score")), 2)
                    risk_scores[i] = score
                    if score >= high_threshold:
                        if i > 0 and risk_scores[i - 1] is not None and float(risk_scores[i - 1]) < high_threshold:
                            prev = float(risk_scores[i - 1])
                            curr = float(score)
                            frac = (high_threshold - prev) / (curr - prev) if curr != prev else 1.0
                            frac = max(0.0, min(1.0, float(frac)))
                            crossing_idx_exact = (i - 1) + frac
                        else:
                            crossing_idx_exact = float(i)
                        crossing_events.append({
                            "idx": i,
                            "idx_exact": crossing_idx_exact,
                            "period": months[i],
                        })
            except Exception:
                pass

        # Constrain model detection to be near manual detection:
        # T_model must be between T1 and T2, and no more than 4 months before T2.
        t_model_idx = None
        t_model_idx_exact = None
        t_model_period = None
        for ev in crossing_events:
            i = ev["idx"]
            idx_exact = float(ev["idx_exact"])
            lead_vs_manual = t2_idx_exact - idx_exact
            if idx_exact < float(t1_idx_exact):
                continue
            if idx_exact > t2_idx_exact:
                continue
            if lead_vs_manual < 0 or lead_vs_manual > MAX_MODEL_LEAD_MONTHS:
                continue
            t_model_idx = i
            t_model_idx_exact = idx_exact
            t_model_period = ev["period"]
            break

        lead_time = None
        if t_model_idx_exact is not None:
            lead_time = round(float(t2_idx_exact - t_model_idx_exact), 2)

        t_model_label = _format_period_exact(t_model_idx_exact, months)

        # T4 recovery rule:
        # first month after T3 where rolling avg has recovered 80% of the drop from T_model to T3
        model_anchor_idx = t_model_idx_exact if t_model_idx_exact is not None else float(t3_idx_exact)
        model_anchor_rating = _interp_value(rolling_ratings, model_anchor_idx)
        bottom_rating = _interp_value(rolling_ratings, t3_idx_exact)
        if model_anchor_rating is None or bottom_rating is None:
            results.append({"asin": asin, "product_name": product_name, "has_crisis": False})
            continue

        # 0% recovered = bottom, 100% recovered = model anchor.
        recovery_target = bottom_rating + (0.8 * (model_anchor_rating - bottom_rating))
        t4_idx = n - 1
        t4_idx_exact = float(t4_idx)
        for i in range(t3_idx + 1, n):
            if rolling_ratings[i] >= recovery_target:
                t4_idx = i
                if i > 0:
                    prev_val = float(rolling_ratings[i - 1])
                    curr_val = float(rolling_ratings[i])
                    if prev_val < recovery_target and curr_val != prev_val:
                        frac = (recovery_target - prev_val) / (curr_val - prev_val)
                        frac = max(0.0, min(1.0, float(frac)))
                        t4_idx_exact = (i - 1) + frac
                    else:
                        t4_idx_exact = float(i)
                else:
                    t4_idx_exact = float(i)
                break

        if t4_idx_exact <= t3_idx_exact:
            results.append({"asin": asin, "product_name": product_name, "has_crisis": False})
            continue

        crisis_duration = round(float(t4_idx_exact - float(t1_idx_exact)), 2)
        detection_quality = round(lead_time / crisis_duration, 3) if lead_time is not None and crisis_duration > 0 else None

        t1_label = _format_period_exact(t1_idx_exact, months)
        t2_label = _format_period_exact(t2_idx_exact, months)
        t3_label = _format_period_exact(t3_idx_exact, months)
        t4_label = _format_period_exact(t4_idx_exact, months)

        results.append({
            "asin": asin,
            "product_name": product_name,
            "has_crisis": True,
            "t1_crisis_start": t1_label,
            "t2_manual_detect": t2_label,
            "t3_crisis_bottom": t3_label,
            "t4_recovery": t4_label,
            "t_model": t_model_label,
            "t1_idx": t1_idx,
            "t2_idx": t2_idx,
            "t3_idx": t3_idx,
            "t4_idx": t4_idx,
            "t1_plot_idx": t1_idx_exact,
            "t2_plot_idx": t2_idx_exact,
            "t3_plot_idx": t3_idx_exact,
            "t4_plot_idx": t4_idx_exact,
            "t_model_idx": t_model_idx,
            "t_model_plot_idx": t_model_idx_exact,
            "lead_time_months": lead_time,
            "crisis_duration_months": crisis_duration,
            "detection_quality_score": detection_quality,
            "model_detected_early": bool(lead_time > 0) if lead_time is not None else None,
            "timeline_labels": [str(m) for m in months],
            "rolling_ratings": [round(v, 3) for v in rolling_ratings],
            "risk_scores": risk_scores,
            "review_counts": [int(v) for v in monthly["review_count"].tolist()],
            "baseline_rating": round(baseline, 3),
            "recovery_target_rating": round(recovery_target, 3),
        })

    with_crisis = [p for p in results if p.get("has_crisis")]
    flagged = [p for p in with_crisis if p.get("t_model") is not None]
    early = [p for p in flagged if p.get("model_detected_early")]
    leads = [p.get("lead_time_months") for p in early if p.get("lead_time_months") is not None]

    return jsonify({
        "status": "success",
        "summary": {
            "replay_shift_years": replay_shift_years,
            "high_threshold": high_threshold,
            "products_analyzed": len(results),
            "products_with_crisis": len(with_crisis),
            "products_flagged": len(flagged),
            "products_model_early": len(early),
            "avg_lead_time_months": round(sum(leads) / len(leads), 2) if leads else None,
        },
        "products": results,
    })


@app.route("/api/developer/evaluation-reviews")
@require_dev_unlock
def api_developer_evaluation_reviews():
    if not os.path.exists(EVALUATION_DATASET_PATH):
        return jsonify({"status": "error", "message": "evaluation_reviews dataset not found. Run training first."}), 404

    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 500))
    except ValueError:
        limit = 100
    try:
        offset = max(0, int(request.args.get("offset", 0)))
    except ValueError:
        offset = 0

    df = pd.read_csv(EVALUATION_DATASET_PATH)
    total = len(df)
    subset = df.iloc[offset: offset + limit].fillna("")

    return jsonify({
        "status": "success",
        "total_rows": total,
        "offset": offset,
        "limit": limit,
        "rows": subset.to_dict(orient="records"),
    })


@app.route("/api/developer/evaluation-reviews", methods=["PUT"])
@require_dev_unlock
def api_developer_evaluation_reviews_update():
    body = request.get_json() or {}
    updates = body.get("updates", [])

    if not isinstance(updates, list) or not updates:
        return jsonify({"status": "error", "message": "updates list required"}), 400

    if not os.path.exists(EVALUATION_DATASET_PATH):
        return jsonify({"status": "error", "message": "evaluation_reviews dataset not found."}), 404

    df = pd.read_csv(EVALUATION_DATASET_PATH)
    if "review_id" not in df.columns:
        return jsonify({"status": "error", "message": "review_id column missing in evaluation dataset."}), 500

    changed = 0
    editable = {"labeled_issue", "labeled_severity_score", "labeled_risk_level"}

    for u in updates:
        rid = str(u.get("review_id", "")).strip()
        if not rid:
            continue

        idx = df.index[df["review_id"].astype(str) == rid]
        if len(idx) == 0:
            continue

        row_index = idx[0]
        for field in editable:
            if field in u:
                df.at[row_index, field] = u[field]
        changed += 1

    df.to_csv(EVALUATION_DATASET_PATH, index=False)

    return jsonify({
        "status": "success",
        "updated_rows": changed,
    })


# ==============================
# START SERVER
# ==============================

def start(host="0.0.0.0", port=5000):
    load_artifacts()
    print(f"\n  Dashboard: http://localhost:{port}")
    print(f"  API Base:  http://localhost:{port}/api")
    print("  Press Ctrl+C to stop.\n")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    start()
