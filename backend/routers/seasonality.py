"""Seasonality analysis router.

User endpoints (auth-only via Firebase ID token in Authorization header):
  GET  /seasonality/stocks                — list managed stocks
  GET  /seasonality/results               — fetch cached analysis results
  GET  /seasonality/upcoming-trades       — upcoming high-probability trades

Admin endpoints (admin claim required):
  POST   /seasonality/admin/stocks        — add a new stock
  POST   /seasonality/admin/upload        — upload 1-min CSV to Drive
  DELETE /seasonality/admin/stocks/{sym}  — remove a stock
  POST   /seasonality/admin/run-analysis  — trigger full compute + cache
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from models.seasonality import (
    AddStockRequest,
    AnalysisRunSummary,
    RunAnalysisRequest,
    StockInfo,
    UpcomingTradesRequest,
)
from services import firebase_service, gdrive_service, seasonality_service
from utils.auth import get_current_user, get_current_admin

logger = logging.getLogger("tradzo.seasonality_router")

router = APIRouter(prefix="/seasonality", tags=["Seasonality"])


# ── Auth helpers ───────────────────────────────────────────────────────────────

def _require_admin(admin: dict = Depends(get_current_admin)) -> dict:
    """Dependency: raises 403 if the user is not an admin or superuser."""
    return admin


# ── User endpoints ─────────────────────────────────────────────────────────────

@router.get("/stocks", summary="List all managed stocks")
def list_stocks(user: dict = Depends(get_current_user)) -> list[StockInfo]:
    """
    Return all stocks registered in ``seasonalityStocks`` with Drive file status.
    Uses Firestore-stored dataUrl as the source of truth for file presence
    (avoids slow Drive scrape on every page load).
    """
    db = firebase_service.get_db()
    docs = db.collection("seasonalityStocks").stream()

    stocks: list[StockInfo] = []
    for d in docs:
        data = d.to_dict()
        sym = d.id
        data_url = data.get("dataUrl") or ""
        # A stock has a file if it has a registered dataUrl (set during sync/import)
        has_file = bool(data_url.strip())
        last_analysis = data.get("lastAnalysisAt")
        stocks.append(
            StockInfo(
                symbol=sym,
                display_name=data.get("displayName"),
                data_url=data_url or None,
                drive_file_present=has_file,
                drive_file_size_bytes=None,
                drive_file_modified=None,
                last_analysis_at=str(last_analysis) if last_analysis else None,
                added_at=str(data.get("addedAt")) if data.get("addedAt") else None,
                added_by=data.get("addedBy"),
            )
        )

    return stocks


@router.get("/results", summary="Fetch seasonality results (computes on-the-fly if missing)")
def get_results(
    symbols: Optional[str] = None,      # comma-separated
    view_mode: Optional[str] = None,
    years: Optional[str] = None,
    return_basis: Optional[str] = "open",
    user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Return seasonality results from Firestore. If any requested combination is missing from cache,
    compute it on-the-fly, store it in cache, and return.
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",")] if symbols else None
    yr: Any = None
    if years:
        yr = int(years) if years.isdigit() else years  # "max" or int

    mode = view_mode if view_mode in ("daily", "weekly", "monthly") else "monthly"
    requested_years = yr if yr is not None else 10
    basis = return_basis if return_basis in ("open", "prev_close") else "open"

    # If no specific symbols provided, get all stocks registered in Firestore
    if not symbol_list:
        db = firebase_service.get_db()
        stock_docs = db.collection("seasonalityStocks").stream()
        symbol_list = [d.id for d in stock_docs]

    results = seasonality_service.load_all_results_from_firestore(
        symbols=symbol_list,
        mode=mode,  # type: ignore[arg-type]
        years=requested_years,
    )

    cached_symbols = {r.get("symbol") for r in results if r.get("symbol")}
    missing_symbols = [s for s in symbol_list if s not in cached_symbols]

    if missing_symbols:
        logger.info("Computing on-the-fly for missing symbols: %s (%s / %s)", missing_symbols, mode, requested_years)
        for sym in missing_symbols:
            computed = seasonality_service.compute_single_stock_seasonality(sym, mode, requested_years, return_basis=basis)  # type: ignore[arg-type]
            if computed:
                results.append(computed)

    return results


@router.post("/upcoming-trades", summary="Get upcoming high-probability trades")
def upcoming_trades(
    body: UpcomingTradesRequest,
    user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    Derive upcoming trades from seasonality analysis.
    Surfaces both BULL and BEAR trades. Computes on-the-fly if missing from cache.
    """
    symbol_list = [s.upper() for s in body.symbols] if body.symbols else None
    yr: Any = body.years
    mode = body.view_mode if body.view_mode in ("daily", "weekly", "monthly") else "monthly"
    requested_years = yr if yr is not None else 10
    basis = body.return_basis if body.return_basis in ("open", "prev_close") else "open"

    if not symbol_list:
        db = firebase_service.get_db()
        stock_docs = db.collection("seasonalityStocks").stream()
        symbol_list = [d.id for d in stock_docs]

    cached = seasonality_service.load_all_results_from_firestore(
        symbols=symbol_list,
        mode=mode,  # type: ignore[arg-type]
        years=requested_years,
    )

    cached_symbols = {r.get("symbol") for r in cached if r.get("symbol")}
    missing_symbols = [s for s in symbol_list if s not in cached_symbols]

    if missing_symbols:
        for sym in missing_symbols:
            computed = seasonality_service.compute_single_stock_seasonality(sym, mode, requested_years, return_basis=basis)  # type: ignore[arg-type]
            if computed:
                cached.append(computed)

    trades = seasonality_service.get_upcoming_trades(
        cached_results=cached,
        probability_threshold=body.probability_threshold,
        lookahead_days=body.lookahead_days,
        avg_return_threshold=body.avg_return_threshold,
        direction_filter=body.direction_filter,
    )
    return trades


