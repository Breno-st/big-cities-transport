import json
import pandas as pd
from pathlib import Path

PERIODS = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']
DAYS = ['mtt', 'fri', 'sat', 'sun']
MODES = ['tube', 'dlr', 'overground']
# KPIs that vary by time
TIME_VARIANT_KPIS = ['distress', 'traffic', 'traffic_distances', 'loads', 'efficiencies']
# KPIs that are time-invariant (constant across days/periods)
TIME_INVARIANT_KPIS = ['distance', 'speed']

def extract_time_variant(graph_dir, output_dir):
    """
    Extract edge KPI values from time-variant graph JSONs.
    File pattern: {od}-{kpi}-{day}-{period}.json
    """
    graph_dir = Path(graph_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    rows = []
    
    for mode in MODES:
        mode_dir = graph_dir / mode
        if not mode_dir.exists():
            print(f"Directory not found: {mode_dir}")
            continue
        
        for kpi in TIME_VARIANT_KPIS:
            for day in DAYS:
                for period in PERIODS:
                    # Build filename: dlr-distress-fri-AM-Peak.json
                    auxk = kpi.replace('_', '')
                    auxp = period.replace(' ', '-')
                    filename = f"{mode}-{auxk}-{day.lower()}-{auxp.lower()}.json"
                    filepath = mode_dir / filename
                    
                    if not filepath.exists():
                        continue  # Not all combos exist, skip silently
                    
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    
                    for link in data.get('links', []):
                        # The KPI field name varies per file (traffic, distress, etc.)
                        # It's the only field besides 'source' and 'target'
                        kpi_value = None
                        for key, val in link.items():
                            if key not in ('source', 'target'):
                                kpi_value = val
                                break
                        
                        rows.append({
                            'mode': mode,
                            'origin_station_id': link['source'],
                            'dest_station_id': link['target'],
                            'day': day,
                            'period': period,
                            'kpi': kpi,
                            'value': kpi_value,
                            'time_granularity': 'period',
                        })
                    
                    print(f"  Processed: {filename} ({len(data.get('links', []))} edges)")
    
    df = pd.DataFrame(rows)
    output_file = output_dir / 'fact_edge_activity.parquet'
    df.to_parquet(output_file, index=False)
    print(f"\nTotal rows: {len(df)}")
    print(f"Saved to: {output_file}")
    print(f"Modes: {df['mode'].unique()}")
    print(f"KPIs: {df['kpi'].unique()}")
    print(f"Days: {df['day'].unique()}")
    return df


if __name__ == "__main__":
    path = Path("/Users/brenotiburcio/build/big-cities-transport/03.GraphModels")
    df = extract_time_variant(path, "./output/edge_activity")