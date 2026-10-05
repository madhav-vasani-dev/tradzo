"""Crude Oil Mini straddle — contract selection, sizing, and an end-to-end Kotak entry + exit
against a simulated Kotak order book (no network, no Firestore)."""
import asyncio
from datetime import date, datetime

import pytest
import pytz

from config import settings
from services import crude_execution, execution_service as ex, kotak_service as ks, mcx_market_data as mcx
from services import order_service
from strategies import get_strategy

IST = pytz.timezone("Asia/Kolkata")


def run(coro):
    return asyncio.run(coro)


# ── Pure rules ────────────────────────────────────────────────────────────────

def test_expiry_roll_rule():
    exps = [date(2026, 10, 15), date(2026, 11, 17), date(2026, 12, 16)]
    assert mcx.pick_option_expiry(exps, date(2026, 10, 6), 1) == date(2026, 10, 15)
    assert mcx.pick_option_expiry(exps, date(2026, 10, 14), 1) == date(2026, 10, 15)
    assert mcx.pick_option_expiry(exps, date(2026, 10, 15), 1) == date(2026, 11, 17)   # expiry day → next month
    assert mcx.pick_option_expiry(exps, date(2026, 10, 15), 0) == date(2026, 10, 15)   # trade-through mode
    assert mcx.pick_option_expiry(exps, date(2026, 10, 16), 1) == date(2026, 11, 17)


def test_future_for_option_month():
    futs = [date(2026, 10, 19), date(2026, 11, 19), date(2026, 12, 18)]
    assert mcx.pick_future_expiry(futs, date(2026, 10, 15)) == date(2026, 10, 19)
    assert mcx.pick_future_expiry(futs, date(2026, 11, 17)) == date(2026, 11, 19)


def test_atm_is_nearest_listed_strike():
    strikes = [6000.0, 6050.0, 6100.0, 6150.0]
    assert mcx.nearest_strike(6074, strikes) == 6050.0
    assert mcx.nearest_strike(6076, strikes) == 6100.0
    assert mcx.nearest_strike(6075, strikes) == 6050.0   # exact tie → lower strike


def test_kotak_quantity_conventions():
    assert mcx.kotak_quantity(3, {"lot_size": 1, "multiplier": 10}) == (3, 10.0)
    assert mcx.kotak_quantity(3, {"lot_size": 10, "multiplier": 1}) == (30, 1.0)
    assert mcx.kotak_quantity(2, {"lot_size": 1, "multiplier": 1}) == (2, 10.0)
    with pytest.raises(RuntimeError):
        mcx.kotak_quantity(1, {"lot_size": 100, "multiplier": 1})
    with pytest.raises(RuntimeError):
        mcx.kotak_quantity(1, {"lot_size": 0})


def test_strategy_rules():
    s = get_strategy("CRUDEOILM_STRADDLE")
    assert s.STOP_LOSS_PCT == 20.0
    assert s.calculate_sl_price(152.35) == 182.9
    legs = s.get_entry_legs({}, 6100, "2026-10-15", 2)
    assert [(l["optionType"], l["quantity"]) for l in legs] == [("CE", 2), ("PE", 2)]


def test_mcx_prices_on_grid():
    assert order_service.protected_limit_price(152.33, "SELL", 2.0, order_service.MCX_TICK) == 149.2
    assert order_service.protected_limit_price(152.33, "BUY", 2.0, order_service.MCX_TICK) == 155.4
    assert order_service.sl_limit_price(182.9, order_service.MCX_TICK) == 201.2
    # float noise must not push an on-grid price up a tick
    assert order_service._round_up_tick(13.0, 0.05) == 13.0


# ── Simulated Kotak ───────────────────────────────────────────────────────────

