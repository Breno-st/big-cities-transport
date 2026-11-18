"""
10_qhr_to_parquet.py
Extract 15-minute (quarter-hour) NUMBAT data for Tube, Overground, and DLR.

Reads:
  01.NUMBAT/NBT19{MTT,FRI,SAT,SUN}_Outputs.xlsx  - Link_Loads, Station_Entries, Station_Exits
  02.Distress/01.Input/{tube,overground,dlr}_od.csv  - NLC -> naptanid mapping

Writes to output/qhr/:
  fact_station_activity_qhr.parquet  - naptanid, day, qhr_slot, mode, entries, exits
  fact_edge_activity_qhr.parquet     - origin_naptanid, dest_naptanid, mode, day, qhr_slot, kpi, value

Pre-validated coverage (MTT file):
  396/455 Station NLCs -> naptanid (100% of Tube+Overground+DLR)
  1028/1141 Link directed pairs -> both endpoints mapped
  Unmapped = Elizabeth Line, NR, Trams (out of scope, filtered automatically)
"""

import openpyxl
import pandas as pd
from pathlib import Path

BASE_DIR   = Path(r'C:\buildbr\big-cities-transport')
NUMBAT_DIR = BASE_DIR / '01.BaseGraph' / '01.NUMBAT'
OD_DIR     = BASE_DIR / '02.Distress'  / '01.Input'
OUT_DIR    = BASE_DIR / 'output' / 'qhr'

DAY_FILES = {
    'mtt': 'NBT19MTT_Outputs.xlsx',
    'fri': 'NBT19FRI_Outputs.xlsx',
    'sat': 'NBT19SAT_Outputs.xlsx',
    'sun': 'NBT19SUN_Outputs.xlsx',
}

# Station_Entries/Station_Exits: columns 0-10 are identity+timebands, 11+ are QHR slots
STATION_QHR_START = 11

# Link_Loads: columns 0-16 are identity+timebands, 17+ are QHR slots
LINK_QHR_START = 17

# Line names normalised to lowercase for case-insensitive lookup.
# FRI file uses lowercase; MTT/SAT/SUN use title case.
# "Waterloo & City" appears as "waterloo_city" in FRI.
# Romford line uses an em-dash (U+2013) in all files.
_LINE_TO_MODE_LOWER = {
    'bakerloo':               'tube',
    'central':                'tube',
    'district':               'tube',
    'h&c and circle':         'tube',
    'jubilee':                'tube',
    'metropolitan':           'tube',
    'northern':               'tube',
    'piccadilly':             'tube',
    'victoria':               'tube',
    'waterloo & city':        'tube',
    'waterloo_city':          'tube',
    'dlr':                    'dlr',
    'lo east london':         'overground',
    'lo gospel oak-barking':  'overground',
    'lo north london':        'overground',
    'lo watford-euston':      'overground',
    'lo west anglia':         'overground',
}
# Add the Romford line with its actual em-dash character
_LINE_TO_MODE_LOWER['lo romford\u2013upminster'] = 'overground'


def _line_to_mode(line_raw):
    """Return mode string for a raw line name (case-insensitive), or None if out-of-scope."""
    if line_raw is None:
        return None
    return _LINE_TO_MODE_LOWER.get(str(line_raw).lower().strip())


def build_nlc_map():
    """
    Build two dicts from the OD CSV files:
      nlc_map  : {nlc_int -> naptanid_str}
      mode_map : {nlc_int -> mode_str}  ('tube' | 'overground' | 'dlr')
    A station may appear in multiple OD files (interchange). The first match wins.
    """
    nlc_map = {}
    mode_map = {}

    for mode, fname in [
        ('tube',        'tube_od.csv'),
        ('overground',  'overground_od.csv'),
        ('dlr',         'dlr_od.csv'),
    ]:
        df = pd.read_csv(OD_DIR / fname, sep=';',
                         usecols=['name_o', 'naptanid_o', 'name_d', 'naptanid_d'])
        for _, row in df.iterrows():
            for nlc_col, nap_col in [('name_o', 'naptanid_o'), ('name_d', 'naptanid_d')]:
                try:
                    nlc = int(row[nlc_col])
                except (TypeError, ValueError):
                    continue
                nap = str(row[nap_col])
                if nlc not in nlc_map:
                    nlc_map[nlc] = nap
                    mode_map[nlc] = mode

    print(f'NLC map built: {len(nlc_map)} entries across tube/overground/dlr')
    return nlc_map, mode_map


