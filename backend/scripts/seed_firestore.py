"""Seed the Firestore database with initial documents.

Run once from the backend directory:
  python scripts/seed_firestore.py

Creates:
  strategies/nifty-straddle  — the live strategy configuration
  settings/tradingMode       — defaults to paperTrading=True (safe)

Requires FIREBASE_CREDENTIALS_PATH to be set in .env
"""
import sys
import os

# Add parent directory to path so we can import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.firebase_service import init_firebase, get_db
from datetime import datetime
import pytz

IST = pytz.timezone("Asia/Kolkata")


# Real backtest data from Algotest.in (Nifty 12PM Straddle) - 2019 to 2026
MONTHLY_PROFITS = [
    # 2019
    {"year": "2019", "month": "Jan", "profit": 0},
    {"year": "2019", "month": "Feb", "profit": 1956},
    {"year": "2019", "month": "Mar", "profit": 9779},
    {"year": "2019", "month": "Apr", "profit": 9880},
    {"year": "2019", "month": "May", "profit": 14004},
    {"year": "2019", "month": "Jun", "profit": 9288},
    {"year": "2019", "month": "Jul", "profit": -2479},
    {"year": "2019", "month": "Aug", "profit": 4205},
    {"year": "2019", "month": "Sep", "profit": 16828},
    {"year": "2019", "month": "Oct", "profit": 1413},
    {"year": "2019", "month": "Nov", "profit": -2021},
    {"year": "2019", "month": "Dec", "profit": -87},
    # 2020
    {"year": "2020", "month": "Jan", "profit": 10536},
    {"year": "2020", "month": "Feb", "profit": 14592},
    {"year": "2020", "month": "Mar", "profit": 35083},
    {"year": "2020", "month": "Apr", "profit": 15619},
    {"year": "2020", "month": "May", "profit": 10039},
    {"year": "2020", "month": "Jun", "profit": 8245},
    {"year": "2020", "month": "Jul", "profit": 17117},
    {"year": "2020", "month": "Aug", "profit": 13643},
    {"year": "2020", "month": "Sep", "profit": 8482},
    {"year": "2020", "month": "Oct", "profit": 6340},
    {"year": "2020", "month": "Nov", "profit": 4085},
    {"year": "2020", "month": "Dec", "profit": 14173},
    # 2021
    {"year": "2021", "month": "Jan", "profit": 11271},
    {"year": "2021", "month": "Feb", "profit": 9090},
    {"year": "2021", "month": "Mar", "profit": 10903},
    {"year": "2021", "month": "Apr", "profit": 19298},
    {"year": "2021", "month": "May", "profit": 12623},
    {"year": "2021", "month": "Jun", "profit": 5518},
    {"year": "2021", "month": "Jul", "profit": 7647},
    {"year": "2021", "month": "Aug", "profit": 10478},
    {"year": "2021", "month": "Sep", "profit": 12710},
    {"year": "2021", "month": "Oct", "profit": 21875},
    {"year": "2021", "month": "Nov", "profit": -3159},
    {"year": "2021", "month": "Dec", "profit": -8108},
    # 2022
    {"year": "2022", "month": "Jan", "profit": 42},
    {"year": "2022", "month": "Feb", "profit": 9256},
    {"year": "2022", "month": "Mar", "profit": 11573},
    {"year": "2022", "month": "Apr", "profit": -8684},
    {"year": "2022", "month": "May", "profit": 19994},
    {"year": "2022", "month": "Jun", "profit": 10377},
    {"year": "2022", "month": "Jul", "profit": 11316},
    {"year": "2022", "month": "Aug", "profit": 4520},
    {"year": "2022", "month": "Sep", "profit": -6909},
    {"year": "2022", "month": "Oct", "profit": 8401},
    {"year": "2022", "month": "Nov", "profit": 3389},
    {"year": "2022", "month": "Dec", "profit": 4761},
    # 2023
    {"year": "2023", "month": "Jan", "profit": -6376},
    {"year": "2023", "month": "Feb", "profit": -2398},
    {"year": "2023", "month": "Mar", "profit": -692},
    {"year": "2023", "month": "Apr", "profit": 620},
    {"year": "2023", "month": "May", "profit": -4244},
    {"year": "2023", "month": "Jun", "profit": -1774},
    {"year": "2023", "month": "Jul", "profit": 2661},
    {"year": "2023", "month": "Aug", "profit": 6077},
    {"year": "2023", "month": "Sep", "profit": 783},
    {"year": "2023", "month": "Oct", "profit": 3714},
    {"year": "2023", "month": "Nov", "profit": 2694},
    {"year": "2023", "month": "Dec", "profit": 8290},
    # 2024
    {"year": "2024", "month": "Jan", "profit": 8209},
    {"year": "2024", "month": "Feb", "profit": 25535},
    {"year": "2024", "month": "Mar", "profit": 16204},
    {"year": "2024", "month": "Apr", "profit": 7920},
    {"year": "2024", "month": "May", "profit": 5993},
    {"year": "2024", "month": "Jun", "profit": 234},
    {"year": "2024", "month": "Jul", "profit": -1075},
    {"year": "2024", "month": "Aug", "profit": 15843},
    {"year": "2024", "month": "Sep", "profit": -7631},
    {"year": "2024", "month": "Oct", "profit": 19093},
    {"year": "2024", "month": "Nov", "profit": 17280},
    {"year": "2024", "month": "Dec", "profit": 32769},
    # 2025
    {"year": "2025", "month": "Jan", "profit": 5122},
    {"year": "2025", "month": "Feb", "profit": 25116},
    {"year": "2025", "month": "Mar", "profit": 7445},
    {"year": "2025", "month": "Apr", "profit": -3295},
    {"year": "2025", "month": "May", "profit": 16094},
    {"year": "2025", "month": "Jun", "profit": 3799},
    {"year": "2025", "month": "Jul", "profit": 10741},
    {"year": "2025", "month": "Aug", "profit": 4104},
    {"year": "2025", "month": "Sep", "profit": 4598},
    {"year": "2025", "month": "Oct", "profit": 15135},
    {"year": "2025", "month": "Nov", "profit": 7072},
    {"year": "2025", "month": "Dec", "profit": 1686},
    # 2026
    {"year": "2026", "month": "Jan", "profit": 6519},
    {"year": "2026", "month": "Feb", "profit": 17127},
    {"year": "2026", "month": "Mar", "profit": 620},
    {"year": "2026", "month": "Apr", "profit": 18720},
    {"year": "2026", "month": "May", "profit": 1680},
    {"year": "2026", "month": "Jun", "profit": 20185},
    {"year": "2026", "month": "Jul", "profit": 8924},
]

