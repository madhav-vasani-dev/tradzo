"""MCX market data for the Crude Oil Mini (CRUDEOILM) straddle.

ATM rule: CRUDEOILM options are options on FUTURES, so the ATM strike is the listed strike
nearest the LTP of the futures contract of the same month as the option (never spot).

Contract selection (`crude_min_days_to_expiry`, default 1): trade the nearest option expiry at
least that many calendar days away — with 1 the strategy never sells the contract that expires
today (brokers block NRML entries in expiring MCX options and the legs would devolve into
futures if an exit failed), it rolls to next month on expiry day.

Two sources, same output shape (`snapshot`):
  * Upstox — the public MCX instrument file (Upstox has no MCX option-chain API) + Upstox LTPs
    via the platform market-data account. Used for Upstox, Jainam and paper deployments.
  * Kotak  — Kotak's own expiries / futures-chain / option-chain APIs, authenticated with the
    client's own access token. Kotak deployments therefore don't depend on the Upstox account.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
import threading
from datetime import date, datetime, timedelta

import httpx
import pytz

from config import settings

log = logging.getLogger("tradzo.mcx")
IST = pytz.timezone("Asia/Kolkata")

UNDERLYING = "CRUDEOILM"
KOTAK_SEGMENT = "mcx_fo"
# MCX contract spec: one CRUDEOILM lot = 10 barrels, prices quoted per barrel.
UNITS_PER_LOT = 10


# ── Pure selection helpers (unit-tested) ──────────────────────────────────────

def pick_option_expiry(expiries: list[date], today: date, min_days: int | None = None) -> date:
    if min_days is None:
        min_days = int(getattr(settings, "crude_min_days_to_expiry", 1))
    cands = sorted(e for e in set(expiries) if (e - today).days >= max(0, min_days))
    if not cands:
        raise RuntimeError(f"No {UNDERLYING} option expiry ≥ {min_days} day(s) after {today} "
                           f"(available: {sorted(set(expiries))[:6]})")
    return cands[0]


def pick_future_expiry(fut_expiries: list[date], option_expiry: date) -> date:
    """The futures contract underlying an option: the first futures expiry on/after it."""
    cands = sorted(e for e in set(fut_expiries) if e >= option_expiry)
    if not cands:
        raise RuntimeError(f"No {UNDERLYING} futures expiring on/after option expiry {option_expiry}")
    return cands[0]


def nearest_strike(price: float, strikes: list[float]) -> float:
    if price <= 0:
        raise RuntimeError(f"Invalid {UNDERLYING} futures price {price}")
    if not strikes:
        raise RuntimeError(f"No {UNDERLYING} strikes available")
    return min(strikes, key=lambda k: (abs(k - price), k))


def _ist_today() -> date:
    return datetime.now(IST).date()


def _parse_date(value) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        v = float(value)
        if v > 1e11:            # epoch milliseconds
            v /= 1000.0
        return datetime.fromtimestamp(v, IST).date()
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%B-%Y", "%d %b %Y", "%d%b%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.title() if "%b" in fmt or "%B" in fmt else s, fmt).date()
        except ValueError:
            continue
    return None


def _strike_key(v) -> float:
    return float(round(float(v), 2))


# ── Upstox source ─────────────────────────────────────────────────────────────

_upstox_cache: dict = {"day": None, "rows": None}
_upstox_lock = threading.Lock()


async def _download_upstox_mcx() -> list[dict]:
    url = getattr(settings, "upstox_mcx_instruments_url",
                  "https://assets.upstox.com/market-quote/instruments/exchange/MCX.json.gz")
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise RuntimeError(f"Upstox MCX instrument download failed: HTTP {resp.status_code}")
    raw = resp.content
    try:
        raw = gzip.decompress(raw)
    except OSError:
        pass  # already decompressed by the transport
    data = json.loads(raw)
    rows = []
    for r in data if isinstance(data, list) else []:
        sym = str(r.get("trading_symbol") or "").upper()
        und = str(r.get("underlying_symbol") or r.get("asset_symbol") or "").upper()
        if und != UNDERLYING and not sym.startswith(UNDERLYING + " ") and not sym.startswith(UNDERLYING + "2"):
            continue
        itype = str(r.get("instrument_type") or "").upper()
        if itype not in ("CE", "PE", "FUT", "FUTCOM"):
            continue
        rows.append(r)
    log.info("Upstox MCX instruments: %d %s contracts cached.", len(rows), UNDERLYING)
    return rows


async def upstox_instruments(force: bool = False) -> list[dict]:
    today = _ist_today()
    with _upstox_lock:
        if not force and _upstox_cache["day"] == today and _upstox_cache["rows"]:
            return _upstox_cache["rows"]
    rows = await _download_upstox_mcx()
    if not rows:
        raise RuntimeError(f"Upstox MCX instrument file has no {UNDERLYING} contracts")
    with _upstox_lock:
        _upstox_cache.update(day=today, rows=rows)
    return rows


def _upstox_index(rows: list[dict]) -> tuple[dict, dict]:
    """(options {expiry: {strike: {CE: row, PE: row}}}, futures {expiry: row})."""
    opts: dict[date, dict[float, dict]] = {}
    futs: dict[date, dict] = {}
    for r in rows:
        exp = _parse_date(r.get("expiry"))
        if not exp:
            continue
        itype = str(r.get("instrument_type") or "").upper()
        if itype in ("CE", "PE"):
            opts.setdefault(exp, {}).setdefault(_strike_key(r.get("strike_price") or 0), {})[itype] = r
        else:
            futs[exp] = r
    return opts, futs


async def upstox_snapshot(today: date | None = None) -> dict:
    from services import market_data_service

    today = today or _ist_today()
    rows = await upstox_instruments()
    opts, futs = _upstox_index(rows)
    expiry = pick_option_expiry(list(opts), today)
    fut_exp = pick_future_expiry(list(futs), expiry)
    fut = futs[fut_exp]
    fut_key = fut["instrument_key"]

    ltps = await market_data_service.get_ltps([fut_key])
    fut_price = ltps.get(fut_key, 0.0)
    if fut_price <= 0:
        raise RuntimeError(f"No LTP for {UNDERLYING} futures {fut.get('trading_symbol')} ({fut_key})")

    chain = {k: v for k, v in opts[expiry].items() if "CE" in v and "PE" in v}
    atm = nearest_strike(fut_price, list(chain))
    ce, pe = chain[atm]["CE"], chain[atm]["PE"]
    leg_ltps = await market_data_service.get_ltps([ce["instrument_key"], pe["instrument_key"]])
    snap = {
        "source": "upstox",
        "underlying": UNDERLYING,
        "expiry": expiry.isoformat(),
        "fut_expiry": fut_exp.isoformat(),
        "fut_key": fut_key,
        "fut_symbol": fut.get("trading_symbol"),
        "fut_price": fut_price,
        "atm_strike": atm,
        "ce_key": ce["instrument_key"],
        "pe_key": pe["instrument_key"],
        "ce_symbol": ce.get("trading_symbol"),
        "pe_symbol": pe.get("trading_symbol"),
        "ce_ltp": leg_ltps.get(ce["instrument_key"], 0.0),
        "pe_ltp": leg_ltps.get(pe["instrument_key"], 0.0),
        "lot_size": int(float(ce.get("lot_size") or 0) or 0),
    }
    log.info("CRUDEOILM (Upstox): fut %s=%.2f → ATM %s, option expiry %s, CE %.2f PE %.2f",
             snap["fut_symbol"], fut_price, atm, snap["expiry"], snap["ce_ltp"], snap["pe_ltp"])
    return snap


def upstox_key_for(expiry: str, strike: float, option_type: str) -> str | None:
    """Upstox instrument key for a CRUDEOILM option, from the cached file (no network)."""
    rows = _upstox_cache.get("rows") or []
    if not rows:
        return None
    opts, _ = _upstox_index(rows)
    leg = opts.get(_parse_date(expiry), {}).get(_strike_key(strike), {}).get(option_type.upper())
    return leg.get("instrument_key") if leg else None


# ── Kotak source ──────────────────────────────────────────────────────────────

async def _kotak_future(handle, option_expiry: date) -> tuple[str, str, float, date]:
    """(neoSymbol, trading symbol, LTP, expiry) of the CRUDEOILM future for that month."""
    from services import kotak_service

    chain = await kotak_service.option_chain(handle, exchange=KOTAK_SEGMENT, underlying=UNDERLYING,
                                             instrument_type="fut")
    futs = []
    for f in chain.get("fut") or []:
        inst = f.get("inst") or f.get("instrument") or {}
        exp = _parse_date(inst.get("expiryDt"))
        ltp = kotak_service._num((f.get("quote") or {}).get("ltp"))
        if exp:
            futs.append((exp, str(inst.get("neoSymbol") or ""), str(inst.get("symbol") or ""), ltp))
    if not futs:
        # Fall back to the expiries API + a single-contract futures chain.
        fut_exps = [d for d in (_parse_date(e) for e in await kotak_service.expiries(
            handle, UNDERLYING, KOTAK_SEGMENT, "fut")) if d]
        fexp = pick_future_expiry(fut_exps, option_expiry)
        chain = await kotak_service.option_chain(handle, exchange=KOTAK_SEGMENT, underlying=UNDERLYING,
                                                 instrument_type="fut", expiry=fexp.isoformat())
        for f in chain.get("fut") or []:
            inst = f.get("inst") or f.get("instrument") or {}
            futs.append((fexp, str(inst.get("neoSymbol") or ""), str(inst.get("symbol") or ""),
                         kotak_service._num((f.get("quote") or {}).get("ltp"))))
    fexp = pick_future_expiry([f[0] for f in futs], option_expiry)
    neo, sym, ltp, _ = next((f[1], f[2], f[3], f[0]) for f in futs if f[0] == fexp)
    if ltp <= 0 and neo:
        q = await kotak_service.quotes_ltp(handle, [neo])
        ltp = q.get(neo, 0.0)
    if ltp <= 0:
        raise RuntimeError(f"No LTP for {UNDERLYING} futures {sym or fexp}")
    return neo, sym, ltp, fexp


async def kotak_snapshot(handle, today: date | None = None) -> dict:
    from services import kotak_service

    today = today or _ist_today()
    exps = [d for d in (_parse_date(e) for e in await kotak_service.expiries(
        handle, UNDERLYING, KOTAK_SEGMENT, "option")) if d]
    expiry = pick_option_expiry(exps, today)
    fut_neo, fut_sym, fut_price, fut_exp = await _kotak_future(handle, expiry)

    chain = await kotak_service.option_chain(handle, exchange=KOTAK_SEGMENT, underlying=UNDERLYING,
                                             expiry=expiry.isoformat(), count=40)
    strikes = {k: v for k, v in kotak_service.chain_strikes(chain).items() if "CE" in v and "PE" in v}
    atm = nearest_strike(fut_price, list(strikes))
    lot, mult = kotak_service.chain_lot_info(chain)
    ce, pe = strikes[atm]["CE"], strikes[atm]["PE"]
    snap = {
        "source": "kotak",
        "underlying": UNDERLYING,
        "expiry": expiry.isoformat(),
        "fut_expiry": fut_exp.isoformat(),
        "fut_key": fut_neo,
        "fut_symbol": fut_sym,
        "fut_price": fut_price,
        "atm_strike": atm,
        "ce_key": ce["key"],
        "pe_key": pe["key"],
        "ce_symbol": ce["symbol"],
        "pe_symbol": pe["symbol"],
        "ce_ltp": ce["ltp"],
        "pe_ltp": pe["ltp"],
        "lot_size": lot,
        "multiplier": mult,
    }
    log.info("CRUDEOILM (Kotak): fut %s=%.2f → ATM %s, option expiry %s, CE %s %.2f, PE %s %.2f, "
             "mktLot=%s multiplier=%s", fut_sym, fut_price, atm, snap["expiry"], ce["symbol"], ce["ltp"],
             pe["symbol"], pe["ltp"], lot, mult)
    return snap


def kotak_quantity(lots: int, snap: dict) -> tuple[int, float]:
    """(order quantity, P&L units per quantity) for a Kotak CRUDEOILM order of `lots` lots.

    Kotak expects `qt` in multiples of its market lot. Whether that lot is 1 (quantity in lots,
    price multiplier 10) or 10 (quantity in barrels, multiplier 1), mktLot × multiplier must
    equal the 10-barrel contract — anything else is refused rather than guessed.
    """
    lot = int(snap.get("lot_size") or 0)
    mult = float(snap.get("multiplier") or 1.0)
    if lot <= 0:
        raise RuntimeError("Kotak did not report a market lot for CRUDEOILM — refusing to size the order")
    if lot == 1 and abs(mult - 1.0) < 1e-9:
        # Lot of 1 with no multiplier: quantity is in lots (how Neo takes commodity orders).
        # If Kotak wanted barrels instead, qt=1 is not a lot multiple and is rejected — safe.
        log.warning("Kotak CRUDEOILM chain reports mktLot=1, multiplier=1 — sizing in lots.")
        return int(lots), float(UNITS_PER_LOT)
    if abs(lot * mult - UNITS_PER_LOT) > 1e-6:
        raise RuntimeError(
            f"Unexpected Kotak CRUDEOILM lot data (mktLot={lot}, multiplier={mult}); "
            f"expected mktLot×multiplier = {UNITS_PER_LOT} barrels. Not placing orders."
        )
    return int(lots) * lot, mult
