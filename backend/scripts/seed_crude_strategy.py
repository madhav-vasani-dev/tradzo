"""Add the Crude Oil Mini Straddle strategy to Firestore WITHOUT touching anything else.

Run once from the backend directory:
  python scripts/seed_crude_strategy.py

Creates/updates strategies/crude-oil-mini-straddle and adds `supportedBrokers` to the existing
Nifty / BTC strategy docs (merge — no other field is changed).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.firebase_service import get_db, init_firebase  # noqa: E402
from scripts.seed_firestore import CRUDE_OIL_MINI_DOC  # noqa: E402


def main():
    init_firebase()
    db = get_db()
    db.collection("strategies").document("crude-oil-mini-straddle").set(CRUDE_OIL_MINI_DOC, merge=True)
    print("[OK] strategies/crude-oil-mini-straddle")
    for doc_id, brokers in (("nifty-straddle", ["upstox", "jainam", "kotak"]),
                            ("btc-option-selling", ["delta"])):
        ref = db.collection("strategies").document(doc_id)
        if ref.get().exists:
            ref.set({"supportedBrokers": brokers}, merge=True)
            print(f"[OK] strategies/{doc_id}.supportedBrokers = {brokers}")


if __name__ == "__main__":
    main()
