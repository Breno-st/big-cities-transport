"""
Build tfl_edges.geojson from the NUMBAT graph + tfl_lines.geojson.

For each NUMBAT directed link (source → target) ONE feature is created per
matching OSM tube line.  A line matches if both station points project within
MAX_PERP_DEG of the line's geometry.  If no line matches, the nearest tube
line is used with a straight-line geometry so the link is never "lost" and
always appears in the mode filter.

Key design decisions:
  - Coordinates are PRE-OFFSET into the GeoJSON geometry (perp to track
    direction) so that Mapbox symbol arrows follow the correct track position.
    The Mapbox layer therefore needs NO line-offset paint property.
  - Coordinates run SOURCE → TARGET (reversed when d_src > d_tgt on the
    OSM line) so arrow glyphs point in the direction of travel.
  - off9/off12/off14 properties are set to 0 — the visual offset is now
    encoded in the geometry, not as a Mapbox paint offset.
"""

import json
import math
from collections import Counter
from pathlib import Path

from shapely.geometry import LineString, Point, shape
from shapely.ops import substring

BASE   = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')
NUMBAT = Path(r'C:\buildbr\big-cities-transport\03.GraphModels\tube\tube-traffic-fri-am-peak.json')

MAX_PERP_DEG = 0.004   # ≈ 450 m

TUBE_LINE_NAMES = {
    'Bakerloo', 'Central', 'Circle', 'District', 'Hammersmith & City',
    'Jubilee', 'Metropolitan', 'Northern', 'Piccadilly', 'Victoria', 'Waterloo & City',
}

# Calibrated to zoom 12: LINE_W_Z12 px × GROUND_RES_Z12 m/px = offset in metres
GROUND_RES_Z12 = 40_075_000 * math.cos(math.radians(51.5)) / (2**12 * 256)
LINE_W_Z12     = 3.5


# ── Geometry helpers ──────────────────────────────────────────────────────────

def best_component(geom, pt1: Point, pt2: Point):
    """Return the LineString component nearest to both pt1 and pt2."""
    if geom.geom_type == 'LineString':
        return geom
    best, best_score = None, float('inf')
    for comp in geom.geoms:
        score = max(comp.interpolate(comp.project(pt1)).distance(pt1),
                    comp.interpolate(comp.project(pt2)).distance(pt2))
        if score < best_score:
            best_score, best = score, comp
    return best


def extract_segment(geom, pt1: Point, pt2: Point):
    """
    Return (segment, perp_error, reversed_flag) from geom between pt1 and pt2.
    reversed_flag=True means the lo→hi substring runs target→source and the
    caller must flip coordinates to get source→target arrow direction.
    """
    comp = best_component(geom, pt1, pt2)
    if comp is None:
        return None, float('inf'), False
    d1   = comp.project(pt1)
    d2   = comp.project(pt2)
    perp = max(comp.interpolate(d1).distance(pt1),
               comp.interpolate(d2).distance(pt2))
    if d1 == d2:
        return None, float('inf'), False
    rev  = d1 > d2
    lo, hi = (d1, d2) if not rev else (d2, d1)
    try:
        seg = substring(comp, lo, hi)
    except Exception:
        return None, float('inf'), False
    if seg is None or seg.is_empty or seg.length == 0:
        return None, float('inf'), False
    if seg.geom_type == 'MultiLineString':
        coords = []
        for s in seg.geoms:
            coords.extend(s.coords)
        seg = LineString(coords)
    return seg, perp, rev


def perp_shift(lng, lat, comp, mult):
    """Shift a single point perpendicular to comp by mult × reference offset."""
    pt = Point(lng, lat)
    d  = comp.project(pt)
    a  = comp.interpolate(min(d + 0.0001, comp.length))
    b  = comp.interpolate(max(d - 0.0001, 0))
    dx, dy = a.x - b.x, a.y - b.y
    length = math.hypot(dx, dy)
    if length < 1e-10:
        return lng, lat
    px, py = dy / length, -dx / length      # perpendicular clockwise
    offset_m = mult * LINE_W_Z12 * GROUND_RES_Z12
    return (lng + px * offset_m / (111_320 * math.cos(math.radians(lat))),
            lat + py * offset_m / 111_320)


def offset_coords(coords, comp, mult):
    """Return a new coordinate list with each point shifted by perp_shift."""
    if abs(mult) < 1e-6:
        return coords
    return [list(perp_shift(lng, lat, comp, mult)) for lng, lat in coords]


