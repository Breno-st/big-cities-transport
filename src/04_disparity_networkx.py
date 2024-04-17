
import sys
import json
import pickle

import numpy as np
import pandas as pd
from collections import defaultdict

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

def node_view(G):
    G.nodes.strengh
    G.nodes.degree
    G.nodes.centrality

#### DISPARITY FUNCTIONS ####
def disparity_filter (graph, kpi):
    """
    implements a disparity filter, based on multiscale backbone networks
    https://arxiv.org/pdf/0904.2389.pdf
    """
    alpha_measures = []
    kpi_measures = []

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
                kpi_measures.append(edge[kpi])
            else:
                edge["alpha"] = 0.0

    for id0, id1 in graph.edges():
        edge = graph[id0][id1]
        edge["alpha_ptile"] = percentileofscore(alpha_measures, edge["alpha"]) / 100.0 # [0, 0.1, 1.0] => 10_ptile, top highest; Observe how cut is made in the code

        edge[f'{kpi}_ptile'] = percentileofscore(kpi_measures, edge[kpi]) / 100.0 # [0, 0.1, 1.0] => 10_ptile, top highest; Observe how cut is made in the code

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

#### GRAPH FUNCTIONS #####

def cut_graph (graph_original, cut=0.5, kpi=None, min_degree=1, Alp=False):
    """
    apply the disparity filter to cut the given graph
    """

    att = "alpha_ptile" if Alp else f'{kpi}_ptile' # kpi instead of f'{kpi}_ptile'

    graph = graph_original.copy()
    filtered_set = set([])

    for id0, id1 in graph.edges():
        edge = graph[id0][id1]

        if (att != "alpha_ptile" and edge[att] < 1-cut) or (att == "alpha_ptile" and edge[att] > cut): # min_alpha_ptile:
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

def calc_centrality (graph, od, kpi="distance", min_degree=1):
    """
    to conserve compute costs, ignore centrality for nodes below `min_degree`
    """
    sub_graph = graph.copy()
    sub_graph.remove_nodes_from([ n for n, d in list(graph.degree) if d < min_degree ])

    centrality = nx.betweenness_centrality(sub_graph, weight=kpi)

    plot_centrality(graph, od, centrality)

    return centrality

#### PLOTS ####
def plot_backbones(G, od, kpi, day=None, period=None):

    if day:

        # # calculate ALPHA and THRSD time variant
        title = f'{od.upper()} {kpi.title()} ALP Ranked Edges {day.upper()} {period.title()}'
        dim = plot_edges(title, G, "Reds_r", od, kpi, Alp=True)

        title = f'{od.upper()} {kpi.title()} THR Ranked Edges {day.upper()} {period.title()}'
        dim = plot_edges(title, G, "Greys", od, kpi)

    else:
        # calculate ALPHA and THRSD time invariant
        title = f'{od.upper()} {kpi.title()} ALP Ranked Edges'
        dim = plot_edges(title, G, "Reds_r", od, kpi, Alp=True) # turbo, jet

        title = f'{od.upper()} {kpi.title()} THR Ranked Edges'
        dim = plot_edges(title, G, "Greys", od, kpi) # turbo, jet

    cuts = [0.25] #[0.25, 0.5, 0.75]
    for cut in cuts:
        if day:
            # calculate ALPHA cuts time variant
            title = f'{od.upper()} {kpi.title()} ALP {round(cut*100)}th Percentile {day.upper()} {period.title()}'
            G_ptile = cut_graph(G, cut, kpi, Alp=True) # alpha_ptile
            plot_edges(title, G_ptile, "Reds_r", od, kpi, dim=dim, Alp=True) # turbo, jet

            # # calculate THRSD cuts time variant (show how bad it is)
            title = f'{od.upper()} {kpi.title()} THR {round(cut*100)}th Percentile {day.upper()} {period.title()}'
            G_ptile = cut_graph(G, cut, kpi) # alpha_ptile
            plot_edges(title, G_ptile, "Greys", od, kpi, dim) # turbo, jet

        else:
            # calculate ALPHA cuts time variant (show difference)
            title = f'{od.upper()} {kpi.title()} ALP {round(cut*100)}th Percentile Edges'
            G_ptile = cut_graph(G, cut, kpi, Alp=True) # inside plots
            plot_edges(title, G_ptile, "Reds_r", od, kpi, dim=dim, Alp=True) # turbo, jet

            # calculate THRSD cuts time invariant
            title = f'{od.upper()} {kpi.title()} THR {round(cut*100)}th Percentile Edges'
            G_ptile = cut_graph(G, cut, kpi) # alpha_ptile
            plot_edges(title, G_ptile, "Greys", od, kpi, dim) # turbo, jet

