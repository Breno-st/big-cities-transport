"""
compute_distance_backbone.py
----------------------------
Compute disparity + GloSS backbone significance for static distance graphs.

Loads {mode}-distance.json for tube, dlr, overground, runs the same algorithms
as the rank_edges Fabric notebook (Cell 2), and exports a parquet file to upload
to Fabric transit_lh as Files/edge_rankings/distance/distance_backbone.parquet.

After upload:
  1. Run load_distance_backbone notebook in Fabric to write fact_distance_backbone_staging
  2. Run distance_rank_load.sql in the Warehouse SQL Editor

Weight used: raw distance_km (as per disparity/GloSS convention — high distance from
a node = anomalously large = structurally significant backbone edge).
"""

import json
import sys
import numpy as np
import pandas as pd
from pathlib import Path

BASE       = Path(r'C:\buildbr\big-cities-transport')
GRAPH_DIR  = BASE / '03.GraphModels'
ID_MAP     = BASE / 'output' / 'dimensions' / 'station_id_map.json'
OUT_DIR    = BASE / 'output' / 'edge_rankings' / 'distance'
MODES      = ['tube', 'dlr', 'overground']


def load_station_id_map() -> dict:
    with open(ID_MAP) as f:
        raw = json.load(f)
    return {mode: {int(k): v for k, v in m.items()} for mode, m in raw.items()}


def disparity_filter(pdf: pd.DataFrame) -> pd.DataFrame:
    """Serrano et al. (2009) — same implementation as rank_edges notebook Cell 2."""
    out_deg = pdf.groupby("origin_station_id").size().to_dict()
    in_deg  = pdf.groupby("dest_station_id").size().to_dict()
    out_str = pdf.groupby("origin_station_id")["weight"].sum().to_dict()

    def total_degree(node: int) -> int:
        return out_deg.get(node, 0) + in_deg.get(node, 0)

    def integral(x: float, k: float) -> float:
        return ((1.0 - x) ** k) / ((k - 1.0) * (x - 1.0))

    def alpha(norm_w: float, k: float) -> float:
        return 1.0 - (k - 1.0) * (integral(norm_w, k) - integral(0.0, k))

    alphas = []
    for _, row in pdf.iterrows():
        i  = row["origin_station_id"]
        w  = float(row["weight"])
        si = float(out_str.get(i, w))
        k  = float(total_degree(i))
        if k <= 1:
            alphas.append(0.0)
            continue
        norm_w = max(w / si, 1e-4) if si > 0 else 1e-4
        if norm_w >= 1.0:
            norm_w = 1.0 - 1e-4
        alphas.append(alpha(norm_w, k))

    pdf = pdf.copy()
    pdf["alpha"] = alphas
    return pdf


def gloss_filter(pdf: pd.DataFrame) -> pd.DataFrame:
    """Radicchi, Ramasco & Fortunato (2011) — same implementation as rank_edges Cell 2."""
    weights = pdf["weight"].values.astype(float)
    weights = np.where(weights <= 0, 1e-9, weights)

    if len(pdf) < 2:
        pdf = pdf.copy()
        pdf["gloss_alpha"] = 0.0
        return pdf

    out_deg = pdf.groupby("origin_station_id").size().to_dict()
    in_deg  = pdf.groupby("dest_station_id").size().to_dict()
    out_str = pdf.groupby("origin_station_id")["weight"].sum().to_dict()
    in_str  = pdf.groupby("dest_station_id")["weight"].sum().to_dict()

    k_max = max(max(out_deg.values()), max(in_deg.values()))
    w_max = float(weights.max())
    w_min = float(weights[weights > 0].min()) if (weights > 0).any() else 1e-9

    S = float((k_max + 1) * w_max)
    Q = max(int(np.ceil(np.log2(max(S / w_min, 2.0)))), 6)
    b = min(2 ** Q, 2048)

    bin_edges   = np.linspace(0.0, S, b + 1)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

    hist, _ = np.histogram(weights, bins=bin_edges)
    P_obs = hist.astype(float)
    if P_obs.sum() > 0:
        P_obs /= P_obs.sum()

    F: dict = {}
    if k_max >= 2:
        P_fft   = np.fft.rfft(P_obs, n=b)
        P_power = P_fft.copy()
        for k in range(1, k_max):
            F[k] = np.fft.irfft(P_power, n=b).clip(0)
            P_power = P_power * P_fft

    gloss_alphas = []
    for _, row in pdf.iterrows():
        i  = row["origin_station_id"]
        j  = row["dest_station_id"]
        w  = float(row["weight"])
        ki = out_deg.get(i, 1)
        kj = in_deg.get(j, 1)
        si = float(out_str.get(i, w))
        sj = float(in_str.get(j, w))

        if ki <= 1 or kj <= 1:
            gloss_alphas.append(0.0)
            continue

        fi_arr = F.get(ki - 1, np.zeros(b))
        fj_arr = F.get(kj - 1, np.zeros(b))

        valid = (P_obs > 0) & (bin_centers <= si) & (bin_centers <= sj)
        if not valid.any():
            gloss_alphas.append(1.0)
            continue

        w_t = bin_centers[valid]
        p_t = P_obs[valid]
        ri_idx = np.clip(((si - w_t) / S * b).astype(int), 0, b - 1)
        rj_idx = np.clip(((sj - w_t) / S * b).astype(int), 0, b - 1)

        vals  = p_t * fi_arr[ri_idx] * fj_arr[rj_idx]
        denom = vals.sum()
        numer = vals[w_t >= w].sum()
        gloss_alphas.append(float(numer / denom) if denom > 0 else 1.0)

    pdf = pdf.copy()
    pdf["gloss_alpha"] = gloss_alphas
    return pdf


