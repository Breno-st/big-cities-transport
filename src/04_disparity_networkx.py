
import sys
import json
import pickle

import numpy as np
import pandas as pd
import networkx as nx
from networkx.readwrite import json_graph

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

from scipy.stats import percentileofscore
from traceback import format_exception

### PICKLE FUNCTIONS ###
def dict_to_pickle(dict, savename):
    with open(savename, 'wb') as handle:
        pickle.dump(dict, handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_pickle(filename):
    with open(filename, 'rb') as handle:
        loadedfile = pickle.load(handle)
    return loadedfile

#### GRAPH IMPORTING FUNCTIONS ####
def load_data_to_networkx(tx):
    ''' Get data from Neo4J and save in .json file'''
    G = nx.DiGraph()
    kpi = 'distress'
    cypher_query = """TODO"""
    result = tx.run(cypher_query)
    for record in result:
       node1 = record["n"]
       relationship = record["r"]
       node2 = record["m"]
       # Add nodes with attributes
       G.add_node(node1._properties['naptanid'], **node1._properties)
       G.add_node(node2._properties['naptanid'], **node2._properties )
       # Add edges with attributes
       G.add_edge(node1._properties['naptanid'], node2._properties['naptanid'], kpi = relationship._properties[kpi])
    save_graph (G, "temp.json")

def save_graph (graph, graph_path):
    ''' save a graph from JSON '''
    with open(graph_path, "w") as f:
        data = json_graph.node_link_data(graph)
        json.dump(data, f)

def load_graph (graph_path):
    ''' load a graph from JSON '''
    with open(graph_path) as f:
        data = json.load(f)
        graph = json_graph.node_link_graph(data, directed=True)
        return graph

#### DISPARITY FUNCTIONS ####
def disparity_filter (graph, kpi):
    """
    implements a disparity filter, based on multiscale backbone networks
    https://arxiv.org/pdf/0904.2389.pdf
    """
    alpha_measures = []

    for node_id in graph.nodes():
        node = graph.nodes[node_id]
        degree = graph.degree(node_id)
        strength = 0.0

        for id0, id1 in graph.edges(nbunch=[node_id]):
            edge = graph[id0][id1]
            strength += edge[kpi]

        node["strength"] = strength

        for id0, id1 in graph.edges(nbunch=[node_id]):
            edge = graph[id0][id1]
            norm_weight = 0.0001 if edge[kpi] == 0 else edge[kpi] / strength
            #norm_weight = edge[kpi] / strength # divide
            aux = 'norm_'+kpi
            edge[aux] = norm_weight ####

            if degree > 1:
                try:
                    if norm_weight == 1.0:
                        norm_weight -= 0.0001

                    alpha = get_disparity_significance(norm_weight, degree)
                except AssertionError:
                    report_error("disparity {}".format(repr(node)), fatal=True)

                edge["alpha"] = alpha # adding alpha
                alpha_measures.append(alpha)
            else:
                edge["alpha"] = 0.0

    for id0, id1 in graph.edges():
        edge = graph[id0][id1]
        edge["alpha_ptile"] = percentileofscore(alpha_measures, edge["alpha"]) / 100.0 # [0, 0.1, 1.0] => 10_ptile, top highest; Observe how cut is made in the code

def disparity_integral (x, k):
    """
    calculate the definite integral for the PDF in the disparity filter
    """
    assert x != 1.0, "x == 1.0"
    assert k != 1.0, "k == 1.0"
    return ((1.0 - x)**k) / ((k - 1.0) * (x - 1.0))

def get_disparity_significance (norm_weight, degree):
    """
    calculate the significance (alpha) for the disparity filter
    """
    return 1.0 - ((degree - 1.0) * (disparity_integral(norm_weight, degree) - disparity_integral(0.0, degree)))

def report_error (cause_string, logger=None, fatal=False):
    """
    TODO: errors should go to logger, and not be fatal
    """
    etype, value, tb = sys.exc_info()
    error_str = "{} {}".format(cause_string, str(format_exception(etype, value, tb, 3)))

    if logger:
        logger.info(error_str)
    else:
        print(error_str)

    if fatal:
        sys.exit(-1)


#### RANKS #####


    pass

def cut_graph (graph_original, min_alpha_ptile=0.5, min_degree=1):
    """
    apply the disparity filter to cut the given graph
    """
    graph = graph_original.copy()
    filtered_set = set([])

    for id0, id1 in graph.edges():
        edge = graph[id0][id1]

        if edge["alpha_ptile"] > min_alpha_ptile:
            filtered_set.add((id0, id1))

    for id0, id1 in filtered_set:
        graph.remove_edge(id0, id1)

    filtered_set = set([])

    for node_id in graph.nodes():
        node = graph.nodes[node_id]

        if graph.degree(node_id) < min_degree:
            filtered_set.add(node_id)

    for node_id in filtered_set:
        graph.remove_node(node_id)

    return graph

def calc_centrality (graph, min_degree=1):
    """
    to conserve compute costs, ignore centrality for nodes below `min_degree`
    """
    sub_graph = graph.copy()
    sub_graph.remove_nodes_from([ n for n, d in list(graph.degree) if d < min_degree ])

    centrality = nx.betweenness_centrality(sub_graph, weight="weight")
    #centrality = nx.closeness_centrality(sub_graph, distance="distance")

    return centrality

#### PLOTS ####
def plot_disparities(G, od, kpi, day=None, period=None):

    # full alpha
    title = f'{od.upper()} {kpi.title()} Alpha Ranked Edges {day.upper()} {period.title()}' if day else f'{od.upper()} {kpi.title()} Alpha ranked edges'
    dim = plot_edges(title, G, "Reds", od, "alpha")
    # full kpi
    title = f'{od.upper()} {kpi.title()} Ranked Edges {day.upper()} {period.title()}' if day else f'{od.upper()} {kpi.title()} ranked edges'
    plot_edges(title, G, "Greys", od, kpi)

    cuts = [0.25, 0.5, 0.75]
    for cut in cuts:
       title = f'{od.upper()} {kpi.title()} {round(cut*100)}th percentile {day.upper()} {period.title()}' if day else f'{od.upper()} {kpi.title()} {round(cut*100)}th percentile edges'
       G_ptile = cut_graph(G, cut)
       plot_edges(title, G_ptile, "Reds", od, "alpha", dim)

def plot_edges(title, G, color, od, kpi, dim=None):

    pos = {}
    for node in G.nodes():
        pos[node] = (G.nodes[node]['long'], G.nodes[node]['lat'])
    # Defining colors
    cmap = plt.get_cmap(color)
    reversed_cmap = ListedColormap(cmap(np.linspace(1, 0, 256)))
    values = [G.edges[edge][kpi] for edge in G.edges()]
    edge_colors = [cmap(value) for value in values]  if kpi != "alpha" else [reversed_cmap(value) for value in values]
    # Defining size
    fig = plt.figure(figsize=(16, 8)) # DLR (8,8)
    if dim:
        plt.xlim(dim[0])
        plt.ylim(dim[1])
    # Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=10, node_color='dimgrey')
    # Draw Nodes Label
    nx.draw_networkx_labels(G, pos, font_size= 10, verticalalignment='bottom', horizontalalignment='left', font_color='dimgrey')
    # Draw Edges
    curved_edges = [edge for edge in G.edges() if reversed(edge) in G.edges()]
    straight_edges = list(set(G.edges()) - set(curved_edges))
    nx.draw_networkx_edges(G, pos, edgelist=straight_edges, edge_color=edge_colors, arrowsize=6,  node_size = 10, width=0.8, connectionstyle=f'arc3, rad = 0.10')
    nx.draw_networkx_edges(G, pos, edgelist=curved_edges, edge_color=edge_colors, arrowsize=6,  node_size = 10, width=0.8, connectionstyle=f'arc3, rad = 0.10')
    # Create a colorbar
    norm = plt.Normalize(vmin=0, vmax=1)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm) if kpi != "alpha" else plt.cm.ScalarMappable(cmap=reversed_cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, orientation='vertical')
    cbar.set_label(f'{kpi.title()} values')  # Set a label for the colorbar
    # Finally, plotting
    map_image = mpimg.imread(f"{path}/04.Disparity/{od}/google_map.png")
    # Display the map image as the background
    west, east = plt.xlim()[0], plt.xlim()[1]
    south, north = plt.ylim()[0], plt.ylim()[1]
    plt.imshow(map_image, extent=[west, east, south, north], aspect='auto', alpha=0.3)
    # Show the plot
    plt.title(title)
    plt.tight_layout()
    # Save the plot to a file
    plt.savefig(f'{path}/04.Disparity/{od}/img/{title}.png')
    return plt.xlim(), plt.ylim()