def plot_entries_exists(Graph, od, min_degree=1):

    G = Graph.copy()



    # Add flow into nodes
    for node_id in G.nodes():
        node = G.nodes[node_id]
        degree = G.degree(node_id)

        node["degree"] = degree
        for idx, period in enumerate(periods):
            node[period] = G.nodes[node_id]['entries'][idx] - G.nodes[node_id]['exits'][idx]
    # Normalize
    for period in periods:
        attribute_values = [G.nodes[node][period] for node in G.nodes()]

        # Calculate minimum and maximum values of the attribute
        min_attribute = min(attribute_values)
        max_attribute = max(attribute_values)

        for node_id in G.nodes():
            if period in G.nodes[node_id]:
                normalized_value = (G.nodes[node_id][period] - min_attribute) / (max_attribute - min_attribute) * (2) - 1
                G.nodes[node_id][period] = normalized_value

        title = f'{od.upper()} Stations MTT {period.title()}'

        plot_nodes(title, G, od, period, dim=None)

def plot_edges(title, G, color, od, kpi, dim=None, Alp=False):

    att = "alpha_ptile" if Alp else f'{kpi}_ptile' # kpi instead of f'{kpi}_ptile'

    pos = {}
    for node in G.nodes():
        pos[node] = (G.nodes[node]['long'], G.nodes[node]['lat'])
    # Defining colors
    cmap = plt.get_cmap(color)
    values = [G.edges[edge][att] for edge in G.edges()]
    edge_colors = [cmap(value) for value in values]
    # Defining size

    fig = plt.figure(figsize=(8, 8)) if od=='dlr' else plt.figure(figsize=(16, 8)) # DLR (8,8), tube and overgroung (16,8)
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
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, orientation='vertical', ax=plt.gca())
    cbar.set_label('Alpha values') if Alp else cbar.set_label(f'{kpi.title()} values')
    # Finally, plotting
    map_image = mpimg.imread(f"{path}/04.Disparity/01.Input/{od}/google_map.png")
    # Display the map image as the background
    west, east = plt.xlim()[0], plt.xlim()[1]
    south, north = plt.ylim()[0], plt.ylim()[1]
    plt.imshow(map_image, extent=[west, east, south, north], aspect='auto', alpha=0.3)
    # Show the plot
    plt.title(title)
    plt.tight_layout()
    # Save the plot to a file
    plt.savefig(f'{path}/04.Disparity/02.Output/{kpi}/img/{title}.png')
    return plt.xlim(), plt.ylim()

def plot_nodes(title, G, od, period, dim=None):

    pos = {}
    for node in G.nodes():
        pos[node] = (G.nodes[node]['long'], G.nodes[node]['lat'])

    # Defining colors
    values = [G.nodes[node][period] for node in G.nodes()]
    node_colors = ['indianred' if value < 0 else 'lightskyblue' for value in values]
    node_sizes = [200*abs(G.nodes[node][period])+40 for node in G.nodes()]


    # Defining size
    fig = plt.figure(figsize=(8, 8)) if od=='dlr' else plt.figure(figsize=(16, 8)) # DLR (8,8), tube and overgroung (16,8)
    if dim:
        plt.xlim(dim[0])
        plt.ylim(dim[1])
    # Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors)
    # Draw Nodes Label
    nx.draw_networkx_labels(G, pos, font_size= 10, verticalalignment='bottom', horizontalalignment='left', font_color='dimgrey')

    # Draw Edges
    curved_edges = [edge for edge in G.edges() if reversed(edge) in G.edges()]
    straight_edges = list(set(G.edges()) - set(curved_edges))
    nx.draw_networkx_edges(G, pos, edgelist=straight_edges, edge_color='grey', arrowsize=6,  node_size = 10, width=0.8, connectionstyle=f'arc3, rad = 0.10')
    nx.draw_networkx_edges(G, pos, edgelist=curved_edges, edge_color='grey', arrowsize=6,  node_size = 10, width=0.8, connectionstyle=f'arc3, rad = 0.10')

    # Custom legend
    legend_labels = {'Entries': 'lightskyblue', 'Exits': 'indianred'}
    legend_handles = [plt.Line2D([0], [0], marker='o', color=color, label=label, markersize=10) for label, color in legend_labels.items()]
    plt.legend(handles=legend_handles, loc='upper right', fontsize='medium')

    # Finally, plotting
    map_image = mpimg.imread(f"{path}/04.Disparity/01.Input/{od}/google_map.png")
    # Display the map image as the background
    west, east = plt.xlim()[0], plt.xlim()[1]
    south, north = plt.ylim()[0], plt.ylim()[1]
    plt.imshow(map_image, extent=[west, east, south, north], aspect='auto', alpha=0.3)
    # Show the plot
    plt.title(title)
    plt.tight_layout()
    # Save the plot to a file
    plt.savefig(f'{path}/04.Disparity/02.Output/Stations/img/{title}.png')
    return plt.xlim(), plt.ylim()

