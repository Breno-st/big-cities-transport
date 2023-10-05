from networkx.readwrite import json_graph
import cProfile
import json
import pstats
import random
import sys

from scipy.stats import percentileofscore
from traceback import format_exception
import networkx as nx
import numpy as np
import pandas as pd
from neo4j import GraphDatabase
import networkx as nx
import matplotlib.pyplot as plt
from scipy.stats import kendalltau
import shutil


#### INPUT FOR DISPARITY FUNCTIONS ####

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

                edge["alpha"] = alpha
                alpha_measures.append(alpha)
            else:
                edge["alpha"] = 0.0

    for id0, id1 in graph.edges():
        edge = graph[id0][id1]
        edge["alpha_ptile"] = percentileofscore(alpha_measures, edge["alpha"]) / 100.0

    return alpha_measures

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

def edge_rank(G, kpi):

    # Combining two ranks: alpha and weight
    combined_edges = sorted(G.edges(data=True), key=lambda x: (x[2]['alpha_ptile'], x[2][kpi]), reverse=True)

    # Getting ranks positions
    alpha_sorted_edges = sorted(G.edges(data=True), key=lambda x: x[2]['alpha_ptile'], reverse=True) # should be the same as the combined
    kpi_sorted_edges = sorted(G.edges(data=True), key=lambda x: x[2][kpi], reverse=True)


    with open('temp.txt', 'w') as file:
        for edge in combined_edges:
            print(f"alpha: ({combined_edges.index(edge)+1}) {round(edge[2]['alpha_ptile'],3):.3f} | ({kpi_sorted_edges.index(edge)+1}) {kpi}: {round(edge[2][kpi],3):.3f}  | ({edge[0]} - {edge[1]}) ")
            file.write(f"alpha: ({combined_edges.index(edge)+1}) {round(edge[2]['alpha_ptile'],3):.3f} | ({kpi_sorted_edges.index(edge)+1}) {kpi}: {round(edge[2][kpi],3):.3f}  | ({edge[0]} - {edge[1]}) \n")

    # Store inside edge as attribute: 'pos_kpi'
    kpi_sorted_edges_ = [(x[0], x[1]) for x in kpi_sorted_edges]
    alpha_sorted_edges_ = [(x[0], x[1]) for x in alpha_sorted_edges]

    for id0, id1 in G.edges():
        edge = graph[id0][id1]
        aux = kpi +'_pos'
        edge[aux] = kpi_sorted_edges_.index((id0, id1))+1
        edge['alpha_pos'] = alpha_sorted_edges_.index((id0, id1))+1


    # Calculate Kendall ranking metric
    kpi_rank = [kpi_sorted_edges.index(edge)+1 for edge in combined_edges]
    alpha_rank = [alpha_sorted_edges.index(edge)+1 for edge in combined_edges]

    tau, p_value = kendalltau(kpi_rank, alpha_rank)
    correlation = spearman_rank_correlation(kpi_rank, alpha_rank)

    # Output Kendall ranking
    print(f"Kendall Ranking Metric: tau: {tau} and P-value: {p_value}")
    print(f"Spearman Rank Correlation: {correlation}")

def spearman_rank_correlation(rank_seq1, rank_seq2):
    """
    Calculate the Spearman Rank Correlation Coefficient between two rank sequences.

    Parameters:
    rank_seq1 (list): The first rank sequence.
    rank_seq2 (list): The second rank sequence.

    Returns:
    float: The Spearman Rank Correlation Coefficient, ranging from -1 to 1.
    """
    if len(rank_seq1) != len(rank_seq2):
        raise ValueError("Both rank sequences must have the same length")

    n = len(rank_seq1)

    # Calculate the rank differences squared
    d_squared = [(rank_seq1[i] - rank_seq2[i]) ** 2 for i in range(n)]

    # Calculate the Spearman Rank Correlation Coefficient
    r = 1 - (6 * sum(d_squared)) / (n * (n ** 2 - 1))

    return r

def node_view(G):
    G.nodes.strengh
    G.nodes.degree
    G.nodes.centrality


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

def draw_grid(G, node_att, edge_att, node_colors_kpi, edge_colors_kpi):

    pos = {}
    for node in G.nodes():
        pos[node] = (G.nodes[node]['long'], G.nodes[node]['lat'])

    plt.figure(figsize=(16, 8))


    # Draw Nodes
    #draw_networkx_nodes(G, pos, nodelist=None, node_size=300, node_color='r', node_shape='o', alpha=1.0, cmap=None, vmin=None, vmax=None, ax=None, linewidths=None, label=None, **kwds)[source]

    nx.draw_networkx_nodes(G, pos, node_size=20, node_color='white')
    # Draw Nodes Label
    nx.draw_networkx_labels(G, pos, font_size= 15)
    # Draw Edges
    curved_edges = [edge for edge in G.edges() if reversed(edge) in G.edges()]
    straight_edges = list(set(G.edges()) - set(curved_edges))
    nx.draw_networkx_edges(G, pos,  edgelist=straight_edges)
    # Draw Edges
    nx.draw_networkx_edges(G, pos,  edgelist=curved_edges, edge_color=edge_colors_kpi,
                           arrowsize=6,  node_size = 20,
                           width=0.8, connectionstyle=f'arc3, rad = 0.10')
    # Draw Edges Labels
    aux = edge_att+'_pos'
    # edge_labels = dict([((u, v,), f'{round(d[aux],2)}\n\n{G.edges[(v,u)][aux]}') for u, v, d in G.edges(data=True) if pos[u][0] > pos[v][0]])
    #nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size= 5, font_color='black')

    # Create a colorbar
    norm = plt.Normalize(vmin=0, vmax=1)
    cmap = plt.get_cmap("Reds")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, orientation='vertical')
    cbar.set_label('Edges values')  # Set a label for the colorbar

    # Show the plot
    plt.title("Edges Ranks by " + edge_att)

    # plt.axis([-0.405, 0.258, 51.37, 51.71]) #overgroung
    plt.tight_layout()
    plt.show()
    plt.savefig("temp.png")


