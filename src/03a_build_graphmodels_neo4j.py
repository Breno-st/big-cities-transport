from pip import main
import pandas as pd
import numpy as np
import pickle
from neo4j import GraphDatabase, basic_auth


#### PICKLE FUNCTIONS ####

def load_pickle(filename):
    with open(filename, 'rb') as handle:
        loadedfile = pickle.load(handle)
    return loadedfile


#### NEO4J BASEGRAPH FUNCTIONS ####

def _directed_pairs():
    '''
    With the open seesion, it connect to NEO4J and extracts a list of
    of tupples (Origins, Destination, Mode)
    Input:   NA
    Output:  List of tuples [(Origins, Destination, Mode),...]
    '''

    result = session.run('MATCH (n)-[r:TO]->(m) RETURN DISTINCT n.naptanid as orig, id(n) as id_orig, m.naptanid as dest, id(m) as id_dest, r.mode as mode')
    pairs = [(record['orig'],record['dest'],record['mode']) for record in result]
    return pairs

#### GRAPH MODELLING FUNCTIONS ####
def reverse_keys(original_dict):
    new_dict = {}
    for key, inner_dict in original_dict.items():
        for day, period_dict in inner_dict.items():
            for period, value in period_dict.items():
                if day not in new_dict:
                    new_dict[day] = {}
                if period not in new_dict[day]:
                    new_dict[day][period] = {}
                new_dict[day][period][key] = value

    return new_dict

def _unique_rel_kpis(mode, pairs):
    '''
    It uses the list of (Orig, Dest, Mode) tuples, to access the relations in the

    Input:      List of tuples [(Origins, Destination, Mode),...]
    Return:     dict[kpis][day][period]
    '''

    # Import file from pickle
    path = 'C:/buildbr/big-cities-transport/02.Distress/02.Output/'
    distress = load_pickle(f'{path}distress_segments_{mode}.pickle') # reverse [key][day][period] to [day][period][key] TOTEST
    distress = reverse_keys(distress)

    output = {'distress': distress}

    # Generate dictionary
    for kpi in kpis:
        output[kpi]={}
        if kpi not in ['distance', 'speed']:
            for day in days:
                output[kpi][day]={}
                for i in range(1,7):
                    output[kpi][day][periods[i]]={}

    lines_cnt = 0 # check value against Neo4j

    for pair in pairs:
        # extract pair and assemble cypher
        origin, destiny, mode = pair[0], pair[1], pair[2]
        rel_by_pairs = "MATCH (n)-[r:TO]->(m) WHERE n.naptanid='{}' and m.naptanid='{}' RETURN r".format(origin, destiny)
        result = session.run(rel_by_pairs)
        relations = [record for record in result]
        lines_cnt += len(relations)
        # merge counters
        from_id, traffics_edge, frequencies_edge, speed_edge, distance_edge, to_id = _merge_lines(relations)
        # store in dictionaires with same key
        key = (from_id, to_id)

        for kpi in kpis:
            if kpi == 'distance':
                output[kpi][key] = round(distance_edge,2) # Dict kpi 1
            elif kpi == 'speed':
                output[kpi][key] = round(speed_edge,2) # Dict kpi 2
            else:
                for day in days:
                    for i in range(1,7):
                        if kpi == 'traffic': # Dict kpi 3
                            output[kpi][day][periods[i]][key] = round(traffics_edge[day][periods[i]],2)
                        elif kpi == 'traffic_distances': # Dict kpi 4
                            output[kpi][day][periods[i]][key] = round(traffics_edge[day][periods[i]] * distance_edge,2)
                        elif kpi == 'loads': # Dict kpi 5
                            if frequencies_edge[day][periods[i]] != 0:
                                output[kpi][day][periods[i]][key] = round((traffics_edge[day][periods[i]])*(speed_edge/frequencies_edge[day][periods[i]]),2)
                            else:
                                output[kpi][day][periods[i]][key] = round((traffics_edge[day][periods[i]])*(speed_edge),2)
                        elif kpi == 'efficiencies': # Dict kpi 6
                            if frequencies_edge[day][periods[i]] != 0:
                                output[kpi][day][periods[i]][key] = round((traffics_edge[day][periods[i]])*(distance_edge)*(speed_edge/frequencies_edge[day][periods[i]]),2)
                            else:
                                output[kpi][day][periods[i]][key] = round((traffics_edge[day][periods[i]])*(distance_edge)*(speed_edge),2)

    return output

def _merge_lines(relations):
    ''' outputs weighted values for counter between edges ''' #TODO make loop work for days considerin dictionary

    # time constant
    distance = relations[0]['r']._properties['distance'] # unique for each pair
    # time variant
    traffics = {}
    frequencies = {}
    # aux
    line_speeds =  [] # length equal to the qtd of lines
    line_traffic = [] # length equal to the qtd of lines

    if len(relations) >1:
        print('break')


    # at each relation (transport line)
    for i in range(len(relations)):
        assert i != 0 or relations[i]['r']._properties['distance'] == relations[i-1]['r']._properties['distance'], "Different distances from nodes {} to {} ".format(relations[i]['r'].start_node.id, relations[i]['r'].end_node.id)

        # from & to
        from_id, to_id = relations[i]['r'].start_node.id, relations[i]['r'].end_node.id

        # To calculate average speed for "i" lines
        line_speeds.append(relations[i]['r']._properties['speed']) # append "i" speed
        sum_of_line_periods = 0 # initialize line traffic sum for "i"

        for day in days:
            traffics[day]={}
            frequencies[day]={}
            for t in range(6):
                # all line traffic days and periods
                sum_of_line_periods += relations[i]['r']._properties[f'traffic_{day}'][t]
                # traffic by hour
                if traffics[day].get(periods[t+1]) is  None:
                    traffics[day][periods[t+1]] = relations[i]['r']._properties[f'traffic_{day}'][t] / periods_hours[t]
                else:
                    traffics[day][periods[t+1]] += relations[i]['r']._properties[f'traffic_{day}'][t] / periods_hours[t]
                # vehicles by hour
                if frequencies[day].get(periods[t+1]) is  None:
                    frequencies[day][periods[t+1]] = relations[i]['r']._properties[f'frequency_{day}'][t] / periods_hours[t]
                else:
                    frequencies[day][periods[t+1]] += relations[i]['r']._properties[f'frequency_{day}'][t] / periods_hours[t]

        line_traffic.append(sum_of_line_periods)

    # Lines Avg. Speed Weighted by Traffic
    speed = sum(x * y for x, y in zip(line_speeds, line_traffic)) / sum(line_traffic) if relations[i]['r']._properties['line'] != 'Out-of-Station' else 0
    return from_id, traffics, frequencies, speed, distance, to_id