def plot_k_core(G, od):

    fig = plt.figure(figsize=(8, 8))

    kcores = defaultdict(list)

    for n, k in nx.core_number(G).items():
        kcores[k].append(n)

    kcores = dict(sorted(kcores.items(), reverse=True))

    # compute position of each node with shell layout
    pos = nx.layout.shell_layout(G, list(kcores.values()))

    # compute colors
    cmap = plt.get_cmap("rainbow")
    x = np.linspace(0, 1, max(kcores))
    reversed_cmap = ListedColormap(cmap(x))
    node_colors = {}
    for kcore in kcores:
        node_colors[kcore] = reversed_cmap(kcore-1)

    # Draw Nodes
    for kcore, nodes in kcores.items():
        nx.draw_networkx_nodes(G, pos, node_size=30, nodelist=nodes, node_color=node_colors[kcore])
    # Draw Nodes Label
    nx.draw_networkx_labels(G, pos, font_size= 10, verticalalignment='bottom', horizontalalignment='left', font_color='dimgrey')

    # Draw Edges
    curved_edges = [edge for edge in G.edges() if reversed(edge) in G.edges()]
    straight_edges = list(set(G.edges()) - set(curved_edges))
    nx.draw_networkx_edges(G, pos, edgelist=straight_edges, edge_color="grey", arrowsize=6,  node_size = 10, width=0.8, connectionstyle=f'arc3, rad = 0.10')
    nx.draw_networkx_edges(G, pos, edgelist=curved_edges, edge_color="grey", arrowsize=6,  node_size = 10, width=0.8, connectionstyle=f'arc3, rad = 0.10')

    # Create a colorbar
    norm = plt.Normalize(vmin=0, vmax=max(kcores))
    sm = plt.cm.ScalarMappable(cmap=reversed_cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, orientation='vertical', ax=plt.gca(), ticks=range(max(kcores)+1))
    cbar.set_label('K-Core values')  # Set a label for the colorbar

    title = f'{od.upper()} K-Means'

    plt.title(title)
    plt.tight_layout()
    # Save the plot to a file
    plt.savefig(f'{path}/04.Disparity/02.Output/kmeans/img/{title}.png')

    return kcores

