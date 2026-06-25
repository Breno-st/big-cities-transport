import json
import pandas as pd
from pathlib import Path

PERIODS = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']

def extract_stations_and_activity(basegraph_path, mode):
    with open(basegraph_path, 'r') as f:
        data = json.load(f)
    
    stations = {}
    activity_rows = []
    
    for node in data['nodes']:
        naptanid = node['naptanid']
        
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
    
    return stations, activity_rows

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
    
    for mode, filepath in modes.items():
        if filepath.exists():
            print(f"Processing {mode}...")
            stations, activity = extract_stations_and_activity(filepath, mode)
            for nid, s in stations.items():
                if nid in all_stations:
                    all_stations[nid]['modes'].update(s['modes'])
                else:
                    all_stations[nid] = s
            all_activity.extend(activity)
            print(f"  Stations: {len(stations)}, Activity rows: {len(activity)}")
        else:
            print(f"File not found: {filepath}")
    
    # Dim_Station
    station_list = []
    for s in all_stations.values():
        station_list.append({
            'naptanid': s['naptanid'],
            'name': s['name'],
            'lat': s['lat'],
            'lon': s['lon'],
            'modes': ','.join(sorted(s['modes'])),
        })
    df_station = pd.DataFrame(station_list)
    output_file = output_dir / 'dim_station.parquet'
    df_station.to_parquet(output_file, index=False)
    print(f"\nDim_Station: {len(df_station)} rows -> {output_file}")
    
    # Fact_StationActivity
    df_activity = pd.DataFrame(all_activity)
    output_file = output_dir / 'fact_station_activity.parquet'
    df_activity.to_parquet(output_file, index=False)
    print(f"Fact_StationActivity: {len(df_activity)} rows -> {output_file}")
    
    return df_station, df_activity

if __name__ == "__main__":
    path = Path("/Users/brenotiburcio/build/big-cities-transport/03.GraphModels")
    df_station, df_activity = export_all(path, "./output/dimensions")