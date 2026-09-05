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


def _period_sort_key(label: str, mode: ViewMode) -> tuple[int, int] | int:
    """Sort key so periods order chronologically (01 Jan to 31 Dec, Jan to Dec, W01 to W53)."""
    if mode == "monthly":
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        return months.index(label) if label in months else 999
    elif mode == "weekly":
        try:
            return int(label[1:]) if label.startswith("W") else 999
        except Exception:
            return 999
    else:  # daily ("DD-MMM")
        months_map = {"Jan":1, "Feb":2, "Mar":3, "Apr":4, "May":5, "Jun":6, "Jul":7, "Aug":8, "Sep":9, "Oct":10, "Nov":11, "Dec":12}
        try:
            parts = label.split("-")
            return (months_map.get(parts[1], 99), int(parts[0]))
        except Exception:
            return (99, 99)


# ── Core computation ──────────────────────────────────────────────────────────

def compute_returns_grid(
    df_period: pd.DataFrame,
    mode: ViewMode,
    years: int | str = "max",
    return_basis: str = "open",
) -> dict[str, Any]:
    """
    Build the seasonality grid.

    Parameters
    ----------
    return_basis : "open" | "prev_close"
        "open"       — (close - open) / open * 100  [intraday basis, default]
        "prev_close" — (close - prev_close) / prev_close * 100  [carry basis]

    Returns
    -------
    {
        "grid":  {year_str: {period_label: return_pct | None}},
        "stats": {period_label: {avg, sigma, pos_prob, neg_prob, count, streak}},
        "year_totals": {year_str: total_return_pct | None},
        "periods_ordered": [label, ...],  # chronologically sorted from Jan to Dec
        "return_basis": "open" | "prev_close",
    }
    """
    df = df_period.copy()
    df["period_end"] = pd.to_datetime(df["period_end"])
    df["year"] = df["period_end"].dt.year
    df["label"] = df["period_end"].apply(lambda t: _period_label(t, mode))

    # Compute period return based on selected basis
    if return_basis == "prev_close":
        # Carry basis: change relative to previous period's close
        df["return_pct"] = df["close"].pct_change() * 100
    elif "open" in df.columns and (df["open"] > 0).any():
        # Intraday basis: change from open to close within the same period
        df["return_pct"] = ((df["close"] - df["open"]) / df["open"]) * 100
    else:
        df["return_pct"] = df["close"].pct_change() * 100

    # Filter to requested years
    if years != "max" and isinstance(years, int):
        cutoff_year = datetime.now().year - years
        df = df[df["year"] > cutoff_year]

    all_years = sorted(df["year"].unique())

    # Build canonical periods_ordered (01 Jan -> 31 Dec, Jan -> Dec, W01 -> W53)
    unique_labels = list(df["label"].unique())
    periods_ordered = sorted(unique_labels, key=lambda lbl: _period_sort_key(lbl, mode))

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

        # Year total = compounded return of valid period returns in that year
        yr_returns = yr_df["return_pct"].dropna().tolist()
        if yr_returns:
            compounded = 1.0
            for r in yr_returns:
                compounded *= (1.0 + r / 100.0)
            year_totals[yr_str] = round((compounded - 1.0) * 100.0, 2)
        else:
            year_totals[yr_str] = None

    # Build per-period stats
    stats: dict[str, dict[str, Any]] = {}
    for lbl in periods_ordered:
        raw_values = [
            grid[yr][lbl]
            for yr in [str(y) for y in all_years]
            if grid[yr].get(lbl) is not None
        ]
        # Exclude 0.0% (untraded / flat holiday periods) so probability is based only on traded years
        values = [v for v in raw_values if v != 0.0]

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

        recent = [
            grid[str(y)][lbl]
            for y in all_years
            if grid[str(y)].get(lbl) is not None and grid[str(y)].get(lbl) != 0.0
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
        "return_basis": return_basis,
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
    avg_return_threshold: float = 0.0,
    direction_filter: str = "ALL",
    min_years_traded: Optional[int | str] = None,
) -> list[dict]:
    """
    From a list of cached seasonality result dicts (as stored in Firestore),
    derive upcoming BULL and BEAR trades.

    A period is surfaced as:
    - BULL trade: pos_prob >= probability_threshold
    - BEAR trade: neg_prob >= probability_threshold

    Additional filters:
    - avg_return_threshold: minimum |avg return| % (e.g. 0.5 means |avg| >= 0.5%)
    - direction_filter: "ALL" | "BULL" | "BEAR"
    - min_years_traded: minimum count of traded years (5, 10, 15, 20, 25, or 'max')

    Returns a list of trade dicts sorted by entry date ascending.
    """
    today = date.today()
    cutoff = today + timedelta(days=lookahead_days)
    trades = []
    seen_keys: set[str] = set()

    for result in cached_results:
        symbol = result.get("symbol", "")
        mode: ViewMode = result.get("viewMode", "monthly")
        stats: dict = result.get("stats", {})

        for label, s in stats.items():
            pos_prob = s.get("pos_prob") or 0.0
            neg_prob = s.get("neg_prob") or 0.0
            avg_return = s.get("avg") or 0.0
            traded_count = s.get("count") or s.get("traded_count") or 0

            # Fallback: compute traded count from grid if missing in stats dict
            if not traded_count and "grid" in result:
                grid_dict = result.get("grid") or {}
                traded_count = sum(
                    1 for yr_data in grid_dict.values()
                    if isinstance(yr_data, dict) and yr_data.get(label) is not None and yr_data.get(label) != 0.0
                )

            # Filter by min years traded
            if min_years_traded is not None and min_years_traded != "max" and min_years_traded != 0:
                try:
                    min_c = int(min_years_traded)
                    if traded_count < min_c:
                        continue
                except (ValueError, TypeError):
                    pass

            # Determine direction
            is_bull = pos_prob >= probability_threshold
            is_bear = neg_prob >= probability_threshold

            if not is_bull and not is_bear:
                continue

            # If both satisfy (rare), pick the dominant direction
            direction = "BULL" if pos_prob >= neg_prob else "BEAR"

            # Apply direction filter
            if direction_filter != "ALL" and direction != direction_filter:
                continue

            # Apply |avg return| filter
            if abs(avg_return) < avg_return_threshold:
                continue

            entry, exit_ = _next_occurrence(label, mode, today)
            if entry is None or exit_ is None:
                continue

            # Calculate days away (0 if trade is active now)
            days_away = max(0, (entry - today).days)

            # Skip if trade entry is beyond lookahead window
            if entry > cutoff:
                continue

            # Deduplicate
            key = f"{symbol}_{label}_{direction}"
            if key in seen_keys:
                continue
            seen_keys.add(key)

            trades.append({
                "symbol": symbol,
                "viewMode": mode,
                "period": label,
                "entryDate": entry.isoformat(),
                "exitDate": exit_.isoformat() if exit_ else None,
                "direction": direction,
                "posProb": pos_prob,
                "negProb": neg_prob,
                "avgReturn": avg_return,
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
        for yr in (year, year + 1):
            try:
                entry = date(yr, m, 1)
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
            try:
                monday = date.fromisocalendar(yr, week_num, 1)
                friday = date.fromisocalendar(yr, week_num, 5)
                if friday >= from_date:
                    return monday, friday
            except ValueError:
                continue
        return None, None

    else:  # daily ("DD-MMM")
        months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"]
        try:
            parts = label.split("-")
            day = int(parts[0])
            month_str = parts[1]
            if month_str not in months:
                return None, None
            m = months.index(month_str) + 1
        except Exception:
            return None, None

        for yr in (year, year + 1):
            try:
                d = date(yr, m, day)
                if d >= from_date:
                    return d, d
            except ValueError:
                continue
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
        "computedAt": datetime.now(IST),
        **result,
        # IMPORTANT: must come AFTER **result — compute_returns_grid also returns a
        # key called "years" (list of actual year strings) which would otherwise
        # overwrite the range label ("max", 10, 5 …) we want stored here.
        "years": years,
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
    """Fetch cached results, optionally filtered by symbol / mode / years.

    Note: `retry=None` is intentional — it disables the built-in Firestore
    retry logic which triggers an `AttributeError` on newer grpc versions
    when a query times out (grpc._channel._UnaryStreamMultiCallable has no
    attribute '_retry').  We handle retries / errors at the call-site instead.
    """
    from services.firebase_service import get_db

    db = get_db()
    query = db.collection("seasonalityResults")

    if mode:
        from google.cloud.firestore_v1.base_query import FieldFilter
        query = query.where(filter=FieldFilter("viewMode", "==", mode))

    # retry=None prevents the broken retry path that causes AttributeError on
    # newer grpc versions; timeout=120 gives the query a reasonable deadline.
    try:
        docs = query.stream(retry=None, timeout=120)
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
    except Exception as exc:
        import logging as _logging
        _logging.getLogger(__name__).error(
            "load_all_results_from_firestore failed (mode=%s): %s", mode, exc
        )
        raise RuntimeError(
            f"Firestore query timed out or failed while loading seasonality results "
            f"(mode={mode!r}). Add a composite index on 'viewMode' in Firestore or "
            f"reduce collection size. Original error: {exc}"
        ) from exc


# ── Year range priority helper ─────────────────────────────────────────────────

_YEAR_PRIORITY = {"max": 9999, "25": 25, "20": 20, "15": 15, "10": 10, "5": 5}


def _year_priority(years_val: Any) -> int:
    """Return a numeric priority for a year range. 'max' wins, then highest number.

    Handles legacy Firestore docs where 'years' was accidentally stored as a list
    of actual year strings (e.g. ['2005', ..., '2026']) instead of the range label
    ('max', '10', …) due to a dict-spread ordering bug in save_result_to_firestore.
    In that case we use the list length as a priority proxy — more years = higher
    priority, which correctly picks the max-range doc over smaller ranges.
    """
    if isinstance(years_val, list):
        return len(years_val)   # e.g. 22 for max-range doc, 10 for 10-year doc
    return _YEAR_PRIORITY.get(str(years_val), 0)


def _date_to_daily_label(d: date) -> str:
    """Convert a date to a daily period label like '12-Aug'."""
    return d.strftime("%-d-%b") if hasattr(d, "strftime") else d.strftime("%d-%b").lstrip("0") or "0"


def scan_trades_by_date(
    target_date: date,
    probability_threshold: float = 60.0,
    avg_return_threshold: float = 0.0,
    min_years_traded: Optional[int | str] = None,
    direction_filter: str = "ALL",
    cached_daily_results: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Scan ALL cached daily seasonality results in Firestore for a given target date.

    For each stock:
    - Picks the cached result with the highest year range (max > 25 > 20 > 15 > 10 > 5).
    - Looks up stats for the label matching target_date (e.g. '12-Aug').
    - Applies probability, avg_return, min_years, and direction filters.

    Parameters
    ----------
    cached_daily_results : already-fetched daily-mode result dicts, if the caller
        has them (e.g. it just checked for missing symbols). Avoids re-running the
        same Firestore query the caller already did. Pass None to have this
        function fetch them itself.

    Returns a list of trade signal dicts sorted by dominant probability descending.
    """
    from services.firebase_service import get_db
    from google.cloud.firestore_v1.base_query import FieldFilter

    if cached_daily_results is None:
        db = get_db()
        docs = db.collection("seasonalityResults").where(
            filter=FieldFilter("viewMode", "==", "daily")
        ).stream(retry=None, timeout=120)
        cached_daily_results = [{"id": d.id, **d.to_dict()} for d in docs]

    # Group best result per symbol (highest year range wins)
    best_per_symbol: dict[str, dict] = {}
    for data in cached_daily_results:
        sym = data.get("symbol", "")
        if not sym:
            continue
        existing = best_per_symbol.get(sym)
        if existing is None or _year_priority(data.get("years")) > _year_priority(existing.get("years")):
            best_per_symbol[sym] = data

    # Convert date to label — try zero-padded and non-padded
    label_padded = target_date.strftime("%d-%b")           # "12-Aug"
    label_unpadded = str(target_date.day) + "-" + target_date.strftime("%b")  # "12-Aug" (same for day >=10)

    no_label = prob_fail = dir_fail = avg_fail = min_years_fail = 0

    results = []
    for sym, result in best_per_symbol.items():
        stats: dict = result.get("stats") or {}

        # Derive the year-range label reliably from the doc ID (e.g. "JPPOWER_daily_max" → "max")
        # For legacy docs the "years" field is a list, not the range label.
        _doc_id_str = result.get("id", "")
        _year_range_label = _doc_id_str.rsplit("_", 1)[-1] if "_" in _doc_id_str else str(result.get("years", ""))

        # Try both label formats — use explicit None check, NOT `or`,
        # because an empty dict {} is falsy and would wrongly skip real entries.
        s = stats.get(label_padded)
        if s is None:
            s = stats.get(label_unpadded)
        if s is None:
            no_label += 1
            continue

        # Use explicit None guards — `or 0.0` would convert a stored None to 0.0
        # and then the avg_return filter (|avg| < threshold) would silently drop
        # stocks that simply have no historical data for this exact date.
        _pos = s.get("pos_prob") if s.get("pos_prob") is not None else s.get("posProb")
        _neg = s.get("neg_prob") if s.get("neg_prob") is not None else s.get("negProb")
        pos_prob:    float = float(_pos) if _pos is not None else 0.0
        neg_prob:    float = float(_neg) if _neg is not None else 0.0
        _avg = s.get("avg")
        avg_return:  float = float(_avg) if _avg is not None else 0.0
        sigma  = s.get("sigma")
        streak = s.get("streak")
        _cnt = s.get("count")
        traded_count: int = int(_cnt) if _cnt is not None else 0

        # Fallback: compute traded count from grid if missing in stats
        if not traded_count and "grid" in result:
            grid_dict = result.get("grid") or {}
            first_yr_keys = list(next(iter(grid_dict.values()), {}).keys()) if grid_dict else []
            label_to_use = label_padded if label_padded in first_yr_keys else label_unpadded
            traded_count = sum(
                1 for yr_data in grid_dict.values()
                if isinstance(yr_data, dict)
                and yr_data.get(label_to_use) is not None
                and yr_data.get(label_to_use) != 0.0
            )

        # Min years traded filter
        if min_years_traded is not None and min_years_traded != "max" and min_years_traded != 0:
            try:
                min_c = int(min_years_traded)
                if traded_count < min_c:
                    min_years_fail += 1
                    continue
            except (ValueError, TypeError):
                pass

        # Must pass probability threshold for at least one direction
        is_bull = pos_prob >= probability_threshold
        is_bear = neg_prob >= probability_threshold
        if not is_bull and not is_bear:
            prob_fail += 1
            continue

        # Determine dominant direction
        direction = "BULL" if pos_prob >= neg_prob else "BEAR"

        # Direction filter
        if direction_filter != "ALL" and direction != direction_filter:
            dir_fail += 1
            continue

        # Avg return filter — only apply when avg is actually available (not None/0)
        if avg_return_threshold > 0 and _avg is not None and abs(avg_return) < avg_return_threshold:
            avg_fail += 1
            continue

        results.append({
            "symbol": sym,
            "displayName": None,   # filled below from stocks collection
            "label": label_padded,
            "direction": direction,
            "posProb": pos_prob,
            "negProb": neg_prob,
            "avgReturn": avg_return,
            "sigma": sigma,
            "streak": streak,
            "count": traded_count,
            "yearRange": _year_range_label,
        })

    logger.info(
        "Trade scanner [%s] label='%s': %d symbols checked → %d passed | "
        "dropped: no_label=%d, min_years=%d, prob=%d, direction=%d, avg=%d",
        target_date, label_padded, len(best_per_symbol), len(results),
        no_label, min_years_fail, prob_fail, dir_fail, avg_fail,
    )

    # Fetch display names in one shot
    try:
        db2 = get_db()
        stock_docs = db2.collection("seasonalityStocks").stream()
        display_names = {d.id: d.to_dict().get("displayName") for d in stock_docs}
        for r in results:
            r["displayName"] = display_names.get(r["symbol"])
    except Exception:
        pass

    # Sort: BULL by posProb desc, BEAR by negProb desc, overall dominant prob desc
    results.sort(key=lambda r: max(r["posProb"], r["negProb"]), reverse=True)
    return results


# ── Admin: full compute-and-cache pipeline ────────────────────────────────────

def compute_and_cache_stock(
    symbol: str,
    modes: list[ViewMode],
    year_ranges: list[int | str],
    progress_callback=None,
    data_url: Optional[str] = None,
    return_basis: str = "open",
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
                result = compute_returns_grid(df_period, mode, yr, return_basis=return_basis)
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
    return_basis: str = "open",
    save_to_cache: bool = True,
) -> Optional[dict]:
    """
    Compute seasonality for a single stock on-the-fly, optionally save to Firestore cache,
    and return result.

    Parameters
    ----------
    save_to_cache : bool
        If True (default), writes the result to ``seasonalityResults`` in Firestore.
        Pass False when computing in-memory only (e.g. ``prev_close`` for predefined scans)
        so the existing ``open``-basis cached doc is not overwritten.
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
        grid_result = compute_returns_grid(df_period, mode, years, return_basis=return_basis)

        doc_payload = {
            "symbol": sym,
            "viewMode": mode,
            "years": years,
            "computedAt": datetime.now(IST),
            **grid_result,
        }
        if save_to_cache:
            save_result_to_firestore(sym, mode, years, grid_result)
        doc_payload["id"] = _doc_id(sym, mode, years)
        return doc_payload
    except Exception as exc:
        logger.error("Failed on-the-fly compute for %s (%s / %s): %s", sym, mode, years, exc)
        return None


# ── Predefined daily scans ────────────────────────────────────────────────────

# The four predefined scan configurations shown in the Trade Scanner UI.
# Each is a fixed combination of filters that runs automatically every day.
PREDEFINED_SCAN_CONFIGS: list[dict] = [
    {"id": "open_10",       "return_basis": "open",       "min_years": 10, "probability": 75.0, "avg_return": 1.0},
    {"id": "prev_close_10", "return_basis": "prev_close", "min_years": 10, "probability": 75.0, "avg_return": 1.0},
    {"id": "open_5",        "return_basis": "open",       "min_years": 5,  "probability": 75.0, "avg_return": 1.0},
    {"id": "prev_close_5",  "return_basis": "prev_close", "min_years": 5,  "probability": 75.0, "avg_return": 1.0},
]


def compute_predefined_scans_for_date(
    target_date: date,
    open_basis_results: list[dict],
) -> dict[str, list[dict]]:
    """
    Compute all predefined scan result sets for a given date in one pass.

    Strategy
    --------
    * ``open`` basis presets: use the already-loaded ``open_basis_results`` (no Drive downloads).
    * ``prev_close`` basis presets: compute each stock in parallel from raw Drive data
      with ``save_to_cache=False`` so the existing ``open``-basis ``seasonalityResults``
      docs are NOT overwritten.  The final filtered signals land in ``dailyScans/{date}``
      which is the cache layer for predefined scans.

    Parameters
    ----------
    target_date       : The calendar date to scan.
    open_basis_results: Already-loaded and up-to-date ``open``-basis daily results
                        (the caller is responsible for ensuring these are fresh).

    Returns
    -------
    dict keyed by preset ID → list of trade signal dicts.
    """
    import concurrent.futures

    # ── Collect all symbols present in the open-basis results ────────────────
    all_symbols = list({r.get("symbol") for r in open_basis_results if r.get("symbol")})

    # ── Compute prev_close results in parallel (Drive downloads, no cache write) ─
    logger.info(
        "Predefined scans [%s]: computing prev_close for %d symbols in parallel",
        target_date, len(all_symbols),
    )
    prev_close_results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, max(len(all_symbols), 1))) as pool:
        futures_map = {
            pool.submit(
                compute_single_stock_seasonality,
                sym, "daily", "max",
                return_basis="prev_close",
                save_to_cache=False,   # keep seasonalityResults at open-basis
            ): sym
            for sym in all_symbols
        }
        for future in concurrent.futures.as_completed(futures_map):
            sym = futures_map[future]
            try:
                result = future.result()
                if result:
                    prev_close_results.append(result)
            except Exception:
                logger.exception("Predefined scans: prev_close compute failed for %s", sym)

    logger.info(
        "Predefined scans [%s]: prev_close computed for %d / %d symbols",
        target_date, len(prev_close_results), len(all_symbols),
    )

    # ── Apply all 4 filter combos ─────────────────────────────────────────────
    output: dict[str, list[dict]] = {}
    basis_results = {
        "open":       open_basis_results,
        "prev_close": prev_close_results,
    }

    for cfg in PREDEFINED_SCAN_CONFIGS:
        source = basis_results[cfg["return_basis"]]
        signals = scan_trades_by_date(
            target_date=target_date,
            probability_threshold=cfg["probability"],
            avg_return_threshold=cfg["avg_return"],
            min_years_traded=cfg["min_years"],
            direction_filter="ALL",
            cached_daily_results=source,
        )
        output[cfg["id"]] = signals
        logger.info(
            "Predefined scans [%s]: %s → %d signals",
            target_date, cfg["id"], len(signals),
        )

    return output