def plot_centrality(G, od, centrality):

    fig = plt.figure(figsize=(8, 8)) if od=='dlr' else plt.figure(figsize=(16, 8)) # DLR (8,8), tube and overgroung (16,8)

    title = f'{od.upper()} Centrality'

    pos, centralities = {}, {}
    for node in G.nodes():
        pos[node] = (G.nodes[node]['long'], G.nodes[node]['lat'])
        centralities[node]= centrality[node]

    # compute colors
    cmap = plt.get_cmap("rainbow")
    x = np.linspace(0, 1, 256)
    reversed_cmap = ListedColormap(cmap(x))


    values = [centralities[node] for node in centralities]
    node_colors = [reversed_cmap(value) for value in values]

    # Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=30, node_color=node_colors)
    # Draw Nodes Label
    nx.draw_networkx_labels(G, pos, font_size= 10, verticalalignment='bottom', horizontalalignment='left', font_color='dimgrey')

    # Draw Edges
    curved_edges = [edge for edge in G.edges() if reversed(edge) in G.edges()]
    straight_edges = list(set(G.edges()) - set(curved_edges))
    nx.draw_networkx_edges(G, pos, edgelist=straight_edges, edge_color="grey", arrowsize=6,  node_size = 10, width=0.8, connectionstyle=f'arc3, rad = 0.10')
    nx.draw_networkx_edges(G, pos, edgelist=curved_edges, edge_color="grey", arrowsize=6,  node_size = 10, width=0.8, connectionstyle=f'arc3, rad = 0.10')

    # Create a colorbar
    norm = plt.Normalize(vmin=0, vmax=1)
    sm = plt.cm.ScalarMappable(cmap=reversed_cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, orientation='vertical', ax=plt.gca())
    cbar.set_label('Centrality Betweenness values')  # Set a label for the colorbar

    # Finally, plotting
    map_image = mpimg.imread(f"{path}/04.Disparity/01.Input/{od}/google_map.png")
    # Display the map image as the background
    west, east = plt.xlim()[0], plt.xlim()[1]
    south, north = plt.ylim()[0], plt.ylim()[1]

    # Display the map image as the background
    west, east = plt.xlim()[0], plt.xlim()[1]
    south, north = plt.ylim()[0], plt.ylim()[1]
    plt.imshow(map_image, extent=[west, east, south, north], aspect='auto', alpha=0.3)
    # Show the plot
    plt.title(title)
    plt.tight_layout()
    # Save the plot to a file
    plt.savefig(f'{path}/04.Disparity/02.Output/centrality/img/{title}.png')

def plot_hist_kpi(name, kpi=None, G=None, edges=False):
    'if not G, then kpi must be an dictinary'

    if not edges:
        data1 = [G.nodes[node][name] for node in G.nodes()] if G else kpi.values()
    else:
        data1 = [G.edges[edge][name] for edge in G.edges()]
        data2 = [G.edges[edge]['alpha'] for edge in G.edges()]

    title = f'{od.upper()} {name.title()} Histogram'

    plt.figure(figsize=(10,7))
    plt.hist(data1, 50, facecolor='forestgreen', alpha=1,edgecolor='b')
    plt.hist(data2, 50, facecolor='sandybrown', alpha=0.5,edgecolor='b') if edges else None
    plt.legend([name.title(), "Alpha"]) if edges else None
    plt.title(title)
    plt.ylabel('Values Count')
    plt.xlabel(f'{name.title()} Values')
    plt.show()
    plt.savefig(f'{path}/04.Disparity/02.Output/{name}/img/{title}.png')

def plot_hist_att(name, Att1=None, Att2=None, G=None, edges=False):

    'implement for edges'

    for p in range(len(periods)):
        Entries = [G.nodes[node]['entries'][p] for node in G.nodes()]
        Exits = [G.nodes[node]['exits'][p] for node in G.nodes()]
        period = periods[p]
        max_value = max(max(Entries), max(Exits))
        # Determine the bin edges

        title = f'{od.upper()} {name.title()} {period.title()} {Att1.title()} & {Att2.title()} Histogram '

        plt.figure(figsize=(10,7))
        plt.hist(Entries, 50, facecolor='lightskyblue', alpha=0.75,edgecolor='b')
        plt.hist(Exits, 50, facecolor='indianred', alpha=0.5,edgecolor='b')
        plt.legend([Att1.title(), Att2.title()])
        plt.title(title)
        plt.ylabel('Values Count')
        plt.xlabel(f'{name.title()} Values')
        plt.savefig(f'{path}/04.Disparity/02.Output/Stations/img/{title}.png')


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

#### AUX FUNCTIONS ####
def populate_dictionaire(G, cols):
    # Create dictionaries for each column
    dictionaries = {name: {} for name in cols}
    for edge in G.edges(data=True):
        for col in cols:
            dictionaries[col][str(edge[:2])] = edge[2][col]

    return dictionaries

def create_dataframe(columns, edges):
    data = {edge: [None] * len(columns) for edge in edges}
    return pd.DataFrame(columns=columns, data=data)

def min_max_normalization(data, min_val=-1, max_val=1):
    """
    Min-Max Normalization for the interval [-1, 1].

    Parameters:
        data (list or numpy array): Input data to be normalized.
        min_val (float): Minimum value of the desired range (default is -1).
        max_val (float): Maximum value of the desired range (default is 1).

    Returns:
        list or numpy array: Normalized data.
    """
    if not data:
        raise ValueError("Input data is empty.")

    # Calculate minimum and maximum values of the data
    min_data = min(data)
    max_data = max(data)

    # Normalize each data point
    normalized_data = [(x - min_data) / (max_data - min_data) * (max_val - min_val) + min_val for x in data]

    return normalized_data


