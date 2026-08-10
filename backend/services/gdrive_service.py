"""Stock file storage service — handles public Google Drive folder auto-sync, public URLs,
local CSV file uploads, and disk caching under backend/data/seasonality_stocks/.

Does NOT require a Google Service Account!
"""
import io
import logging
import os
import re
from typing import Any, Optional

import requests

logger = logging.getLogger("tradzo.gdrive")

DEFAULT_PUBLIC_FOLDER_ID = "1QYm76CRM1F3qTWCZWUVE4lu7Alefu_nP"
DEFAULT_PUBLIC_FOLDER_URL = f"https://drive.google.com/drive/folders/{DEFAULT_PUBLIC_FOLDER_ID}"

# Store files in backend/data/seasonality_stocks/
STORAGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "seasonality_stocks",
)
os.makedirs(STORAGE_DIR, exist_ok=True)


def _get_local_file_path(symbol: str) -> str:
    """Return primary local file path for symbol."""
    sym = symbol.upper()
    return os.path.join(STORAGE_DIR, f"{sym}_1min.csv")


def extract_gdrive_file_id(url_or_id: str) -> str:
    """Extract Google Drive file ID from shared link or return as-is."""
    match = re.search(r"(?:file/d/|id=)([\w-]+)", url_or_id)
    if match:
        return match.group(1).split("-0-")[0]
    return url_or_id.strip().split("-0-")[0]


def scrape_public_drive_folder(folder_url_or_id: str = DEFAULT_PUBLIC_FOLDER_ID) -> dict[str, dict[str, str]]:
    """
    Scrape a public Google Drive folder page and return a dict mapping:
    SYMBOL -> {"symbol": SYMBOL, "filename": filename, "file_id": file_id, "download_url": url}

    Uses Google Drive API v3 if GOOGLE_API_KEY is configured in backend/config.py or .env (supports up to 1000+ files per page).
    Otherwise, uses multi-sort sweep scanning on public HTML pages to discover all files.
    """
    if "drive.google.com" in folder_url_or_id:
        match = re.search(r"folders/([\w-]+)", folder_url_or_id)
        folder_id = match.group(1) if match else folder_url_or_id
    else:
        folder_id = folder_url_or_id.strip()

    from config import settings
    api_key = (settings.google_api_key or os.getenv("GOOGLE_API_KEY", "")).strip()
    results = {}

    # Method 1: Direct Google Drive API v3 (if GOOGLE_API_KEY is provided in .env)
    if api_key:
        try:
            session = requests.Session()
            page_token = None
            while True:
                params = {
                    "q": f"'{folder_id}' in parents and trashed = false",
                    "fields": "nextPageToken, files(id, name)",
                    "pageSize": 1000,
                    "key": api_key,
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = session.get("https://www.googleapis.com/drive/v3/files", params=params, timeout=30)
                if resp.status_code == 200:
                    data = resp.json()
                    for f in data.get("files", []):
                        fname = f.get("name", "")
                        if fname.lower().endswith(".csv"):
                            clean_fid = f.get("id")
                            symbol = fname.replace(".csv", "").strip().upper()
                            results[symbol] = {
                                "symbol": symbol,
                                "filename": fname,
                                "file_id": clean_fid,
                                "download_url": f"https://docs.google.com/uc?export=download&id={clean_fid}",
                            }
                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break
                else:
                    logger.warning("Google Drive API v3 returned status %d", resp.status_code)
                    break
            if results:
                logger.info("Fetched %d files from Google Drive API v3.", len(results))
                return results
        except Exception as exc:
            logger.warning("Google Drive API v3 query failed: %s. Falling back to multi-sort scraping.", exc)

    # Method 2: Multi-sort web scraping sweep across sorting rules
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )

    sort_rules = [
        (13, 1), (13, 2),  # Name A-Z, Z-A
        (7, 1), (7, 2),    # Date Modified ASC, DESC
        (10, 1), (10, 2),  # Size ASC, DESC
        (1, 1), (1, 2),
        (2, 1), (2, 2),
        (3, 1), (3, 2),
        (4, 1), (4, 2),
        (5, 1), (5, 2),
        (6, 1), (6, 2),
        (8, 1), (8, 2),
        (9, 1), (9, 2),
        (11, 1), (11, 2),
        (12, 1), (12, 2),
        (19, 1), (19, 2),
    ]

    for s, d in sort_rules:
        url = f"https://drive.google.com/drive/folders/{folder_id}?sort={s}&direction={d}"
        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                continue
            text = resp.text

            matches = re.findall(r'aria-label="([\w\.-]+\.csv)[^"]*"\s+[^>]*ssk=\'\d+:\w+:([\w-]+)', text)
            if not matches:
                matches = re.findall(r'ssk=\'\d+:\w+:([\w-]+)[^\']*\'[^>]*aria-label="([\w\.-]+\.csv)', text)
                matches = [(m[1], m[0]) for m in matches]

            dt_matches = re.findall(r'data-id="([a-zA-Z0-9_-]{25,45})"[^>]*data-tooltip="([^"]+\.csv)', text)
            for fid, fname in dt_matches:
                matches.append((fname, fid))

            for fname, raw_file_id in matches:
                clean_file_id = raw_file_id.split("-0-")[0] if "-0-" in raw_file_id else raw_file_id
                symbol = fname.replace(".csv", "").strip().upper()
                if symbol not in results:
                    results[symbol] = {
                        "symbol": symbol,
                        "filename": fname,
                        "file_id": clean_file_id,
                        "download_url": f"https://docs.google.com/uc?export=download&id={clean_file_id}",
                    }
        except Exception as exc:
            logger.warning("Error fetching folder sort=%d&direction=%d: %s", s, d, exc)

    logger.info("Scraped %d files from public Google Drive folder using multi-sort sweep.", len(results))
    return results