# ── Admin endpoints ────────────────────────────────────────────────────────────

@router.post("/admin/stocks", summary="Add a new stock to the watchlist")
async def add_stock(
    body: AddStockRequest,
    admin: dict = Depends(_require_admin),
) -> dict[str, Any]:
    """Register a new stock. If data_url is supplied, downloads the CSV immediately."""
    from datetime import datetime
    import pytz

    db = firebase_service.get_db()
    sym = body.symbol.upper()
    doc_ref = db.collection("seasonalityStocks").document(sym)
    snap = doc_ref.get()
    if snap.exists:
        raise HTTPException(status_code=409, detail=f"Stock '{sym}' already exists.")

    download_bytes = 0
    if body.data_url and body.data_url.strip():
        try:
            download_bytes = gdrive_service.download_and_save_public_url(sym, body.data_url.strip())
        except Exception as exc:
            logger.error("Failed to download public URL for %s: %s", sym, exc)
            raise HTTPException(status_code=400, detail=f"Could not download file from URL: {exc}") from exc

    doc_ref.set(
        {
            "symbol": sym,
            "displayName": body.display_name or sym,
            "dataUrl": body.data_url.strip() if body.data_url else None,
            "addedAt": datetime.now(pytz.timezone("Asia/Kolkata")),
            "addedBy": admin.get("uid"),
            "lastAnalysisAt": None,
        }
    )
    logger.info("Admin %s added stock %s (URL downloaded: %d bytes).", admin.get("uid"), sym, download_bytes)
    return {"symbol": sym, "status": "created", "downloaded_bytes": download_bytes}


@router.post("/admin/sync-drive-folder", summary="Sync all stocks from public Google Drive folder")
async def sync_drive_folder(
    folder_url: Optional[str] = Form(None),
    admin: dict = Depends(_require_admin),
) -> dict[str, Any]:
    """
    Scrape and auto-register/sync all {SYMBOL}.csv files from Google Drive folder.
    Default folder: https://drive.google.com/drive/folders/1QYm76CRM1F3qTWCZWUVE4lu7Alefu_nP
    """
    target_folder = folder_url.strip() if folder_url and folder_url.strip() else gdrive_service.DEFAULT_PUBLIC_FOLDER_ID
    try:
        folder_files = gdrive_service.scrape_public_drive_folder(target_folder)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to scrape Google Drive folder: {exc}") from exc

    from datetime import datetime
    import pytz

    db = firebase_service.get_db()
    now = datetime.now(pytz.timezone("Asia/Kolkata"))

    added_count = 0
    updated_count = 0

    for sym, meta in folder_files.items():
        doc_ref = db.collection("seasonalityStocks").document(sym)
        snap = doc_ref.get()
        data_url = meta["download_url"]

        if not snap.exists:
            doc_ref.set(
                {
                    "symbol": sym,
                    "displayName": sym,
                    "dataUrl": data_url,
                    "addedAt": now,
                    "addedBy": admin.get("uid"),
                    "lastAnalysisAt": None,
                }
            )
            added_count += 1
        else:
            doc_ref.update({"dataUrl": data_url})
            updated_count += 1

    return {
        "status": "success",
        "total_files_found": len(folder_files),
        "stocks_added": added_count,
        "stocks_updated": updated_count,
        "symbols": sorted(list(folder_files.keys())),
    }


@router.post("/admin/sync-nifty500", summary="Import and register all Nifty 500 stocks from ind_nifty500list.csv")
async def sync_nifty500_list(
    admin: dict = Depends(_require_admin),
) -> dict[str, Any]:
    """
    Import all 500+ stocks from ind_nifty500list.csv into seasonalityStocks.
    Automatically links company names, industries, and matching Google Drive URLs.
    """
    import csv
    import os
    from datetime import datetime
    import pytz

    # Scrape current available Drive folder files
    folder_files = {}
    try:
        folder_files = gdrive_service.scrape_public_drive_folder()
    except Exception as exc:
        logger.warning("Could not scrape Drive folder during Nifty 500 import: %s", exc)

    # __file__ = backend/routers/seasonality.py → dirname×3 = Tradzo root
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "ind_nifty500list.csv"
    )
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail=f"ind_nifty500list.csv not found at: {csv_path}")

    db = firebase_service.get_db()
    now = datetime.now(pytz.timezone("Asia/Kolkata"))

    added_count = 0
    updated_count = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sym = row.get("Symbol", "").strip().upper()
            company_name = row.get("Company Name", "").strip() or sym
            industry = row.get("Industry", "").strip()

            if not sym:
                continue

            doc_ref = db.collection("seasonalityStocks").document(sym)
            snap = doc_ref.get()

            # Check if matching Drive file URL exists
            drive_meta = folder_files.get(sym)
            data_url = drive_meta["download_url"] if drive_meta else None

            payload = {
                "symbol": sym,
                "displayName": company_name,
                "industry": industry,
                "addedBy": admin.get("uid"),
            }
            if data_url:
                payload["dataUrl"] = data_url

            if not snap.exists:
                payload["addedAt"] = now
                payload["lastAnalysisAt"] = None
                doc_ref.set(payload)
                added_count += 1
            else:
                doc_ref.update(payload)
                updated_count += 1

    return {
        "status": "success",
        "stocks_added": added_count,
        "stocks_updated": updated_count,
        "total_drive_files_matched": len([s for s in folder_files if s in folder_files]),
    }


@router.post("/admin/upload", summary="Upload CSV file or download from URL")
async def upload_stock_file(
    symbol: str = Form(...),
    file: Optional[UploadFile] = File(None),
    data_url: Optional[str] = Form(None),
    admin: dict = Depends(_require_admin),
) -> dict[str, Any]:
    """
    Save 1-min OHLCV CSV for *symbol* via direct file upload OR public Google Drive/HTTP link.
    """
    sym = symbol.upper()
    size_bytes = 0

    if data_url and data_url.strip():
        try:
            size_bytes = gdrive_service.download_and_save_public_url(sym, data_url.strip())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Download failed from URL: {exc}") from exc
    elif file:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")
        gdrive_service.upload_stock_file(sym, content)
        size_bytes = len(content)
    else:
        raise HTTPException(status_code=400, detail="Provide either a CSV file upload or a public URL.")

    # Ensure Firestore record exists/updates
    from datetime import datetime
    import pytz

    db = firebase_service.get_db()
    doc_ref = db.collection("seasonalityStocks").document(sym)
    snap = doc_ref.get()
    update_data = {}
    if data_url:
        update_data["dataUrl"] = data_url.strip()

    if snap.exists:
        if update_data:
            doc_ref.update(update_data)
    else:
        doc_ref.set(
            {
                "symbol": sym,
                "displayName": sym,
                "dataUrl": data_url.strip() if data_url else None,
                "addedAt": datetime.now(pytz.timezone("Asia/Kolkata")),
                "addedBy": admin.get("uid"),
                "lastAnalysisAt": None,
            }
        )

    logger.info("Admin %s updated data for %s (%d bytes verified in-memory).", admin.get("uid"), sym, size_bytes)
    return {"symbol": sym, "status": "verified", "size_bytes": size_bytes}


