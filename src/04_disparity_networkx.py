
from networkx.readwrite import json_graph
from scipy.stats import percentileofscore
from traceback import format_exception
import cProfile
import json
import networkx as nx
import numpy as np
import pandas as pd
import pstats
import random
import sys



## (19-Jun) Lundi:      5h: ----, 8h: ----, 12h: ----, 14h:----, 18h: ----, 20h: ----, 21h: ----			>>> Frascheta Sant'Angelo
## (20-Jun) Mardi:      5h: ----, 8h: ----, 12h: ----, 14h:----, 18h: ----, 20h: ----, 21h: ----			>>> Frascheta Sant'Angelo
## (14-Jun) Mecredi:    5h: ----, 8h: ----, 12h: ----, 14h:----, 18h: runn, 20h: Seat, 21h: Cook
## (15-Jun) Jeudi:      5h: bike, 8h: Work, 12h:lunch, 14h:Work, 18h: back, 20h: Shav, 21h: Toil
## (16-Jun) Vendredi:   5h: bike, 8h: Work, 12h: hair, 14h:Gift, 18h: chst, 20h: AirP, 21h: ----
## (17-Jun) Samedi:     5h: ----, 8h: ----, 12h: ----, 14h:----, 18h: ----, 20h: ----, 21h: ----   			>>> tickets to London, run, gelato, cook carbonara, beer matsui
## (18-Jun) Dimache:    5h: ----, 8h: ----, 12h: ----, 14h:----, 18h: ----, 20h: ----, 21h: ----			>>> Frascheta Sant'Angelo, S. Cosimate


## TODO SHORT

### Pay Giulia/
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
