
# big-cities-transport
My thesis project. Database design, statistical inferences, algorithm for data exploration, modeling and visualization.

## Analysis
     
#### Operational 
- Segments importance rank by time (maintenace windows)
- Stations mobility index (avg trip speed,  tips frequency)
         
#### Customer 
- Shortest path (time, comfort) (network algorithm)    
- Study "Go-sitted  & Go-Standing" by regions against time (less priviledge regions?)
- Region mobility index (cluster aggregation)

## Theorem
- Urban Transportation Network.([Urban Transportation Networks](http://web.mit.edu/sheffi/www/selectedMedia/sheffi_urban_trans_networks.pdf))
- Markov process. Probabilities for currents
- Fluctuation Theorem.([NonLinear Response coeficients](https://arxiv.org/pdf/0704.3318.pdf))

## Models
- Dynamic Traffic Prediction [Predicting traffic flow using Bayesian networks](https://ideas.repec.org/a/eee/transb/v42y2008i5p482-509.html)
- Nash equilibrium [Modeling Network Traffic using Game Theory](https://www.cs.cornell.edu/home/kleinber/networks-book/networks-book-ch08.pdf
- Ranking segments importance (Backbone algorithm)
- Clustering stations nodes to (N) regions (unsupervised learning)

## Visualization
- Visualize the Crowdedness of Trains with Kepler (https://towardsdatascience.com/visualization-of-crowdedness-for-dutch-trains-with-kepler-f55057a3ba24)
- Visualization of travel times with OTP and QGIS (https://towardsdatascience.com/visualization-of-travel-times-with-otp-and-qgis-3947d36980420)

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
     
- Chap 2 - Data collection  
     - Sub chap 2.1- Explaning data sources: API / NUMBAT
     - Sub chap 2.2- Present Network divided by data categories (Structural / Functional / Operational / Traffic)
     - Sub chap 2.2- Explain each category: (Data origing, data limitation, indicators formulation) 
     
- Chap 3 - Model/Network ?
     - Sub chap 3.1 - TFL INfra structure: stations (structure) / Links / walkable distances
     - Sub chap 3.2 - TFL Transport systems: tube, DLR, ... (arrivals/traffic)
     - Sub chap 3.3 - 3 Operation Days Categories (Mon to Friday / SAT & Holidays / SUN)
     - Sub chap 3.4 - 4 Traffic Days Categories (MTT / FRI / SAT / SUN)
     
- Chap 4 - Central Question = Do we have three different networks?
     - Sub chap 4.1 -  each day type (MTT/FRI/SAT/SUN) compares to each other

- Chap 5 - Methodology
     - Sub chap 5.1 - Backbone (identify lines importance levels)
     - Sub chap 5.2 - How to Rank segments based on chosen indicator
     - Sub chap 5.3 - How to Classy fault severity based on segments affected

- Chap 6 - Results

- Chap 7 - Conlcusion  
     
- Chap 8 - Others quastion ?
     - Sub chap 8.1 - Applications 
     - Sub chap 8.2 - Following step (model to predict disruption)
     - Sub chap 8.3 - What could be done with more data (weather, dates in DD/MM/YY format)
     - Sub chap 8.4 - Following step (model to predict passengers)
     - Sub chap 8.5 - Following step (Predict impact from disruption/passengers predictions)
   
     * Time impact = delay_time * number of passenger
                
    
- List references :speech_balloon:
- Write (Abstract, Chapters):wrench: :raised_back_of_hand:   
  

### Presentation   
- Slides :heavy_check_mark:
- Breaking the ice :heavy_check_mark:
