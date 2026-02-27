"""
Synthetic support ticket simulation for testing model stability and emerging risk.
"""
import pandas as pd
import numpy as np
from typing import Literal


def simulate_synthetic_support_tickets(
    agg: pd.DataFrame,
    trend_type: Literal["none", "slow_spike"] = "none",
    duration_months: int = 6,
    random_state: int = 42,
) -> pd.DataFrame:
    """
    Simulate synthetic support ticket volume over time.

    trend_type:
      - "none": Stable baseline, tests model stability
      - "slow_spike": Gradual increase in ticket count, tests emerging risk detection

    duration_months: Number of months to simulate (applied per ASIN).
    """
    rng = np.random.default_rng(random_state)
    months = agg["month"].unique()
    asins = agg["asin"].unique()

    if len(months) < duration_months:
        duration_months = len(months)

    # Build ticket rows per asin x month
    rows = []
    for asin in asins:
        asin_months = sorted(months)[:duration_months] if len(months) >= duration_months else months
        for i, month in enumerate(asin_months):
            if trend_type == "none":
                ticket_count = rng.poisson(2)
                high_severity_rate = 0.1 + rng.uniform(0, 0.1)
            else:  # slow_spike
                # Gradually increase tickets over time
                base = 2 + (i / len(asin_months)) * 8
                ticket_count = max(0, int(rng.poisson(base)))
                high_severity_rate = 0.1 + (i / len(asin_months)) * 0.3 + rng.uniform(0, 0.1)
                high_severity_rate = min(high_severity_rate, 1.0)
            resolution_hours = 24 + rng.exponential(48)
            rows.append({
                "asin": asin,
                "month": month,
                "ticket_count": ticket_count,
                "high_severity_rate": high_severity_rate,
                "resolution_time_avg": resolution_hours,
            })
    tickets = pd.DataFrame(rows)
    return tickets
