import re
import pandas as pd
from pathlib import Path

def parse_edge_script(filepath, line_name, mode):
    """
    Parse Neo4j CREATE script.
    Returns edges with: mode, line, origin_naptanid, dest_naptanid, distance, time, speed
    """
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Extract variable → naptanid mapping
    var_to_naptanid = {}
    for var_name, naptanid in re.findall(r"(\w+)\.naptanid\s*=\s*'([^']+)'", content):
        var_to_naptanid[var_name] = naptanid
    
    # Extract edges
    edges = []
    rel_pattern = r'\((\w+)\)\s*-\s*\[(\w+):TO\{([^}]+)\}\]\s*->\s*\((\w+)\)'
    
    for origin_var, rel_var, props_str, dest_var in re.findall(rel_pattern, content):
        origin_naptanid = var_to_naptanid.get(origin_var)
        dest_naptanid = var_to_naptanid.get(dest_var)
        
        if not origin_naptanid or not dest_naptanid:
            continue
        
        edge = {
            'mode': mode,
            'line': line_name,
            'origin_naptanid': origin_naptanid,
            'dest_naptanid': dest_naptanid,
            'distance': None,
            'time': None,
            'speed': None,
        }
        
        # Extract distance, time, speed
        for key, val in re.findall(r"(\w+):\s*([^,}]+)", props_str):
            val = val.strip().strip("'\"")
            if key == 'distance':
                edge['distance'] = float(val)
            elif key == 'time':
                edge['time'] = float(val)
            elif key == 'speed':
                edge['speed'] = float(val)
        
        edges.append(edge)
    
    return edges


def extract_all_line_edges(scripts_dir, output_dir):
    scripts_dir = Path(scripts_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tube_lines = [
        'bakerloo', 'central', 'district', 'H_circle', 'jubilee',
        'metropolitan', 'north', 'piccadilly', 'victoria', 'Waterloo_city'
    ]
    
    all_edges = []
    
    for line_name in tube_lines:
        filepath = scripts_dir / f"{line_name}.txt"
        if filepath.exists():
            print(f"Processing tube/{line_name}...")
            edges = parse_edge_script(filepath, line_name, 'tube')
            all_edges.extend(edges)
            print(f"  Edges: {len(edges)}")
    
    for name in ['dlr_edges', 'dlr']:
        filepath = scripts_dir / f"{name}.txt"
        if filepath.exists():
            print(f"Processing DLR...")
            edges = parse_edge_script(filepath, 'dlr', 'dlr')
            all_edges.extend(edges)
            print(f"  Edges: {len(edges)}")
            break
    
    for name in ['overground_edges', 'overground']:
        filepath = scripts_dir / f"{name}.txt"
        if filepath.exists():
            print(f"Processing Overground...")
            edges = parse_edge_script(filepath, 'overground', 'overground')
            all_edges.extend(edges)
            print(f"  Edges: {len(edges)}")
            break
    
    df = pd.DataFrame(all_edges)
    df = df.drop_duplicates(subset=['origin_naptanid', 'dest_naptanid', 'line', 'mode'])
    
    df.to_parquet(output_dir / 'dim_line_edge.parquet', index=False)
    
    print(f"\nTotal unique line edges: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    
    return df


if __name__ == "__main__":
    path = Path("/Users/brenotiburcio/build/big-cities-transport/01.BaseGraph/02.Neo4J_Scripts")
    df = extract_all_line_edges(path, "./output/dimensions")