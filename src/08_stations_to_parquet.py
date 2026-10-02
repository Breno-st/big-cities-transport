import json
import pickle
import pandas as pd
from pathlib import Path

PERIODS = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']

def extract_stations_and_activity(basegraph_path, mode):
    with open(basegraph_path, 'r') as f:
        data = json.load(f)

    stations = {}
    activity_rows = []
    basegraph_id_to_naptanid = {}  # Neo4j internal id → naptanid for this mode

    for node in data['nodes']:
        naptanid = node['naptanid']
        node_id = node['id']  # Neo4j-local integer — may collide across mode DBs
        basegraph_id_to_naptanid[node_id] = naptanid

        if naptanid not in stations:
            stations[naptanid] = {
                'naptanid': naptanid,
                'name': node.get('name', ''),
                'lat': node.get('lat'),
                'lon': node.get('long'),
                'modes': {mode},
            }
        else:
            stations[naptanid]['modes'].add(mode)

        entries = node.get('entries', [])
        exits = node.get('exits', [])

        for i, period in enumerate(PERIODS):
            if i < len(entries):
                activity_rows.append({
                    'naptanid': naptanid,
                    'period': period,
                    'mode': mode,
                    'entries': entries[i],
                    'exits': exits[i],
                    'time_granularity': 'period',
                })

    return stations, activity_rows, basegraph_id_to_naptanid

def export_all(basegraph_dir, output_dir):
    basegraph_dir = Path(basegraph_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    modes = {
        'tube': basegraph_dir / 'tube' / 'tube-basegraph.json',
        'dlr': basegraph_dir / 'dlr' / 'dlr-basegraph.json',
        'overground': basegraph_dir / 'overground' / 'overground-basegraph.json',
    }

    all_stations = {}
    all_activity = []
    per_mode_basegraph_to_naptanid = {}  # {mode: {basegraph_id: naptanid}}

    for mode, filepath in modes.items():
        if filepath.exists():
            print(f"Processing {mode}...")
            stations, activity, basegraph_id_to_naptanid = extract_stations_and_activity(filepath, mode)
            per_mode_basegraph_to_naptanid[mode] = basegraph_id_to_naptanid
            for naptanid, s in stations.items():
                if naptanid in all_stations:
                    all_stations[naptanid]['modes'].update(s['modes'])
                else:
                    all_stations[naptanid] = s
            all_activity.extend(activity)
            print(f"  Stations: {len(stations)}, Activity rows: {len(activity)}")
        else:
            print(f"File not found: {filepath}")

    # Assign globally unique canonical IDs: sorted by naptanid, 1-indexed.
    # This ensures station_id is unique across ALL modes, regardless of Neo4j DB.
    sorted_naptanids = sorted(all_stations.keys())
    naptanid_to_canonical = {nap: idx + 1 for idx, nap in enumerate(sorted_naptanids)}

    # Build per-mode translation map: {mode: {basegraph_id (int): canonical_id (int)}}
    per_mode_canonical = {}
    for mode, id_to_nap in per_mode_basegraph_to_naptanid.items():
        per_mode_canonical[mode] = {
            basegraph_id: naptanid_to_canonical[naptanid]
            for basegraph_id, naptanid in id_to_nap.items()
        }

    # Save translation map — required by 09_edges_kpis_to_parquet.py and 07_pickle_to_parquet.py
    id_map_path = output_dir / 'station_id_map.json'
    with open(id_map_path, 'w') as f:
        json.dump(per_mode_canonical, f)
    print(f"\nStation ID map saved to {id_map_path}")
    print(f"  Modes covered: {list(per_mode_canonical.keys())}")

    # Dim_Station — one row per station, station_id is now globally unique
    station_list = []
    for naptanid in sorted_naptanids:
        s = all_stations[naptanid]
        station_list.append({
            'id': naptanid_to_canonical[naptanid],
            'naptanid': s['naptanid'],
            'name': s['name'],
            'lat': s['lat'],
            'lon': s['lon'],
            'modes': ','.join(sorted(s['modes'])),
        })
    df_station = pd.DataFrame(station_list)
    df_station.to_parquet(output_dir / 'dim_station.parquet', index=False)
    print(f"Dim_Station: {len(df_station)} rows (all station_id values unique: {df_station['id'].nunique() == len(df_station)})")

    # Fact_StationActivity
    df_activity = pd.DataFrame(all_activity)
    df_activity.to_parquet(output_dir / 'fact_station_activity.parquet', index=False)
    print(f"Fact_StationActivity: {len(df_activity)} rows")

    return df_station, df_activity, per_mode_canonical

if __name__ == "__main__":
    path = Path("/Users/brenotiburcio/build/big-cities-transport/03.GraphModels")
    df_station, df_activity, id_map = export_all(path, "./output/dimensions")
    print(f"\nID map entries per mode: { {m: len(v) for m, v in id_map.items()} }")
