"""
Build tfl_edges.geojson + stations.json.

Topology source : NUMBAT graph (614 directed links, 268 stations) — canonical,
                  no duplicates.
Line assignment  : Overpass route relations — for each consecutive OSM stop
                   pair, match both to the nearest NUMBAT naptanid; that pair
                   then belongs to the relation's line.  This is semantically
                   correct and immune to geometry-proximity false positives.
Edge geometry    : tfl_lines.geojson substring between the projected NUMBAT
                   station positions — smooth OSM-merged curves.
Offset           : perpendicular geographic offset baked into coordinates so
                   Mapbox symbol arrows follow the correct track (no line-offset
                   paint property needed).

Run after: fetch_tfl_overpass.py
"""

import json
import math
import re
from collections import defaultdict
from pathlib import Path

from shapely.geometry import LineString, Point, shape
from shapely.ops import substring

BASE   = Path(r'C:\buildbr\big-cities-transport\01.BaseGraph')
NUMBAT = Path(r'C:\buildbr\big-cities-transport\03.GraphModels\tube\tube-traffic-fri-am-peak.json')
NEO    = BASE / '02.Neo4J_Scripts' / 'nodes'

GROUND_RES_Z12 = 40_075_000 * math.cos(math.radians(51.5)) / (2**12 * 256)
LINE_W_Z12     = 3.5

SNAP_THRESHOLD  = 0.004   # °  ≈ 450 m — OSM stop → nearest NUMBAT station
GEOM_THRESHOLD  = 0.006   # °  ≈ 650 m — NUMBAT station → tfl_lines.geojson

LINE_PREFIX_MAP = {
    'Bakerloo':           'Bakerloo',
    'Central':            'Central',
    'Circle':             'Circle',
    'District':           'District',
    'Hammersmith & City': 'Hammersmith & City',
    'Jubilee':            'Jubilee',
    'Metropolitan':       'Metropolitan',
    'Northern':           'Northern',
    'Piccadilly':         'Piccadilly',
    'Victoria':           'Victoria',
    'Waterloo & City':    'Waterloo & City',
}

STRIP_SUFFIXES = [
    ' Underground Station', ' Rail Station', ' DLR Station', ' Station',
]


# ── Geometry helpers ───────────────────────────────────────────────────────────

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


def best_component_single(geom, pt: Point):
    if geom.geom_type == 'LineString':
        return geom
    best, best_d = None, float('inf')
    for comp in geom.geoms:
        d = comp.distance(pt)
        if d < best_d:
            best_d, best = d, comp
    return best


def extract_segment(geom, pt1: Point, pt2: Point):
    comp = best_component(geom, pt1, pt2)
    if comp is None:
        return None, False
    d1, d2 = comp.project(pt1), comp.project(pt2)
    if d1 == d2:
        return None, False
    perp = max(comp.interpolate(d1).distance(pt1),
               comp.interpolate(d2).distance(pt2))
    if perp > GEOM_THRESHOLD:
        return None, False
    rev  = d1 > d2
    lo, hi = (d1, d2) if not rev else (d2, d1)
    try:
        seg = substring(comp, lo, hi)
    except Exception:
        return None, False
    if seg is None or seg.is_empty or seg.length == 0:
        return None, False
    if seg.geom_type == 'MultiLineString':
        coords = []
        for s in seg.geoms:
            coords.extend(s.coords)
    else:
        coords = list(seg.coords)
    return coords, rev


def perp_shift(lng, lat, comp, mult):
    pt = Point(lng, lat)
    d  = comp.project(pt)
    a  = comp.interpolate(min(d + 0.0001, comp.length))
    b  = comp.interpolate(max(d - 0.0001, 0))
    dx, dy = a.x - b.x, a.y - b.y
    L = math.hypot(dx, dy)
    if L < 1e-10:
        return lng, lat
    px, py  = dy / L, -dx / L
    off_m   = mult * LINE_W_Z12 * GROUND_RES_Z12
    return (lng + px * off_m / (111_320 * math.cos(math.radians(lat))),
            lat + py * off_m / 111_320)


