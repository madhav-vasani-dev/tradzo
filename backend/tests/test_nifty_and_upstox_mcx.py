"""Regression: Nifty straddle on Upstox and Kotak through the refactored entry path, plus the
Upstox MCX snapshot + order payloads."""
import asyncio
from datetime import date, datetime

import pytest
import pytz

from config import settings
from services import crude_execution, execution_service as ex, kotak_service as ks, mcx_market_data as mcx
from services import market_data_service as md, order_service

IST = pytz.timezone("Asia/Kolkata")


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def base(monkeypatch):
    store = {"positions": {}, "statuses": {}, "logs": [], "upstox_orders": []}
    fb = ex.firebase_service
    monkeypatch.setattr(fb, "update_user_strategy_status", lambda d, st: store["statuses"].__setitem__(d, st))
    monkeypatch.setattr(fb, "is_paper_trading", lambda: False)
    ps = ex.position_service

    def create(data):
        pid = f"P{len(store['positions']) + 1}"
        store["positions"][pid] = {**data, "id": pid}
        return pid
    monkeypatch.setattr(ps, "create_position", create)
    monkeypatch.setattr(ps, "get_open_positions_for_user_strategy", lambda d, day: [])
    monkeypatch.setattr(ex.activity, "log_activity", lambda **k: store["logs"].append(k))
    monkeypatch.setattr(ex, "_refresh_live_feed", lambda: None)
    monkeypatch.setattr(settings, "entry_marketdata_lead_seconds", 0)
    monkeypatch.setattr(settings, "order_status_timeout_seconds", 0.3)
    monkeypatch.setattr(settings, "mcx_order_wait_seconds", 0.3)

    # Upstox order engine: everything fills at its limit (or LTP for market).
    orders = {}

    async def real_place(token, payload):
        oid = f"U{len(orders) + 1}"
        orders[oid] = payload
        store["upstox_orders"].append(payload)
        return {"data": {"order_id": oid}}

    async def details(token, oid):
        p = orders[oid]
        if p["order_type"] in ("SL", "SL-M"):
            return {"status": "trigger pending", "order_type": p["order_type"], "price": p["price"]}
        return {"status": "complete", "filled_quantity": p["quantity"], "average_price": p["price"] or 100.0}
    monkeypatch.setattr(order_service, "_real_place", real_place)
    monkeypatch.setattr(order_service, "get_order_details", details)
    return store


def _dep(broker, code="NIFTY_STRADDLE", acc="acc1"):
    return {"id": "dep1", "userId": "u1", "strategyId": "x", "strategyCode": code, "brokerAccountId": acc,
            "brokerName": broker, "multiplier": 1, "status": "ready"}


def test_nifty_upstox_entry_unchanged(base, monkeypatch):
    store = base
    fb = ex.firebase_service
    monkeypatch.setattr(fb, "list_deployments_by_status", lambda st: [_dep("upstox")] if st == "ready" else [])
    monkeypatch.setattr(ex, "_accounts_by_id", lambda: {"acc1": {"id": "acc1", "broker": "upstox", "isConnected": True}})
    monkeypatch.setattr(ex, "_users_by_id", lambda: {"u1": {"paperTrading": False}})
    monkeypatch.setattr(ex, "_get_token", lambda acc: "UPSTOX_TOKEN")

    async def atm():
        return {"spot": 25012.0, "atm_strike": 25000, "expiry": "2026-10-13", "ce_key": "NSE_FO|1",
                "pe_key": "NSE_FO|2", "ce_ltp": 100.0, "pe_ltp": 90.0}
    monkeypatch.setattr(md, "get_atm_data", atm)
    monkeypatch.setattr(settings, "order_style", "market")
    s = run(ex.execute_entry(entry_time=datetime.now(IST).strftime("%H:%M")))
    assert s["placed"] == 2 and s["failed"] == 0
    sells = [o for o in store["upstox_orders"] if o["transaction_type"] == "SELL"]
    assert all(o["order_type"] == "MARKET" and o["quantity"] == 65 for o in sells)
    sls = [o for o in store["upstox_orders"] if o["transaction_type"] == "BUY"]
    assert {o["order_type"] for o in sls} == {"SL-M"}
    p = next(iter(store["positions"].values()))
    assert p["exchange"] == "NSE" and p["pnlMultiplier"] == 1.0 and p["symbol"].startswith("NIFTY1013")