def color_map(G, edge_att="alpha_ptile", node_att="strength"):

    cmap = plt.get_cmap("Reds")

    values = [G.edges[edge][edge_att] for edge in G.edges()]
    edge_colors_kpi = [cmap(value) for value in values]

    cmap = plt.cm.jet
    values = [G.nodes[node][node_att] for node in G.nodes()]
    node_colors_kpi = [cmap(value) for value in values]

    if edge_att == "alpha_ptile":
        edge_att="alpha"

    draw_grid( G, node_att, edge_att, node_colors_kpi, edge_colors_kpi)

    return node_colors_kpi


if __name__ == "__main__":



    #### LOOP through KPIs  ####
    ods = [ 'tube'] # 'overground', 'dlr',
    days = ['mtt', 'sun']
    period = ['Total', 'Early', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']
    kpis = ['distancetraffic', 'efficiency', 'loads', 'traffic', 'speed', 'distance'] # 'distress' review distress graphs
    # od-day-period-kpi
    # od-kpi

    for od in ods:
        for kpi in kpis:
            if kpi not in ['speed', 'distance', 'basegraph']:
                for day in days:
                    db = od+'-'+day+'-'+kpi
            else:
                db = od+'-'+kpi

            #### LOAD JSON DISPARITY  ####
            path = "C:/buildbr/big-cities-transport/03.GraphModels"
            graph = load_graph(f'{path}/{od}/{db}.json')

            #### APPLY DISPARITY  ####
            alpha_measures = disparity_filter(graph, kpi)

            #### APPLY TABLE  ####
            path = "C:/buildbr/big-cities-transport/04.Disparity"
            edge_rank(graph, kpi)
            #node_view(graph)
            shutil.move('temp.txt', f'{path}/{od}/{db}_rank.txt', copy_function=shutil.copy2)

            #### PLOT DISPARITY COLORING EDGES ####
            ' based on edges attributes [kpi], based on nodes attributes^[entries, exist, strength], how many graphs? '
            alpha_edge = color_map(graph)
            shutil.move('temp.png', f'{path}/{od}/alpha_{db}.png', copy_function=shutil.copy2)

            kpi_edge = color_map(graph, kpi)
            shutil.move('temp.png', f'{path}/{od}/{db}.png', copy_function=shutil.copy2)





# # Run 5h/3, Bike 10h/4, Gym 5h (back, chest, leg, core, core)
# # 23-sep week:45   12-12-21 free
# # 30-sep week:52   16-12-24 free
# # 07-oct week:58   14-14-30 speed
# # 14-oct week:68   16-16-10-26 transition
# # 21-oct week:74   16-16-12-30 transition
# # 28-oct week:82   16-8-16-8-10-24 transition
# # 04-nov week:97   14-8-14-8-21-28 volume
# # 11-nov-week:98   10-10

# # run, bike, gym: 4/4/5
# # proj,lang, read,
# # cook, clea, clot, mrkt


# ## (17-Jul) Lundi:      5h: ----, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: legs, 21h: lang, 22h: read		>>> Night Legs
# ## (18-Jul) Mardi:      5h: ru16, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: core, 21h: proj, 22h: read		>>> Morning Run/Core
# ## (19-Jul) Mecredi:    5h: bike, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: chst, 21h: ----, 22h: read		>>> Morning Bike/Run, Night Chst
# ## (20-JuL) Jeudi:      5h: ru12, 8h: Work, 12h:lunch, 14h: Work, 18h: cook, 20h: proj, 21h: proj, 22h: read		>>> Morning Run/Core, London
# ## (21-JuL) Vendredi:   5h: bike, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: back, 21h: ----, 22h: read		>>> London
# ## (22-JuL) Samedi:     5h: bike, 8h: room, 12h: mrkt, 14h: proj, 18h: proj, 20h: ----, 21h: ----, 22h: ----   		>>> London Run
# ## (23-Jul) Dimache:    5h: bike, 8h: clot, 12h: cook, 14h: proj, 18h: ru24, 20h: ----, 21h: ----, 22h: ----		>>> London


# ## (23-Jul) Dimache:    5h: ----, 8h: ----, 12h: ----, 14h: ----, 18h: ----, 20h: ----, 21h: ----, 22h:----			>>> London

# ## TODO SHORT

# ###

# ## TODO PLAN

# ## Thesis:


#5### Recreate distress graphsfor periods
#6### Recreate kpis graphs for periods
#6### Compare diff periods within a day, resulting in 3 correlation matrix
#6### Compare same period through out days, resultion table periods (6) x days (3)
#6### Cut off the most interesting graphs comparissons
#7### Write Results part 5
#7### Write Modeling KPIs part 4
#11### Write Methodology Distress part 2
#11### Write Methodology Disparity part 2
#12### Write Data Collections part 3
#12### Generate all results vizualizations
#13### Write Conclusion part 7
#13### Write Following Steps part 6
#14### Re-Write Introduction part 1

# ### Create code for GloSS
# ### Improve data visualisations
# ### Turn big-citis-transpot into App:
# ### Connect and improve codes to build an app (example 2)
# ### Example 2: Application Development (Databases, Django)


# ### Desing Finance Application



