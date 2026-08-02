import requests
import re

PUBLIC_FOLDER_ID = "1QYm76CRM1F3qTWCZWUVE4lu7Alefu_nP"

def scrape_public_drive_folder(folder_url_or_id: str = PUBLIC_FOLDER_ID):
    if "drive.google.com" in folder_url_or_id:
        match = re.search(r'folders/([\w-]+)', folder_url_or_id)
        folder_id = match.group(1) if match else folder_url_or_id
    else:
        folder_id = folder_url_or_id.strip()

    url = f"https://drive.google.com/drive/folders/{folder_id}"
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    resp = session.get(url, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Could not load Google Drive folder (HTTP {resp.status_code})")

    text = resp.text
    matches = re.findall(r'aria-label="([\w\.-]+\.csv)[^"]*"\s+[^>]*ssk=\'\d+:\w+:([\w-]+)', text)
    if not matches:
        matches = re.findall(r'ssk=\'\d+:\w+:([\w-]+)[^\']*\'[^>]*aria-label="([\w\.-]+\.csv)', text)
        matches = [(m[1], m[0]) for m in matches]

    results = {}
    for fname, raw_file_id in matches:
        clean_file_id = raw_file_id.split("-0-")[0] if "-0-" in raw_file_id else raw_file_id
        symbol = fname.replace(".csv", "").strip().upper()
        results[symbol] = {
            "symbol": symbol,
            "filename": fname,
            "file_id": clean_file_id,
            "download_url": f"https://docs.google.com/uc?export=download&id={clean_file_id}"
        }
    return results

if __name__ == "__main__":
    folder_data = scrape_public_drive_folder()
    print(f"Scraped {len(folder_data)} files successfully:")
    for sym, d in list(folder_data.items())[:10]:
        print(f"  {sym:12} -> File ID: {d['file_id']} -> URL: {d['download_url']}")
