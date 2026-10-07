"""
Rebuild tfl_community_edges.geojson so that each physical station is
represented by exactly one node, regardless of how many naptanids TfL
uses for it (e.g. Barking appears as both 910GBARKING and 940GZZLUBKG).

Algorithm
---------
1. Collect all (naptanid, name) pairs from edge src/tgt properties.
2. Group naptanids by station name.
3. For each name-group, choose a canonical naptanid
   (prefer 940G tube IDs; fall back to the most-connected one).
4. Remap every edge endpoint to the canonical naptanid.
5. Merge parallel edges that become identical after remapping
   (sum weight, take min distance_km, keep first geometry).
6. Drop self-loops (src_canonical == tgt_canonical).
7. Write the cleaned GeoJSON back to the assets folder.
"""

import json
from pathlib import Path
from collections import defaultdict

SRC  = Path(r'C:\buildbr\bt-fnt\fntweb\src\assets\data\tfl_community_edges.geojson')
DEST = Path(r'C:\buildbr\bt-fnt\fntweb\src\assets\data\tfl_community_edges.geojson')

# ── Load ──────────────────────────────────────────────────────────────────────
with open(SRC, encoding='utf-8') as f:
    data = json.load(f)

features = data['features']
print(f'Input:  {len(features)} edges')

# ── Step 1: collect (naptanid → name) ────────────────────────────────────────
naptanid_name: dict[str, str] = {}
for feat in features:
    p = feat['properties']
    naptanid_name[p['src']] = p['src_name']
    naptanid_name[p['tgt']] = p['tgt_name']

# ── Step 2: group naptanids by station name ───────────────────────────────────
name_to_ids: dict[str, list[str]] = defaultdict(list)
for nid, name in naptanid_name.items():
    name_to_ids[name].append(nid)

# Duplicates (same name, >1 naptanid)
dups = {name: ids for name, ids in name_to_ids.items() if len(ids) > 1}
print(f'Station names with multiple naptanids: {len(dups)}')
for name, ids in sorted(dups.items()):
    print(f'  {name}: {sorted(ids)}')

# ── Step 3: choose canonical naptanid ────────────────────────────────────────
# Preference order: 940G (TfL tube internal) > 910G (national rail) > anything else
def canonical_for(ids: list[str]) -> str:
    tube_ids  = [i for i in ids if i.startswith('940G')]
    rail_ids  = [i for i in ids if i.startswith('910G')]
    # Count edge appearances to break ties
    counts = defaultdict(int)
    for feat in features:
        p = feat['properties']
        if p['src'] in ids:
            counts[p['src']] += 1
        if p['tgt'] in ids:
            counts[p['tgt']] += 1
    if tube_ids:
        return max(tube_ids, key=lambda i: counts[i])
    if rail_ids:
        return max(rail_ids, key=lambda i: counts[i])
    return max(ids, key=lambda i: counts[i])

# naptanid → canonical_naptanid (identity for unique stations)
remap: dict[str, str] = {}
for nid in naptanid_name:
    name = naptanid_name[nid]
    group = name_to_ids[name]
    remap[nid] = canonical_for(group) if len(group) > 1 else nid

# ── Step 4 & 5: remap endpoints, merge parallel edges ────────────────────────
# Key: (canonical_src, canonical_tgt) — undirected, so normalise order
merged: dict[tuple[str,str], dict] = {}

for feat in features:
    p    = feat['properties']
    geom = feat['geometry']

    csrc = remap[p['src']]
    ctgt = remap[p['tgt']]

    # Step 6: drop self-loops
    if csrc == ctgt:
        continue

    # Normalise direction for undirected dedup
    key = (csrc, ctgt) if csrc < ctgt else (ctgt, csrc)

    if key not in merged:
        merged[key] = {
            'src':      key[0],
            'tgt':      key[1],
            'src_name': naptanid_name[remap[p['src']]],
            'tgt_name': naptanid_name[remap[p['tgt']]],
            'distance_km': float(p.get('distance_km', 0) or 0),
            'mode':    p.get('mode', 'tube'),
            'geometry': geom,
        }
    else:
        # Aggregate: minimum distance (shortest route between the pair)
        merged[key]['distance_km'] = min(
            merged[key]['distance_km'],
            float(p.get('distance_km', 0) or 0)
        )

print(f'Output: {len(merged)} edges (removed {len(features) - len(merged)} duplicates/self-loops)')

# ── Build output GeoJSON ──────────────────────────────────────────────────────
out_features = []
for entry in merged.values():
    d = entry['distance_km']
    # weight = 1/distance_km for community detection (nearby stations → high weight)
    # guard against zero-distance entries
    inv_d = round(1.0 / d, 6) if d > 0 else 9999.0
    out_features.append({
        'type': 'Feature',
        'geometry': entry['geometry'],
        'properties': {
            'src':         entry['src'],
            'tgt':         entry['tgt'],
            'src_name':    entry['src_name'],
            'tgt_name':    entry['tgt_name'],
            'weight':      inv_d,
            'distance_km': round(d, 4),
            'mode':        entry['mode'],
        },
    })

out = {'type': 'FeatureCollection', 'features': out_features}

with open(DEST, 'w', encoding='utf-8') as f:
    json.dump(out, f, separators=(',', ':'))

print(f'Written to {DEST}')