if __name__ == "__main__":

    global path
    global days
    global periods
    global od

    #### Defining variables  ####
    ods = ['tube', 'dlr', 'overground'] #'dlr', 'overground', 'tube'
    kpis = ['distress'] # 'distress', 'distance', 'speed', 'traffic', 'traffic_distances', 'loads','efficiencies', 'distress'
    days = ['mtt', 'fri', 'sat', 'sun'] # [ 'mtt', 'sun']
    periods = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late'] # ['Early', 'Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late'] for ov n dlr distress ranks
    path = "/mnt/c/buildbr/big-cities-transport"

    # Interact through variables hierarchically

    for od in ods:
        #### LOAD JSON BASEGRAPH  ###
        basegraph = load_graph(f'{path}/03.GraphModels/{od}/{od}-basegraph.json')
        edges = [(x[0], x[1]) for x in basegraph.edges(data=True)]
        # #### APPLY K-CORE  ####
        # kcores = plot_k_core(basegraph, od)
        # degree = {}
        # degree = {node: basegraph.degree(node)/2 for node in basegraph}
        # plot_hist_kpi('degree', kpi = degree)
        # #### APPLY CENTRALITY for DISTANCE  ####
        # centrality = calc_centrality (basegraph, od, "distance", min_degree=1)
        # plot_hist_kpi('centrality', kpi= centrality)
        # ### PLOTS Entries / Exists  ####
        # plot_entries_exists (basegraph, od, min_degree=1)
        # plot_hist_att('Stations', 'Entries', 'Exits', G= basegraph)

        for kpi in kpis:

            cols = ['alpha', 'alpha_rnk', f'{kpi}', f'{kpi}_rnk']

            #### Two type ov variables: Time-Independent & Time-Dependent ###
            if kpi in ['speed', 'distance']:
                # create name
                db = od+'-'+kpi
                #### LOAD JSON KPI-GRAPH  ####
                graph = load_graph(f'{path}/03.GraphModels/{od}/{db}.json')
                #### APPLY DISPARITY ####
                disparity_filter(graph, kpi) # add: alpha_ptile*, alpha* into graph
                #### PLOT BACKBONES ######
                plot_backbones(graph, od, kpi)
                ### ADD RANK INTO EDGES  ####
                # rank_edge(graph, kpi)  # add: kpi_rank*, alpha_rank* into graph
                # #### ADD RANK INTO DICT ####
                # kpi_dic = populate_dictionaire(graph, cols) # add: alpha**, alpha_rank**, kpi**, kpi_rank** into graph
                # #### EXPORT DICTIONARY AS PICKLE ####
                # dict_to_pickle(kpi_dic, f'{path}/04.Disparity/02.Output/{kpi}/ranks/rank-{od}-{kpi}.pickle')
                # #### EXPORT DICTIONARY AS CSV ####
                # df = pd.DataFrame.from_dict(kpi_dic, orient='index').transpose()
                # df.to_csv(f'{path}/04.Disparity/02.Output/{kpi}/ranks/rank-{od}-{kpi}.csv')
                # ### HISTOGRAMS: Kpi, Alpha ####
                # plot_hist_kpi(kpi, G= graph, edges=True) # do alpha as well?

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
                        ### PLOT BACKBONES ######
                        plot_backbones(graph, od, kpi, day, period)
                        # ### ADD RANK INTO EDGES  ####
                #         rank_edge(graph, kpi)  # add: weight_rank*, alpha_rank into graph
                #         #### ADD RANK INTO DICT ####
                #         kpi_dic[day][period] = populate_dictionaire(graph, cols)
                # #### EXPORT DICTIONARY AS PICKLE ####
                # dict_to_pickle(kpi_dic, f'{path}/04.Disparity/01.Input/{od}/{od}-{kpi}.pickle')
                # #### EXPORT DICTIONARY AS CSV ####
                # mux = pd.MultiIndex.from_product([days, periods, cols])
                # df = pd.DataFrame(columns=mux)
                # for col1, data1 in kpi_dic.items():
                #     for col2, data2 in data1.items():
                #         for col3, data3 in data2.items():
                #             df[col1, col2, col3] = pd.Series(data3)
                # df.to_csv(f'{path}/04.Disparity/02.Output/{kpi}/ranks/rank-{od}-{kpi}.csv')




