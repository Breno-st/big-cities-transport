"""
Build stations.json from Neo4J Cypher node files + tfl_lines.geojson + tfl_edges.geojson.

Tube stations: one record per (station × matched line).
  - Primary assignment: which lines appear in tfl_edges.geojson for that naptanid.
    This is the most accurate because the edge data already ran proximity matching
    against OSM geometry.
  - Fallback: perpendicular distance to line geometry (same MAX_PERP as edge script).
  - The dot position is shifted perpendicular to the track so it sits on the correct
    side-by-side offset track (calibrated to zoom 12).

Overground / DLR stations: one record per station, no offset.

Prerequisite: run split_tfl_edges.py first so tfl_edges.geojson exists.
"""

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from shapely.geometry import Point, shape

BASE = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')
NEO  = BASE / '02.Neo4J_Scripts' / 'nodes'

GROUND_RES_Z12 = 40_075_000 * math.cos(math.radians(51.5)) / (2**12 * 256)
LINE_W_Z12     = 3.5

MAX_PERP = 0.004   # ≈ 450 m

STRIP_SUFFIXES = [
    ' Underground Station', ' Rail Station', ' DLR Station', ' Station',
]

TUBE_LINE_NAMES = {
    'Bakerloo', 'Central', 'Circle', 'District', 'Hammersmith & City',
    'Jubilee', 'Metropolitan', 'Northern', 'Piccadilly', 'Victoria', 'Waterloo & City',
}


def parse_cypher(path: Path) -> list[dict]:
    pat = re.compile(
        r"naptanid:'(?P<id>[^']+)'.*?name:'(?P<name>[^']+)'.*?"
        r"lat:(?P<lat>[\d.]+),long:(?P<lng>[-\d.]+).*?"
        r"entries:\[(?P<entries>[^\]]+)\],exits:\[(?P<exits>[^\]]+)\]"
    )
    out = []
    for row in path.read_text(encoding='utf-8').splitlines():
        m = pat.search(row)
        if not m:
            continue
        name = m['name']
        for suf in STRIP_SUFFIXES:
            name = name.replace(suf, '')
        try:
            entries = [float(x) for x in m['entries'].split(',')]
            exits   = [float(x) for x in m['exits'].split(',')]
        except ValueError:
            entries = exits = [0.0] * 6
        out.append({
            'id':      m['id'],
            'name':    name.strip(),
            'lat':     float(m['lat']),
            'lng':     float(m['lng']),
            'zone':    0,
            'entries': entries,
            'exits':   exits,
        })
    return out


def best_component(multigeom, pt: Point):
    if multigeom.geom_type == 'LineString':
        return multigeom
    best, best_d = None, float('inf')
    for comp in multigeom.geoms:
        d = comp.distance(pt)
        if d < best_d:
            best_d = d
            best   = comp
    return best


def perp_offset(line_geom, station_pt: Point, mult: float):
    comp    = best_component(line_geom, station_pt)
    d       = comp.project(station_pt)
    ahead   = comp.interpolate(min(d + 0.0001, comp.length))
    behind  = comp.interpolate(max(d - 0.0001, 0.0))
    dx, dy  = ahead.x - behind.x, ahead.y - behind.y
    length  = math.hypot(dx, dy)
    if length < 1e-10:
        return station_pt.x, station_pt.y
    px, py   = dy / length, -dx / length
    offset_m = mult * LINE_W_Z12 * GROUND_RES_Z12
    lat      = station_pt.y
    return (station_pt.x + px * offset_m / (111_320 * math.cos(math.radians(lat))),
            station_pt.y + py * offset_m / 111_320)


