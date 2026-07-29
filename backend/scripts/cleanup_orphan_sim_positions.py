"""Clean up orphaned system simulation positions.

A previous version of execute_entry ran a generic "Strategy Simulations" loop that cloned
the 12:00 Nifty market data for EVERY strategy. This created bad system positions:
  - NIFTY-symbol trades tagged strategyId="btc-option-selling" (showed Nifty trades on the
    BTC strategy page), stored under userStrategyId="system_btc-option-selling"
  - duplicate Nifty benchmark trades under userStrategyId="system_nifty-straddle"

The only VALID system simulation positions are the dedicated benchmarks:
  - system_nifty_benchmark   (created by execute_entry)
  - system_btc_benchmark     (created by execute_btc_entry)

This script deletes every other userId=="system" position.

Usage (from the backend directory):
  python scripts/cleanup_orphan_sim_positions.py          # dry run — lists what WOULD be deleted
  python scripts/cleanup_orphan_sim_positions.py --apply   # actually delete

Requires FIREBASE_CREDENTIALS_PATH to be set in .env
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.firebase_service import init_firebase, get_db

# userStrategyIds that are legitimate system benchmarks — everything else under
# userId=="system" is an orphan from the old generic simulation loop.
KEEP_USER_STRATEGY_IDS = {"system_nifty_benchmark", "system_btc_benchmark"}


def main(apply: bool) -> None:
    init_firebase()
    db = get_db()

    docs = list(db.collection("positions").where("userId", "==", "system").stream())
    orphans = []
    kept = 0
    for d in docs:
        data = d.to_dict() or {}
        if data.get("userStrategyId") in KEEP_USER_STRATEGY_IDS:
            kept += 1
            continue
        orphans.append((d.id, data))

    print(f"System positions scanned : {len(docs)}")
    print(f"Valid benchmark (kept)   : {kept}")
    print(f"Orphans to delete        : {len(orphans)}")
    print("-" * 60)
    for doc_id, data in orphans:
        print(
            f"  {data.get('date', '?'):12} "
            f"{str(data.get('userStrategyId', '?')):26} "
            f"{str(data.get('symbol', '?')):22} "
            f"strategyId={data.get('strategyId', '?')}"
        )

    if not orphans:
        print("\nNothing to clean up.")
        return

    if not apply:
        print(f"\nDRY RUN — nothing deleted. Re-run with --apply to delete these {len(orphans)} documents.")
        return

    deleted = 0
    for doc_id, _ in orphans:
        db.collection("positions").document(doc_id).delete()
        deleted += 1
    print(f"\nDeleted {deleted} orphaned system position(s).")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