@router.delete("/admin/stocks/{symbol}", summary="Remove a stock")
def remove_stock(
    symbol: str,
    admin: dict = Depends(_require_admin),
) -> dict[str, Any]:
    """Delete stock from Firestore and remove its CSV from Drive."""
    sym = symbol.upper()
    db = firebase_service.get_db()

    doc_ref = db.collection("seasonalityStocks").document(sym)
    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail=f"Stock '{sym}' not found.")

    # Best-effort Drive delete
    try:
        gdrive_service.delete_stock_file(sym)
    except Exception as exc:
        logger.warning("Could not delete Drive file for %s: %s", sym, exc)

    doc_ref.delete()

    # Also remove cached analysis results
    results = (
        db.collection("seasonalityResults")
        .where("symbol", "==", sym)
        .stream()
    )
    for r in results:
        r.reference.delete()

    logger.info("Admin %s removed stock %s.", admin.get("uid"), sym)
    return {"symbol": sym, "status": "deleted"}


@router.post("/admin/run-analysis", summary="Trigger full seasonality analysis")
def run_analysis(
    body: RunAnalysisRequest,
    admin: dict = Depends(_require_admin),
) -> AnalysisRunSummary:
    """
    Compute seasonality for **all** stocks in the watchlist for the requested
    view modes and year ranges, then cache results in Firestore.

    This is a synchronous call — for large stock universes it may take a while.
    """
    from datetime import datetime
    import pytz

    year_ranges: list[Any] = []
    for yr in body.year_ranges:
        if yr == "max" or yr == 0:
            year_ranges.append("max")
        else:
            year_ranges.append(int(yr))

    logger.info(
        "Admin %s triggered analysis: modes=%s years=%s",
        admin.get("uid"), body.view_modes, year_ranges,
    )

    summary = seasonality_service.compute_and_cache_all(
        modes=body.view_modes,
        year_ranges=year_ranges,
    )

    # Update lastAnalysisAt on each stock
    db = firebase_service.get_db()
    now = datetime.now(pytz.timezone("Asia/Kolkata"))
    for sym in summary:
        try:
            db.collection("seasonalityStocks").document(sym).update({"lastAnalysisAt": now})
        except Exception:
            pass

    # Flatten summary for response
    total = success = errors = 0
    details: dict[str, Any] = {}
    for sym, combos in summary.items():
        if isinstance(combos, dict):
            for k, v in combos.items():
                total += 1
                if v == "ok":
                    success += 1
                else:
                    errors += 1
                details[k] = v
        else:
            details[sym] = str(combos)

    return AnalysisRunSummary(
        total_combos=total,
        success=success,
        errors=errors,
        details=details,
    )


@router.post("/admin/run-analysis/stream", summary="Trigger full seasonality analysis with SSE progress stream")
async def run_analysis_stream(
    body: RunAnalysisRequest,
    admin: dict = Depends(_require_admin),
):
    """
    Same as run-analysis but streams per-stock JSON progress events via
    Server-Sent Events so the frontend can show a live progress bar.
    Each event is a JSON object on a single line.
    """
    import json
    import asyncio
    from datetime import datetime
    import pytz
    from fastapi.responses import StreamingResponse

    year_ranges: list[Any] = []
    for yr in body.year_ranges:
        if yr == "max" or yr == 0:
            year_ranges.append("max")
        else:
            year_ranges.append(int(yr))

    db = firebase_service.get_db()
    stock_docs = list(db.collection("seasonalityStocks").stream())
    total_stocks = len(stock_docs)
    modes = body.view_modes
    total_combos = total_stocks * len(modes) * len(year_ranges)

    async def event_stream():
        done = 0
        now = datetime.now(pytz.timezone("Asia/Kolkata"))

        # Send initial metadata
        yield json.dumps({"type": "start", "total": total_combos, "total_stocks": total_stocks}) + "\n"
        await asyncio.sleep(0)  # flush

        for doc in stock_docs:
            symbol = doc.id
            data = doc.to_dict()
            data_url = data.get("dataUrl")

            yield json.dumps({"type": "stock_start", "symbol": symbol}) + "\n"
            await asyncio.sleep(0)

            stock_summary = seasonality_service.compute_and_cache_stock(
                symbol, modes, year_ranges, data_url=data_url
            )

            for combo_key, status in stock_summary.items():
                done += 1
                yield json.dumps({"type": "combo", "symbol": symbol, "key": combo_key, "status": status, "done": done, "total": total_combos}) + "\n"
                await asyncio.sleep(0)

            # Update Firestore lastAnalysisAt
            try:
                db.collection("seasonalityStocks").document(symbol).update({"lastAnalysisAt": now})
            except Exception:
                pass

        # Final summary
        yield json.dumps({"type": "done", "done": done, "total": total_combos}) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