def main():
    with open(BASE / 'tfl_lines.geojson', encoding='utf-8') as f:
        tfl_lines = json.load(f)

    line_geoms  = {}
    line_mult   = {}
    line_colour = {}

    for feat in tfl_lines['features']:
        p    = feat['properties']
        name = p['name']
        line_geoms[name]  = shape(feat['geometry'])
        line_mult[name]   = round(p.get('off12', 0.0) / LINE_W_Z12, 6)
        line_colour[name] = p.get('colour', '#888888')

    # ── Build station → line(s) from edge data (most reliable source) ─────────
    edges_path = BASE / 'tfl_edges.geojson'
    # station_line_votes[naptanid][line_name] = count of edges on that line
    station_line_votes: dict[str, Counter] = defaultdict(Counter)

    if edges_path.exists():
        with open(edges_path, encoding='utf-8') as f:
            edges_fc = json.load(f)
        for feat in edges_fc['features']:
            p    = feat['properties']
            lname = p.get('line', '')
            if lname not in TUBE_LINE_NAMES:
                continue
            station_line_votes[p['source']][lname] += 1
            station_line_votes[p['target']][lname] += 1
        print(f"Loaded {len(edges_fc['features'])} edge features; "
              f"{len(station_line_votes)} stations with edge-based line votes")
    else:
        print("WARNING: tfl_edges.geojson not found — falling back to geometry distance only")

    # ── Tube stations ─────────────────────────────────────────────────────────
    tube_raw = parse_cypher(NEO / 'tube_nodes.txt')
    print(f"Tube stations in Neo4J: {len(tube_raw)}")

    station_feats = []
    edge_assigned = 0
    geom_assigned = 0
    fallback_count = 0

    for s in tube_raw:
        pt    = Point(s['lng'], s['lat'])
        votes = station_line_votes.get(s['id'])

        if votes:
            # Use lines confirmed by edge data (most votes first, all tied get included)
            matched = sorted(votes.keys(), key=lambda k: -votes[k])
            edge_assigned += 1
        else:
            # No edge data — fall back to geometry distance
            matched = [lname for lname in TUBE_LINE_NAMES
                       if line_geoms.get(lname) is not None
                       and line_geoms[lname].distance(pt) <= MAX_PERP]
            if matched:
                geom_assigned += 1
            else:
                # Last resort: nearest tube line
                best_name, best_d = '', float('inf')
                for lname in TUBE_LINE_NAMES:
                    d = line_geoms[lname].distance(pt)
                    if d < best_d:
                        best_d, best_name = d, lname
                matched = [best_name]
                fallback_count += 1

        for lname in matched:
            geom = line_geoms.get(lname)
            mult = line_mult.get(lname, 0.0)
            if geom and abs(mult) > 1e-6:
                lng, lat = perp_offset(geom, pt, mult)
            else:
                lng, lat = s['lng'], s['lat']
            station_feats.append({
                'id':      s['id'],
                'name':    s['name'],
                'lat':     round(lat, 7),
                'lng':     round(lng, 7),
                'line':    lname,
                'colour':  line_colour.get(lname, '#888888'),
                'zone':    0,
                'entries': s['entries'],
                'exits':   s['exits'],
            })

    tube_records = len([f for f in station_feats if f['line'] in TUBE_LINE_NAMES])
    print(f"Tube station-line records : {tube_records}")
    print(f"  Edge-data assigned      : {edge_assigned}")
    print(f"  Geometry-distance match : {geom_assigned}")
    print(f"  Last-resort fallback    : {fallback_count}")

    # ── Overground ────────────────────────────────────────────────────────────
    ovr_raw = parse_cypher(NEO / 'overground_nodes.txt')
    for s in ovr_raw:
        station_feats.append({**s, 'line': 'Overground', 'colour': '#FF6600'})
    print(f"Overground stations: {len(ovr_raw)}")

    # ── DLR ───────────────────────────────────────────────────────────────────
    dlr_raw = parse_cypher(NEO / 'dlr_nodes.txt')
    for s in dlr_raw:
        station_feats.append({**s, 'line': 'DLR', 'colour': '#00AFAD'})
    print(f"DLR stations: {len(dlr_raw)}")

    out_path = BASE / 'stations.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(station_feats, f, separators=(',', ':'))

    size_kb = out_path.stat().st_size / 1024
    print(f"\nTotal records : {len(station_feats)}")
    print(f"Output        : {out_path}")
    print(f"Size          : {size_kb:.1f} KB")


if __name__ == '__main__':
    main()