def offset_straight_coords(coords, mult):
    """Perpendicular offset for a 2-point straight segment (no OSM component)."""
    if abs(mult) < 1e-6 or len(coords) < 2:
        return coords
    lng1, lat1 = coords[0]
    lng2, lat2 = coords[-1]
    dx, dy     = lng2 - lng1, lat2 - lat1
    length     = math.hypot(dx, dy)
    if length < 1e-10:
        return coords
    px, py   = dy / length, -dx / length
    lat_mid  = (lat1 + lat2) / 2
    offset_m = mult * LINE_W_Z12 * GROUND_RES_Z12
    dlat     = offset_m / 111_320
    dlng     = offset_m / (111_320 * math.cos(math.radians(lat_mid)))
    return [[lng + px * dlng, lat + py * dlat] for lng, lat in coords]


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    with open(BASE / 'tfl_lines.geojson', encoding='utf-8') as f:
        tfl_data = json.load(f)

    line_geoms  = {}
    line_colour = {}
    line_mult   = {}   # name → offset multiplier (recovered from off12 / LINE_W_Z12)

    for feat in tfl_data['features']:
        p    = feat['properties']
        name = p['name']
        line_geoms[name]  = shape(feat['geometry'])
        line_colour[name] = p.get('colour', '#888888')
        line_mult[name]   = round(p.get('off12', 0.0) / LINE_W_Z12, 6)

    with open(NUMBAT, encoding='utf-8') as f:
        numbat = json.load(f)
    nodes_by_id = {n['id']: n for n in numbat['nodes']}

    out_features   = []
    stats_matched  = 0
    stats_fallback = 0
    line_counter   = Counter()

    for link in numbat['links']:
        src = nodes_by_id[link['source']]
        tgt = nodes_by_id[link['target']]
        src_pt = Point(src['long'], src['lat'])
        tgt_pt = Point(tgt['long'], tgt['lat'])
        src_name = src['name'].replace(' Underground Station', '').replace(' Station', '')
        tgt_name = tgt['name'].replace(' Underground Station', '').replace(' Station', '')
        traffic  = round(link['traffic'], 4)

        matches = []  # list of (lname, coords_raw, perp, rev)
        for lname in TUBE_LINE_NAMES:
            geom = line_geoms.get(lname)
            if geom is None:
                continue
            seg, perp, rev = extract_segment(geom, src_pt, tgt_pt)
            if seg is not None and perp <= MAX_PERP_DEG:
                matches.append((lname, list(seg.coords), perp, rev))

        if matches:
            for lname, raw_coords, perp, rev in matches:
                coords = raw_coords if not rev else raw_coords[::-1]
                comp   = best_component(line_geoms[lname], src_pt, tgt_pt)
                mult   = line_mult[lname]
                coords = offset_coords(coords, comp, mult)
                colour = line_colour[lname]
                out_features.append(_feat(src, tgt, src_name, tgt_name, lname, colour, traffic, coords))
                line_counter[lname] += 1
                stats_matched += 1
        else:
            # No line within tolerance — use nearest tube line so the link is
            # never filtered out.  Geometry is a straight line between the two
            # NUMBAT stations, offset perpendicular to the nearest OSM line.
            best_lname, best_d = '', float('inf')
            for lname in TUBE_LINE_NAMES:
                d = line_geoms[lname].distance(src_pt) + line_geoms[lname].distance(tgt_pt)
                if d < best_d:
                    best_d, best_lname = d, lname

            coords = [[src['long'], src['lat']], [tgt['long'], tgt['lat']]]
            mult   = line_mult.get(best_lname, 0.0)
            coords = offset_straight_coords(coords, mult)
            colour = line_colour.get(best_lname, '#888888')
            out_features.append(_feat(src, tgt, src_name, tgt_name, best_lname, colour, traffic, coords))
            line_counter[best_lname] += 1
            stats_fallback += 1

    for i, feat in enumerate(out_features):
        feat['id'] = i

    result = {'type': 'FeatureCollection', 'features': out_features}
    dst = BASE / 'tfl_edges.geojson'
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(result, f, separators=(',', ':'))

    size_kb = dst.stat().st_size / 1024
    print(f"NUMBAT links     : {len(numbat['links'])}")
    print(f"Output features  : {len(out_features)}")
    print(f"  Multi-line OSM : {stats_matched}")
    print(f"  Nearest fallback: {stats_fallback}")
    print(f"Output : {dst}  ({size_kb:.1f} KB)")
    print("\nFeatures per line:")
    for name, cnt in sorted(line_counter.items(), key=lambda x: -x[1]):
        print(f"  {name:35s}  {cnt:4d}")


def _feat(src, tgt, src_name, tgt_name, lname, colour, traffic, coords):
    return {
        'type': 'Feature',
        'geometry': {'type': 'LineString', 'coordinates': coords},
        'properties': {
            'id':         f"{src['naptanid']}-{tgt['naptanid']}-{lname}",
            'source':     src['naptanid'],
            'target':     tgt['naptanid'],
            'sourceName': src_name,
            'targetName': tgt_name,
            'line':       lname,
            'colour':     colour,
            'color':      colour,
            'traffic':    traffic,
            # Offset is encoded in coordinates — Mapbox layer needs no line-offset.
            'off9': 0.0, 'off12': 0.0, 'off14': 0.0,
        },
    }


if __name__ == '__main__':
    main()
