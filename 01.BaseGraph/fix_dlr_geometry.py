"""
Fix straight-line (2-point) DLR edges in tfl_rail_edges.geojson by injecting
the proper OSM segment from tfl_lines.geojson where one can be found.

Run from any directory — uses absolute paths.
"""

import json
import math
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.ops import substring

BASE      = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')
LINES     = BASE / 'tfl_lines.geojson'
ASSETS    = Path(r'C:\buildbr\bt-fnt\fntweb\src\assets\data')
RAIL_FILE = ASSETS / 'tfl_rail_edges.geojson'

GEOM_THRESHOLD = 0.012  # degrees — wider than tube (0.006) because DLR uses NR naptanids
                         # whose station positions may be slightly off the OSM DLR geometry


def best_component(geom, pt1: Point, pt2: Point):
    if geom.geom_type == 'LineString':
        return geom
    best, best_score = None, float('inf')
    for comp in geom.geoms:
        s = max(comp.interpolate(comp.project(pt1)).distance(pt1),
                comp.interpolate(comp.project(pt2)).distance(pt2))
        if s < best_score:
            best_score, best = s, comp
    return best


def extract_segment(geom, pt1: Point, pt2: Point, threshold: float):
    comp = best_component(geom, pt1, pt2)
    if comp is None:
        return None
    d1, d2 = comp.project(pt1), comp.project(pt2)
    if d1 == d2:
        return None
    perp = max(comp.interpolate(d1).distance(pt1),
               comp.interpolate(d2).distance(pt2))
    if perp > threshold:
        return None
    lo, hi = (d1, d2) if d1 <= d2 else (d2, d1)
    rev = d1 > d2
    try:
        seg = substring(comp, lo, hi)
    except Exception:
        return None
    if seg is None or seg.is_empty or seg.length == 0:
        return None
    if seg.geom_type == 'MultiLineString':
        coords = []
        for s in seg.geoms:
            coords.extend(list(s.coords))
    else:
        coords = list(seg.coords)
    if rev:
        coords = coords[::-1]
    return [[c[0], c[1]] for c in coords]


def main():
    with open(LINES, encoding='utf-8') as f:
        lines_data = json.load(f)

    dlr_geom = None
    for feat in lines_data['features']:
        if feat['properties'].get('name') == 'DLR':
            dlr_geom = shape(feat['geometry'])
            break

    if dlr_geom is None:
        print('ERROR: No DLR feature found in tfl_lines.geojson')
        return

    with open(RAIL_FILE, encoding='utf-8-sig') as f:
        rail_data = json.load(f)

    fixed = 0
    skipped = 0
    for feat in rail_data['features']:
        p = feat['properties']
        if p.get('mode') != 'dlr':
            continue
        coords = feat['geometry']['coordinates']
        if len(coords) != 2:
            continue  # already has OSM geometry

        src_pt = Point(coords[0][0], coords[0][1])
        tgt_pt = Point(coords[1][0], coords[1][1])

        osm_coords = extract_segment(dlr_geom, src_pt, tgt_pt, GEOM_THRESHOLD)
        if osm_coords and len(osm_coords) >= 2:
            # Pin endpoints exactly to station positions
            osm_coords[0]  = coords[0]
            osm_coords[-1] = coords[1]
            feat['geometry']['coordinates'] = osm_coords
            fixed += 1
            print(f'  Fixed: {p.get("src")} -> {p.get("tgt")}  ({len(osm_coords)} pts)')
        else:
            skipped += 1
            print(f'  No OSM match: {p.get("src")} -> {p.get("tgt")}')

    with open(RAIL_FILE, 'w', encoding='utf-8') as f:
        json.dump(rail_data, f, separators=(',', ':'))

    print(f'\nDone. Fixed: {fixed}  No match: {skipped}')


if __name__ == '__main__':
    main()