class FakeKotak:
    """Minimal Kotak order book: limits fill at their price if marketable, SLs rest."""

    def __init__(self, ltp: dict[str, float], resting_first: int = 0):
        self.ltp = dict(ltp)
        self.orders: dict[str, dict] = {}
        self.seq = 0
        self.resting_first = resting_first     # first N limit orders rest (to test re-pricing)
        self.net: dict[str, int] = {}

    async def place_order(self, handle, *, segment, trading_symbol, side, quantity, order_type, price=0.0,
                          trigger_price=0.0, product="NRML", validity="DAY", tag=""):
        assert segment == "mcx_fo" and validity == "DAY" and product == "NRML"
        if order_type in ("L", "SL"):
            assert price > 0
        self.seq += 1
        oid = f"OID{self.seq}"
        o = {"sym": trading_symbol, "side": side, "qty": quantity, "type": order_type, "price": price,
             "trigger": trigger_price, "status": "open", "filled": 0, "avg": 0.0, "tag": tag}
        self.orders[oid] = o
        if order_type == "L":
            if self.resting_first > 0:
                self.resting_first -= 1
            else:
                self._fill(o)
        return oid

    def _fill(self, o):
        o.update(status="complete", filled=o["qty"], avg=self.ltp[o["sym"]])
        sign = -1 if o["side"].upper().startswith("S") else 1
        self.net[o["sym"]] = self.net.get(o["sym"], 0) + sign * o["qty"]

    async def order_state(self, handle, oid):
        o = self.orders[oid]
        return {"terminal": o["status"] != "open", "status": o["status"], "filled_qty": o["filled"],
                "avg_price": o["avg"], "message": "", "raw_status": o["status"], "trigger": o["trigger"]}

    async def cancel_order(self, handle, oid):
        o = self.orders[oid]
        self.cancel_calls = getattr(self, "cancel_calls", 0) + 1
        if getattr(self, "ignore_cancels", 0) > 0:
            self.ignore_cancels -= 1           # simulate a cancel that doesn't land
            return {"stat": "Ok"}
        if o["status"] == "open":
            o["status"] = "cancelled"
        return {"stat": "Ok"}

    def partial(self, oid, qty):
        o = self.orders[oid]
        o.update(filled=qty, avg=self.ltp[o["sym"]])
        sign = -1 if o["side"].upper().startswith("S") else 1
        self.net[o["sym"]] = self.net.get(o["sym"], 0) + sign * qty

    async def net_position(self, handle, key):
        _, _, sym = ks.parse_instrument_key(key)
        n = self.net.get(sym, 0)
        found = sym in self.net and sym not in getattr(self, "hidden", set())
        return {"net_qty": n, "buy_price": 0.0, "sell_price": 0.0, "realised": None, "found": found}

    async def get_ltp(self, handle, key):
        return self.ltp[ks.parse_instrument_key(key)[2]]

    # market data
    async def expiries(self, handle, underlying, exchange, instrument_type="option"):
        assert (underlying, exchange) == ("CRUDEOILM", "mcx_fo")
        return ["2026-10-15", "2026-11-17"] if instrument_type == "option" else ["2026-10-19", "2026-11-19"]

    async def option_chain(self, handle, *, exchange, underlying, expiry=None, instrument_type="option", count=40):
        if instrument_type == "fut":
            return {"fut": [
                {"inst": {"neoSymbol": "mcx_fo|900", "symbol": "CRUDEOILM26OCTFUT", "expiryDt": "19-OCT-2026"},
                 "quote": {"ltp": "6087.00"}},
                {"inst": {"neoSymbol": "mcx_fo|901", "symbol": "CRUDEOILM26NOVFUT", "expiryDt": "19-NOV-2026"},
                 "quote": {"ltp": "6120.00"}}]}
        assert expiry == "2026-10-15"
        rows = {"call": [], "put": [], "common_data": {"mktLot": "1", "multiplier": "10"}}
        for k in (6000, 6050, 6100, 6150):
            for side, opt in (("call", "CE"), ("put", "PE")):
                sym = f"CRUDEOILM26OCT{k}{opt}"
                rows[side].append({"instrument": {"neoSymbol": f"mcx_fo|{k}{opt}", "symbol": sym,
                                                  "optionType": opt, "strikePrice": str(k)},
                                   "quote": {"ltp": str(self.ltp.get(sym, 100.0))}})
        return rows


