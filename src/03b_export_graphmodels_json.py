from neo4j import GraphDatabase
import networkx as nx
from networkx.readwrite import json_graph
import json
import shutil


def load_data_to_networkx(tx):
    ''' Get data from Neo4J and save in .json file'''
    G = nx.DiGraph()
    cypher_query = """MATCH r=(n)-->(m) RETURN n,m,r """
    result = tx.run(cypher_query)
    for record in result:
       node1 = record["n"]
       relationship = record["r"]
       node2 = record["m"]
       # Add nodes with attributes
       G.add_node(node1.id, **node1._properties)
       G.add_node(node2.id, **node2._properties )
       # Add edges with attributes
       G.add_edge(node1.id, node2.id, **relationship._relationships[0]._properties)
    save_graph (G, "temp.json")

def save_graph (graph, graph_path):
    ''' save a graph from JSON '''
    with open(graph_path, "w") as f:
        data = json_graph.node_link_data(graph)
        json.dump(data, f)

if __name__ == '__main__':
    '''
    Convert Base-Graph relation to list of dict(UDR) Kpis
    '''
    # export graph in CSV for NetworkX
    # connect to neo4J and get graphs

    ods = ['tube'] # ,'overground', 'tube',
    days = ['fri', 'sat', 'mtt', 'sun']
    periods = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']
    kpis = ['trafficdistances', 'distress', 'efficiencies', 'loads', 'traffic', 'basegraph', 'speed', 'distance']

    driver = GraphDatabase.driver("bolt://localhost:7687/", auth=('neo4j', "TFLbst1608."))
    for od in ods:
        for kpi in kpis:
            if kpi not in ['speed', 'distance', 'basegraph']:
                for day in days:
                    for period in periods:
                        auxp = period.replace(' ', '-')
                        auxk = kpi.replace('_', '')
                        db = od+"-"+auxk+"-"+day.lower()+"-"+auxp.lower()
                        with driver.session(database=db) as session:
                            result = session.execute_read(load_data_to_networkx)
                            # rename temp
                            path = "C:/buildbr/big-cities-transport/03.GraphModels"
                            shutil.move('temp.json', f'{path}/{od}/{db}.json', copy_function=shutil.copy2)
                        session.close()
            else:
                db = od+'-'+kpi
            with driver.session(database=db) as session:
                result = session.execute_read(load_data_to_networkx)
                # rename temp
                path = "C:/buildbr/big-cities-transport/03.GraphModels"
                shutil.move('temp.json', f'{path}/{od}/{db}.json', copy_function=shutil.copy2)
            session.close()
    driver.close()

    print('==> Done! Now disparity ranks')



