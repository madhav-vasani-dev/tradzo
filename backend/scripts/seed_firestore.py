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


# Real backtest data from Algotest.in (Nifty 12PM Straddle)
MONTHLY_PROFITS = [
    # 2021
    {"year": "2021", "month": "Jan", "profit": 9845},
    {"year": "2021", "month": "Feb", "profit": 7673},
    {"year": "2021", "month": "Mar", "profit": 9282},
    {"year": "2021", "month": "Apr", "profit": -17884},
    {"year": "2021", "month": "May", "profit": 11244},
    {"year": "2021", "month": "Jun", "profit": 4106},
    {"year": "2021", "month": "Jul", "profit": 6384},
    {"year": "2021", "month": "Aug", "profit": 9177},
    {"year": "2021", "month": "Sep", "profit": 11348},
    {"year": "2021", "month": "Oct", "profit": 20481},
    {"year": "2021", "month": "Nov", "profit": -4505},
    {"year": "2021", "month": "Dec", "profit": -9754},
    # 2022
    {"year": "2022", "month": "Jan", "profit": -1465},
    {"year": "2022", "month": "Feb", "profit": 7611},
    {"year": "2022", "month": "Mar", "profit": 9773},
    {"year": "2022", "month": "Apr", "profit": -10060},
    {"year": "2022", "month": "May", "profit": 18297},
    {"year": "2022", "month": "Jun", "profit": 8697},
    {"year": "2022", "month": "Jul", "profit": 9812},
    {"year": "2022", "month": "Aug", "profit": 3107},
    {"year": "2022", "month": "Sep", "profit": -8592},
    {"year": "2022", "month": "Oct", "profit": 7119},
    {"year": "2022", "month": "Nov", "profit": 2024},
    {"year": "2022", "month": "Dec", "profit": 3300},
    # 2023
    {"year": "2023", "month": "Jan", "profit": -7839},
    {"year": "2023", "month": "Feb", "profit": -3731},
    {"year": "2023", "month": "Mar", "profit": -2076},
    {"year": "2023", "month": "Apr", "profit": -395},
    {"year": "2023", "month": "May", "profit": -5599},
    {"year": "2023", "month": "Jun", "profit": -3054},
    {"year": "2023", "month": "Jul", "profit": 1307},
    {"year": "2023", "month": "Aug", "profit": 4727},
    {"year": "2023", "month": "Sep", "profit": -468},
    {"year": "2023", "month": "Oct", "profit": 2443},
    {"year": "2023", "month": "Nov", "profit": 1491},
    {"year": "2023", "month": "Dec", "profit": 6261},
    # 2024
    {"year": "2024", "month": "Jan", "profit": 6590},
    {"year": "2024", "month": "Feb", "profit": 23942},
    {"year": "2024", "month": "Mar", "profit": 6515},
    {"year": "2024", "month": "Apr", "profit": 4335},
    {"year": "2024", "month": "May", "profit": -1397},
    {"year": "2024", "month": "Jun", "profit": -2742},
    {"year": "2024", "month": "Jul", "profit": 14300},
    {"year": "2024", "month": "Aug", "profit": -9170},
    {"year": "2024", "month": "Sep", "profit": 15875},
    {"year": "2024", "month": "Oct", "profit": 31091},
    {"year": "2024", "month": "Nov", "profit": 51684},
    {"year": "2024", "month": "Dec", "profit": -20110},
    # 2025
    {"year": "2025", "month": "Jan", "profit": 3254},
    {"year": "2025", "month": "Feb", "profit": 23589},
    {"year": "2025", "month": "Mar", "profit": 6079},
    {"year": "2025", "month": "Apr", "profit": -4735},
    {"year": "2025", "month": "May", "profit": 14311},
    {"year": "2025", "month": "Jun", "profit": 2133},
    {"year": "2025", "month": "Jul", "profit": 2794},
    {"year": "2025", "month": "Aug", "profit": 3150},
    {"year": "2025", "month": "Sep", "profit": 3150},
    {"year": "2025", "month": "Oct", "profit": 13742},
    {"year": "2025", "month": "Nov", "profit": 5722},
    {"year": "2025", "month": "Dec", "profit": 223},
    # 2026
    {"year": "2026", "month": "Jan", "profit": 5021},
    {"year": "2026", "month": "Feb", "profit": 15542},
    {"year": "2026", "month": "Mar", "profit": -1326},
    {"year": "2026", "month": "Apr", "profit": 16842},
    {"year": "2026", "month": "May", "profit": 79},
    {"year": "2026", "month": "Jun", "profit": 11373},
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

# 3. Compute equity curve list
equity_curve = [{"date": "2021-01-01", "value": START_CAPITAL}]
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
        "cagr": 16.32,
        "sharpeRatio": 1.25,
        "maxDrawdown": 9.64,  # -28,913.35 / 300,000
        "winRate": 62.48,
        "totalTrades": 1346,
        "avgTradeReturn": 0.10,  # 286.18 / 300,000 * 100
        "avgTradeDurationMinutes": 209,
        "profitFactor": 1.51,
        "calmarRatio": 1.69,
        "expectancy": 0.19,
        "backtestStartDate": "2021-01-01",
        "backtestEndDate": "2026-06-21",
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