START_CAPITAL = 300000.0

# 1. Compute monthly returns list
monthly_returns = []
for item in MONTHLY_PROFITS:
    pct = round((item["profit"] / START_CAPITAL) * 100, 2)
    monthly_returns.append({
        "month": f"{item['month']} {item['year']}",
        "returnPct": pct
    })

# 2. Compute yearly returns list
yearly_profits = {}
for item in MONTHLY_PROFITS:
    yearly_profits[item["year"]] = yearly_profits.get(item["year"], 0.0) + item["profit"]

yearly_returns = []
for yr in sorted(yearly_profits.keys()):
    pct = round((yearly_profits[yr] / START_CAPITAL) * 100, 2)
    yearly_returns.append({
        "year": yr,
        "returnPct": pct
    })

# 3. Compute equity curve list starting from 2019
equity_curve = [{"date": "2019-01-01", "value": START_CAPITAL}]
current_equity = START_CAPITAL
month_nums = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
    "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12"
}
for item in MONTHLY_PROFITS:
    current_equity += item["profit"]
    m_num = month_nums[item["month"]]
    equity_curve.append({
        "date": f"{item['year']}-{m_num}-28",
        "value": round(current_equity, 2)
    })

NIFTY_STRADDLE_DOC = {
    "id": "nifty-straddle",
    "name": "Nifty Straddle",
    "strategyCode": "NIFTY_STRADDLE",
    "description": (
        "Sells ATM Nifty 50 CE + PE at 12:00 PM every trading day using the "
        "current Tuesday weekly expiry. Both legs have a 30% stop-loss placed "
        "as SL-M orders at the time of entry. All positions are squared off at "
        "15:29 PM if not already stopped out."
    ),
    "category": "Options",
    "instrumentType": "Nifty 50 Weekly Options",
    "riskLevel": "High",
    "isVisible": True,
    "minimumAmount": START_CAPITAL,
    "lotSize": 65,
    "stopLossPercent": 30,
    "entryTime": "12:00",
    "exitTime": "15:29",
    "tags": ["Intraday", "Options Selling", "Straddle", "ATM"],
    "performance": {
        "cagr": 13.63,
        "sharpeRatio": 1.45,
        "maxDrawdown": 8.50,  # -25,496.25 / 300,000
        "winRate": 64.80,
        "totalTrades": 1824,
        "avgTradeReturn": 0.13,  # 394.76 / 300,000 * 100
        "avgTradeDurationMinutes": 209,
        "profitFactor": 1.80,
        "calmarRatio": 1.60,
        "expectancy": 0.28,
        "backtestStartDate": "2019-01-01",
        "backtestEndDate": "2026-07-12",
        "monthlyReturns": monthly_returns,
        "yearlyReturns": yearly_returns,
        "equityCurve": equity_curve,
    },
    "createdAt": datetime.now(IST),
    "updatedAt": datetime.now(IST),
    "createdByUid": "system",
}

TRADING_MODE_DOC = {
    "paperTrading": True,
    "updatedBy": "system",
    "updatedByName": "System Seed",
    "updatedAt": datetime.now(IST),
}




def seed():
    print("Initialising Firebase…")
    init_firebase()
    db = get_db()

    # ── strategies/nifty-straddle ─────────────────────────────────────────
    strategies_ref = db.collection("strategies").document("nifty-straddle")
    strategies_ref.set(NIFTY_STRADDLE_DOC)
    print("[OK] Created/updated strategies/nifty-straddle with real stats")

    # ── settings/tradingMode ──────────────────────────────────────────────
    settings_ref = db.collection("settings").document("tradingMode")
    if settings_ref.get().exists:
        print("[OK] settings/tradingMode already exists — skipping.")
    else:
        settings_ref.set(TRADING_MODE_DOC)
        print("[OK] Created settings/tradingMode (paperTrading=True)")

    print("\nSeeding complete.")



if __name__ == "__main__":
    seed()
