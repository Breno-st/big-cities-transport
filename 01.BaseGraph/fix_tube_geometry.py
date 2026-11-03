"""
fix_tube_geometry.py
--------------------
Replace incorrect tube edge geometries in tfl_rail_edges.geojson with
OSM-based curved segments from tfl_lines.geojson.

Two classes of broken edges are fixed:

  1. Straight-line (2-point) fallbacks — the original issue.
  2. Multi-point edges where the geometry endpoints do NOT match the expected
     station positions (naptanid coords from tube_nodes.txt).  This happens
     when NUMBAT has inconsistent lat/long values for the same physical station
     across different directed links, causing extract_segment to snap to the
     wrong OSM substring (e.g. East Putney→Southfields landing near East Putney).

For class-2 edges the script looks up the CORRECT station positions from
tube_nodes.txt and re-extracts the OSM segment from scratch.

Logic for each tube edge:
  1. Load source/target naptanid positions from tube_nodes.txt.
  2. Check if coords[0] and coords[-1] are within ENDPOINT_TOL of those positions.
  3. If either endpoint is wrong (or the edge is 2-point), attempt OSM re-extraction
     using the naptanid-derived src_pt / tgt_pt as the authoritative positions.
  4. If OSM extraction succeeds, replace the geometry.
  5. If no OSM match, keep as corrected straight line between the naptanid positions.
"""

import json, re
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.ops import substring

BASE       = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')
ASSETS     = Path(r'C:\buildbr\bt-fnt\fntweb\src\assets\data')
RAIL_FILE  = ASSETS / 'tfl_rail_edges.geojson'
LINES_FILE = BASE   / 'tfl_lines.geojson'
NODES_FILE = BASE / '02.Neo4J_Scripts' / 'nodes' / 'tube_nodes.txt'

TUBE_LINE_NAMES = {
    'Bakerloo', 'Central', 'Circle', 'District', 'Hammersmith & City',
    'Jubilee', 'Metropolitan', 'Northern', 'Piccadilly', 'Victoria',
    'Waterloo & City',
    'Lioness',
}

GEOM_THRESHOLD = 0.012    # ° ≈ ~1.3 km at London latitude
ENDPOINT_TOL   = 0.003    # ° ≈ ~250 m — max acceptable deviation of geometry endpoint from naptanid position


# ── Parse tube_nodes.txt → {naptanid: (lat, lng)} ─────────────────────────────

def load_naptanid_positions(path: Path) -> dict[str, tuple[float, float]]:
    pat = re.compile(
        r"naptanid:'(?P<id>[^']+)'.*?lat:(?P<lat>[\d.]+),long:(?P<lng>[-\d.]+)"
    )
    result: dict[str, tuple[float, float]] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        m = pat.search(line)
        if m:
            result[m['id']] = (float(m['lat']), float(m['lng']))
    return result


# ── OSM geometry helpers ───────────────────────────────────────────────────────

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
    # Reject if extracted segment is much shorter than the straight-line distance —
    # this catches cases where both stations project to the same OSM line endpoint
    # (e.g. District line terminating at Wimbledon Park, not Wimbledon).
    straight = pt1.distance(pt2)
    if seg.length < 0.35 * straight:
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


def needs_fix(coords: list, src_pt: Point, tgt_pt: Point) -> bool:
    """Return True if geometry endpoints are too far from the expected station positions."""
    if len(coords) == 2:
        return True  # straight-line fallback always gets a re-extraction attempt
    start = Point(coords[0][0],  coords[0][1])
    end   = Point(coords[-1][0], coords[-1][1])
    return start.distance(src_pt) > ENDPOINT_TOL or end.distance(tgt_pt) > ENDPOINT_TOL


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # Load naptanid → (lat, lng)
    naptanid_pos = load_naptanid_positions(NODES_FILE)
    print(f"Naptanid positions loaded: {len(naptanid_pos)}")

    # Load OSM line geometries
    with open(LINES_FILE, encoding='utf-8') as f:
        tfl_lines = json.load(f)
    line_geoms: dict[str, object] = {}
    for feat in tfl_lines['features']:
        name = feat['properties']['name']
        if name in TUBE_LINE_NAMES:
            line_geoms[name] = shape(feat['geometry'])
    print(f"Line geometries loaded: {sorted(line_geoms.keys())}")

    # Load rail edges
    with open(RAIL_FILE, encoding='utf-8-sig') as f:
        rail = json.load(f)

    n_fixed     = 0
    n_straight  = 0
    n_skipped   = 0
    n_no_naptan = 0
    line_hits: dict[str, int] = {}

    for feat in rail['features']:
        props = feat['properties']
        if props.get('mode') != 'tube':
            continue

        src_nap = props.get('src', '') or props.get('source', '')
        tgt_nap = props.get('tgt', '') or props.get('target', '')

        if src_nap not in naptanid_pos or tgt_nap not in naptanid_pos:
            n_no_naptan += 1
            continue

        src_lat, src_lng = naptanid_pos[src_nap]
        tgt_lat, tgt_lng = naptanid_pos[tgt_nap]
        src_pt = Point(src_lng, src_lat)
        tgt_pt = Point(tgt_lng, tgt_lat)

        coords = feat['geometry']['coordinates']
        if not needs_fix(coords, src_pt, tgt_pt):
            n_skipped += 1
            continue

        src_name = props.get('src_name') or props.get('sourceName', src_nap)
        tgt_name = props.get('tgt_name') or props.get('targetName', tgt_nap)

        # Attempt OSM re-extraction using correct naptanid positions
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
            print(f"  Fixed  [{best_line:30s}]  {src_name} → {tgt_name}  (perp={best_perp:.5f}°)")
        else:
            # Fallback: straight line using correct naptanid positions
            feat['geometry']['coordinates'] = [[src_lng, src_lat], [tgt_lng, tgt_lat]]
            n_straight += 1
            print(f"  Straight fallback: {src_name} → {tgt_name}")

    # Write updated file
    with open(RAIL_FILE, 'w', encoding='utf-8') as f:
        json.dump(rail, f, separators=(',', ':'))

    size_kb = RAIL_FILE.stat().st_size / 1024
    print(f"\nEdges fixed (OSM curve) : {n_fixed}")
    for lname, cnt in sorted(line_hits.items(), key=lambda x: -x[1]):
        print(f"  {lname:35s}: {cnt}")
    print(f"Edges fixed (straight)  : {n_straight}")
    print(f"Edges already correct   : {n_skipped}")
    print(f"Missing naptanid        : {n_no_naptan}")
    print(f"\nFile: {RAIL_FILE}  ({size_kb:.1f} KB)")


if __name__ == '__main__':
    main()
