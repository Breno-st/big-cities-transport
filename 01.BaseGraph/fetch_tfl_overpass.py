"""
Fetch TfL tube route relations from the Overpass API and cache to disk.

Uses 'out body geom' so each way member includes its geometry inline and
each stop node member includes its lat/lon — no secondary download needed.

Run once (or re-run to refresh):
    python fetch_tfl_overpass.py
"""

import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')

# Fetch all subway route relations for London Underground.
# 'out body geom' gives us inline way geometry + node lat/lon.
QUERY = """
[out:json][timeout:180];
relation["route"="subway"]["network"="London Underground"];
out body geom;
"""


def main():
    print("Querying Overpass API ...")
    data = urllib.parse.urlencode({'data': QUERY}).encode('utf-8')
    req  = urllib.request.Request(
        'https://overpass-api.de/api/interpreter',
        data=data,
        headers={
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'TfL-map-builder/1.0 (research)',
            'Accept': 'application/json',
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read()

    result = json.loads(raw)

    out_path = BASE / 'overpass_tfl_routes.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f)

    relations = [e for e in result['elements'] if e['type'] == 'relation']
    print(f"Saved {len(result['elements'])} elements ({len(relations)} route relations)")
    for r in sorted(relations, key=lambda x: x['tags'].get('name', '')):
        n_stops = sum(1 for m in r['members'] if m.get('role', '') in ('stop', 'stop_entry_only', 'stop_exit_only', 'platform'))
        n_ways  = sum(1 for m in r['members'] if m['type'] == 'way')
        print(f"  [{r['id']}] {r['tags'].get('name','?'):45s}  stops={n_stops}  ways={n_ways}")
    print(f"\nSaved → {out_path}")


if __name__ == '__main__':
    main()