def download_public_url(url: str) -> bytes:
    """Download file content from a public Google Drive share URL or direct HTTP/S link."""
    url = url.strip()
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    )

    if "drive.google.com" in url or "docs.google.com" in url or re.search(r"file/d/|id=", url):
        file_id = extract_gdrive_file_id(url)
        download_url = f"https://docs.google.com/uc?export=download&id={file_id}"
        resp = session.get(download_url, stream=True, timeout=60)

        for key, val in resp.cookies.items():
            if key.startswith("download_warning"):
                confirm_url = f"{download_url}&confirm={val}"
                resp = session.get(confirm_url, stream=True, timeout=60)
                break
    else:
        resp = session.get(url, stream=True, timeout=60)

    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code} download error for URL: {url}")

    if not resp.content:
        raise RuntimeError("Downloaded file content is empty.")

    return resp.content


def purge_local_disk_cache() -> int:
    """Remove any cached CSV files from local storage directory."""
    removed_count = 0
    if os.path.exists(STORAGE_DIR):
        for fname in os.listdir(STORAGE_DIR):
            if fname.endswith(".csv"):
                try:
                    os.remove(os.path.join(STORAGE_DIR, fname))
                    removed_count += 1
                except Exception as exc:
                    logger.warning("Could not delete local cached file %s: %s", fname, exc)
    if removed_count > 0:
        logger.info("Purged %d cached CSV files from local disk storage.", removed_count)
    return removed_count


def upload_stock_file(symbol: str, file_bytes: bytes, mime_type: str = "text/csv") -> dict[str, Any]:
    """In-memory handler: Returns byte size and symbol without writing to local disk."""
    sym = symbol.upper()
    logger.info("Processed %d bytes for symbol %s in-memory (no local disk save).", len(file_bytes), sym)
    return {"symbol": sym, "size_bytes": len(file_bytes)}


def download_and_save_public_url(symbol: str, data_url: str) -> int:
    """Download CSV from a public URL directly into memory and verify byte length."""
    content = download_public_url(data_url)
    return len(content)


def download_stock_file(symbol: str, data_url: Optional[str] = None) -> bytes:
    """
    Return raw CSV bytes for *symbol* entirely in-memory over HTTP.
    Does NOT save files to local disk.
    Checks provided data_url or scrapes the public Google Drive folder index.
    """
    sym = symbol.upper()

    # 1. Direct URL download if provided
    if data_url and data_url.strip():
        try:
            return download_public_url(data_url.strip())
        except Exception as exc:
            logger.warning("Could not download %s from registered URL %s: %s", sym, data_url, exc)

    # 2. Try downloading automatically from the public Google Drive folder index
    try:
        folder_files = scrape_public_drive_folder(DEFAULT_PUBLIC_FOLDER_ID)
        if sym in folder_files:
            download_url = folder_files[sym]["download_url"]
            return download_public_url(download_url)
    except Exception as exc:
        logger.warning("Could not auto-download %s from Drive folder: %s", sym, exc)

    # 3. Fallback check for legacy file on disk if present
    primary = os.path.join(STORAGE_DIR, f"{sym}_1min.csv")
    secondary = os.path.join(STORAGE_DIR, f"{sym}.csv")
    for path in (primary, secondary):
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()

    raise FileNotFoundError(f"No CSV data found for stock '{sym}'.")


def delete_stock_file(symbol: str) -> bool:
    """Delete local CSV file for *symbol* if present."""
    sym = symbol.upper()
    deleted = False
    for fname in (f"{sym}_1min.csv", f"{sym}.csv"):
        path = os.path.join(STORAGE_DIR, fname)
        if os.path.exists(path):
            try:
                os.remove(path)
                deleted = True
            except Exception:
                pass
    return deleted


def get_file_info(symbol: str) -> Optional[dict]:
    """Return file status for *symbol* based on Google Drive folder index or URL availability."""
    sym = symbol.upper()
    try:
        folder_files = scrape_public_drive_folder(DEFAULT_PUBLIC_FOLDER_ID)
        if sym in folder_files:
            return {
                "symbol": sym,
                "file_id": folder_files[sym]["file_id"],
                "modified": "Drive Live Stream",
                "size_bytes": 0,
            }
    except Exception:
        pass
    return None


def list_stock_files() -> list[dict]:
    """Return a list of stock info dicts for all available files in Google Drive folder."""
    results = []
    try:
        folder_files = scrape_public_drive_folder(DEFAULT_PUBLIC_FOLDER_ID)
        for sym, d in folder_files.items():
            results.append({
                "symbol": sym,
                "file_id": d["file_id"],
                "modified": "Drive Live Stream",
                "size_bytes": 0,
            })
    except Exception as exc:
        logger.warning("Could not list Google Drive stock files: %s", exc)
    return results
