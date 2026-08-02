"""Seasonality computation engine.

Workflow:
1. Download raw 1-min CSV bytes from Google Drive.
2. Parse into a pandas DataFrame.
3. Resample to daily / weekly / monthly OHLCV.
4. Compute per-period returns for each year.
5. Aggregate statistics (avg, σ, positive-probability, streaks).
6. Write results to Firestore under ``seasonalityResults``.
7. Derive upcoming trades from the cached stats.
"""
from __future__ import annotations

import io
import logging
from datetime import date, datetime, timedelta
from typing import Any, Literal, Optional

import numpy as np
import pandas as pd
import pytz

logger = logging.getLogger("tradzo.seasonality")

IST = pytz.timezone("Asia/Kolkata")

# ── Column name aliases that the CSV might use ────────────────────────────────
_COL_MAP = {
    "datetime": "date",
    "timestamp": "date",
    "time": "date",
    "date": "date",
    "tradedate": "date",
    "trade_date": "date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume",
    "vol": "volume",
    "shares_traded": "volume",
}

ViewMode = Literal["daily", "weekly", "monthly"]
YEAR_OPTIONS = {5, 10, 15, 20, 25}


# ── CSV parsing ───────────────────────────────────────────────────────────────

def parse_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Parse a raw OHLCV CSV (1-min or 1-day timeframe) and return a cleaned DataFrame."""
    df = pd.read_csv(io.BytesIO(raw_bytes))
    
    # Normalize column names (lower-case stripped mapping)
    rename_dict = {}
    for col in df.columns:
        col_clean = str(col).strip().lower()
        if col_clean in _COL_MAP:
            rename_dict[col] = _COL_MAP[col_clean]
    df.rename(columns=rename_dict, inplace=True)

    # Ensure required columns exist
    required = {"date", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}. Found columns: {list(df.columns)}")

    # Flexible datetime parsing for ISO, Indian date formats, or timestamps
    df["date"] = pd.to_datetime(df["date"], errors="coerce", format="mixed", utc=False)
    df.dropna(subset=["date"], inplace=True)
    df = df.sort_values("date").reset_index(drop=True)

    # Keep only numeric OHLCV
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(subset=["close"], inplace=True)

    return df


# ── Resampling ────────────────────────────────────────────────────────────────

_RESAMPLE_RULES: dict[ViewMode, str] = {
    "daily":   "D",
    "weekly":  "W-FRI",   # week ending Friday (Indian market convention)
    "monthly": "ME",      # month-end
}

def resample_to_period(df_raw: pd.DataFrame, mode: ViewMode) -> pd.DataFrame:
    """Resample raw OHLCV candles (1-min or 1-day) to daily / weekly / monthly OHLCV.

    Returns a DataFrame indexed by the *period end date* with columns
    [open, high, low, close, volume].
    """
    df = df_raw.set_index("date")
    rule = _RESAMPLE_RULES[mode]

    agg = df.resample(rule).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum") if "volume" in df.columns else ("close", "count"),
    ).dropna(subset=["close"])

    return agg.reset_index().rename(columns={"date": "period_end"})


# ── Period label helpers ──────────────────────────────────────────────────────

def _period_label(ts: pd.Timestamp, mode: ViewMode) -> str:
    """Human-readable column label for a period end timestamp."""
    if mode == "monthly":
        return ts.strftime("%b")          # Jan, Feb, …
    elif mode == "weekly":
        return f"W{ts.isocalendar().week:02d}"
    else:
        return ts.strftime("%d-%b")       # 01-Jan, …


def _period_sort_key(label: str, mode: ViewMode) -> int:
    """Integer sort key so columns render chronologically."""
    if mode == "monthly":
        months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]
        return months.index(label) if label in months else 999
    elif mode == "weekly":
        return int(label[1:]) if label.startswith("W") else 999
    else:
        try:
            return int(label.split("-")[0])
        except Exception:
            return 999


# ── Core computation ──────────────────────────────────────────────────────────

def compute_returns_grid(
    df_period: pd.DataFrame,
    mode: ViewMode,
    years: int | str = "max",
) -> dict[str, Any]:
    """
    Build the seasonality grid.

    Returns
    -------
    {
        "grid":  {year_str: {period_label: return_pct | None}},
        "stats": {period_label: {avg, sigma, pos_prob, neg_prob, count, streak}},
        "year_totals": {year_str: total_return_pct | None},
        "periods_ordered": [label, ...],  # chronologically sorted
    }
    """
    df = df_period.copy()
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["year"] = df["period_end"].dt.year
    df["label"] = df["period_end"].apply(lambda t: _period_label(t, mode))

    # Compute period return: (close - open) / open * 100
    if "open" in df.columns and (df["open"] > 0).any():
        df["return_pct"] = ((df["close"] - df["open"]) / df["open"]) * 100
    else:
        df["return_pct"] = df["close"].pct_change() * 100

    # Filter to requested years
    if years != "max" and isinstance(years, int):
        cutoff_year = datetime.now().year - years
        df = df[df["year"] > cutoff_year]

    all_years = sorted(df["year"].unique())
    all_labels_raw = df[["label", "period_end"]].drop_duplicates()
    periods_ordered = (
        all_labels_raw
        .groupby("label")["period_end"]
        .min()
        .reset_index()
        .sort_values("period_end")["label"]
        .tolist()
    )

    # Build grid
    grid: dict[str, dict[str, Any]] = {}
    year_totals: dict[str, Any] = {}

    for yr in all_years:
        yr_str = str(yr)
        yr_df = df[df["year"] == yr]
        grid[yr_str] = {}
        for lbl in periods_ordered:
            row = yr_df[yr_df["label"] == lbl]
            if row.empty or pd.isna(row.iloc[0]["return_pct"]):
                grid[yr_str][lbl] = None
            else:
                grid[yr_str][lbl] = round(float(row.iloc[0]["return_pct"]), 2)

        # Year total = compounded return
        yr_close = yr_df["close"].dropna()
        if len(yr_close) >= 2:
            total = (yr_close.iloc[-1] / yr_close.iloc[0] - 1) * 100
            year_totals[yr_str] = round(float(total), 2)
        else:
            year_totals[yr_str] = None

    # Build per-period stats
    stats: dict[str, dict[str, Any]] = {}
    for lbl in periods_ordered:
        values = [
            grid[yr][lbl]
            for yr in [str(y) for y in all_years]
            if grid[yr].get(lbl) is not None
        ]
        if not values:
            stats[lbl] = {
                "avg": None, "sigma": None,
                "pos_prob": None, "neg_prob": None,
                "posProb": None, "negProb": None,
                "count": 0, "streak": 0,
            }
            continue

        arr = np.array(values, dtype=float)
        pos = int(np.sum(arr > 0))
        neg = int(np.sum(arr < 0))
        count = len(arr)

        # Streak: consecutive +/- at the tail of the sorted year list
        recent = [
            grid[str(y)][lbl]
            for y in all_years
            if grid[str(y)].get(lbl) is not None
        ]
        streak = _compute_streak(recent)

        pos_p = round(pos / count * 100, 1)
        neg_p = round(neg / count * 100, 1)

        stats[lbl] = {
            "avg":      round(float(np.mean(arr)), 2),
            "sigma":    round(float(np.std(arr)), 2),
            "pos_prob": pos_p,
            "neg_prob": neg_p,
            "posProb":  pos_p,
            "negProb":  neg_p,
            "count":    count,
            "streak":   streak,
        }

    return {
        "grid": grid,
        "stats": stats,
        "year_totals": year_totals,
        "periods_ordered": periods_ordered,
        "years": [str(y) for y in all_years],
    }


def _compute_streak(values: list[float | None]) -> int:
    """Return the length of the current streak of same-sign returns at the tail.

    Positive streak = positive integer, negative = negative integer, 0 = mixed.
    """
    filtered = [v for v in values if v is not None]
    if not filtered:
        return 0
    sign = 1 if filtered[-1] > 0 else (-1 if filtered[-1] < 0 else 0)
    if sign == 0:
        return 0
    count = 0
    for v in reversed(filtered):
        if (v > 0 and sign == 1) or (v < 0 and sign == -1):
            count += 1
        else:
            break
    return count * sign


# ── Upcoming trades ───────────────────────────────────────────────────────────

def get_upcoming_trades(
    cached_results: list[dict],
    probability_threshold: float,
    lookahead_days: int = 30,
) -> list[dict]:
    """
    From a list of cached seasonality result dicts (as stored in Firestore),
    derive trades whose next occurrence falls within *lookahead_days* and whose
    positive probability meets the threshold.

    Returns a list of trade dicts sorted by entry date ascending.
    """
    today = date.today()
    cutoff = today + timedelta(days=lookahead_days)
    trades = []

    for result in cached_results:
        symbol = result.get("symbol", "")
        mode: ViewMode = result.get("viewMode", "monthly")
        stats: dict = result.get("stats", {})

        for label, s in stats.items():
            pos_prob = s.get("pos_prob") or 0.0
            if pos_prob < probability_threshold:
                continue

            entry, exit_ = _next_occurrence(label, mode, today)
            if entry is None or entry > cutoff:
                continue

            days_away = (entry - today).days
            trades.append({
                "symbol": symbol,
                "viewMode": mode,
                "period": label,
                "entryDate": entry.isoformat(),
                "exitDate": exit_.isoformat() if exit_ else None,
                "direction": "BULL" if (s.get("avg") or 0) >= 0 else "BEAR",
                "posProb": pos_prob,
                "negProb": s.get("neg_prob"),
                "avgReturn": s.get("avg"),
                "sigma": s.get("sigma"),
                "streak": s.get("streak"),
                "daysAway": days_away,
            })

    trades.sort(key=lambda t: t["daysAway"])
    return trades


def _next_occurrence(label: str, mode: ViewMode, from_date: date) -> tuple[Optional[date], Optional[date]]:
    """Return (entry_date, exit_date) for the next occurrence of *label* from *from_date*."""
    year = from_date.year

    if mode == "monthly":
        months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]
        if label not in months:
            return None, None
        m = months.index(label) + 1
        # Try this calendar year, then next
        for yr in (year, year + 1):
            try:
                entry = date(yr, m, 1)
                # Exit = last day of that month
                if m == 12:
                    exit_ = date(yr, 12, 31)
                else:
                    exit_ = date(yr, m + 1, 1) - timedelta(days=1)
                if exit_ >= from_date:
                    return entry, exit_
            except ValueError:
                continue
        return None, None

    elif mode == "weekly":
        try:
            week_num = int(label[1:])
        except (ValueError, IndexError):
            return None, None
        for yr in (year, year + 1):
            for day_offset in range(365):
                d = date(yr, 1, 1) + timedelta(days=day_offset)
                if d.isocalendar().week == week_num:
                    # Week starts Monday, ends Friday
                    monday = d - timedelta(days=d.weekday())
                    friday = monday + timedelta(days=4)
                    if friday >= from_date:
                        return monday, friday
                    break
        return None, None

    else:  # daily
        # For daily, just use upcoming trading days — not trivial without a calendar.
        # Return (today, today) as a placeholder if label matches today.
        return None, None


# ── Firestore caching ─────────────────────────────────────────────────────────

def _doc_id(symbol: str, mode: ViewMode, years: int | str) -> str:
    return f"{symbol.upper()}_{mode}_{years}"


def save_result_to_firestore(
    symbol: str,
    mode: ViewMode,
    years: int | str,
    result: dict,
) -> None:
    """Write a computed seasonality result to Firestore."""
    from services.firebase_service import get_db
    db = get_db()
    doc_id = _doc_id(symbol, mode, years)
    payload = {
        "symbol": symbol.upper(),
        "viewMode": mode,
        "years": years,
        "computedAt": datetime.now(IST),
        **result,
    }
    db.collection("seasonalityResults").document(doc_id).set(payload)
    logger.info("Saved seasonality result for %s (%s / %s).", symbol, mode, years)


def load_result_from_firestore(
    symbol: str,
    mode: ViewMode,
    years: int | str,
) -> Optional[dict]:
    """Fetch a cached result from Firestore, or None if not found."""
    from services.firebase_service import get_db
    db = get_db()
    doc_id = _doc_id(symbol, mode, years)
    snap = db.collection("seasonalityResults").document(doc_id).get()
    if not snap.exists:
        return None
    return {"id": snap.id, **snap.to_dict()}


def load_all_results_from_firestore(
    symbols: list[str] | None = None,
    mode: ViewMode | None = None,
    years: int | str | None = None,
) -> list[dict]:
    """Fetch cached results, optionally filtered by symbol / mode / years."""
    from services.firebase_service import get_db

    db = get_db()
    query = db.collection("seasonalityResults")

    if mode:
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = query.where(filter=FieldFilter("viewMode", "==", mode))

    docs = query.stream()
    results = []
    symbol_set = {s.upper() for s in symbols} if symbols else None
    years_str = str(years) if years is not None else None

    for d in docs:
        data = {"id": d.id, **d.to_dict()}
        sym = data.get("symbol")
        doc_years = str(data.get("years")) if data.get("years") is not None else None

        if symbol_set and sym not in symbol_set:
            continue
        if years_str is not None and doc_years != years_str:
            continue

        results.append(data)
    return results


# ── Admin: full compute-and-cache pipeline ────────────────────────────────────

def compute_and_cache_stock(
    symbol: str,
    modes: list[ViewMode],
    year_ranges: list[int | str],
    progress_callback=None,
    data_url: Optional[str] = None,
) -> dict[str, int]:
    """
    Download the stock's CSV in-memory from Drive / URL, resample, compute for all requested
    mode × year combinations, and write each result to Firestore.

    Returns a summary dict ``{combo_key: "ok" | "error_message"}``.
    """
    from services import gdrive_service

    summary: dict[str, str] = {}

    try:
        raw_bytes = gdrive_service.download_stock_file(symbol, data_url=data_url)
        df_1min = parse_csv(raw_bytes)
    except Exception as exc:
        logger.error("Failed to load CSV for %s: %s", symbol, exc)
        for mode in modes:
            for yr in year_ranges:
                summary[f"{symbol}_{mode}_{yr}"] = f"CSV error: {exc}"
        return summary

    for mode in modes:
        try:
            df_period = resample_to_period(df_1min, mode)
        except Exception as exc:
            logger.error("Resample failed for %s / %s: %s", symbol, mode, exc)
            for yr in year_ranges:
                summary[f"{symbol}_{mode}_{yr}"] = f"Resample error: {exc}"
            continue

        for yr in year_ranges:
            key = f"{symbol}_{mode}_{yr}"
            try:
                result = compute_returns_grid(df_period, mode, yr)
                save_result_to_firestore(symbol, mode, yr, result)
                summary[key] = "ok"
                if progress_callback:
                    progress_callback(symbol, mode, yr, "ok")
            except Exception as exc:
                logger.error("Compute failed for %s: %s", key, exc)
                summary[key] = str(exc)
                if progress_callback:
                    progress_callback(symbol, mode, yr, str(exc))

    return summary


def compute_and_cache_all(
    modes: list[ViewMode],
    year_ranges: list[int | str],
    progress_callback=None,
) -> dict[str, Any]:
    """
    Admin-triggered: compute seasonality for all stocks in the Firestore
    ``seasonalityStocks`` collection and cache results.

    Returns a full summary keyed by symbol.
    """
    from services.firebase_service import get_db

    db = get_db()
    stock_docs = list(db.collection("seasonalityStocks").stream())

    if not stock_docs:
        logger.warning("No stocks found in seasonalityStocks collection.")
        return {"error": "No stocks configured."}

    all_summary: dict[str, Any] = {}
    for doc in stock_docs:
        symbol = doc.id
        data = doc.to_dict()
        data_url = data.get("dataUrl")
        logger.info("Computing seasonality for %s (in-memory) …", symbol)
        all_summary[symbol] = compute_and_cache_stock(
            symbol, modes, year_ranges, progress_callback, data_url=data_url
        )

    logger.info("Compute-all complete. %d stocks processed.", len(stock_docs))
    return all_summary


def compute_single_stock_seasonality(
    symbol: str,
    mode: ViewMode,
    years: int | str,
) -> Optional[dict]:
    """
    Compute seasonality for a single stock on-the-fly, save to Firestore cache, and return result.
    Does NOT save CSV files locally.
    """
    from services import gdrive_service, firebase_service

    sym = symbol.upper()
    try:
        # Fetch registered dataUrl if present in Firestore
        data_url: Optional[str] = None
        try:
            db = firebase_service.get_db()
            doc_snap = db.collection("seasonalityStocks").document(sym).get()
            if doc_snap.exists:
                data_url = doc_snap.to_dict().get("dataUrl")
        except Exception:
            pass

        raw_bytes = gdrive_service.download_stock_file(sym, data_url=data_url)
        df_1min = parse_csv(raw_bytes)
        df_period = resample_to_period(df_1min, mode)
        grid_result = compute_returns_grid(df_period, mode, years)

        doc_payload = {
            "symbol": sym,
            "viewMode": mode,
            "years": years,
            "computedAt": datetime.now(IST),
            **grid_result,
        }
        save_result_to_firestore(sym, mode, years, grid_result)
        doc_payload["id"] = _doc_id(sym, mode, years)
        return doc_payload
    except Exception as exc:
        logger.error("Failed on-the-fly compute for %s (%s / %s): %s", sym, mode, years, exc)
        return None
