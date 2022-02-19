
# big-cities-transport
My thesis project. Database design, statistical inferences, algorithm for data exploration, modeling and visualization.

## Ideas

### Analytical (Statisctics) 
     
#### Operational perspective
- Compare train load in different areas
         
#### Customer perspective
- Go-sitted regions & Go-Standing regions against time
- Faster trains by regions & Go-Standing regions against time
         
### Forecasting (Machine Learning & Data mining)
- Clustering stations nodes to (N) regions (unsupervised learning)
- Use graph minining  
- Shortest path (time, comfort, cost) (reinforcement learning)    

## Theorem
- Urban Transportation Network.([Urban Transportation Networks](http://web.mit.edu/sheffi/www/selectedMedia/sheffi_urban_trans_networks.pdf))
- Markov process. Probabilities for currents
- Fluctuation Theorem.([NonLinear Response coeficients](https://arxiv.org/pdf/0704.3318.pdf))

## Models
- Dynamic Traffic Prediction([Predicting traffic flow using Bayesian networks](https://ideas.repec.org/a/eee/transb/v42y2008i5p482-509.html))
- Nash equilibrium ([Modeling Network Traffic using Game Theory](https://www.cs.cornell.edu/home/kleinber/networks-book/networks-book-ch08.pdf))
- Reinforcement learning

## Visualization
- Visualize the Crowdedness of Trains with Kepler (https://towardsdatascience.com/visualization-of-crowdedness-for-dutch-trains-with-kepler-f55057a3ba24)
- Visualization of travel times with OTP and QGIS (https://towardsdatascience.com/visualization-of-travel-times-with-otp-and-qgis-3947d36980420)

## Implementation

### Collect and store data
              
#### TFL
- APIs :heavy_check_mark:
- Data explorations :wrench:
- pipelines & storage     
         
#### Weather
- Source
- Storage

### Build transport system

#### Neo4j 
- Get stations (nodes)
- stations types (mean labels)
- stations area (1 -> 8 labels)
- stations class (1 -> 8 labels)
- stations connections (edges)
- connections types (intra/inter labels)

#### Networkx
- Import journey segments.

### Data Analysis (Climate / Journey) 

#### Statistical     
- Use ANOVA to indentify journeys relevant statistical independence to among: 
- Ticket type / Season of the year / Day of week / Time of the day / Meteo condition / Temperature   

#### Pattern mining   
- Graph mining
- Bayesian

## Reporting & Presenting

### Overleaf
- Find template :heavy_check_mark:
- Structure report :speech_balloon:
     - Abstract
     
     - Chap 1 - Introduction
     
     - Chap 2 - Data ?  
     - Explaning data sources: API / NUMBAT
     - Present Network divided by data categories (Structural / Functional / Operational / Traffic)
     - Explain each category: (Data origing, data limitation, indicators formulation) 
     
     - Chap 3 - Model/Network ?
     - Sub chap 3.1 - TFL INfra structure: stations
     - Sub chap 3.2 - TFL Transport systems: tube, DLR, ... (traffic/
     - Sub chap 3.3 - Day time categories 
     
     - Chap 4 - Methodology/ Central Question ?
     - Backbone (identify lines importance levels)
     - How to Rank segments based on chosen indicator
     - How to Classy fault severity based on segments affected
     
     - Chap 5 - Central Question ? Do we have three different networks?
     - How each day type (MTT/FRI/SAT/SUN) compares to each other
     -
          
     - Chap 6 - Central Question ? Do we have three different networks?
     
- List references :speech_balloon:
- Write (Abstract, Chapters):wrench: :raised_back_of_hand:   
  

### Presentation   
- Slides :heavy_check_mark:
- Breaking the ice :heavy_check_mark:
