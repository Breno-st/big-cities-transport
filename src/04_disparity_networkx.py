from networkx.readwrite import json_graph
import cProfile
import json
import pstats
import random
import sys
from matplotlib.transforms import Affine2D
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
import folium
from folium.plugins import MiniMap
import mplleaflet
from mpl_toolkits.basemap import Basemap
from matplotlib.colors import ListedColormap

import folium
from math import sin, cos, sqrt, atan2, radians
from folium import plugins

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
import math


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

def cut_graph (graph_original, min_alpha_ptile=0.5, min_degree=2):
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

def populate_single_period(G, cols):
    # Create dictionaries for each column
    dictionaries = {name: {} for name in cols}
    for edge in G.edges(data=True):
        for col in cols:
            dictionaries[col][str(edge[:2])] = edge[2][col]

    return pd.DataFrame.from_dict(dictionaries, orient='index').transpose()

def populate_multi_periods(df, G, kpi, day, period):
    pass

def rank_correlation_matrix(df):
    ''' Calculate Kendall & Spearman ranking metric '''
    # Get two lists for comparisson:
    days_against_days_list = []
    period_against_period_list = []

    # Day perspective: comparing periods
    for day in days:
        for period1, period2 in period_against_period_list:
            list1 = df[day][period1].to_list()
            list2 = df[day][period2].to_list()
            # Enter the two lists and store into Day Matrix 6x6
            tau, p_value = kendalltau(list1, list2)
            correlation = spearman_rank_correlation(list1, list2)
            # Output Kendall ranking
            print(f"Kendall Ranking Metric for {day}: {period1}x{period2} : tau: {tau} and P-value: {p_value}")
            print(f"Spearman Rank Correlation for {day}: {period1}x{period2}: {correlation}")

    # Period perspective: comparing day
    for period in periods:
        for day1, day2 in days_against_days_list:
            list1 = df[day1][period].to_list()
            list2 = df[day2][period].to_list()
            # Enter the two lists and store into Period Matrix 4x4
            tau, p_value = kendalltau(list1, list2)
            correlation = spearman_rank_correlation(list1, list2)
            # Output Kendall ranking
            print(f"Kendall Ranking Metric for {period}: {day1}x{day2} : tau: {tau} and P-value: {p_value}")
            print(f"Spearman Rank Correlation for {period}: {day1}x{day2}: {correlation}")

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

    cuts = [0.25, 0.5, 0.75]
    title = f'{od} {kpi} {day} {period} disparity ranked edges' if day else f'{od} {kpi} disparity ranked edges'
    dim = plot_edges(title, G, "Reds", "alpha")
    title = f'{od} {kpi} {day} {period} ranked edges' if day else f'{od} {kpi} ranked edges'
    plot_edges(title, G, "Greens", kpi)

    cuts = [0.25, 0.5, 0.75]
    for cut in cuts:
       title = f'{od} {kpi} {round(cut*100)}th percentile edges {day} {period}' if day else f'{od} {kpi} {round(cut*100)}th percentile edges'
       G_ptile = cut_graph(G, cut, min_degree=2)
       plot_edges(title, G_ptile, "Reds", "alpha", dim)