def create_dataframe(columns, edges):
    data = {edge: [None] * len(columns) for edge in edges}
    return pd.DataFrame(columns=columns, data=data)

def node_view(G):
    G.nodes.strengh
    G.nodes.degree
    G.nodes.centrality

#### RANK FUNCTIONS ####
def rank_edge(G, kpi):
    '''Add rank values into G'''

    # Getting ranks positions
    alpha_sorted_edges = sorted(G.edges(data=True), key=lambda x: (x[2]['alpha'])) # increasing
    kpi_sorted_edges = sorted(G.edges(data=True), key=lambda x: x[2][kpi], reverse=True) # decreasing
    alpha_edges_rnk = [(x[0], x[1]) for x in alpha_sorted_edges]
    kpi_edges_rnk = [(x[0], x[1]) for x in kpi_sorted_edges]


    # Store inside edge as attribute: 'pos_kpi'
    for id0, id1 in graph.edges():
        edge = graph[id0][id1]
        edge["alpha_rnk"] = alpha_edges_rnk.index((id0, id1))+1
        edge[f'{kpi}_rnk'] = kpi_edges_rnk.index((id0, id1))+1

def populate_dictionaire(G, cols):
    # Create dictionaries for each column
    dictionaries = {name: {} for name in cols}
    for edge in G.edges(data=True):
        for col in cols:
            dictionaries[col][str(edge[:2])] = edge[2][col]

    return dictionaries

