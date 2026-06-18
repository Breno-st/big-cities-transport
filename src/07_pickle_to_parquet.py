import pickle
import pandas as pd
from pathlib import Path

def load_pickle(filename):
    with open(filename, 'rb') as handle:
        return pickle.load(handle)

def unpickle_ranks_to_dataframe(pickle_path, od, kpi):
    """
    Converts the nested kpi_dic into a flat DataFrame matching Fact_EdgeRanking.
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
                origin = origin.strip("'")
                dest = dest.strip("'")

                rows.append({
                    "origin_station_id": origin,
                    "dest_station_id": dest,
                    "day": day,
                    "period": period,
                    "mode": od,
                    "weight": cols_dict.get(kpi, {}).get(edge_str),
                    "weight_rnk": cols_dict.get(f"{kpi}_rnk", {}).get(edge_str),
                    "alpha": cols_dict.get("alpha", {}).get(edge_str),
                    "alpha_rnk": cols_dict.get("alpha_rnk", {}).get(edge_str),
                })

    return pd.DataFrame(rows)

# Usage
if __name__ == "__main__":
    path = Path("/Users/brenotiburcio/build/big-cities-transport/04.Disparity/01.Input")
    ods = ['tube', 'dlr', 'overground'] # 
    kpis = ['traffic', 'efficiencies', 'distress']


    for od in ods:
        for kpi in kpis:
            pickle_file = path / od / f"{od}-{kpi}.pickle"
            df = unpickle_ranks_to_dataframe(pickle_file, od, kpi)
            # Partition by mode and day for efficient querying
            df.to_parquet(
                f"./output/edge_rankings/{od}/{kpi}/",
                partition_cols=["mode", "day"],
                index=False
            )
            print(f"Wrote {len(df)} rows for {od}/{kpi}")