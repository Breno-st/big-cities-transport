
# big-cities-transport
The aim of this project is to model a public transport sytem to evaluate its dynamic along different moments of the week. Eventually, this project relies on assumptions and indicators that hipothetically reflects the network operators interest in order to rank, compare and evaluate the variance of the infra-structure branches importance along the time.
In summary, this project model uses network science techiniques to outcome valuable information to decision takers for a goal-oriented and optimized system operation.

## Objectives

#### Operational
- Segments importance rank by time (maintenace windows)
- Stations mobility index (avg trip speed,  tips frequency)

#### Customer
- Shortest path (time, comfort) (network algorithm)
- Study "Go-sitted  & Go-Standing" by regions against time (less priviledged regions?)
- Region mobility index (cluster aggregation)

## Implementation

### Data Collection

#### TFL
- APIs :heavy_check_mark:
- Data explorations :wrench:

### Modeling the system

#### Neo4j and/or Networkx
- Node: stations
- Stations attributes (mode, lines)
- Edges: connections
- connections attributes (intra/inter, traffic, speed, hour)

### Statistics
- Use ANOVA to indentify journeys relevant statistical independence to among:
- Day of week / Time of the day

#### Algorithms
- Clustering
- Shortest path
- Backbone

#### Machine Learning
- Disruptions (when it will be the next disruption)
- Reinforcement learning (day + weather = passenger prediction)

## Reporting & Presenting

### Overleaf
- Find template :heavy_check_mark:
- Structure report :speech_balloon:
- Abstract

- Chap 1 - Introduction
     - Sub chap 1.1 - Central Question = Do we have three different networks?
     - Sub chap 1.2 - Each day type (MTT/FRI/SAT/SUN) compares to each other in term of functioning and traffic

- Chap 2 - Methodology
     - Sub chap 2.1 - Backbone (identify lines importance levels)
     - Sub chap 2.2 - How to Rank segments based on chosen indicator
     - Sub chap 2.3 - How to classify fault severity based on segments affected

- Chap 3 - Data collection
     - Sub chap 3.1- Explaning data sources: API / NUMBAT
     - Sub chap 3.2- Present Network divided by data categories (Structural / Functional / Operational / Traffic)
     - Sub chap 3.2- Explain each category: (Data origing, data limitation, indicators formulation)

- Chap 4 - Model/Network ?
     - Sub chap 4.1 - TFL Infra structure: stations (structure) / Links / walkable distances
     - Sub chap 4.2 - TFL Transport systems: tube, DLR, ... (arrivals/traffic)
     - Sub chap 4.3 - 3 Operation Days Categories (Mon to Friday / SAT & Holidays / SUN)
     - Sub chap 4.4 - 4 Traffic Days Categories (MTT / FRI / SAT / SUN)
     - Sub chap 4.5 - Indicators creation (mobility index, Avg. speed, Rank, clustering)
     - How to model?
     - - The edges are weighted by traffic (real)
     - - Nodes traffic balance and the delta between connection becomes weight (insight for finance)
     - - Compare two above
     - - Everything is connectec to everything, what goes up/down together from graph perspective?
     - - Fundamentalist indicators inputs ()
     - - Historic Data
     - - Portifolio management, diversity, volatility, risk

- Chap 5 - Results
     - Sub chap 5.1 - Statistical methods
     - Sub chap 5.2 - Compares operation (MTT/FRI/SAT/SUN)
     - Sub chap 5.3 - Compares traffic (MTT/FRI/SAT/SUN)
     - Sub chap 5.4 - Compares operational response (MTT/FRI/SAT/SUN) in terms of  traffic

- Chap 6 - Following steps ?
     - Sub chap 6.1 - Applications
     - Sub chap 6.2 - Model to predict disruption
     - Sub chap 6.3 - What could be done with more data (weather, dates in DD/MM/YY format)
     - Sub chap 6.4 - Model to predict passengers)
     - Sub chap 6.5 - Predict impact from disruption/passengers predictions)
     - Sub chap 6.6 - Dynamic route timetable (tailored to passangers predictions)

     * Time impact = delay_time * number of passenger

- Chap 7 - Conlcusion


### Presentation
- Slides :heavy_check_mark:
- Breaking the ice :heavy_check_mark:

## References
- Backbone [Extracting the multiscale backbone of complex weighted networks]
- Nash equilibrium [Modeling Network Traffic using Game Theory](https://www.cs.cornell.edu/home/kleinber/networks-book/networks-book-ch08.pdf
- Urban Transportation Network.([Urban Transportation Networks](http://web.mit.edu/sheffi/www/selectedMedia/sheffi_urban_trans_networks.pdf))
- Markov process. Probabilities for currents
- Fluctuation Theorem.([NonLinear Response coeficients](https://arxiv.org/pdf/0704.3318.pdf))
- Dynamic Traffic Prediction [Predicting traffic flow using Bayesian networks](https://ideas.repec.org/a/eee/transb/v42y2008i5p482-509.html)
- Visualize the Crowdedness of Trains with Kepler (https://towardsdatascience.com/visualization-of-crowdedness-for-dutch-trains-with-kepler-f55057a3ba24)
- Visualization of travel times with OTP and QGIS (https://towardsdatascience.com/visualization-of-travel-times-with-otp-and-qgis-3947d36980420)
