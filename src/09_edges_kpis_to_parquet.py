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

def load_station_id_map(id_map_path):
    """
    Load the per-mode basegraph_id → canonical_id translation map produced by
    08_stations_to_parquet.py.  JSON keys are strings; cast basegraph_ids to int.
    """
    if id_map_path and Path(id_map_path).exists():
        with open(id_map_path, 'r') as f:
            raw = json.load(f)
        result = {
            mode: {int(k): v for k, v in id_map.items()}
            for mode, id_map in raw.items()
        }
        print(f"Loaded station ID map for modes: {list(result.keys())}")
        return result
    print("WARNING: station_id_map.json not found — station IDs may collide across modes.")
    return {}

def extract_time_variant(graph_dir, output_dir, id_map_path=None):
    """
    Extract edge KPI values from time-variant graph JSONs.
    File pattern: {od}-{kpi}-{day}-{period}.json

    Applies canonical station ID translation when id_map_path is provided,
    ensuring origin_station_id / dest_station_id are globally unique across modes.
    """
    graph_dir = Path(graph_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    station_id_map = load_station_id_map(id_map_path)

    rows = []

    for mode in MODES:
        mode_map = station_id_map.get(mode, {})
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
                        kpi_value = None
                        for key, val in link.items():
                            if key not in ('source', 'target'):
                                kpi_value = val
                                break

                        # Translate Neo4j-local IDs → globally unique canonical IDs
                        src = mode_map.get(link['source'], link['source'])
                        tgt = mode_map.get(link['target'], link['target'])

                        rows.append({
                            'mode': mode,
                            'origin_station_id': src,
                            'dest_station_id': tgt,
                            'day': day,
                            'period': period,
                            'kpi': kpi,
                            'value': kpi_value,
                            'time_granularity': 'period',
                        })

                    print(f"  Processed: {filename} ({len(data.get('links', []))} edges)")

    df = pd.DataFrame(rows)

    # fact_edge_activity.parquet
    output_file = output_dir / 'fact_edge_activity.parquet'
    df.to_parquet(output_file, index=False)
    print(f"\nfact_edge_activity: {len(df)} rows → {output_file}")
    print(f"Modes: {df['mode'].unique()}")
    print(f"KPIs: {df['kpi'].unique()}")
    print(f"Days: {df['day'].unique()}")

    # Derive dim_edge.parquet — unique (mode, origin_station_id, dest_station_id) combinations.
    # Used by warehouse_load.sql step 5 to populate Dim_Edge.
    dim_output_dir = output_dir.parent / 'dimensions'
    dim_output_dir.mkdir(parents=True, exist_ok=True)
    df_edge_dim = (
        df[['mode', 'origin_station_id', 'dest_station_id']]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    dim_edge_path = dim_output_dir / 'dim_edge.parquet'
    df_edge_dim.to_parquet(dim_edge_path, index=False)
    print(f"dim_edge: {len(df_edge_dim)} unique (mode, origin, dest) → {dim_edge_path}")

    return df


if __name__ == "__main__":
    path = Path("/Users/brenotiburcio/build/big-cities-transport/03.GraphModels")
    id_map_path = "./output/dimensions/station_id_map.json"
    df = extract_time_variant(path, "./output/edge_activity", id_map_path)