def plot_edges(title, G, color, kpi, dim=None):

    pos = {}
    for node in G.nodes():
        pos[node] = (G.nodes[node]['long'], G.nodes[node]['lat'])

    # Defining colors
    cmap = plt.get_cmap(color)
    reversed_cmap = ListedColormap(cmap(np.linspace(1, 0, 256)))
    values = [G.edges[edge][kpi] for edge in G.edges()]
    edge_colors = [cmap(value) for value in values]  if kpi != "alpha" else [reversed_cmap(value) for value in values]
    # Defining size
    fig = plt.figure(figsize=(16, 8))
    if dim:
        plt.xlim(dim[0])
        plt.ylim(dim[1])
    # Draw Nodes
    nx.draw_networkx_nodes(G, pos, node_size=20, node_color='dimgrey')
    # Draw Nodes Label
    nx.draw_networkx_labels(G, pos, font_size= 10, verticalalignment='bottom', horizontalalignment='left', font_color='dimgrey')
    # Draw Edges
    curved_edges = [edge for edge in G.edges() if reversed(edge) in G.edges()]
    straight_edges = list(set(G.edges()) - set(curved_edges))
    nx.draw_networkx_edges(G, pos, edgelist=straight_edges)
    nx.draw_networkx_edges(G, pos, edgelist=curved_edges, edge_color=edge_colors, arrowsize=6,  node_size = 20, width=0.8, connectionstyle=f'arc3, rad = 0.10')
    # Create a colorbar
    norm = plt.Normalize(vmin=0, vmax=1)
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm) if kpi != "alpha" else plt.cm.ScalarMappable(cmap=reversed_cmap, norm=norm)
    sm.set_array([])
    cbar = plt.colorbar(sm, orientation='vertical')
    cbar.set_label('Edges values')  # Set a label for the colorbar
    # Show the plot
    plt.title(title)
    plt.tight_layout()
    # Save the plot to a file
    plt.savefig(f'{title}.png')
    return plt.xlim(), plt.ylim()

def create_dataframe(columns, edges):
    data = {edge: [None] * len(columns) for edge in edges}
    return pd.DataFrame(columns=columns, data=data)

def node_view(G):
    G.nodes.strengh
    G.nodes.degree
    G.nodes.centrality


if __name__ == "__main__":

    global path
    #### Defining variables  ####
    ods = [ 'dlr'] # 'overground', 'dlr', 'tube'
    days = ['fri', 'sat', 'mtt', 'sun']
    periods = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']
    kpis = ['distance', 'speed', 'traffic', 'traffic_distances', 'loads', 'efficiencies', 'distress']# 'distress' review distress graphs
    path = "C:/buildbr/big-cities-transport"

    # Interact through variables hierarchically
    for od in ods:
        for kpi in kpis:
            #### Extract graph edges from BaseGraph  ###
            basegraph = load_graph(f'{path}/03.GraphModels/{od}/{od}-basegraph.json')
            edges = [(x[0], x[1]) for x in basegraph.edges(data=True)]

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
                # based on edges attributes: kpi, alpha_ptile, cutted by alpha
                plot_disparities(graph, od, kpi)
                #### CRATE DATAFRAME ####
                cols = ['alpha', 'alpha_rnk', f'{kpi}', f'{kpi}_rnk']
                df = populate_single_period(graph, cols) # add: alpha**, alpha_rank**, kpi**, kpi_rank** into graph
                #### APLY RANK CORRELATION ####
                rank_correlation_matrix(df)

            else: # loop through day and periods
                kpi_dic = {}
                for day in days:
                    for period in periods:
                        # create name
                        auxk = kpi.replace('_', '')
                        auxp = period.replace(' ', '-')
                        db = od+"-"+auxk+"-"+day.lower()+"-"+auxp.lower()
                        #### LOAD JSON DISPARITY  ####
                        graph = load_graph(f'{path}/03.GraphModels/{od}/{db}.json')
                        #### APPLY DISPARITY  ####
                        disparity_filter(graph, kpi) # add: alpha_ptile, alpha into graph
                        #### RANK EDGES BASED ON KPI AND ALPHA ####
                        rank_edge(graph)  # add: weight_rank*, alpha_rank into graph
                        #### PLOTs kpi (Greens), alpha (Reds), ptiles (Reds)#### #TODO
                        plot_disparities(graph, od, kpi, day, period)

                        shutil.move('temp.png', f'{path}/04.Disparity/{od}/alpha_{db}.png', copy_function=shutil.copy2)

                        # based on nodes attributes^[entries, exist, strength]

                #### CRATE DATAFRAME ####
                df = populate_multi_periods(kpi_dic) #TODO
                #### APLY RANK CORRELATION ####
                rank_correlation_matrix(df) #TODO



            df.to_csv(f'{path}/04.Disparity/{od}/{db}.csv')


            # #### APPLY RANK CORRELATION ALGORTIHMS #### READY to Go
            # rank_correlation_matrix(df)

            # #### PLOT CORRELATIONS MATRIX ####


            # #### EFFICIENCY & DISTRESS COMPARISSON ####
            # rank_correlation_matrix(df)


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

