"""
TflStopCoords — fetch all TfL stop coordinates from the Unified API
and export to tbl_coord.csv.

Usage:
    python tfl_stop_coords.py              # fetch all stop types
    python tfl_stop_coords.py --metro      # metro + rail only

The TfL Unified API does not require authentication for read-only requests,
but an app_key query parameter raises the rate limit substantially.
Set TFL_APP_KEY in your environment (optional).

Output: tbl_coord.csv  (same directory as this script)
Columns: naptanid, stopType, commonName, line, lat, lon
"""

import csv
import os
import time
import urllib.parse
import urllib.request
import json
from pathlib import Path

TFL_BASE    = "https://api.tfl.gov.uk"
OUTPUT_PATH = Path(__file__).parent / "tbl_coord.csv"
APP_KEY     = os.getenv("TFL_APP_KEY", "")

# Stop types to fetch — covers all modes relevant to transit analysis.
# Remove bus/coach types if you only want rail/metro.
ALL_STOP_TYPES = [
    "NaptanMetroStation",
    "NaptanRailStation",
    "NaptanPublicBusCoachTram",
    "NaptanOnstreetBusCoachStopPair",
    "NaptanOnstreetBusCoachStopCluster",
    "NaptanBusCoachStation",
    "NaptanFerryPort",
    "NaptanFerryBerth",
    "NaptanMetroPlatform",
    "NaptanCoachBay",
    "NaptanRailAccessArea",
]

METRO_RAIL_TYPES = [
    "NaptanMetroStation",
    "NaptanRailStation",
]


class TflStopCoords:
    """Fetch stop coordinates from the TfL StopPoint API and write to CSV."""

    PAGE_SIZE = 1000  # max allowed by the API

    def __init__(self, app_key: str = APP_KEY):
        self.app_key = app_key

    def _get(self, path: str, params: dict) -> dict:
        if self.app_key:
            params["app_key"] = self.app_key
        url = f"{TFL_BASE}{path}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())

    def _fetch_stop_type(self, stop_type: str) -> list[dict]:
        """Paginate through all stops of a given stopType."""
        rows = []
        page = 1
        while True:
            data = self._get(
                "/StopPoint",
                {"stopTypes": stop_type, "page": page},
            )
            stops = data.get("stopPoints", [])
            if not stops:
                break
            for s in stops:
                rows.append({
                    "naptanid":   s.get("naptanId", ""),
                    "stopType":   s.get("stopType", stop_type),
                    "commonName": s.get("commonName", ""),
                    "line":       1,
                    "lat":        s.get("lat", 0.0),
                    "lon":        s.get("lon", 0.0),
                })
            total = data.get("total", len(stops))
            print(f"  {stop_type}: page {page} — {len(rows)}/{total}")
            if len(rows) >= total:
                break
            page += 1
            time.sleep(0.3)  # be polite
        return rows

    def fetch(self, stop_types: list[str] | None = None) -> list[dict]:
        """Fetch all stops of the given types (defaults to all types)."""
        types = stop_types or ALL_STOP_TYPES
        all_rows: list[dict] = []
        for st in types:
            rows = self._fetch_stop_type(st)
            all_rows.extend(rows)
            print(f"  → {len(rows)} stops fetched for {st}")
        return all_rows

    def save(self, rows: list[dict], path: Path = OUTPUT_PATH) -> None:
        """Write rows to CSV, overwriting any existing file."""
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["naptanid", "stopType", "commonName", "line", "lat", "lon"]
            )
            writer.writeheader()
            writer.writerows(rows)
        print(f"Saved {len(rows):,} rows → {path}")

    def update(
        self,
        stop_types: list[str] | None = None,
        path: Path = OUTPUT_PATH,
    ) -> None:
        """Fetch and save in one call."""
        rows = self.fetch(stop_types)
        self.save(rows, path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Refresh tbl_coord.csv from TfL API")
    parser.add_argument(
        "--metro", action="store_true",
        help="Fetch metro + rail stations only (faster)"
    )
    args = parser.parse_args()

    client = TflStopCoords()
    types  = METRO_RAIL_TYPES if args.metro else None
    client.update(stop_types=types)
