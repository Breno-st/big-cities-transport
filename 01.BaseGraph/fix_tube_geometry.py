"""
fix_tube_geometry.py
--------------------
Replace straight-line (2-point) tube edges in tfl_rail_edges.geojson with
OSM-based curved segments from tfl_lines.geojson.

These 78 edges failed the original 0.004° threshold used when the file was built.
We retry with a relaxed threshold (0.012°) and try ALL tube line geometries plus
Lioness (which shares the Bakerloo/DC corridor) to catch the Wembley section.

Logic:
  For each straight tube edge:
    1. Try every tube line (+ Lioness) in tfl_lines.geojson
    2. Pick the best match (lowest perp error below GEOM_THRESHOLD)
    3. If found, extract the OSM substring and replace the geometry
    4. If still no match, keep as straight line
"""

import json
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.ops import substring

BASE       = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')
ASSETS     = Path(r'C:\buildbr\bt-fnt\fntweb\src\assets\data')
RAIL_FILE  = ASSETS / 'tfl_rail_edges.geojson'
LINES_FILE = BASE  / 'tfl_lines.geojson'

# Tube line names in tfl_lines.geojson (+ Lioness for the Bakerloo/DC corridor)
TUBE_LINE_NAMES = {
    'Bakerloo', 'Central', 'Circle', 'District', 'Hammersmith & City',
    'Jubilee', 'Metropolitan', 'Northern', 'Piccadilly', 'Victoria',
    'Waterloo & City',
    'Lioness',   # shares track with Bakerloo in Wembley/Harlesden corridor
}

# Relaxed threshold — these edges already failed 0.004°, so use up to 0.012°
GEOM_THRESHOLD = 0.012   # ° ≈ ~1.3 km at London latitude


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
    # ── Load line geometries ───────────────────────────────────────────────────
    with open(LINES_FILE, encoding='utf-8') as f:
        tfl_lines = json.load(f)

    line_geoms: dict[str, object] = {}
    for feat in tfl_lines['features']:
        name = feat['properties']['name']
        if name in TUBE_LINE_NAMES:
            line_geoms[name] = shape(feat['geometry'])

    print(f"Line geometries loaded: {sorted(line_geoms.keys())}")

    # ── Load rail edges ────────────────────────────────────────────────────────
    with open(RAIL_FILE, encoding='utf-8-sig') as f:
        rail = json.load(f)

    n_fixed    = 0
    n_still_straight = 0
    line_hits: dict[str, int] = {}

    for feat in rail['features']:
        if feat['properties'].get('mode') != 'tube':
            continue
        coords = feat['geometry']['coordinates']
        if len(coords) != 2:
            continue   # already curved — skip

        src_pt = Point(coords[0][0], coords[0][1])
        tgt_pt = Point(coords[1][0], coords[1][1])

        best_coords, best_perp, best_line = None, GEOM_THRESHOLD + 1, None

        for lname, geom in line_geoms.items():
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
            n_still_straight += 1

    # ── Write updated file ─────────────────────────────────────────────────────
    with open(RAIL_FILE, 'w', encoding='utf-8') as f:
        json.dump(rail, f, separators=(',', ':'))

    size_kb = RAIL_FILE.stat().st_size / 1024
    print(f"\nStraight tube edges fixed : {n_fixed}")
    for lname, cnt in sorted(line_hits.items(), key=lambda x: -x[1]):
        print(f"  {lname:30s}: {cnt}")
    print(f"Still straight            : {n_still_straight}")
    print(f"\nFile: {RAIL_FILE}  ({size_kb:.1f} KB)")


if __name__ == '__main__':
    main()
