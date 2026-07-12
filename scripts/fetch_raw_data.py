"""Download the two raw source files this project builds on.

Usage: uv run python scripts/fetch_raw_data.py

Sources (both public, no auth):
- VDOT SYIP "STE VDOT SYIP APPRVD SUM" export, via virginiaroads.org's ArcGIS Hub download
  API. That API generates the export on demand, so this polls until it's ready.
- VDOT Performance Dashboard's Project_Development export, a static direct-download URL.
"""

import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

SYIP_ITEM_ID = "bc064bf0fd9d4cd8a3cde3392faf39ef"
SYIP_URL = f"https://www.virginiaroads.org/api/download/v1/items/{SYIP_ITEM_ID}/csv?layers=0"
DASHBOARD_URL = "https://dashboard.vdot.virginia.gov/s3/P/Dashboard/Project_Export_Dashboard4.xlsx"

POLL_ATTEMPTS = 15
POLL_DELAY_SECONDS = 10


def fetch_syip(dest: Path) -> None:
    # The generation-status response is JSON ({"status": "Pending", ...}); the ready file
    # comes back as application/octet-stream with a UTF-8 BOM prefix before "OBJECTID" —
    # so "not JSON" is the ready signal, not a specific content-type/prefix match.
    for attempt in range(1, POLL_ATTEMPTS + 1):
        response = requests.get(SYIP_URL, timeout=60)
        response.raise_for_status()
        if not response.headers.get("content-type", "").startswith("application/json"):
            dest.write_bytes(response.content)
            print(f"saved {dest} ({len(response.content):,} bytes)")
            return
        print(f"SYIP export still generating (attempt {attempt}/{POLL_ATTEMPTS}), waiting...")
        time.sleep(POLL_DELAY_SECONDS)
    raise TimeoutError("SYIP export did not finish generating in time — try again later")


def fetch_dashboard(dest: Path) -> None:
    response = requests.get(DASHBOARD_URL, timeout=60)
    response.raise_for_status()
    dest.write_bytes(response.content)
    print(f"saved {dest} ({len(response.content):,} bytes)")


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetch_syip(RAW_DIR / "syip_approved_projects.csv")
    fetch_dashboard(RAW_DIR / "vdot_performance_dashboard.xlsx")


if __name__ == "__main__":
    main()
