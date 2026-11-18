"""
fetch_overground_overpass.py
----------------------------
Fetch TfL Overground route geometries for the four brand lines missing
from tfl_lines.geojson (Mildmay, Windrush, Suffragette, Weaver).

Strategy (two-phase to avoid Overpass timeouts):
  Phase 1 — Overpass: get relation IDs only (tiny response, fast).
  Phase 2 — OSM API: fetch each relation's full way+node geometry
            individually via api.openstreetmap.org/api/0.6/relation/{id}/full.json

Then runs the same geometry-repair pass against the remaining 98 straight
overground edges in tfl_rail_edges.geojson.

Dependencies: shapely (already installed), urllib/json (stdlib)
"""

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

from shapely.geometry import LineString, Point
from shapely.ops import linemerge, substring

BASE       = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')
ASSETS     = Path(r'C:\buildbr\bt-fnt\fntweb\src\assets\data')
RAIL_FILE  = ASSETS / 'tfl_rail_edges.geojson'
OUT_FILE   = BASE   / 'overground_lines.geojson'

GEOM_THRESHOLD = 0.012

BBOX = '51.28,-0.51,51.70,0.33'

# Phase-1 query: search by terminus names since OSM pre-rebranding tags vary.
# Mildmay    : Stratford - Richmond / Clapham Junction
# Windrush   : Highbury - Crystal Palace / Clapham Junction / New Cross Gate
# Suffragette: Gospel Oak - Barking
# Weaver     : Liverpool Street - Cheshunt / Enfield Town / Chingford
ID_QUERY = f"""
[out:json][timeout:60];
(
  relation["type"="route"]["from"~"Gospel Oak"]({BBOX});
  relation["type"="route"]["to"~"Gospel Oak"]({BBOX});
  relation["type"="route"]["from"~"Barking"]["to"~"Gospel Oak"]({BBOX});
  relation["type"="route"]["from"~"Highbury"]["to"~"Crystal Palace|Clapham|New Cross"]({BBOX});
  relation["type"="route"]["from"~"Crystal Palace|New Cross"]["to"~"Highbury"]({BBOX});
  relation["type"="route"]["from"~"Stratford"]["to"~"Richmond|Clapham"]({BBOX});
  relation["type"="route"]["from"~"Richmond|Clapham Junction"]["to"~"Stratford"]({BBOX});
  relation["type"="route"]["from"~"Liverpool Street"]["to"~"Cheshunt|Enfield|Chingford"]({BBOX});
  relation["type"="route"]["from"~"Cheshunt|Enfield Town|Chingford"]["to"~"Liverpool"]({BBOX});
  relation["network"="London Overground"]({BBOX});
  relation["operator"="London Overground"]({BBOX});
  relation["brand"~"Mildmay|Windrush|Suffragette|Weaver"]({BBOX});
);
out ids tags;
"""

OVERPASS_MIRRORS = [
    'https://z.overpass-api.de/api/interpreter',
    'https://overpass-api.de/api/interpreter',
    'https://overpass.openstreetmap.ru/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
]

OSM_API = 'https://api.openstreetmap.org/api/0.6/relation/{id}/full.json'


def overpass_get(query: str) -> dict:
    encoded = urllib.parse.quote(query)
    for base_url in OVERPASS_MIRRORS:
        # Try GET first (lighter), fall back to POST
        for method, args in [
            ('GET',  dict(url=f"{base_url}?data={encoded}")),
            ('POST', dict(url=base_url,
                          data=urllib.parse.urlencode({'data': query}).encode('utf-8'))),
        ]:
            try:
                if method == 'GET':
                    req = urllib.request.Request(
                        args['url'],
                        headers={'User-Agent': 'tfl-map-builder/1.0'},
                    )
                else:
                    req = urllib.request.Request(
                        args['url'], data=args['data'],
                        headers={'Content-Type': 'application/x-www-form-urlencoded',
                                 'User-Agent': 'tfl-map-builder/1.0'},
                    )
                with urllib.request.urlopen(req, timeout=90) as resp:
                    raw = resp.read()
                print(f"  Overpass OK [{method}] ({base_url}): {len(raw):,} bytes")
                return json.loads(raw)
            except Exception as e:
                print(f"  [{method}] {base_url}: {e}")
                time.sleep(1)
        time.sleep(2)
    raise RuntimeError("All Overpass mirrors failed")


