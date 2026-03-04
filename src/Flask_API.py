import os
import pickle
import pandas as pd
from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from functools import wraps

from Sentiment_Analyzer import analyze_sentiment, clean_review_text
from Theme_Extractor import classify_review_themes, COMPLAINT_CATEGORIES
from Risk_Score_Engine import _get_alert_level
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

ARTIFACTS_PATH = os.path.join(os.path.dirname(__file__), "models", "Risk_Model_Artifacts.pkl")

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
    if not os.path.exists(ARTIFACTS_PATH):
        raise FileNotFoundError(
            f"Model artifacts not found at {ARTIFACTS_PATH}. Run Train_Model.py first."
        )
    with open(ARTIFACTS_PATH, "rb") as f:
        artifacts = pickle.load(f)
    print(f"Loaded model artifacts ({len(artifacts['risk_results'])} products)")


# ==============================
# ROUTES - DASHBOARD
# ==============================

@app.route("/")
@require_profile
def dashboard():
    user = get_current_user()
    return render_template("Dashboard.html", user=user)


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
    
    return jsonify({
        "status": "success",
        "departments": departments
    })


@app.route("/logout")
def logout():
    """Log out current user."""
    session.clear()
    return redirect(url_for('login_page'))


# ==============================
# ROUTES - API
# ==============================

@app.route("/api/dashboard")
@require_profile
def api_dashboard():
    user = get_current_user()
    
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
        "alerts": alerts[:10],
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
    elif risk_score >= 75:
        response = (
            f"CRITICAL ALERT: The {data['product_name']} currently has a risk score of "
            f"{risk_score}/100 ({alert}). This product requires immediate attention. "
            f"Top complaint themes: {themes_str}. Average rating: {avg_rating}. "
            f"Estimated monthly revenue at risk: {monthly_risk}. "
            f"Based on {review_count} reviews analyzed. "
            f"Recommended action: Escalate to product team immediately."
        )
    elif risk_score >= 50:
        response = (
            f"The {data['product_name']} has a risk score of {risk_score}/100 ({alert}). "
            f"Top complaint themes: {themes_str}. Average rating: {avg_rating}. "
            f"Estimated monthly revenue at risk: {monthly_risk}. "
            f"Based on {review_count} reviews analyzed. "
            f"Recommended action: Investigate top complaint themes and monitor trends."
        )
    elif risk_score >= 25:
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