def test_nifty_on_kotak(base, monkeypatch):
    store = base
    fb = ex.firebase_service
    monkeypatch.setattr(fb, "list_deployments_by_status", lambda st: [_dep("kotak")] if st == "ready" else [])
    monkeypatch.setattr(ex, "_accounts_by_id", lambda: {"acc1": {"id": "acc1", "broker": "kotak", "isConnected": True}})
    monkeypatch.setattr(ex, "_users_by_id", lambda: {"u1": {"paperTrading": False}})
    sess = ks.KotakSession(account_id="acc1", access_token="t", ucc="U", auth="A", sid="S",
                           base_url="https://x", created_at=datetime.now(IST).isoformat())

    async def ensure(a, **k):
        return sess
    monkeypatch.setattr(ks, "ensure_session", ensure)

    async def atm():
        return {"spot": 25012.0, "atm_strike": 25000, "expiry": "2026-10-13", "ce_key": "NSE_FO|1",
                "pe_key": "NSE_FO|2", "ce_ltp": 100.0, "pe_ltp": 90.0}
    monkeypatch.setattr(md, "get_atm_data", atm)

    async def chain(handle, **k):
        assert k["exchange"] == "nse_fo" and k["underlying"] == "NIFTY" and k["expiry"] == "2026-10-13"
        return {"common_data": {"mktLot": "65", "multiplier": "1"},
                "call": [{"instrument": {"neoSymbol": "nse_fo|71", "symbol": "NIFTY26OCT25000CE",
                                         "optionType": "CE", "strikePrice": "25000"}, "quote": {"ltp": "101"}}],
                "put": [{"instrument": {"neoSymbol": "nse_fo|72", "symbol": "NIFTY26OCT25000PE",
                                        "optionType": "PE", "strikePrice": "25000"}, "quote": {"ltp": "91"}}]}
    monkeypatch.setattr(ks, "option_chain", chain)
    placed = []

    async def place(handle, **k):
        placed.append(k)
        return f"K{len(placed)}"

    async def state(handle, oid):
        k = placed[int(oid[1:]) - 1]
        if k["order_type"] == "SL":
            return {"terminal": False, "status": "open", "filled_qty": 0, "avg_price": 0, "message": ""}
        return {"terminal": True, "status": "complete", "filled_qty": k["quantity"], "avg_price": k["price"],
                "message": ""}
    monkeypatch.setattr(ks, "place_order", place)
    monkeypatch.setattr(ks, "order_state", state)

    async def ltp(handle, key):
        return 100.0
    monkeypatch.setattr(ks, "get_ltp", ltp)
    s = run(ex.execute_entry(entry_time=datetime.now(IST).strftime("%H:%M")))
    assert s["placed"] == 2, store["logs"]
    sells = [k for k in placed if k["side"] == "SELL"]
    assert all(k["order_type"] == "L" and k["validity"] == "IOC" and k["segment"] == "nse_fo"
               and k["quantity"] == 65 for k in sells)
    sls = [k for k in placed if k["order_type"] == "SL"]
    assert len(sls) == 2 and all(k["price"] > k["trigger_price"] for k in sls)
    pos = next(iter(store["positions"].values()))
    assert pos["instrumentKey"].startswith("nse_fo|7") and pos["marketDataKey"] in ("NSE_FO|1", "NSE_FO|2")


UPSTOX_ROWS = [
    {"segment": "MCX_FO", "instrument_type": "FUT", "instrument_key": "MCX_FO|900", "underlying_symbol": "CRUDEOILM",
     "trading_symbol": "CRUDEOILM FUT 19 OCT 26", "expiry": 1760895000000, "lot_size": 1},
    {"segment": "MCX_FO", "instrument_type": "FUT", "instrument_key": "MCX_FO|901", "underlying_symbol": "CRUDEOILM",
     "trading_symbol": "CRUDEOILM FUT 19 NOV 26", "expiry": 1763573400000, "lot_size": 1},
]
for k in (6050, 6100, 6150):
    for t in ("CE", "PE"):
        UPSTOX_ROWS.append({"segment": "MCX_FO", "instrument_type": t, "instrument_key": f"MCX_FO|{k}{t}",
                            "underlying_symbol": "CRUDEOILM", "trading_symbol": f"CRUDEOILM {k} {t} 15 OCT 26",
                            "strike_price": float(k), "expiry": 1760549400000, "lot_size": 1})


