import pandas as pd

# ==============================
# CONSTANTS (FusionTech Financials)
# ==============================

TOTAL_ANNUAL_REVENUE = 2_800_000_000  # $2.8B
MONTHLY_REVENUE = TOTAL_ANNUAL_REVENUE / 12  # ~$233.3M
NUM_PRODUCTS = 40
AVG_PRODUCT_MONTHLY_REVENUE = MONTHLY_REVENUE / NUM_PRODUCTS  # ~$5.83M

# Risk score maps to 0-15% revenue decline
MAX_RISK_IMPACT_PERCENT = 0.15

# Assume 70% of at-risk revenue can be recovered with prompt action
DEFAULT_RECOVERY_RATE = 0.70


# ==============================
# REVENUE IMPACT CALCULATION
# ==============================

def calculate_revenue_impact(risk_score, months_at_risk=1, recovery_rate=DEFAULT_RECOVERY_RATE):
    """
    Convert a product risk score to estimated revenue impact.

    Args:
        risk_score: float 0-100
        months_at_risk: how many months this risk has been active
        recovery_rate: fraction of revenue recoverable with prompt action

    Returns:
        dict with revenue impact estimates
    """
    if risk_score is None or risk_score <= 0:
        return {
            "monthly_revenue_at_risk": 0,
            "annualized_revenue_at_risk": 0,
            "potential_monthly_savings": 0,
            "potential_annual_savings": 0,
            "risk_factor_percent": 0,
        }

    # Risk score 0-100 maps to 0-15% revenue decline
    risk_factor = (risk_score / 100) * MAX_RISK_IMPACT_PERCENT

    estimated_monthly_loss = AVG_PRODUCT_MONTHLY_REVENUE * risk_factor
    potential_savings = estimated_monthly_loss * recovery_rate

    return {
        "monthly_revenue_at_risk": round(estimated_monthly_loss, 2),
        "annualized_revenue_at_risk": round(estimated_monthly_loss * 12, 2),
        "potential_monthly_savings": round(potential_savings, 2),
        "potential_annual_savings": round(potential_savings * 12, 2),
        "risk_factor_percent": round(risk_factor * 100, 2),
    }


def calculate_portfolio_impact(risk_results):
    """
    Aggregate revenue impact across all products.

    Args:
        risk_results: dict from compute_product_risk_scores(), already enriched
                      with revenue_impact per product

    Returns:
        dict with portfolio-level impact summary
    """
    total_monthly_at_risk = 0
    total_potential_savings = 0
    products_at_risk = 0

    for asin, data in risk_results.items():
        impact = data.get('revenue_impact', {})
        monthly = impact.get('monthly_revenue_at_risk', 0)
        savings = impact.get('potential_monthly_savings', 0)
        if monthly > 0:
            total_monthly_at_risk += monthly
            total_potential_savings += savings
            products_at_risk += 1

    return {
        "total_monthly_revenue_at_risk": round(total_monthly_at_risk, 2),
        "total_annual_revenue_at_risk": round(total_monthly_at_risk * 12, 2),
        "total_potential_monthly_savings": round(total_potential_savings, 2),
        "total_potential_annual_savings": round(total_potential_savings * 12, 2),
        "products_at_risk": products_at_risk,
        "company_monthly_revenue": round(MONTHLY_REVENUE, 2),
        "percent_portfolio_at_risk": round(
            (total_monthly_at_risk / MONTHLY_REVENUE) * 100, 2
        ) if MONTHLY_REVENUE > 0 else 0,
    }


def price_adjusted_impact(risk_score, product_price, avg_price):
    """
    Adjust revenue impact based on product's actual price vs average.
    Higher-priced products carry proportionally more revenue impact.
    """
    if product_price is None or avg_price is None or avg_price <= 0:
        return calculate_revenue_impact(risk_score)

    price_multiplier = product_price / avg_price
    base_impact = calculate_revenue_impact(risk_score)
    return {k: round(v * price_multiplier, 2) if isinstance(v, (int, float)) else v
            for k, v in base_impact.items()}


def format_currency(amount):
    """Format a number as a readable currency string."""
    if amount is None:
        return "$0"
    if abs(amount) >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    elif abs(amount) >= 1_000:
        return f"${amount / 1_000:.0f}K"
    else:
        return f"${amount:.0f}"
