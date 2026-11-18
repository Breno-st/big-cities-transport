import json
import pickle
import pandas as pd
from pathlib import Path


def load_pickle(filename):
    with open(filename, 'rb') as handle:
        return pickle.load(handle)


def load_station_id_map(id_map_path):
    """
    Load per-mode basegraph_id → canonical_id map from 08_stations_to_parquet.py output.
    JSON keys are strings; basegraph_id keys are cast to int.
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


def unpickle_ranks_to_dataframe(pickle_path, od, kpi, mode_map=None):
    """
    Converts the nested kpi_dic into a flat DataFrame matching Fact_EdgeRanking.

    mode_map: optional dict {basegraph_id (int): canonical_id (int)} for this mode.
    When provided, translates Neo4j-local edge source/target IDs to canonical IDs.
    """
    data = load_pickle(pickle_path)
    rows = []

    for day, periods_dict in data.items():
        for period, cols_dict in periods_dict.items():
            # Get the set of all edges across all columns
            edges = set()
            for col_vals in cols_dict.values():
                edges.update(col_vals.keys())

            for edge_str in edges:
                # edge_str looks like "(id0, id1)"
                origin, dest = edge_str.strip("()").split(", ")
                origin_raw = int(origin.strip("'"))
                dest_raw   = int(dest.strip("'"))

                # Translate to canonical IDs if map is available
                if mode_map:
                    origin_id = mode_map.get(origin_raw, origin_raw)
                    dest_id   = mode_map.get(dest_raw,   dest_raw)
                else:
                    origin_id = origin_raw
                    dest_id   = dest_raw

                rows.append({
                    "origin_station_id": origin_id,
                    "dest_station_id":   dest_id,
                    "day":               day,
                    "period":            period,
                    "mode":              od,
                    "weight":            cols_dict.get(kpi, {}).get(edge_str),
                    "weight_rnk":        cols_dict.get(f"{kpi}_rnk", {}).get(edge_str),
                    "alpha":             cols_dict.get("alpha", {}).get(edge_str),
                    "alpha_rnk":         cols_dict.get("alpha_rnk", {}).get(edge_str),
                })

    return pd.DataFrame(rows)


# Usage
if __name__ == "__main__":
    path     = Path("/Users/brenotiburcio/build/big-cities-transport/04.Disparity/01.Input")
    id_map_p = Path("./output/dimensions/station_id_map.json")
    ods  = ['tube', 'dlr', 'overground']
    kpis = ['traffic', 'efficiencies', 'distress']

    station_id_map = load_station_id_map(id_map_p)

    for od in ods:
        mode_map = station_id_map.get(od, {})
        for kpi in kpis:
            pickle_file = path / od / f"{od}-{kpi}.pickle"
            df = unpickle_ranks_to_dataframe(pickle_file, od, kpi, mode_map=mode_map)
            df.to_parquet(
                f"./output/edge_rankings/{od}/{kpi}/",
                partition_cols=["mode", "day"],
                index=False
            )
            print(f"Wrote {len(df)} rows for {od}/{kpi}")
