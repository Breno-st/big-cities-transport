import scipy.integrate as spi
import numpy as np
from networkx.readwrite import json_graph

import json
from scipy.stats import percentileofscore
from traceback import format_exception
import networkx as nx
import numpy as np
import pandas as pd
from neo4j import GraphDatabase
import networkx as nx
import matplotlib.pyplot as plt
from scipy.stats import kendalltau

#################################### GLOSS CODE ###############

# Define the weight distribution function Pobs(w)
def Pobs(w):
    # Implement the weight distribution function here
    pass

# Define the probability function F(s, k)
def F(s, k):
    # Implement the probability function F(s, k) here
    pass

# Define a function to calculate the statistical significance alpha_ij
def calculate_significance(wij, si, ki, sj, kj):
    # Calculate the integrals in the numerator and denominator
    numerator_integral, _ = spi.quad(lambda w: Pobs(w) * F(si - w, ki - 1) * F(sj - w, kj - 1), wij, np.inf)
    denominator_integral, _ = spi.quad(lambda w: Pobs(w) * F(si - w, ki - 1) * F(sj - w, kj - 1), 0, np.inf)

    # Calculate the statistical significance alpha_ij
    alpha_ij = numerator_integral / denominator_integral

    return alpha_ij

# Define a threshold for significance
threshold = 0.05  # You can choose an appropriate threshold

# Iterate through edges in your network and calculate significance
for edge in edges:
    # Replace these values with the actual values from your network data
    wij = edge.weight
    si = edge.vertex_i_strength
    ki = edge.vertex_i_degree
    sj = edge.vertex_j_strength
    kj = edge.vertex_j_degree

    alpha_ij = calculate_significance(wij, si, ki, sj, kj)

    # Check if alpha_ij is below the threshold
    if alpha_ij < threshold:
        # Edge is not significant, do something with it (e.g., remove it)
        pass
    else:
        # Edge is significant, keep it or perform further analysis
        pass


#################################### OPERATE ###############

def load_graph (graph_path):
    ''' load a graph from JSON '''
    with open(graph_path) as f:
        data = json.load(f)
        graph = json_graph.node_link_graph(data, directed=True)
        return graph

if __name__ == "__main__":

    #### LOOP through KPIs  ####
    kpis = ['weight']

    for kpi in kpis:
        #### LOAD JSON DISPARITY  ####
        graph = load_graph("C:/buildbr/big-cities-transport/04.Disparity/weight.json")


        #### APPLY DISPARITY  ####

        alpha_measures = calculate_significance(graph, kpi)


        #### APPLY TABLE  ####
        edge_rank(graph, kpi)
        #node_view(graph)



        #### PLOT DISPARITY COLORING EDGES ####
        ' based on edges attributes [kpi], based on nodes attributes^[entries, exist, strength], how many graphs? '
        alpha_edge = color_map(graph)
        kpi_edge = color_map(graph, kpi)
