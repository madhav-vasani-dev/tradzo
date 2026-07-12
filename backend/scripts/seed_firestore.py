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
    "minimumAmount": 300000,
    "lotSize": 65,
    "stopLossPercent": 30,
    "entryTime": "12:00",
    "exitTime": "15:29",
    "tags": ["Intraday", "Options Selling", "Straddle", "ATM"],
    "performance": {
        "cagr": 0,
        "sharpeRatio": 0,
        "maxDrawdown": 0,
        "winRate": 0,
        "totalTrades": 0,
        "avgTradeReturn": 0,
        "avgTradeDurationMinutes": 0,
        "profitFactor": 0,
        "calmarRatio": 0,
        "expectancy": 0,
        "backtestStartDate": "",
        "backtestEndDate": "",
        "monthlyReturns": [],
        "yearlyReturns": [],
        "equityCurve": [],
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
    if strategies_ref.get().exists:
        print("[OK] strategies/nifty-straddle already exists — skipping.")
    else:
        strategies_ref.set(NIFTY_STRADDLE_DOC)
        print("[OK] Created strategies/nifty-straddle")

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
