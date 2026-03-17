import json
import os

# ---------------------------------------------------------------------------
# Department code → friendly display name mapping.
# Keeps the system prompt readable regardless of how the code is stored in DB.
# ---------------------------------------------------------------------------
_DEPARTMENT_DISPLAY_NAMES = {
    "ENGINEERING_IT":    "Engineering & IT",
    "MARKETING":         "Marketing",
    "SALES":             "Sales",
    "FINANCE":           "Finance",
    "SUPPLY_CHAIN":      "Supply Chain / Global Operations",
    "CUSTOMER_SUPPORT":  "Customer Support / Customer Success",
    "SECURITY":          "Security",
}

def _display_department(raw):
    """Return a human-readable department name from a code or plain string."""
    if not raw:
        return ""
    return _DEPARTMENT_DISPLAY_NAMES.get(raw.strip().upper(), raw.strip())


# ---------------------------------------------------------------------------
# Seed context — loaded ONCE at module import, never reloaded between requests.
# Edit src/chatbot/seed_context.json to update domain knowledge without
# touching code or restarting.
# ---------------------------------------------------------------------------
_SEED_CONTEXT_PATH = os.path.join(os.path.dirname(__file__), "seed_context.json")

def _load_seed_context():
    try:
        with open(_SEED_CONTEXT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return []

_SEED_CONTEXT = _load_seed_context()


def build_system_prompt(user):
    """Build a system prompt scaffold that can be personalized by user profile."""
    name = ""
    raw_dept = ""

    if user and isinstance(user, dict):
        name = str(user.get("first_name") or user.get("name") or "").strip()
        raw_dept = str(user.get("department") or "").strip()

    display_dept = _display_department(raw_dept)
    dept_code = raw_dept.upper()

    greeting_name = name if name else "there"

    # --- Base prompt ---
    if display_dept:
        identity_line = f"You are currently assisting {greeting_name}, who works in the {display_dept} department at FusionTech Systems."
    else:
        identity_line = f"You are currently assisting {greeting_name}, an employee at FusionTech Systems."

    base = (
        f"You are a concise, helpful AI assistant supporting employees at FusionTech Systems.\n\n"
        f"{identity_line}\n\n"
        f"You can answer a wide range of topics, including technical, business, and general questions.\n\n"
        f"Always start with a concise answer (2–4 sentences). "
        f"Only expand into detailed explanations, lists, or technical depth if the user explicitly asks for more detail."
    )

    # --- Department-specific tone add-on ---
    if dept_code in ("ENGINEERING_IT", "ENGINEERING"):
        addon = (
            "When relevant, prioritize technical depth, root-cause analysis, and system-level reasoning. "
            "Frame insights around defect patterns, performance signals, and diagnostic clarity."
        )
    elif dept_code == "MARKETING":
        addon = (
            "When relevant, focus on customer sentiment, brand perception, and emerging trends. "
            "Frame insights in terms of user experience, reputation, and market positioning."
        )
    elif dept_code == "SALES":
        addon = (
            "When relevant, emphasize revenue impact, customer risk, and business priorities. "
            "Highlight implications that affect deals, retention, and growth opportunities."
        )
    elif dept_code == "FINANCE":
        addon = (
            "When relevant, focus on financial risk, cost implications, and quantitative impact. "
            "Frame insights in terms of margins, exposure, and budget considerations."
        )
    elif dept_code in ("CUSTOMER_SUPPORT", "CUSTOMER SUPPORT / CUSTOMER SUCCESS"):
        addon = (
            "When relevant, focus on complaint patterns, resolution paths, and customer satisfaction signals. "
            "Prioritize actionable guidance that helps resolve issues quickly."
        )
    elif dept_code == "SUPPLY_CHAIN":
        addon = (
            "When relevant, focus on operational efficiency, bottlenecks, and supply reliability signals. "
            "Frame insights around logistics, lead times, and risk to fulfillment."
        )
    elif dept_code == "SECURITY":
        addon = (
            "When relevant, apply a security-first perspective: identify risk vectors, compliance gaps, "
            "and mitigation steps. Prioritize clarity on threat impact and remediation."
        )
    else:
        addon = (
            "Tailor examples and framing to be as relevant as possible to the user's context, "
            "without restricting the scope of what you can answer."
        )

    return f"{base}\n\n{addon}"


def build_model_summary(artifacts, dept_code=""):
    """Convert live model artifacts into a concise natural-language summary (≤5 sentences).
    Returns an empty string when no artifacts are available.
    """
    if not artifacts or not isinstance(artifacts, dict):
        return ""

    dept_code = (dept_code or "").upper()
    parts = []

    # --- High-risk products (top 5) ---
    risk_results = artifacts.get("risk_results", {})
    if isinstance(risk_results, dict):
        elevated = [
            (d.get("product_name", asin), d["risk_score"])
            for asin, d in risk_results.items()
            if isinstance(d, dict)
            and d.get("risk_score") is not None
            and d.get("alert_level") in ("CRITICAL", "HIGH")
        ]
        elevated.sort(key=lambda x: x[1], reverse=True)
        if elevated:
            names = ", ".join(p[0] for p in elevated[:5])
            parts.append(f"Products currently at elevated risk: {names}.")

    # --- Monthly revenue at risk ---
    portfolio = artifacts.get("portfolio_impact", {})
    monthly_risk = portfolio.get("total_monthly_revenue_at_risk") if isinstance(portfolio, dict) else None
    revenue_line = f"Estimated monthly revenue at risk: ${monthly_risk:,.0f}." if monthly_risk else None
    if revenue_line:
        parts.append(revenue_line)

    # --- Top complaint themes (top 3) ---
    global_themes = artifacts.get("global_themes", [])
    if isinstance(global_themes, list) and global_themes:
        top = [t for t in global_themes[:3] if isinstance(t, (list, tuple)) and len(t) >= 2]
        if top:
            formatted = ", ".join(f"{t[0]} ({t[1]}" + " mentions)" for t in top)
            parts.append(f"Top complaint themes: {formatted}.")

    if not parts:
        return ""

    # Department-aware ordering: Sales sees revenue first, Engineering sees themes first
    if dept_code == "SALES" and revenue_line and parts[0] != revenue_line:
        parts = [revenue_line] + [p for p in parts if p != revenue_line]
    elif dept_code in ("ENGINEERING_IT", "ENGINEERING") and len(parts) >= 3:
        themes_line = parts[-1]
        parts = [themes_line] + parts[:-1]

    return " ".join(parts)


def build_system_prompt(user, artifacts=None):
    """Build a system prompt scaffold personalized by user profile and live model data."""
    name = ""
    raw_dept = ""

    if user and isinstance(user, dict):
        name = str(user.get("first_name") or user.get("name") or "").strip()
        raw_dept = str(user.get("department") or "").strip()

    display_dept = _display_department(raw_dept)
    dept_code = raw_dept.upper()

    greeting_name = name if name else "there"

    # --- Base prompt ---
    if display_dept:
        identity_line = f"You are currently assisting {greeting_name}, who works in the {display_dept} department at FusionTech Systems."
    else:
        identity_line = f"You are currently assisting {greeting_name}, an employee at FusionTech Systems."

    base = (
        f"You are a concise, helpful AI assistant supporting employees at FusionTech Systems.\n\n"
        f"{identity_line}\n\n"
        f"You can answer a wide range of topics, including technical, business, and general questions.\n\n"
        f"Always start with a concise answer (2\u20134 sentences). "
        f"Only expand into detailed explanations, lists, or technical depth if the user explicitly asks for more detail."
    )

    # --- Department-specific tone add-on ---
    if dept_code in ("ENGINEERING_IT", "ENGINEERING"):
        addon = (
            "When relevant, prioritize technical depth, root-cause analysis, and system-level reasoning. "
            "Frame insights around defect patterns, performance signals, and diagnostic clarity."
        )
    elif dept_code == "MARKETING":
        addon = (
            "When relevant, focus on customer sentiment, brand perception, and emerging trends. "
            "Frame insights in terms of user experience, reputation, and market positioning."
        )
    elif dept_code == "SALES":
        addon = (
            "When relevant, emphasize revenue impact, customer risk, and business priorities. "
            "Highlight implications that affect deals, retention, and growth opportunities."
        )
    elif dept_code == "FINANCE":
        addon = (
            "When relevant, focus on financial risk, cost implications, and quantitative impact. "
            "Frame insights in terms of margins, exposure, and budget considerations."
        )
    elif dept_code in ("CUSTOMER_SUPPORT", "CUSTOMER SUPPORT / CUSTOMER SUCCESS"):
        addon = (
            "When relevant, focus on complaint patterns, resolution paths, and customer satisfaction signals. "
            "Prioritize actionable guidance that helps resolve issues quickly."
        )
    elif dept_code == "SUPPLY_CHAIN":
        addon = (
            "When relevant, focus on operational efficiency, bottlenecks, and supply reliability signals. "
            "Frame insights around logistics, lead times, and risk to fulfillment."
        )
    elif dept_code == "SECURITY":
        addon = (
            "When relevant, apply a security-first perspective: identify risk vectors, compliance gaps, "
            "and mitigation steps. Prioritize clarity on threat impact and remediation."
        )
    else:
        addon = (
            "Tailor examples and framing to be as relevant as possible to the user's context, "
            "without restricting the scope of what you can answer."
        )

    prompt = f"{base}\n\n{addon}"

    # --- Live model insights (injected only when artifacts are available) ---
    model_summary = build_model_summary(artifacts, dept_code)
    if model_summary:
        prompt += (
            f"\n\nCurrent model insights (from the latest training run):\n{model_summary}\n\n"
            f"Use this information when answering questions related to products, risk, customers, or business decisions."
        )

    return prompt


def build_model_input(conversation, user, artifacts=None):
    """Compose OpenAI input payload from system prompt + seed context + live turns.

    Layout:
        [system]  <- role/persona + optional user personalisation + live model insights
        [seed…]   <- pre-curated Q&A pairs loaded once from seed_context.json
        [conv…]   <- live messages from the current session
    """
    system_prompt = build_system_prompt(user, artifacts=artifacts)
    return [{"role": "system", "content": system_prompt}] + _SEED_CONTEXT + conversation