def osm_relation_full(rel_id: int) -> dict:
    url = OSM_API.format(id=rel_id)
    req = urllib.request.Request(url, headers={'User-Agent': 'tfl-map-builder/1.0'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def brand_from_tags(tags: dict) -> str:
    brand = tags.get('brand', '')
    if brand in ('Mildmay', 'Windrush', 'Suffragette', 'Weaver', 'Lioness', 'Liberty'):
        return brand
    name = tags.get('name', '') + ' ' + tags.get('ref', '')
    for b in ('Mildmay', 'Windrush', 'Suffragette', 'Weaver', 'Lioness', 'Liberty'):
        if b.lower() in name.lower():
            return b
    return 'Overground'


def assemble_from_elements(elements: list):
    """Build node dict + way dict, then collect all way geometries."""
    nodes: dict[int, tuple] = {}
    ways:  dict[int, list]  = {}
    rel_member_ways: list[int] = []

    for el in elements:
        t = el.get('type')
        if t == 'node':
            nodes[el['id']] = (el['lon'], el['lat'])
        elif t == 'way':
            ways[el['id']] = el.get('nodes', [])
        elif t == 'relation':
            for m in el.get('members', []):
                if m.get('type') == 'way':
                    rel_member_ways.append(m['ref'])

    segments = []
    for wid in rel_member_ways:
        node_ids = ways.get(wid, [])
        coords = [nodes[n] for n in node_ids if n in nodes]
        if len(coords) >= 2:
            segments.append(LineString(coords))
    return segments


def best_component(geom, pt1: Point, pt2: Point):
    if geom.geom_type == 'LineString':
        return geom
    best, best_score = None, float('inf')
    for comp in geom.geoms:
        score = max(comp.interpolate(comp.project(pt1)).distance(pt1),
                    comp.interpolate(comp.project(pt2)).distance(pt2))
        if score < best_score:
            best_score, best = score, comp
    return best


def extract_segment(geom, pt1: Point, pt2: Point, threshold: float):
    comp = best_component(geom, pt1, pt2)
    if comp is None:
        return None, float('inf')
    d1 = comp.project(pt1)
    d2 = comp.project(pt2)
    if d1 == d2:
        return None, float('inf')
    perp = max(comp.interpolate(d1).distance(pt1),
               comp.interpolate(d2).distance(pt2))
    if perp > threshold:
        return None, float('inf')
    rev = d1 > d2
    lo, hi = (d1, d2) if not rev else (d2, d1)
    try:
        seg = substring(comp, lo, hi)
    except Exception:
        return None, float('inf')
    if seg is None or seg.is_empty or seg.length == 0:
        return None, float('inf')
    if seg.geom_type == 'MultiLineString':
        coords = []
        for s in seg.geoms:
            coords.extend(s.coords)
    else:
        coords = list(seg.coords)
    if rev:
        coords = coords[::-1]
    return coords, perp


def main():
    # ── Phase 1: get relation IDs ──────────────────────────────────────────────
    print("=== Phase 1: Fetching relation IDs from Overpass ===")
    result = overpass_get(ID_QUERY)
    all_rels = result.get('elements', [])
    print(f"  Total elements: {len(all_rels)}")

    # Collect unique relation IDs and their tags
    seen_ids: dict[int, dict] = {}
    for el in all_rels:
        if el.get('type') == 'relation':
            seen_ids[el['id']] = el.get('tags', {})

    print(f"  Unique relations: {len(seen_ids)}")
    for rid, tags in list(seen_ids.items())[:20]:
        name = tags.get('name', '?').encode('ascii', 'replace').decode()
        brand = tags.get('brand', '-')
        typ = tags.get('type', '?')
        print(f"    {rid}: [{typ}] {name[:55]} | brand={brand}")

    # Filter to route relations only (not route_master)
    route_ids = {rid: tags for rid, tags in seen_ids.items()
                 if tags.get('type') == 'route'}
    print(f"\n  Route relations: {len(route_ids)}")

    # ── Phase 2: fetch full geometry for each route relation via OSM API ───────
    print("\n=== Phase 2: Fetching full way geometry via OSM API ===")
    brand_segments: dict[str, list] = {}

    for i, (rid, tags) in enumerate(route_ids.items()):
        brand = brand_from_tags(tags)
        name  = tags.get('name', '?').encode('ascii', 'replace').decode()
        print(f"  [{i+1}/{len(route_ids)}] {rid}: {name[:40]} -> {brand}")
        try:
            full = osm_relation_full(rid)
            segs = assemble_from_elements(full.get('elements', []))
            brand_segments.setdefault(brand, []).extend(segs)
            print(f"    {len(segs)} way segments")
        except Exception as e:
            print(f"    ERROR: {e}")
        time.sleep(0.5)   # polite rate limiting

    # ── Merge per-brand geometries ─────────────────────────────────────────────
    brand_geoms: dict[str, object] = {}
    for brand, segs in brand_segments.items():
        merged = linemerge(segs)
        brand_geoms[brand] = merged
        n = 1 if merged.geom_type == 'LineString' else len(list(merged.geoms))
        print(f"  {brand:15s}: {len(segs)} segments -> {n} component(s)")

    # ── Save overground_lines.geojson ─────────────────────────────────────────
    features = []
    for brand, geom in brand_geoms.items():
        if geom.geom_type == 'LineString':
            g = {'type': 'LineString', 'coordinates': list(geom.coords)}
        else:
            g = {'type': 'MultiLineString',
                 'coordinates': [list(c.coords) for c in geom.geoms]}
        features.append({'type': 'Feature',
                         'properties': {'name': brand},
                         'geometry': g})
    fc = {'type': 'FeatureCollection', 'features': features}
    with open(OUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(fc, f, separators=(',', ':'))
    print(f"\nSaved {OUT_FILE}  ({OUT_FILE.stat().st_size / 1024:.1f} KB)")

    # ── Fix remaining straight overground edges ────────────────────────────────
    TARGET_BRANDS = {'Mildmay', 'Windrush', 'Suffragette', 'Weaver'}
    fix_geoms = {b: g for b, g in brand_geoms.items() if b in TARGET_BRANDS}
    if not fix_geoms:
        print(f"\nNo target brand geometries found in {sorted(brand_geoms.keys())} — nothing to fix.")
        return

    print(f"\n=== Phase 3: Fixing straight overground edges ===")
    print(f"Fix geometries: {sorted(fix_geoms.keys())}")

    with open(RAIL_FILE, encoding='utf-8-sig') as f:
        rail = json.load(f)

    n_fixed    = 0
    n_straight = 0
    n_already  = 0
    line_hits: dict[str, int] = {}

    for feat in rail['features']:
        if feat['properties'].get('mode') != 'overground':
            continue
        coords = feat['geometry']['coordinates']
        if len(coords) != 2:
            n_already += 1
            continue

        src_pt = Point(coords[0][0], coords[0][1])
        tgt_pt = Point(coords[1][0], coords[1][1])

        best_coords, best_perp, best_line = None, GEOM_THRESHOLD + 1, None

        for lname, geom in fix_geoms.items():
            seg_coords, perp = extract_segment(geom, src_pt, tgt_pt, GEOM_THRESHOLD)
            if seg_coords is not None and perp < best_perp:
                best_perp   = perp
                best_coords = seg_coords
                best_line   = lname

        if best_coords is not None:
            feat['geometry']['coordinates'] = best_coords
            n_fixed += 1
            line_hits[best_line] = line_hits.get(best_line, 0) + 1
        else:
            n_straight += 1

    with open(RAIL_FILE, 'w', encoding='utf-8') as f:
        json.dump(rail, f, separators=(',', ':'))

    size_kb = RAIL_FILE.stat().st_size / 1024
    print(f"\nEdges already curved (skipped): {n_already}")
    print(f"Fixed this pass               : {n_fixed}")
    for lname, cnt in sorted(line_hits.items(), key=lambda x: -x[1]):
        print(f"  {lname:20s}: {cnt}")
    print(f"Still straight                : {n_straight}")
    print(f"\nFile: {RAIL_FILE}  ({size_kb:.1f} KB)")


if __name__ == '__main__':
    main()
