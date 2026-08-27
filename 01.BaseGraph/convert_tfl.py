"""
Merge per-mode GeoJSON exports from overpass-turbo into tfl_lines.geojson.
One MultiLineString feature per TfL named line, with official colour.

Input files (place alongside this script):
  tube.geojson        — subway ways, network=London Underground
  overground.geojson  — rail ways, operator/network=London Overground
  dlr.geojson         — light_rail ways, DLR
  elizabeth.geojson   — rail ways, line=Elizabeth

Output:
  tfl_lines.geojson   — one feature per line, ready for Mapbox
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import linemerge, unary_union

BASE = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')

# ── Official colours ──────────────────────────────────────────────────────────

COLOURS = {
    # Tube
    'Bakerloo':           '#B36305',
    'Central':            '#E32017',
    'Circle':             '#FFD300',
    'District':           '#00782A',
    'Hammersmith & City': '#F3A9BB',
    'Jubilee':            '#A0A5A9',
    'Metropolitan':       '#9B0056',
    'Northern':           '#000000',
    'Piccadilly':         '#003688',
    'Victoria':           '#0098D4',
    'Waterloo & City':    '#95CDBA',
    # Elizabeth line
    'Elizabeth':          '#6950A1',
    # DLR
    'DLR':                '#00AFAD',
    # Overground brands
    'Lioness':            '#FDB32B',
    'Mildmay':            '#0082C6',
    'Windrush':           '#E61E25',
    'Suffragette':        '#00A650',
    'Weaver':             '#7B2D8B',
    'Liberty':            '#6B717E',
    'Anthem':             '#00AFAD',
}

# Overground OSM ref codes → brand name
OVERGROUND_REF = {
    'BOK1': 'Windrush',   'BOK2': 'Windrush',
    'CWJ':  'Lioness',    # Camden–Watford Junction connector
    'DWW1': 'Mildmay',    'DWW2': 'Mildmay',
    'ELL1': 'Windrush',   'ELL2': 'Windrush',
    'ELL3': 'Windrush',   'ELL4': 'Windrush',
    'GOB1': 'Suffragette','GOB2': 'Suffragette',
    'HBK1': 'Weaver',     'HBK2': 'Weaver',
    'SAR1': 'Mildmay',    # Stratford Avoiding Route (North London line)
    'SEC1': 'Liberty',    'SEC2': 'Liberty',
    'WCL1': 'Lioness',    'WCL2': 'Lioness',
    'ECL1': 'Anthem',     'ECL2': 'Anthem',
}

# Name aliases → canonical
ALIASES = {
    r'Central Line.*':                  'Central',
    r'Piccadilly Line.*':               'Piccadilly',
    r'Victoria Line.*':                 'Victoria',
    r'Jubilee Line.*':                  'Jubilee',
    r'Bakerloo Line.*':                 'Bakerloo',
    r'Metropolitan Line.*':             'Metropolitan',
    r'Northern Line.*':                 'Northern',
    r'Waterloo & City Line.*':          'Waterloo & City',
    r'Hammersmith.*City.*':             'Hammersmith & City',
    r'Circle.*':                        'Circle',
    r'East London line.*':              'Windrush',
    r'Thames Tunnel.*':                 'Windrush',
    r'North London.*':                  'Mildmay',
    r'Watford DC.*':                    'Lioness',
    r'Camden to Watford.*':             'Lioness',
    r'Gospel Oak.*Barking.*':           'Suffragette',
    r'Barking.*Gospel Oak.*':           'Suffragette',
    r'Goblin.*':                        'Suffragette',
    r'Romford.*Upminster.*':            'Liberty',
    r'Upminster.*Romford.*':            'Liberty',
    r'Suffragette.*':                   'Suffragette',
    r'Weaver.*':                        'Weaver',
    r'Liberty.*':                       'Liberty',
    r'Anthem.*':                        'Anthem',
    r'Lioness.*':                       'Lioness',
    r'Mildmay.*':                       'Mildmay',
    r'Windrush.*':                      'Windrush',
    r'DLR.*':                           'DLR',
    r'Docklands Light Railway.*':       'DLR',
    r'Elizabeth.*':                     'Elizabeth',
    r'Crossrail.*':                     'Elizabeth',
}

# Service track types to skip
SKIP_SERVICE = {'crossover', 'siding', 'yard', 'spur'}

# ── Per-mode config: which files to read and a fallback line name ─────────────

MODES = [
    {'file': 'tube.geojson',        'fallback': None,       'mode': 'tube'},
    {'file': 'overground.geojson',  'fallback': None,       'mode': 'overground'},
    {'file': 'dlr.geojson',         'fallback': 'DLR',      'mode': 'dlr'},
    {'file': 'elizabeth.geojson',   'fallback': 'Elizabeth', 'mode': 'elizabeth'},
]


def canonical(raw: str) -> str:
    raw = raw.strip()
    for pattern, replacement in ALIASES.items():
        if re.fullmatch(pattern, raw, re.IGNORECASE):
            return replacement
    # Strip trailing " Line" / " line"
    cleaned = re.sub(r'\s+[Ll]ine$', '', raw).strip()
    return cleaned if cleaned else raw


def line_keys(props: dict, fallback: str | None, mode: str) -> list[str]:
    """Return all canonical line names from feature properties."""
    # Overground: ref codes are authoritative
    if mode == 'overground':
        ref = (props.get('ref') or '').strip()
        if ref in OVERGROUND_REF:
            return [OVERGROUND_REF[ref]]

    raw = props.get('line') or props.get('ref') or ''
    if not raw and fallback:
        return [fallback]
    if not raw:
        return []

    parts = [p.strip() for p in raw.split(';') if p.strip()]
    return [canonical(p) for p in parts]


def best_colour(name: str) -> str:
    return COLOURS.get(name, '#888888')


def should_skip(props: dict) -> bool:
    service = (props.get('service') or '').lower()
    return service in SKIP_SERVICE


def load_file(path: Path, fallback: str | None, mode: str, buckets: dict) -> tuple[int, int]:
    if not path.exists():
        print(f"  [MISSING] {path.name} — skipping")
        return 0, 0

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    loaded, skipped = 0, 0

    for feat in features:
        geom = feat.get('geometry')
        if not geom or geom['type'] not in ('LineString', 'MultiLineString'):
            continue
        props = feat.get('properties') or {}
        if should_skip(props):
            skipped += 1
            continue

        keys = line_keys(props, fallback, mode)
        if not keys:
            skipped += 1
            continue

        shp = shape(geom)
        for name in keys:
            buckets[name]['segs'].append(shp)
        loaded += 1

    return loaded, skipped


def load_overground_raw(path: Path, buckets: dict) -> tuple[int, int]:
    """Parse raw Overpass JSON (out body; >; out geom) for Overground.
    Reads line name from route relations, assigns it to member ways by way id."""
    if not path.exists():
        print(f"  [MISSING] {path.name} — skipping")
        return 0, 0

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    elements = data.get('elements', [])

    # Pass 1 — build way_id → list[brand] from route relations
    way_brand: dict[int, set[str]] = {}
    for el in elements:
        if el.get('type') != 'relation':
            continue
        tags = el.get('tags', {})
        raw_name = tags.get('line') or tags.get('name') or ''
        brand = canonical(raw_name)
        if brand not in COLOURS:
            continue  # not a recognised brand — skip
        for member in el.get('members', []):
            if member.get('type') == 'way':
                wid = member['ref']
                way_brand.setdefault(wid, set()).add(brand)

    # Pass 2 — build geometries from way elements
    loaded, skipped = 0, 0
    for el in elements:
        if el.get('type') != 'way':
            continue
        tags = el.get('tags', {})
        if should_skip(tags):
            skipped += 1
            continue

        wid = el['id']
        brands = way_brand.get(wid)
        # Also try the way's own line tag as a fallback
        if not brands:
            keys = line_keys(tags, None, 'overground')
            brands = set(keys) if keys else None
        if not brands:
            skipped += 1
            continue

        geometry = el.get('geometry', [])
        if len(geometry) < 2:
            skipped += 1
            continue

        coords = [[pt['lon'], pt['lat']] for pt in geometry]
        geom = {'type': 'LineString', 'coordinates': coords}
        shp = shape(geom)
        for brand in brands:
            buckets[brand]['segs'].append(shp)
        loaded += 1

    return loaded, skipped


def main():
    buckets: dict = defaultdict(lambda: {'segs': []})

    print("Reading mode files:")
    total_loaded = 0
    for m in MODES:
        path = BASE / m['file']
        if m['mode'] == 'overground':
            raw_path = BASE / 'overground_raw.json'
            if raw_path.exists():
                loaded, skipped = load_overground_raw(raw_path, buckets)
                print(f"  {'overground_raw.json':25s}  {loaded:5d} loaded  {skipped:4d} skipped  (raw Overpass JSON)")
                total_loaded += loaded
                continue
        loaded, skipped = load_file(path, m['fallback'], m['mode'], buckets)
        print(f"  {m['file']:25s}  {loaded:5d} loaded  {skipped:4d} skipped")
        total_loaded += loaded

    print(f"\nTotal segments loaded: {total_loaded}")
    print(f"Lines identified     : {len(buckets)}\n")

    out_features = []
    total_pts = 0
    missing_colour = []

    for name in sorted(buckets):
        segs = buckets[name]['segs']
        try:
            merged = linemerge(segs)
        except Exception:
            merged = unary_union(segs)

        geoms = list(merged.geoms) if hasattr(merged, 'geoms') else [merged]
        pts   = sum(len(g.coords) for g in geoms)
        total_pts += pts
        colour = best_colour(name)
        flag   = '✓' if colour != '#888888' else '?'
        if colour == '#888888':
            missing_colour.append(name)

        print(f"  {flag}  {name:35s}  {len(segs):5d} segs  {pts:7,} pts  {colour}")

        out_features.append({
            'type': 'Feature',
            'geometry': mapping(merged),
            'properties': {'name': name, 'colour': colour, 'mode': 'tfl'},
        })

    result = {'type': 'FeatureCollection', 'features': out_features}
    dst = BASE / 'tfl_lines.geojson'
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(result, f, separators=(',', ':'))

    size_kb = dst.stat().st_size / 1024
    print(f"\nOutput : {dst}")
    print(f"Lines  : {len(out_features)}")
    print(f"Points : {total_pts:,}")
    print(f"Size   : {size_kb:.1f} KB")

    if missing_colour:
        print(f"\n? No official colour for: {', '.join(missing_colour)}")
        print("  Add them to COLOURS dict if needed.")


if __name__ == '__main__':
    main()
