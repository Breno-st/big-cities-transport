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

G = nx.Graph()

def load_data_to_networkx(tx):
    kpi = 'distress'
    cypher_query = "MATCH (n)-[r]->(m) RETURN n, r, m"
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
    nx.draw(G, with_labels=True, node_color='lightblue', font_weight='bold')
    plt.show()


driver = GraphDatabase.driver("bolt://localhost:7687/", auth=('neo4j', "TFLbst1608."))
with driver.session(database='dlr-mtt-distress') as session:
    result = session.execute_read(load_data_to_networkx)


session.close()
driver.close()



# Run 5h/3, Bike 10h/4, Gym 5h (back, chest, leg, core, core)
# 10-jul week:45   12-12-21 free
# 17-jul week:52   16-12-24 free
# 24-jul week:58   16-16-24 speed
# 31-jul week:58   14-14-30 speed
# 07-aug week:58   14-14-30 speed
# 14-aug week:68   16-16-10-26 transition
# 21-aug week:74   16-16-12-30 transition
# 28-aug week:82   16-8-16-8-10-24 transition
# 04-sep week:97   14-8-14-8-21-28 volume
# 11-sep-sep:98    16-8-16-8-18-32 volume
# 18-sep week:20   10-10

# run, bike, gym: 4/4/5
# proj,lang, read,
# cook, clea, clot, mrkt

## (12-Jul) Mecredi:    5h: ----, 8h: work, 12h: work, 14h: work, 18h: cook, 20h: cst,  21h: ru12,  22h: read		>>> mrkt, cook, gym, eat, sleep
## (13-JuL) Jeudi:      5h: bike, 8h: work, 12h: work, 14h: work, 18h: beer, 20h: proj, 21h: proj, 22h: read		>>> Coffee in leuven
## (14-JuL) Vendredi:   5h: ru12, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: back, 21h: ----, 22h: read		>>> Coffee in leuven
## (22-JuL) Samedi:     5h: bike, 8h: room, 12h: mrkt, 14h: proj, 18h: proj, 20h: ----, 21h: ----, 22h: ----   		>>> Morning Bike, Afternoon Run
## (23-Jul) Dimache:    5h: ru21, 8h: clot, 12h: cook, 14h: proj, 18h: proj, 20h: ----, 21h: ----, 22h: ----		>>> Morning Bike, Afternoon Run

## (17-Jul) Lundi:      5h: legs, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: lang, 21h: lang, 22h: read		>>> Morning Legs
## (18-Jul) Mardi:      5h: ru16, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: proj, 21h: proj, 22h: read		>>> Morning Run/Core
## (19-Jul) Mecredi:    5h: bike, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: chst, 21h: ----, 22h: read		>>> Morning Bike/Run, Night Chst
## (20-JuL) Jeudi:      5h: ru12, 8h: Work, 12h:lunch, 14h: Work, 18h: cook, 20h: proj, 21h: proj, 22h: read		>>> Morning Run/Core, London
## (21-JuL) Vendredi:   5h: bike, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: back, 21h: ----, 22h: read		>>> London
## (22-JuL) Samedi:     5h: bike, 8h: room, 12h: mrkt, 14h: proj, 18h: proj, 20h: ----, 21h: ----, 22h: ----   		>>> London Run
## (23-Jul) Dimache:    5h: bike, 8h: clot, 12h: cook, 14h: proj, 18h: ru24, 20h: ----, 21h: ----, 22h: ----		>>> London


## (23-Jul) Dimache:    5h: ----, 8h: ----, 12h: ----, 14h: ----, 18h: ----, 20h: ----, 21h: ----, 22h:----			>>> London

## TODO SHORT

###

## TODO PLAN

## Thesis:
### Adjust Disparity Algo to Neo4J and prepare: Ranks, Percentiles
### Write Modeling KPIs part 4
### Write Methodology Distress part 2
### Write Methodology Disparity part 2
### Write Data Collections part 3
### Generate all results vizualizations
### Write Results part 5
### Write Conclusion part 7
### Write Following Steps part 6
### Re-Write Introduction part 1