# ## (23-Oct) Lundi:      5h: ----, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: legs, 21h: lang, 22h: read		>>> Colruyte, LINGI
# ## (24-Oct) Mardi:      5h: ru16, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: core, 21h: proj, 22h: read		>>> Morning Run/Core
# ## (25-Oct) Mecredi:    5h: bike, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: chst, 21h: ----, 22h: read		>>> Zena, Giulia, Candidates
# ## (26-Oct) Jeudi:      5h: ru12, 8h: Work, 12h:lunch, 14h: Work, 18h: cook, 20h: proj, 21h: proj, 22h: read		>>> Pay Lucas, Praty, Gong
# ## (27-Oct) Vendredi:   5h: bike, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: back, 21h: ----, 22h: read		>>>
# ## (28-Oct) Samedi:     5h: bike, 8h: room, 12h: mrkt, 14h: proj, 18h: proj, 20h: ----, 21h: ----, 22h: ----   	>>>
# ## (29-Oct) Dimache:    5h: bike, 8h: clot, 12h: cook, 14h: proj, 18h: ru24, 20h: ----, 21h: ----, 22h: ----		>>> Praty

# ## (22-Oct) Dimache:    5h: ----, 8h: ----, 12h: ----, 14h: ----, 18h: ----, 20h: ----, 21h: ----, 22h:----		>>> 4h proj
# ## (23-Oct) Dimache:    5h: ----, 8h: ----, 12h: ----, 14h: ----, 18h: ----, 20h: ----, 21h: ----, 22h:----		>>> 4h proj

# ## TODO SHORT
# ### 04 Nov: Farewell Lille
# ### 11 Nov: Athens
# ### 18 Nov: Farewell NE
# ### 25 Nov: Farewell ML
# ### 02 Dec: Farewell LU
# ### 10 Dec: ??


# ### 01 Dec: Breda xxx€ normal   (RENT - fillup car)
# ### 15 Dec: BE>IT  45€ remote   (5 days IT)
# ### 20 Dec: IT>SP 464€ unpaid   (23 days BR)
# ### 12 Jan: SP>PT 680€ holidays (5 days PT)
# ### 17 Jan: PT>BE  62€ holidays (13 days HAL) Exam, thesis, resignation (give back the car and unpaid leaves), domiciliation, Basic-fit
# ### 30 Jan: BE>BE 375€ holidays (7 days HAL)
# ### 30 Jan: BE>?? xxx€ --------------------------------------------------------------------
# ### TOTAL:  1726€

# ### DEP:    1700€
# ### DEZ:    2500€
# ### 13o:    3000€
# ### JAN:    3000€
# ### TOTAL: 11098€


# ### UCL:   -4300€

# ### Bal:    6798€

# ## TODO PLAN
# ## UCL pay, My Trip, Camila Trip, Laptop,

# ## TODO Thesis:

#4h### Check Alpha and Ranking order for significance
#4h### Compare diff periods within a day, resulting in 3 correlation matrix 23/10
#4h### Compare same period through out days, resultion table periods (6) x days (3)
#4h### Cut off the most interesting graphs comparissons by 30/10
#8h### Write Results part 5 06/11
#8h### Write Modeling KPIs part 4 13/11
#4h### Write Methodology Distress part 2
#4h### Write Methodology Disparity part 2 20/11
#4h### Write Data Collections part
#4h### Write Conclusion part 7  by 27/11
#8h### Generate all results vizualizations by 04/12
#4h### Write Following Steps part 6
#4h### Re-Write Introduction part 1  11/12
#68###

# ### Create code for GloSS
# ### Improve data visualisations
# ### Turn big-citis-transpot into App:
# ### Connect and improve codes to build an app (example 2)
# ### Example 2: Application Development (Databases, Django)


# ### Desing Finance Application