def test_upstox_crude_entry(base, monkeypatch):
    store = base
    # epochs above are 2025 dates; shift "today" accordingly
    exp = mcx._parse_date(1760549400000)
    monkeypatch.setattr(mcx, "_ist_today", lambda: exp.replace(day=exp.day - 5))
    monkeypatch.setattr(mcx, "_upstox_cache", {"day": None, "rows": None})

    async def dl():
        return UPSTOX_ROWS
    monkeypatch.setattr(mcx, "_download_upstox_mcx", dl)

    async def ltps(keys, access_token=None):
        prices = {"MCX_FO|900": 6112.0, "MCX_FO|6100CE": 150.0, "MCX_FO|6100PE": 138.0}
        return {k: prices[k] for k in keys if k in prices}
    monkeypatch.setattr(md, "get_ltps", ltps)

    async def one(k, access_token=None):
        return (await ltps([k])).get(k, 0.0)
    monkeypatch.setattr(md, "get_option_ltp", one)
    fb = ex.firebase_service
    monkeypatch.setattr(fb, "list_deployments_by_status",
                        lambda st: [_dep("upstox", "CRUDEOILM_STRADDLE")] if st == "ready" else [])
    monkeypatch.setattr(ex, "_accounts_by_id", lambda: {"acc1": {"id": "acc1", "broker": "upstox", "isConnected": True}})
    monkeypatch.setattr(ex, "_users_by_id", lambda: {"u1": {"paperTrading": False}})
    monkeypatch.setattr(ex, "_get_token", lambda acc: "UPSTOX_TOKEN")
    s = run(crude_execution.execute_crude_entry(entry=datetime.now(IST).strftime("%H:%M")))
    assert s["placed"] == 2 and s["atmStrike"] == 6100.0, store["logs"]
    sells = [o for o in store["upstox_orders"] if o["transaction_type"] == "SELL"]
    assert all(o["order_type"] == "LIMIT" and o["validity"] == "DAY" and o["quantity"] == 1 for o in sells)
    assert {o["instrument_token"] for o in sells} == {"MCX_FO|6100CE", "MCX_FO|6100PE"}
    sls = [o for o in store["upstox_orders"] if o["transaction_type"] == "BUY"]
    assert {o["order_type"] for o in sls} == {"SL"} and all(o["price"] > o["trigger_price"] for o in sls)
    p = next(iter(store["positions"].values()))
    assert p["pnlMultiplier"] == 10.0 and p["exchange"] == "MCX"


def test_jainam_mcx_resolution(monkeypatch):
    from services import jainam_service
    calls = []

    async def lookup(**k):
        calls.append(k)
        return {"exchangeInstrumentID": 4455 if k["option_type"] == "CE" else 4456, "lotSize": 10}
    monkeypatch.setattr(jainam_service, "get_option_instrument", lookup)
    item = {"dep": {"id": "dep1"}, "strategy": crude_execution.get_strategy("CRUDEOILM_STRADDLE"), "lots": 3,
            "md_token": "MD"}
    snap = {"atm_strike": 6100.0, "expiry": "2026-10-15", "ce_key": "MCX_FO|1", "pe_key": "MCX_FO|2",
            "ce_ltp": 1, "pe_ltp": 1, "source": "upstox"}
    crude_execution._make_orders(item, snap)
    run(crude_execution._resolve_jainam(item, snap))
    assert all(c["exchange_segment"] == "MCXFO" and c["series"] == "OPTFUT" for c in calls)
    ce = item["orders"][0]
    assert (ce["instrument_key"], ce["qty"], ce["pnl_multiplier"]) == ("4455", 30, 1.0)
    assert ce["extra"]["marketDataKey"] == "MCX_FO|1"


def test_live_feed_keys():
    from services import live_feed_service as lf
    assert lf.upstox_key_for({"broker": "kotak", "instrumentKey": "mcx_fo|1|X"}) is None
    assert lf.upstox_key_for({"broker": "kotak", "instrumentKey": "mcx_fo|1|X", "marketDataKey": "MCX_FO|9"}) == "MCX_FO|9"
    assert lf.upstox_key_for({"broker": "jainam", "instrumentKey": "4455", "exchange": "MCX"}) is None
    assert lf.upstox_key_for({"broker": "jainam", "instrumentKey": "43427"}) == "NSE_FO|43427"
    assert lf.upstox_key_for({"broker": "upstox", "instrumentKey": "NSE_FO|43427"}) == "NSE_FO|43427"
