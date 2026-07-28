"""
Synthetic KPI data generator for InsightGuardAI.
Generates 24 months of realistic KPI data across Finance, Operations, and Customer domains
with intentionally injected anomalies for demo purposes.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

SEED = 42
np.random.seed(SEED)

START_DATE = datetime(2024, 8, 1)
MONTHS = 24


def date_range(n=MONTHS):
    return [START_DATE + timedelta(days=30 * i) for i in range(n)]


def seasonal(n, amplitude=0.1, period=12):
    t = np.arange(n)
    return amplitude * np.sin(2 * np.pi * t / period)


def trend(n, slope=0.003):
    return np.arange(n) * slope


def noise(n, sigma=0.02):
    return np.random.normal(0, sigma, n)


def inject_anomaly(series, indices, multiplier=1.6):
    s = series.copy()
    for i in indices:
        s[i] *= multiplier
    return s


def generate_finance_kpis(dates):
    n = len(dates)
    base_revenue = 5_000_000

    revenue = base_revenue * (1 + trend(n, 0.008) + seasonal(n, 0.12) + noise(n, 0.03))
    revenue = inject_anomaly(revenue, [18, 19], multiplier=0.72)  # sudden revenue drop

    revenue_target = base_revenue * (1 + trend(n, 0.010))

    cogs_ratio = 0.58 + noise(n, 0.015) + seasonal(n, 0.03)
    cogs_ratio = inject_anomaly(cogs_ratio, [14], multiplier=1.18)
    gross_profit = revenue * (1 - cogs_ratio)
    gross_margin_pct = gross_profit / revenue * 100

    opex = revenue * (0.28 + noise(n, 0.01))
    ebitda = gross_profit - opex
    ebitda_margin_pct = ebitda / revenue * 100

    ar_days = 45 + noise(n, 2) * 10 + trend(n, 0.4)
    ar_days = inject_anomaly(ar_days, [20, 21, 22], multiplier=1.35)

    cash_balance = 8_000_000 * (1 + trend(n, 0.005) + noise(n, 0.04))
    cash_balance = inject_anomaly(cash_balance, [19, 20], multiplier=0.65)

    df = pd.DataFrame({
        "date": dates,
        "domain": "Finance",
        "revenue": revenue.round(0),
        "revenue_target": revenue_target.round(0),
        "gross_profit": gross_profit.round(0),
        "gross_margin_pct": gross_margin_pct.round(2),
        "ebitda": ebitda.round(0),
        "ebitda_margin_pct": ebitda_margin_pct.round(2),
        "ar_days": ar_days.round(1),
        "cash_balance": cash_balance.round(0),
    })
    return df


def generate_operations_kpis(dates):
    n = len(dates)

    oee = 82 + trend(n, 0.1) + seasonal(n, 3) + noise(n, 1.5)
    oee = inject_anomaly(oee, [9, 10], multiplier=0.78)
    oee = np.clip(oee, 0, 100)
    oee_target = np.full(n, 88.0)

    defect_rate = 1.8 + noise(n, 0.2) - trend(n, 0.02)
    defect_rate = inject_anomaly(defect_rate, [9, 10, 11], multiplier=2.1)
    defect_rate = np.clip(defect_rate, 0.1, 10)

    on_time_delivery = 94 + noise(n, 1.2) - seasonal(n, 2)
    on_time_delivery = inject_anomaly(on_time_delivery, [16, 17], multiplier=0.89)
    on_time_delivery = np.clip(on_time_delivery, 0, 100)

    inventory_turnover = 6.5 + trend(n, 0.05) + noise(n, 0.3)
    inventory_turnover = inject_anomaly(inventory_turnover, [12, 13], multiplier=0.70)

    downtime_hours = 18 + noise(n, 3) - trend(n, 0.2)
    downtime_hours = inject_anomaly(downtime_hours, [9, 10], multiplier=2.8)
    downtime_hours = np.clip(downtime_hours, 0, 200)

    unit_cost = 42 + trend(n, 0.15) + noise(n, 0.8)
    unit_cost = inject_anomaly(unit_cost, [14, 15], multiplier=1.22)

    df = pd.DataFrame({
        "date": dates,
        "domain": "Operations",
        "oee_pct": oee.round(1),
        "oee_target_pct": oee_target,
        "defect_rate_pct": defect_rate.round(2),
        "on_time_delivery_pct": on_time_delivery.round(1),
        "inventory_turnover": inventory_turnover.round(2),
        "downtime_hours": downtime_hours.round(1),
        "unit_cost": unit_cost.round(2),
    })
    return df


def generate_customer_kpis(dates):
    n = len(dates)

    nps = 52 + trend(n, 0.3) + seasonal(n, 5) + noise(n, 2)
    nps = inject_anomaly(nps, [18, 19, 20], multiplier=0.68)
    nps = np.clip(nps, -100, 100)

    csat = 4.1 + trend(n, 0.01) + noise(n, 0.08)
    csat = inject_anomaly(csat, [18, 19, 20], multiplier=0.82)
    csat = np.clip(csat, 1, 5)

    churn_rate = 2.8 - trend(n, 0.03) + noise(n, 0.2) + seasonal(n, 0.4)
    churn_rate = inject_anomaly(churn_rate, [19, 20, 21], multiplier=1.85)
    churn_rate = np.clip(churn_rate, 0.1, 20)

    new_customers = 320 + trend(n, 3) + seasonal(n, 30) + noise(n, 15) * 10
    new_customers = inject_anomaly(new_customers, [18, 19], multiplier=0.55)

    avg_resolution_time = 4.2 - trend(n, 0.03) + noise(n, 0.3)
    avg_resolution_time = inject_anomaly(avg_resolution_time, [15, 16], multiplier=1.6)
    avg_resolution_time = np.clip(avg_resolution_time, 0.5, 24)

    clv = 1200 + trend(n, 8) + noise(n, 40)
    clv = inject_anomaly(clv, [19, 20], multiplier=0.75)

    df = pd.DataFrame({
        "date": dates,
        "domain": "Customer",
        "nps": nps.round(1),
        "csat": csat.round(2),
        "churn_rate_pct": churn_rate.round(2),
        "new_customers": new_customers.round(0).astype(int),
        "avg_resolution_time_hrs": avg_resolution_time.round(1),
        "customer_lifetime_value": clv.round(0),
    })
    return df


def generate_all(output_dir="data"):
    os.makedirs(output_dir, exist_ok=True)
    dates = date_range()

    finance_df = generate_finance_kpis(dates)
    ops_df = generate_operations_kpis(dates)
    customer_df = generate_customer_kpis(dates)

    finance_df.to_csv(os.path.join(output_dir, "finance_kpis.csv"), index=False)
    ops_df.to_csv(os.path.join(output_dir, "operations_kpis.csv"), index=False)
    customer_df.to_csv(os.path.join(output_dir, "customer_kpis.csv"), index=False)

    print(f"Generated {len(dates)} months of KPI data across 3 domains.")
    return finance_df, ops_df, customer_df


if __name__ == "__main__":
    generate_all()
