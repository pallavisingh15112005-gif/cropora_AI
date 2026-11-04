#!/usr/bin/env python3
"""
Fetch the latest mandi prices from the Government of India open data API
(data.gov.in, resource "Current Daily Price of Various Commodities from Various
Markets (Mandi)") and write them to prices.json for the website.

Usage:
    export DATA_GOV_API_KEY="your-key-from-data.gov.in"
    python3 fetch_mandi.py

Run it once a day (cron, GitHub Actions, or Task Scheduler). Agmarknet data
updates once a day, so "real time" here means "latest published", not live ticks.

Field names below follow the Agmarknet resource as commonly documented. Check the
first run's output; if a field is missing, adjust FIELD_MAP.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"
API_URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
PAGE_SIZE = 1000
OUT_FILE = Path(__file__).with_name("prices.json")

# Crops shown on the website: the key is what the site uses, the value is the
# commodity name as Agmarknet spells it.
WANTED = {
    "gehu": "Wheat",
    "chawal": "Rice",
    "sarson": "Mustard",
    "pyaaz": "Onion",
    "aloo": "Potato",
    "tamatar": "Tomato",
    "makka": "Maize",
}

# Keep only these markets so the file stays small. Add more as needed.
WANTED_STATE = os.environ.get("MANDI_STATE", "Uttar Pradesh")

FIELD_MAP = {
    "commodity": "commodity",
    "state": "state",
    "district": "district",
    "market": "market",
    "variety": "variety",
    "date": "arrival_date",
    "modal": "modal_price",
    "min": "min_price",
    "max": "max_price",
}


def fetch_page(api_key: str, offset: int) -> dict:
    params = {
        "api-key": api_key,
        "format": "json",
        "limit": PAGE_SIZE,
        "offset": offset,
        f"filters[state]": WANTED_STATE,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "mandi-bhav-bot/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_all(api_key: str) -> list:
    rows, offset = [], 0
    while True:
        payload = fetch_page(api_key, offset)
        batch = payload.get("records", [])
        rows.extend(batch)
        total = int(payload.get("total", 0) or 0)
        offset += PAGE_SIZE
        if not batch or offset >= total:
            break
    return rows


def to_number(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_output(rows: list) -> dict:
    wanted_names = {v.lower(): k for k, v in WANTED.items()}
    items = []
    for r in rows:
        name = str(r.get(FIELD_MAP["commodity"], "")).strip().lower()
        key = wanted_names.get(name)
        if not key:
            continue
        modal = to_number(r.get(FIELD_MAP["modal"]))
        if modal is None:
            continue
        items.append({
            "crop": key,
            "commodity": r.get(FIELD_MAP["commodity"]),
            "mandi": r.get(FIELD_MAP["market"]),
            "district": r.get(FIELD_MAP["district"]),
            "state": r.get(FIELD_MAP["state"]),
            "date": r.get(FIELD_MAP["date"]),
            "modal": modal,
            "min": to_number(r.get(FIELD_MAP["min"])),
            "max": to_number(r.get(FIELD_MAP["max"])),
        })

    # Keep the most recent date per crop and mandi, plus the previous date for the trend.
    grouped: dict = {}
    for it in items:
        grouped.setdefault((it["crop"], it["mandi"]), []).append(it)

    result = []
    for (crop, mandi), entries in grouped.items():
        entries.sort(key=lambda e: str(e["date"]), reverse=True)
        latest = entries[0]
        prev = entries[1] if len(entries) > 1 else None
        result.append({**latest, "prev_modal": prev["modal"] if prev else None})

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "data.gov.in / Agmarknet",
        "state": WANTED_STATE,
        "items": sorted(result, key=lambda e: (e["crop"], e["mandi"] or "")),
    }


def main() -> int:
    api_key = os.environ.get("DATA_GOV_API_KEY")
    if not api_key:
        print("Set DATA_GOV_API_KEY first. Register at data.gov.in to get one.", file=sys.stderr)
        return 1
    try:
        rows = fetch_all(api_key)
    except Exception as exc:  # network, HTTP, or JSON error
        print(f"Fetch failed: {exc}", file=sys.stderr)
        return 2
    out = build_output(rows)
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(out['items'])} rows from {len(rows)} raw records to {OUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