def to_base(n, b):
    ''' Convert strint to number '''
    res = ""
    while n:
        res+=BS[n%b]
        n//= b
    return res[::-1] or "0"

def minmax_dict(kpi):
    '''
    It normalizes dictionaire values or takes the percentag: https://developers.google.com/machine-learning/data-prep/transform/normalization
    '''
    minimum = min(kpi.values())
    maximum = max(kpi.values())
    if (maximum - minimum) ==0:
        factor =0
    else:
        factor=1.0/(maximum - minimum)
    for pair in kpi:
        kpi[pair] = (kpi[pair]-minimum)*factor
    return kpi

#### NEO4J MODEL FUNCTIONS ####

def create_db(db):
    create_db_cypher = "CREATE DATABASE `"+db+"`"
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "TFLbst1608."))
    with driver.session() as session:
        result = session.run(create_db_cypher)
    session.close()
    driver.close()
    return

def generate_nodes(db, mode):
    path = "C:/buildbr/big-cities-transport/01.BaseGraph/02.Neo4J_Scripts/"
    create_nodes_cypher = open(path+mode+'_nodes.txt', 'r')
    with open(path+mode+'_nodes.txt', 'r') as file:
        create_nodes_cypher = file.read().rstrip()
    driver = GraphDatabase.driver("bolt://localhost:7687/", auth=('neo4j', "TFLbst1608."))
    with driver.session(database=db) as session:
        result = session.run(create_nodes_cypher)
    session.close()
    driver.close()
    return

def generate_edges(db, kpi, dict):
    ''' Generate relation to pre-existing nodes graph database '''

    # Initiate session with all nodes
    driver = GraphDatabase.driver("bolt://localhost:7687/", auth=('neo4j', "TFLbst1608."))
    with driver.session(database=db) as session:
        id_pairs = list(dict.keys())
        for id_pair in id_pairs:
            ids= id_pair
            start, end = to_base(int(ids[0])+1,len(BS)), to_base(int(ids[1])+1,len(BS))
            kpi_value = dict[id_pair]
            seg = to_base(int(ids[0])+1,len(BS))+"_"+to_base(int(ids[1])+1,len(BS))

            create = "MATCH ({0}),({1}) WHERE ID({0})={2} AND ID({1})={3} CREATE ({0})-[{4}:TO{{{5}:{6}}}]->({1})".format(start, end, ids[0], ids[1], seg, kpi, kpi_value)
            result = session.run(create)

    session.close()
    driver.close()
    return


if __name__ == '__main__':
    '''
    Convert Base-Graph relation to list of dict(UDR) Kpis
    '''
    global days
    global periods
    global kpis
    global UDR
    BS="ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    ods = [ 'tube'] # , 'overground', 'dlr', 'tube'
    days = ['SUN', 'FRI', 'SAT', 'MTT']
    kpis = ['distance', 'speed', 'traffic', 'traffic_distances', 'loads', 'efficiencies'] #
    periods = {0:'Early', 1:'Morning', 2:'AM Peak', 3:'Midday', 4:'PM Peak', 5:'Evening', 6:'Late', 7:'Night', 8:'Total'}
    periods_hours = [2, 2, 3, 6, 3, 3, 2.5, 2.5, 19.5] # number of hours in each period

    # Connect to base-graph
    for mode in ods:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=('neo4j', "TFLbst1608."))
        with driver.session(database=mode+'-basegraph') as session:
            # get all directed pairs:
            pairs = _directed_pairs()
            df = pd.DataFrame(pairs)
            df.to_csv(f"{mode}_pairs.csv", index=False)
            # Normalized UDR
            UDR = _unique_rel_kpis(mode, pairs)
        session.close()
        driver.close()

        # Create a Graph for each KPI
        for kpi in UDR.keys():
            if kpi == 'loads':
                if isinstance(list(UDR[kpi].values())[0], float): # regardless of day
                    db = mode+"-"+kpi
                    minmax_dict(UDR[kpi])
                    create_db(db)
                    generate_nodes(db, mode) # day independent
                    generate_edges(db, kpi, UDR[kpi]) # db, kpi_name, dictionaire
                else:
                    for day in UDR[kpi].keys():
                        if day in ['MTT']:
                            for period in UDR[kpi][day].keys():
                                if period not in ['Early', 'Night', 'Total']:
                                    auxp = period.replace(' ', '-')
                                    auxk = kpi.replace('_', '')
                                    db = mode+"-"+auxk+"-"+day.lower()+"-"+auxp.lower()
                                    minmax_dict(UDR[kpi][day][period])
                                    create_db(db)
                                    generate_nodes(db, mode) # day independent
                                    generate_edges(db, kpi, UDR[kpi][day][period]) # generate for the day sum p=0

    print('==> Done! Now disparity ranks')