def extract_station_qhr(day_code, xlfile, nlc_map, mode_map):
    """
    Extract Station_Entries and Station_Exits QHR data.
    Returns DataFrame: naptanid, day, qhr_slot, mode, entries, exits
    """
    wb = openpyxl.load_workbook(xlfile, read_only=True, data_only=True)

    combined = {}  # key = (naptanid, day, qhr_slot, mode)

    for tab, col_key in [('Station_Entries', 'entries'), ('Station_Exits', 'exits')]:
        ws = wb[tab]
        all_rows = list(ws.iter_rows(values_only=True))
        qhr_labels = [str(c) for c in all_rows[2][STATION_QHR_START:] if c is not None]

        for row in all_rows[3:]:
            if row[0] is None:
                continue
            try:
                nlc = int(row[0])
            except (TypeError, ValueError):
                continue
            if nlc not in nlc_map:
                continue

            naptanid = nlc_map[nlc]
            mode     = mode_map[nlc]

            for j, qhr in enumerate(qhr_labels):
                raw = row[STATION_QHR_START + j]
                val = float(raw) if raw is not None else 0.0
                if val <= 0:
                    continue
                k = (naptanid, day_code, qhr, mode)
                if k not in combined:
                    combined[k] = {'entries': 0.0, 'exits': 0.0}
                combined[k][col_key] += val

    wb.close()

    records = [
        {'naptanid': naptanid, 'day': day, 'qhr_slot': qhr, 'mode': mode,
         'entries': v['entries'], 'exits': v['exits']}
        for (naptanid, day, qhr, mode), v in combined.items()
    ]
    df = pd.DataFrame(records)
    print(f'  {day_code} station QHR rows: {len(df):,}')
    return df


def extract_link_qhr(day_code, xlfile, nlc_map):
    """
    Extract Link_Loads QHR data for in-scope lines.
    Returns DataFrame: origin_naptanid, dest_naptanid, mode, day, qhr_slot, kpi, value
    """
    wb = openpyxl.load_workbook(xlfile, read_only=True, data_only=True)
    ws  = wb['Link_Loads']
    all_rows = list(ws.iter_rows(values_only=True))
    qhr_labels = [str(c) for c in all_rows[2][LINK_QHR_START:] if c is not None]

    records = []
    skipped_line = skipped_nlc = 0

    for row in all_rows[3:]:
        if row[0] is None:
            continue

        mode = _line_to_mode(row[1])
        if mode is None:
            skipped_line += 1
            continue

        try:
            from_nlc = int(row[4])
            to_nlc   = int(row[7])
        except (TypeError, ValueError):
            skipped_nlc += 1
            continue

        if from_nlc not in nlc_map or to_nlc not in nlc_map:
            skipped_nlc += 1
            continue

        o_nap = nlc_map[from_nlc]
        d_nap = nlc_map[to_nlc]

        for j, qhr in enumerate(qhr_labels):
            raw = row[LINK_QHR_START + j]
            val = float(raw) if raw is not None else 0.0
            if val <= 0:
                continue
            records.append({
                'origin_naptanid': o_nap,
                'dest_naptanid':   d_nap,
                'mode':            mode,
                'day':             day_code,
                'qhr_slot':        qhr,
                'kpi':             'traffic',
                'value':           val,
            })

    wb.close()

    print(f'  {day_code} link QHR raw records: {len(records):,} '
          f'(skipped {skipped_line} out-of-scope lines, {skipped_nlc} unmapped NLCs)')

    if not records:
        return pd.DataFrame(columns=[
            'origin_naptanid', 'dest_naptanid', 'mode', 'day', 'qhr_slot', 'kpi', 'value'
        ])

    df = pd.DataFrame(records)
    df = df.groupby(
        ['origin_naptanid', 'dest_naptanid', 'mode', 'day', 'qhr_slot', 'kpi'],
        as_index=False
    )['value'].sum()

    print(f'  {day_code} link QHR after aggregation: {len(df):,} rows')
    return df


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    nlc_map, mode_map = build_nlc_map()

    station_dfs = []
    edge_dfs    = []

    for day_code, fname in DAY_FILES.items():
        xlfile = NUMBAT_DIR / fname
        if not xlfile.exists():
            print(f'WARNING: {xlfile} not found - skipping {day_code}')
            continue
        print(f'\nProcessing {fname}...')
        station_dfs.append(extract_station_qhr(day_code, xlfile, nlc_map, mode_map))
        edge_dfs.append(extract_link_qhr(day_code, xlfile, nlc_map))

    df_station = pd.concat(station_dfs, ignore_index=True)
    df_edge    = pd.concat(edge_dfs, ignore_index=True)

    sa_path = OUT_DIR / 'fact_station_activity_qhr.parquet'
    ea_path = OUT_DIR / 'fact_edge_activity_qhr.parquet'
    df_station.to_parquet(sa_path, index=False)
    df_edge.to_parquet(ea_path, index=False)

    print(f'\n=== Output summary ===')
    print(f'fact_station_activity_qhr.parquet: {len(df_station):,} rows -> {sa_path}')
    print(f'  Columns: {list(df_station.columns)}')
    print(f'  Unique naptanids: {df_station["naptanid"].nunique()}')
    print(f'  Unique qhr_slots: {df_station["qhr_slot"].nunique()}')
    print(f'  Days: {sorted(df_station["day"].unique())}')
    print(f'\nfact_edge_activity_qhr.parquet: {len(df_edge):,} rows -> {ea_path}')
    print(f'  Columns: {list(df_edge.columns)}')
    print(f'  Unique directed pairs: {df_edge[["origin_naptanid","dest_naptanid"]].drop_duplicates().shape[0]}')
    print(f'  Days: {sorted(df_edge["day"].unique())}')


if __name__ == '__main__':
    main()