@pytest.fixture
def env(monkeypatch):
    sess = ks.KotakSession(account_id="accK", access_token="tok", ucc="AB123", auth="A", sid="S",
                           base_url="https://e21.kotaksecurities.com",
                           created_at=datetime.now(IST).isoformat())
    fake = FakeKotak({"CRUDEOILM26OCT6100CE": 152.35, "CRUDEOILM26OCT6100PE": 140.10})
    for name in ("place_order", "order_state", "cancel_order", "net_position", "get_ltp", "expiries", "option_chain"):
        monkeypatch.setattr(ks, name, getattr(fake, name))

    async def ensure(account_id, **k):
        return sess
    monkeypatch.setattr(ks, "ensure_session", ensure)
    monkeypatch.setattr(ks, "cached_session", lambda a: sess)
    monkeypatch.setattr(ks, "mark_login_failed", lambda *a, **k: None)

    store = {"positions": {}, "statuses": {}, "logs": []}
    dep = {"id": "dep1", "userId": "u1", "strategyId": "crude-oil-mini-straddle",
           "strategyCode": "CRUDEOILM_STRADDLE", "brokerAccountId": "accK", "brokerName": "kotak",
           "multiplier": 2, "status": "ready"}
    fb = ex.firebase_service
    monkeypatch.setattr(fb, "list_deployments_by_status", lambda st: [dep] if st == "ready" else [])
    monkeypatch.setattr(fb, "update_user_strategy_status", lambda d, st: store["statuses"].__setitem__(d, st))
    monkeypatch.setattr(fb, "is_paper_trading", lambda: False)
    monkeypatch.setattr(ex, "_accounts_by_id", lambda: {"accK": {"id": "accK", "broker": "kotak", "isConnected": True}})
    monkeypatch.setattr(ex, "_users_by_id", lambda: {"u1": {"paperTrading": False, "username": "client"}})
    ps = ex.position_service

    def create(data):
        pid = f"P{len(store['positions']) + 1}"
        store["positions"][pid] = {**data, "id": pid}
        return pid
    monkeypatch.setattr(ps, "create_position", create)
    monkeypatch.setattr(ps, "update_position", lambda pid, upd: store["positions"][pid].update(upd))
    monkeypatch.setattr(ps, "get_open_positions_for_user_strategy",
                        lambda d, day: [p for p in store["positions"].values() if p["userStrategyId"] == d])
    monkeypatch.setattr(ps, "get_exitable_positions_for_date",
                        lambda day: [dict(p) for p in store["positions"].values() if p["status"] in ("open", "closing")])
    monkeypatch.setattr(ps, "claim_position_for_exit", lambda pid: True)
    monkeypatch.setattr(ps, "get_stale_open_positions", lambda day: [])
    monkeypatch.setattr(ps, "release_position_claim", lambda pid: None)
    monkeypatch.setattr(ex.activity, "log_activity", lambda **k: store["logs"].append(k))
    monkeypatch.setattr(ex, "_refresh_live_feed", lambda: None)
    monkeypatch.setattr(ex, "_stopped_reason", lambda d: None)
    monkeypatch.setattr(settings, "entry_marketdata_lead_seconds", 0)
    monkeypatch.setattr(settings, "mcx_order_wait_seconds", 0.3)
    monkeypatch.setattr(settings, "order_status_timeout_seconds", 0.3)
    monkeypatch.setattr(mcx, "_ist_today", lambda: date(2026, 10, 6))
    return fake, store


def test_kotak_entry_then_exit(env):
    fake, store = env
    now = datetime.now(IST).strftime("%H:%M")
    summary = run(crude_execution.execute_crude_entry(entry=now))
    assert summary["placed"] == 2 and summary["failed"] == 0, (summary, store["logs"][-3:])
    assert summary["atmStrike"] == 6100.0 and summary["expiry"] == "2026-10-15"   # fut 6087 → 6100

    sells = [o for o in fake.orders.values() if o["type"] == "L"]
    sls = [o for o in fake.orders.values() if o["type"] == "SL"]
    assert {o["sym"] for o in sells} == {"CRUDEOILM26OCT6100CE", "CRUDEOILM26OCT6100PE"}
    assert all(o["side"] == "SELL" and o["qty"] == 2 for o in sells)          # 2 lots, mktLot 1
    ce_sl = next(o for o in sls if o["sym"].endswith("CE"))
    assert ce_sl["side"] == "BUY" and ce_sl["trigger"] == 182.9 and ce_sl["price"] == 201.2

    pos = sorted(store["positions"].values(), key=lambda p: p["optionType"])
    assert [p["exchange"] for p in pos] == ["MCX", "MCX"]
    assert pos[0]["pnlMultiplier"] == 10.0 and pos[0]["quantity"] == 2 and pos[0]["entryPrice"] == 152.35
    assert store["statuses"]["dep1"] == "trade_active"

    # 23:24 — premiums decayed; exit cancels SLs and buys back.
    fake.ltp.update({"CRUDEOILM26OCT6100CE": 120.0, "CRUDEOILM26OCT6100PE": 150.10})
    out = run(crude_execution.execute_crude_exit())
    assert out["closed"] == 2 and out["failed"] == 0
    assert all(o["status"] == "cancelled" for o in fake.orders.values() if o["type"] == "SL")
    assert fake.net == {"CRUDEOILM26OCT6100CE": 0, "CRUDEOILM26OCT6100PE": 0}
    pnl = {p["optionType"]: p["pnl"] for p in store["positions"].values()}
    assert pnl["CE"] == round((152.35 - 120.0) * 2 * 10, 2)      # ₹647.00
    assert pnl["PE"] == round((140.10 - 150.10) * 2 * 10, 2)     # −₹200.00
    assert store["statuses"]["dep1"] == "trade_closed"