if __name__ == "__main__":

    global path
    global days
    global periods

    #### Defining variables  ####
    ods = [ 'overground'] # 'overground', 'dlr', 'tube'
    days = ['fri', 'sat', 'mtt', 'sun']
    periods = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']
    kpis = ['distance', 'speed', 'traffic', 'traffic_distances', 'loads','efficiencies', 'distress']# 'distress' review distress graphs 'distance', 'speed', 'traffic', 'traffic_distances', 'loads','efficiencies', 'distress'
    path = "C:/buildbr/big-cities-transport"


    # Interact through variables hierarchically

    for od in ods:
        for kpi in kpis:
            #### Extract graph edges from BaseGraph  ###
            basegraph = load_graph(f'{path}/03.GraphModels/{od}/{od}-basegraph.json')
            edges = [(x[0], x[1]) for x in basegraph.edges(data=True)]
            cols = ['alpha', 'alpha_rnk', f'{kpi}', f'{kpi}_rnk']

            #### Two type ov variables: Time-Independent & Time-Dependent ###
            if kpi in ['speed', 'distance']:
                # create name
                db = od+'-'+kpi
                #### LOAD JSON DISPARITY  ####
                graph = load_graph(f'{path}/03.GraphModels/{od}/{db}.json')
                #### APPLY DISPARITY ####
                disparity_filter(graph, kpi) # add: alpha_ptile*, alpha* into graph
                #### RANK EDGES  ####
                rank_edge(graph, kpi)  # add: kpi_rank*, alpha_rank* into graph
                #### PLOTs kpi #####
                # # based on edges attributes: kpi, alpha_ptile, cutted by alpha
                # plot_disparities(graph, od, kpi)
                #### POPULATE DICT ####
                kpi_dic = populate_dictionaire(graph, cols) # add: alpha**, alpha_rank**, kpi**, kpi_rank** into graph
                #### EXPORT DICTIONARY ####
                dict_to_pickle(kpi_dic, f'{path}/04.Disparity/{od}/{od}-{kpi}.pickle')
                #### CREATE DATAFRAME ####
                df = pd.DataFrame.from_dict(kpi_dic, orient='index').transpose()

            else: # loop through day and periods
                kpi_dic = {}
                for day in days:
                    kpi_dic[day]={}
                    for period in periods:
                        kpi_dic[day][period]={}
                        # create name
                        auxk = kpi.replace('_', '')
                        auxp = period.replace(' ', '-')
                        db = od+"-"+auxk+"-"+day.lower()+"-"+auxp.lower()
                        #### LOAD JSON DISPARITY  ####
                        graph = load_graph(f'{path}/03.GraphModels/{od}/{db}.json')
                        #### APPLY DISPARITY  ####
                        disparity_filter(graph, kpi) # add: alpha_ptile, alpha into graph
                        #### RANK EDGES BASED ON KPI AND ALPHA ####
                        rank_edge(graph, kpi)  # add: weight_rank*, alpha_rank into graph
                        #### POPULATE DICT ####
                        kpi_dic[day][period] = populate_dictionaire(graph, cols)
                        # #### PLOTs kpi (Greens), alpha (Reds), ptiles (Reds)####
                        # plot_disparities(graph, od, kpi, day, period)
                #### EXPORT DICTIONARY ####
                dict_to_pickle(kpi_dic, f'{path}/04.Disparity/{od}/{od}-{kpi}.pickle')
                #### CREATE DATAFRAME ####
                mux = pd.MultiIndex.from_product([days, periods, cols])
                df = pd.DataFrame(columns=mux)
                for col1, data1 in kpi_dic.items():
                    for col2, data2 in data1.items():
                        for col3, data3 in data2.items():
                            df[col1, col2, col3] = pd.Series(data3)

            df.to_csv(f'{path}/04.Disparity/{od}/{od}-{kpi}.csv')
