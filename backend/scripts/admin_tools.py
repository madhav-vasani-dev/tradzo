"""Admin maintenance commands — run on the server inside the backend container.

  docker compose exec web python scripts/admin_tools.py open-positions
  docker compose exec web python scripts/admin_tools.py delete-position <positionId>        # dry run
  docker compose exec web python scripts/admin_tools.py delete-position <positionId> --yes  # delete
  docker compose exec web python scripts/admin_tools.py purge-btc                           # dry run
  docker compose exec web python scripts/admin_tools.py purge-btc --yes                     # delete

Every command is a dry run unless --yes is given. Deleting a position only removes Tradzo's
record — it never touches the broker. Check the broker app first that the leg is really flat.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud.firestore_v1.base_query import FieldFilter  # noqa: E402

from services.firebase_service import get_db, init_firebase  # noqa: E402

BTC_CODE = "BTC_OPTION_SELLING"
BTC_STRATEGY_ID = "btc-option-selling"


def _fmt_pos(pid: str, p: dict) -> str:
    return (f"{pid}  {p.get('date')}  {p.get('strategyCode')}  {p.get('broker')}  {p.get('symbol')}  "
            f"status={p.get('status')}  paper={p.get('isPaper')}  qty={p.get('quantity')}  "
            f"entry={p.get('entryPrice')}  entryOrder={p.get('entryOrderId')}  slOrder={p.get('slOrderId')}  "
            f"user={p.get('userId')}")


def open_positions(_args) -> None:
    db = get_db()
    docs = db.collection("positions").where(filter=FieldFilter("status", "in", ["open", "closing"])).stream()
    rows = [(d.id, d.to_dict() or {}) for d in docs]
    if not rows:
        print("No open/closing positions.")
    for pid, p in sorted(rows, key=lambda r: (r[1].get("date") or "", r[1].get("symbol") or "")):
        print(_fmt_pos(pid, p))


def delete_position(args) -> None:
    db = get_db()
    ref = db.collection("positions").document(args.position_id)
    snap = ref.get()
    if not snap.exists:
        print(f"Position {args.position_id} not found.")
        return
    p = snap.to_dict() or {}
    print(_fmt_pos(snap.id, p))
    if not args.yes:
        print("\nDry run — nothing deleted. Make sure this leg is NOT open in the broker app, then re-run with --yes.")
        return
    ref.delete()
    print("Deleted.")
    dep_id = p.get("userStrategyId")
    if dep_id and not str(dep_id).startswith("system"):
        left = list(db.collection("positions").where(filter=FieldFilter("userStrategyId", "==", dep_id))
                    .where(filter=FieldFilter("status", "in", ["open", "closing"])).stream())
        dep = db.collection("userStrategies").document(dep_id).get()
        if not left and dep.exists and (dep.to_dict() or {}).get("status") == "trade_active":
            dep.reference.update({"status": "trade_closed"})
            print(f"Deployment {dep_id}: status trade_active -> trade_closed (no open legs left).")


def _delete_refs(refs: list) -> None:
    db = get_db()
    for i in range(0, len(refs), 400):
        batch = db.batch()
        for r in refs[i:i + 400]:
            batch.delete(r)
        batch.commit()


def purge_btc(args) -> None:
    db = get_db()
    from google.cloud import firestore as gcf

    positions = {d.id: d.reference for q in (
        db.collection("positions").where(filter=FieldFilter("strategyCode", "==", BTC_CODE)).stream(),
        db.collection("positions").where(filter=FieldFilter("strategyId", "==", BTC_STRATEGY_ID)).stream(),
    ) for d in q}
    deployments = {d.id: d.reference for q in (
        db.collection("userStrategies").where(filter=FieldFilter("strategyCode", "==", BTC_CODE)).stream(),
        db.collection("userStrategies").where(filter=FieldFilter("strategyId", "==", BTC_STRATEGY_ID)).stream(),
    ) for d in q}
    logs = [d.reference for d in
            db.collection("activityLogs").where(filter=FieldFilter("strategyId", "==", BTC_STRATEGY_ID)).stream()]
    users = [d.reference for d in
             db.collection("users").where(filter=FieldFilter("deployedStrategyIds", "array_contains",
                                                              BTC_STRATEGY_ID)).stream()]
    strategy = db.collection("strategies").document(BTC_STRATEGY_ID)
    has_strategy = strategy.get().exists

    print(f"BTC strategy doc:        {'yes' if has_strategy else 'not found'}")
    print(f"BTC deployments:         {len(deployments)}")
    print(f"BTC positions (all-time): {len(positions)}")
    print(f"BTC activity-log entries: {len(logs)}")
    print(f"Users to unlink:          {len(users)}")
    if not args.yes:
        print("\nDry run — nothing deleted. Re-run with --yes to delete all of the above permanently.")
        return
    _delete_refs(list(positions.values()) + list(deployments.values()) + logs)
    for u in users:
        u.update({"deployedStrategyIds": gcf.ArrayRemove([BTC_STRATEGY_ID])})
    if has_strategy:
        strategy.delete()
    print("BTC data deleted.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("open-positions").set_defaults(fn=open_positions)
    dp = sub.add_parser("delete-position")
    dp.add_argument("position_id")
    dp.add_argument("--yes", action="store_true")
    dp.set_defaults(fn=delete_position)
    pb = sub.add_parser("purge-btc")
    pb.add_argument("--yes", action="store_true")
    pb.set_defaults(fn=purge_btc)
    args = ap.parse_args()
    init_firebase()
    args.fn(args)


if __name__ == "__main__":
    main()