def test_resting_limit_is_cancelled_and_repriced(env):
    fake, store = env
    fake.resting_first = 1           # the first SELL rests unfilled → must be cancelled, then re-priced
    now = datetime.now(IST).strftime("%H:%M")
    summary = run(crude_execution.execute_crude_entry(entry=now))
    assert summary["placed"] == 2
    cancelled = [o for o in fake.orders.values() if o["type"] == "L" and o["status"] == "cancelled"]
    assert len(cancelled) == 1
    sells = [o for o in fake.orders.values() if o["type"] == "L" and o["status"] == "complete"]
    assert len(sells) == 2
    assert all(abs(fake.net[s]) == 2 for s in fake.net)   # never double-sold


def test_exit_skips_buy_when_sl_already_filled(env):
    fake, store = env
    now = datetime.now(IST).strftime("%H:%M")
    run(crude_execution.execute_crude_entry(entry=now))
    # CE stop-loss triggers and fills at 185.0
    sl_id = next(i for i, o in fake.orders.items() if o["type"] == "SL" and o["sym"].endswith("CE"))
    fake.ltp["CRUDEOILM26OCT6100CE"] = 185.0
    fake._fill(fake.orders[sl_id])
    n_orders = len(fake.orders)
    out = run(crude_execution.execute_crude_exit())
    assert out["closed"] == 2
    ce = next(p for p in store["positions"].values() if p["optionType"] == "CE")
    assert ce["exitReason"] == "sl_hit" and ce["pnl"] == round((152.35 - 185.0) * 2 * 10, 2)
    # Only ONE new order (the PE buy-back) — no second buy on the stopped-out CE.
    assert len(fake.orders) == n_orders + 1
    assert fake.net["CRUDEOILM26OCT6100CE"] == 0 and fake.net["CRUDEOILM26OCT6100PE"] == 0


def test_login_failure_skips_entry_without_orders(env, monkeypatch):
    fake, store = env

    async def bad(account_id, **k):
        raise ks.KotakLoginError("Kotak rejected the TOTP")
    monkeypatch.setattr(ks, "ensure_session", bad)
    summary = run(crude_execution.execute_crude_entry(entry=datetime.now(IST).strftime("%H:%M")))
    assert summary["placed"] == 0 and not fake.orders
    assert any("Kotak login failed" in l["message"] for l in store["logs"])


def test_partly_filled_stop_then_exit_buys_only_the_rest(env):
    fake, store = env
    run(crude_execution.execute_crude_entry(entry=datetime.now(IST).strftime("%H:%M")))
    sl_id = next(i for i, o in fake.orders.items() if o["type"] == "SL" and o["sym"].endswith("CE"))
    fake.partial(sl_id, 1)                    # stop bought back 1 of the 2 lots, then stalled
    out = run(crude_execution.execute_crude_exit())
    assert out["closed"] == 2 and out["failed"] == 0
    assert fake.orders[sl_id]["status"] == "cancelled"
    buys = [o for o in fake.orders.values() if o["type"] == "L" and o["side"] == "BUY" and o["sym"].endswith("CE")]
    assert [b["qty"] for b in buys] == [1]
    assert fake.net["CRUDEOILM26OCT6100CE"] == 0 and fake.net["CRUDEOILM26OCT6100PE"] == 0


def test_missing_position_row_never_treated_as_flat(env):
    fake, store = env
    run(crude_execution.execute_crude_entry(entry=datetime.now(IST).strftime("%H:%M")))
    fake.hidden = {"CRUDEOILM26OCT6100CE"}
    out = run(crude_execution.execute_crude_exit())
    ce = next(p for p in store["positions"].values() if p["optionType"] == "CE")
    assert out["failed"] == 1 and ce["status"] != "squared_off"
    # stop-loss put back so the short is not naked
    live_sls = [o for o in fake.orders.values() if o["type"] == "SL" and o["sym"].endswith("CE") and o["status"] == "open"]
    assert len(live_sls) == 1
    assert fake.net["CRUDEOILM26OCT6100CE"] == -2


def test_cancel_is_resent_until_order_is_dead(env):
    fake, store = env
    fake.resting_first = 1
    fake.ignore_cancels = 2                   # first two cancels don't land
    summary = run(crude_execution.execute_crude_entry(entry=datetime.now(IST).strftime("%H:%M")))
    assert summary["placed"] == 2
    assert fake.cancel_calls >= 3
    assert all(abs(v) == 2 for v in fake.net.values())   # no duplicate short