def offset_coords(coords, comp, mult):
    if abs(mult) < 1e-6:
        return [list(c) for c in coords]
    return [list(perp_shift(lng, lat, comp, mult)) for lng, lat in coords]


def offset_straight(coords, mult):
    if abs(mult) < 1e-6 or len(coords) < 2:
        return [list(c) for c in coords]
    lng1, lat1 = coords[0]
    lng2, lat2 = coords[-1]
    dx, dy  = lng2 - lng1, lat2 - lat1
    L       = math.hypot(dx, dy)
    if L < 1e-10:
        return [list(c) for c in coords]
    px, py   = dy / L, -dx / L
    lat_mid  = (lat1 + lat2) / 2
    off_m    = mult * LINE_W_Z12 * GROUND_RES_Z12
    dlat     = off_m / 111_320
    dlng     = off_m / (111_320 * math.cos(math.radians(lat_mid)))
    return [[lng + px * dlng, lat + py * dlat] for lng, lat in coords]


def normalize_line(osm_name: str) -> str | None:
    lo = osm_name.lower()
    for key, canonical in LINE_PREFIX_MAP.items():
        if lo.startswith(key.lower() + ' line'):
            return canonical
    return None


def parse_cypher_basic(path: Path) -> list[dict]:
    pat = re.compile(
        r"naptanid:'(?P<id>[^']+)'.*?name:'(?P<name>[^']+)'.*?"
        r"lat:(?P<lat>[\d.]+),long:(?P<lng>[-\d.]+)"
    )
    out = []
    for row in path.read_text(encoding='utf-8').splitlines():
        m = pat.search(row)
        if not m:
            continue
        name = m['name']
        for suf in STRIP_SUFFIXES:
            name = name.replace(suf, '')
        out.append({'id': m['id'], 'name': name.strip(),
                    'lat': float(m['lat']), 'lng': float(m['lng'])})
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # ── Load tfl_lines.geojson (geometry + offsets) ───────────────────────────
    with open(BASE / 'tfl_lines.geojson', encoding='utf-8') as f:
        tfl_lines = json.load(f)

    line_geoms  = {}
    line_mult   = {}
    line_colour = {}
    line_offs   = {}
    for feat in tfl_lines['features']:
        p = feat['properties']
        n = p['name']
        line_geoms[n]  = shape(feat['geometry'])
        line_mult[n]   = round(p.get('off12', 0.0) / LINE_W_Z12, 6)
        line_colour[n] = p.get('colour', '#888888')
        line_offs[n]   = {'off9': p.get('off9', 0.0), 'off12': p.get('off12', 0.0), 'off14': p.get('off14', 0.0)}

    # ── Load NUMBAT graph ─────────────────────────────────────────────────────
    with open(NUMBAT, encoding='utf-8') as f:
        numbat = json.load(f)

    nodes_by_id  = {n['id']: n for n in numbat['nodes']}
    numbat_nodes = numbat['nodes']   # list for nearest-neighbour search

    # Build fast naptanid lookup
    naptan_to_node = {n['naptanid']: n for n in numbat_nodes}
    print(f"NUMBAT: {len(numbat_nodes)} nodes, {len(numbat['links'])} links")

    # ── Build link→lines table from Overpass route relations ─────────────────
    # Reverse matching: for each NUMBAT link, scan all route relations and check
    # if the nearest stop to src AND the nearest stop to tgt are consecutive in
    # that relation.  This avoids the forward-matching pitfall where a W&C Bank
    # stop (physically between Cannon St and Bank) snaps to the wrong NUMBAT node.
    with open(BASE / 'overpass_tfl_routes.json', encoding='utf-8') as f:
        overpass = json.load(f)

    relations = [e for e in overpass['elements'] if e['type'] == 'relation']
    print(f"Overpass relations: {len(relations)}")

    # Pre-process each relation: extract ordered stops, merging same-station
    # duplicates (two platform nodes within 0.001° of each other).
    rel_data: list[tuple[str, list[dict]]] = []
    for rel in relations:
        lname = normalize_line(rel['tags'].get('name', ''))
        if lname is None:
            continue
        raw = [m for m in rel['members']
               if m['type'] == 'node'
               and m.get('role', '') in ('stop', 'stop_entry_only', 'stop_exit_only')]
        merged: list[dict] = []
        for s in raw:
            if (merged and
                    math.hypot(s['lat'] - merged[-1]['lat'],
                               s['lon'] - merged[-1]['lon']) < 0.001):
                # Average into existing merged stop
                n  = merged[-1].get('_n', 1) + 1
                merged[-1] = {
                    'lat': (merged[-1]['lat'] * (n - 1) + s['lat']) / n,
                    'lon': (merged[-1]['lon'] * (n - 1) + s['lon']) / n,
                    '_n': n,
                }
            else:
                merged.append({'lat': s['lat'], 'lon': s['lon'], '_n': 1})
        if len(merged) >= 2:
            rel_data.append((lname, merged))

    # For each NUMBAT link scan every route relation (reverse matching).
    link_lines: dict[tuple, set] = defaultdict(set)

    for link in numbat['links']:
        src    = nodes_by_id[link['source']]
        tgt    = nodes_by_id[link['target']]
        src_nid = src['naptanid']
        tgt_nid = tgt['naptanid']
        slat, slon = src['lat'], src['long']
        tlat, tlon = tgt['lat'], tgt['long']

        for lname, stops in rel_data:
            # Find nearest merged stop to src
            si, sd = min(((i, math.hypot(st['lat'] - slat, st['lon'] - slon))
                          for i, st in enumerate(stops)),
                         key=lambda x: x[1])
            # Find nearest merged stop to tgt
            ti, td = min(((i, math.hypot(st['lat'] - tlat, st['lon'] - tlon))
                          for i, st in enumerate(stops)),
                         key=lambda x: x[1])

            if not (sd <= SNAP_THRESHOLD and td <= SNAP_THRESHOLD
                    and si != ti and abs(si - ti) == 1):
                continue

            # Sanity check: if the matched OSM stop is significantly closer to a
            # different NUMBAT node (< 50 % of the match distance), this is a
            # false positive caused by nearby parallel lines
            # (e.g., Paddington Circle stop falsely matching Lancaster Gate Central).
            # W&C Bank (343 m to Bank, 205 m to Cannon St ≈ 60 %) is kept.
            sst, tst = stops[si], stops[ti]
            cs = min(numbat_nodes,
                     key=lambda n: math.hypot(n['lat'] - sst['lat'], n['long'] - sst['lon']))
            ct = min(numbat_nodes,
                     key=lambda n: math.hypot(n['lat'] - tst['lat'], n['long'] - tst['lon']))
            cs_d = math.hypot(cs['lat'] - sst['lat'], cs['long'] - sst['lon'])
            ct_d = math.hypot(ct['lat'] - tst['lat'], ct['long'] - tst['lon'])
            if cs['naptanid'] != src_nid and cs_d < sd * 0.5:
                continue
            if ct['naptanid'] != tgt_nid and ct_d < td * 0.5:
                continue

            link_lines[(src_nid, tgt_nid)].add(lname)

    print(f"Unique directed links with line data: {len(link_lines)}")

    # ── Build edges from NUMBAT links ─────────────────────────────────────────
    out_edges_cl   = []   # centerline: no offset baked in; off9/off12/off14 in props
    out_edges_off  = []   # pre-offset: offset baked in; off9/off12/off14 = 0
    stats_matched  = 0
    stats_fallback = 0
    stats_noline   = 0

    for link in numbat['links']:
        src = nodes_by_id[link['source']]
        tgt = nodes_by_id[link['target']]
        src_nid = src['naptanid']
        tgt_nid = tgt['naptanid']
        src_pt  = Point(src['long'], src['lat'])
        tgt_pt  = Point(tgt['long'], tgt['lat'])
        src_name = src['name'].replace(' Underground Station', '').replace(' Station', '')
        tgt_name = tgt['name'].replace(' Underground Station', '').replace(' Station', '')
        traffic  = round(link['traffic'], 4)

        lines = link_lines.get((src_nid, tgt_nid))

        if not lines:
            # No route relation covers this NUMBAT link — fall back to nearest
            # tube line by geometry so the link still appears in the map.
            best_lname, best_d = '', float('inf')
            for lname, geom in line_geoms.items():
                if lname not in LINE_PREFIX_MAP.values():
                    continue
                d = geom.distance(src_pt) + geom.distance(tgt_pt)
                if d < best_d:
                    best_d, best_lname = d, lname
            lines = {best_lname}
            stats_noline += 1

        for lname in lines:
            geom   = line_geoms.get(lname)
            mult   = line_mult.get(lname, 0.0)
            colour = line_colour.get(lname, '#888888')
            offs   = line_offs.get(lname, {'off9': 0.0, 'off12': 0.0, 'off14': 0.0})

            raw_coords, rev = (None, False) if geom is None else extract_segment(geom, src_pt, tgt_pt)

            if raw_coords is not None:
                coords     = raw_coords if not rev else raw_coords[::-1]
                comp       = best_component(geom, src_pt, tgt_pt)
                off_coords = offset_coords(coords, comp, mult)
                stats_matched += 1
            else:
                coords     = [[src['long'], src['lat']], [tgt['long'], tgt['lat']]]
                off_coords = offset_straight(coords, mult)
                stats_fallback += 1

            base_props = {
                'id':         f'{src_nid}-{tgt_nid}-{lname}',
                'source':     src_nid,
                'target':     tgt_nid,
                'sourceName': src_name,
                'targetName': tgt_name,
                'line':       lname,
                'colour':     colour,
                'color':      colour,
                'traffic':    traffic,
            }

            # Centerline feature: OSM coords, actual offset values in properties
            out_edges_cl.append({
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': [list(c) for c in coords]},
                'properties': {**base_props, **offs},
            })

            # Pre-offset feature: offset coords, zero offset values in properties
            out_edges_off.append({
                'type': 'Feature',
                'geometry': {'type': 'LineString', 'coordinates': off_coords},
                'properties': {**base_props, 'off9': 0.0, 'off12': 0.0, 'off14': 0.0},
            })

    for i, feat in enumerate(out_edges_cl):
        feat['id'] = i
    for i, feat in enumerate(out_edges_off):
        feat['id'] = i

    # ── Station dots: geometric projection + perpendicular offset ────────────
    # ep-averaging fails at branching/terminal stations on offset lines: edges
    # going in opposite directions produce perpendicular offsets that cancel
    # (e.g. Circle at Ladbroke Grove: east→WBP shifts SOUTH, west→LTR shifts
    # NORTH, average = H&C track center).  Use best_component_single projection
    # instead — consistent regardless of edge directions.

    station_lines: dict[str, set] = defaultdict(set)
    for (src_nid, tgt_nid), lines in link_lines.items():
        for lname in lines:
            station_lines[src_nid].add(lname)
            station_lines[tgt_nid].add(lname)

    station_feats = []

    for n in numbat_nodes:
        nid   = n['naptanid']
        name  = n['name']
        for suf in STRIP_SUFFIXES:
            name = name.replace(suf, '')
        name = name.strip()

        lines = station_lines.get(nid)
        if not lines:
            best_lname, best_d = '', float('inf')
            pt = Point(n['long'], n['lat'])
            for lname, geom in line_geoms.items():
                if lname not in LINE_PREFIX_MAP.values():
                    continue
                d = geom.distance(pt)
                if d < best_d:
                    best_d, best_lname = d, lname
            lines = {best_lname}

        for lname in lines:
            colour = line_colour.get(lname, '#888888')
            geom   = line_geoms.get(lname)
            mult   = line_mult.get(lname, 0.0)
            lon, lat = n['long'], n['lat']
            if geom is not None:
                comp = best_component_single(geom, Point(lon, lat))
                d    = comp.project(Point(lon, lat))
                proj = comp.interpolate(d)
                lon, lat = proj.x, proj.y
                if abs(mult) > 1e-6:
                    lon, lat = perp_shift(lon, lat, comp, mult)

            station_feats.append({
                'id':      nid,
                'name':    name,
                'lat':     round(lat, 7),
                'lng':     round(lon, 7),
                'line':    lname,
                'colour':  colour,
                'zone':    0,
                'entries': n.get('entries', []),
                'exits':   n.get('exits', []),
            })

    # ── Write tfl_edges.geojson (centerline) and tfl_edges_arrows.geojson ────
    import shutil
    from collections import Counter

    cl_fc   = {'type': 'FeatureCollection', 'features': out_edges_cl}
    cl_path = BASE / 'tfl_edges.geojson'
    with open(cl_path, 'w', encoding='utf-8') as f:
        json.dump(cl_fc, f, separators=(',', ':'))

    off_fc   = {'type': 'FeatureCollection', 'features': out_edges_off}
    off_path = BASE / 'tfl_edges_arrows.geojson'
    with open(off_path, 'w', encoding='utf-8') as f:
        json.dump(off_fc, f, separators=(',', ':'))

    cl_kb  = cl_path.stat().st_size / 1024
    off_kb = off_path.stat().st_size / 1024
    line_dist = Counter(f['properties']['line'] for f in out_edges_cl)
    print(f"\nEdges (centerline → tfl_edges.geojson)")
    print(f"  OSM-geometry matched : {stats_matched}")
    print(f"  Straight fallback    : {stats_fallback}")
    print(f"  No-route fallback    : {stats_noline}")
    print(f"  Total features       : {len(out_edges_cl)}")
    print(f"  File                 : {cl_path}  ({cl_kb:.1f} KB)")
    for lname, cnt in sorted(line_dist.items(), key=lambda x: -x[1]):
        print(f"    {lname:35s} {cnt:4d}")

    print(f"\nEdges (pre-offset → tfl_edges_arrows.geojson)")
    print(f"  Total features       : {len(out_edges_off)}")
    print(f"  File                 : {off_path}  ({off_kb:.1f} KB)")

    # Copy to Angular assets
    ASSETS = Path(r'C:\buildbr\bt-fnt\fntweb\src\assets\data')
    shutil.copy2(cl_path,  ASSETS / 'tfl_edges.geojson')
    shutil.copy2(off_path, ASSETS / 'tfl_edges_arrows.geojson')
    print(f"\nCopied to Angular assets: {ASSETS}")

    # OVR and DLR from Neo4J
    neo_ovr = parse_cypher_basic(NEO / 'overground_nodes.txt')
    neo_dlr = parse_cypher_basic(NEO / 'dlr_nodes.txt')
    for s in neo_ovr:
        station_feats.append({**s, 'line': 'Overground', 'colour': '#FF6600',
                               'zone': 0, 'entries': [], 'exits': []})
    for s in neo_dlr:
        station_feats.append({**s, 'line': 'DLR', 'colour': '#00AFAD',
                               'zone': 0, 'entries': [], 'exits': []})

    stations_path = BASE / 'stations.json'
    with open(stations_path, 'w', encoding='utf-8') as f:
        json.dump(station_feats, f, separators=(',', ':'))

    size_kb2     = stations_path.stat().st_size / 1024
    tube_dots    = sum(1 for s in station_feats if s['line'] not in ('Overground','DLR'))
    unique_stns  = len({s['id'] for s in station_feats if s['line'] not in ('Overground','DLR')})
    print(f"\nStations")
    print(f"  Tube unique stations : {unique_stns}")
    print(f"  Tube station-line    : {tube_dots}")
    print(f"  OVR                  : {len(neo_ovr)}")
    print(f"  DLR                  : {len(neo_dlr)}")
    print(f"  Total records        : {len(station_feats)}")
    print(f"  File                 : {stations_path}  ({size_kb2:.1f} KB)")


if __name__ == '__main__':
    main()