def rank_asc(series: pd.Series) -> pd.Series:
    """Rank ascending — lower value → rank 1."""
    return series.rank(method='min').astype(int)


def rank_desc(series: pd.Series) -> pd.Series:
    """Rank descending — higher value → rank 1."""
    return (-series).rank(method='min').astype(int)


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    station_id_map = load_station_id_map()

    all_dfs = []

    for mode in MODES:
        graph_path = GRAPH_DIR / mode / f"{mode}-distance.json"
        if not graph_path.exists():
            print(f"  SKIP (not found): {graph_path}")
            continue

        with open(graph_path) as f:
            data = json.load(f)

        mode_map = station_id_map.get(mode, {})

        # Build directed edge rows: weight = distance_km
        rows = []
        for link in data['links']:
            d = float(link['distance'])
            if d <= 0:
                continue
            src_id = mode_map.get(link['source'], link['source'])
            tgt_id = mode_map.get(link['target'], link['target'])
            rows.append({'origin_station_id': src_id, 'dest_station_id': tgt_id, 'weight': d})
            rows.append({'origin_station_id': tgt_id, 'dest_station_id': src_id, 'weight': d})

        if not rows:
            print(f"  SKIP (no valid edges): {mode}")
            continue

        pdf = pd.DataFrame(rows)
        print(f"  {mode}: {len(data['links'])} undirected -> {len(pdf)} directed rows", end='')

        pdf = disparity_filter(pdf)
        pdf = gloss_filter(pdf)

        # Rankings per mode:
        # weight_rnk:      rank 1 = longest distance (highest weight)
        # alpha_rnk:       rank 1 = lowest alpha (most significant, disparity)
        # gloss_alpha_rnk: rank 1 = lowest gloss_alpha (most significant, GloSS)
        pdf['weight_rnk']      = rank_desc(pdf['weight'])
        pdf['alpha_rnk']       = rank_asc(pdf['alpha'])
        pdf['gloss_alpha_rnk'] = rank_asc(pdf['gloss_alpha'])

        pdf['mode'] = mode
        pdf['kpi']  = 'distance'

        all_dfs.append(pdf[[
            'origin_station_id', 'dest_station_id', 'mode', 'kpi',
            'weight', 'weight_rnk',
            'alpha', 'alpha_rnk',
            'gloss_alpha', 'gloss_alpha_rnk',
        ]])
        print(f" -> done")

    if not all_dfs:
        print("No data produced.")
        sys.exit(1)

    df_out = pd.concat(all_dfs, ignore_index=True)
    out_path = OUT_DIR / 'distance_backbone.parquet'
    df_out.to_parquet(out_path, index=False)
    print(f"\nWritten {len(df_out)} rows -> {out_path}")
    print("\nNext steps:")
    print("  1. Upload to Fabric: transit_lh/Files/edge_rankings/distance/distance_backbone.parquet")
    print("  2. Run load_distance_backbone notebook in Fabric")
    print("  3. Run distance_rank_load.sql in Warehouse SQL Editor")
