import pandas as pd
import numpy as np
from neo4j import GraphDatabase, basic_auth
from pip import main
import csv


def _directed_pairs():
    '''
    With the open seesion, it connect to NEO4J and extracts a list of
    of tupples (Origins, Destination, Mode)
    Input:   NA
    Output:  List of tuples [(Origins, Destination, Mode),...]
    '''

    result = session.run('MATCH (n)-[r:TO]->(m) RETURN DISTINCT n.naptanid as orig, m.naptanid as dest, r.mode as mode')
    pairs = [(record['orig'],record['dest'],record['mode']) for record in result]

    return pairs


def _unique_rel_kpis(mode, pairs):
    '''
    It uses the list of (Orig, Dest, Mode) tuples, to access the relations in the

    Input:      List of tuples [(Origins, Destination, Mode),...]
    Return:     dict[kpis][day][period]
    '''

    ## KPIs new (7): two constant / three variable in time

    distance = {}
    speeds = {}
    traffics={'MTT':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}, 'SUN':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}}
    traffic_distances = {'MTT':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}, 'SUN':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}}
    efficiencies = {'MTT':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}, 'SUN':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}}
    loads = {'MTT':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}, 'SUN':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}}
    distress = {'MTT':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}, 'SUN':{0:{}, 1:{}, 2:{} , 3:{}, 4:{}, 5:{}, 6:{}}}

    lines_cnt = 0 # check value against Neo4j

    for pair in pairs:
        # extract pair and assemble cypher
        origin, destiny, mode = pair[0], pair[1], pair[2]
        rel_by_pairs = "MATCH (n)-[r:TO]->(m) WHERE n.naptanid='{}' and m.naptanid='{}' RETURN r".format(origin, destiny)
        # consult Neo4j
        result = session.run(rel_by_pairs)
        relations = [record for record in result]
        lines_cnt += len(relations)
        # merge counters
        from_id, traffics_edge, frequencies_edge, speed_edge, distance_edge, to_id = _merge_lines(relations)
        # store in dictionaires with same key
        key = str(from_id) +'_'+ str(to_id)
        distance[key] = round(distance_edge,2) # Dict kpi 1
        speeds[key] = speed_edge # Dict kpi 2
        for day in days:
            for period in range(len(periods_hours)+1):
                traffics[day][period][key] = round(traffics_edge[day][period],2) # Dict kpi 3
                traffic_distances[day][period][key] = round(traffics_edge[day][period] * distance_edge,2) # Dict kpi 4

                if frequencies_edge[day][period] != 0: # Dict kpi 5
                    loads[day][period][key] = round((traffics_edge[day][period])*(speed_edge/frequencies_edge[day][period]),2)
                else:
                    loads[day][period][key] = round((traffics_edge[day][period])*(speed_edge),2)
                if frequencies_edge[day][period] != 0: # Dict kpi 6
                    efficiencies[day][period][key] = round((traffics_edge[day][period])*(distance_edge)*(speed_edge/frequencies_edge[day][period]),2)
                else:
                    efficiencies[day][period][key] = round((traffics_edge[day][period])*(distance_edge)*(speed_edge),2)


    mtt_path = 'C:/buildbr/big-cities-transport/2.Distress/2.Output/norm_weighted_time_by_segment_'+mode+'_MTT_Total.csv'
    with open(mtt_path, mode='r') as infile:
        for row in csv.DictReader(infile):
            o_d_tup = row["Segment"].replace("(", "").replace(")", "").replace(" ", "").split(',')
            o_d = o_d_tup[0]+'_'+o_d_tup[1]
            distress['MTT'][0][o_d] = float(row["Distress"])
    sun_path = 'C:/buildbr/big-cities-transport/2.Distress/2.Output/norm_weighted_time_by_segment_'+mode+'_SUN_Total.csv'
    with open(sun_path, mode='r') as infile:
        for row in csv.DictReader(infile):
            o_d_tup = row["Segment"].replace("(", "").replace(")", "").replace(" ", "").split(',')
            o_d = o_d_tup[0]+'_'+o_d_tup[1]
            distress['SUN'][0][o_d] = float(row["Distress"])

    output = {'distance':distance,
        'speed':speeds,
        'traffic':traffics,
        'distancetraffic':traffic_distances,
        'efficiency':efficiencies,
        'loads': loads,
        'distress': distress
        }

    return output

def _merge_lines(relations):
    ''' outputs weighted values for counter between edges '''

    distance = relations[0]['r']._properties['distance'] # unique for each pair
    line_speeds =  [] # length equal to the qtd of lines
    line_traffic = [] # length equal to the qtd of lines
    traffics = {'MTT':{0:0,1:0,2:0,3:0,4:0,5:0,6:0}, 'SUN':{0:0,1:0,2:0,3:0,4:0,5:0,6:0}}
    frequencies = {'MTT':{0:0,1:0,2:0,3:0,4:0,5:0,6:0}, 'SUN':{0:0,1:0,2:0,3:0,4:0,5:0,6:0}}

    # at each relation (transport line)
    for i in range(len(relations)):
        assert i != 0 or relations[i]['r']._properties['distance'] == relations[i-1]['r']._properties['distance'], "Different distances from nodes {} to {} ".format(relations[i]['r'].start_node.id, relations[i]['r'].end_node.id)

        # from & to
        from_id, to_id = relations[i]['r'].start_node.id, relations[i]['r'].end_node.id

        # Speeds by lines
        line_speeds.append(relations[i]['r']._properties['speed'])

        # Total traffic by lines
        sum_of_line_periods = 0
        for t in range(6):
            sum_of_line_periods += relations[i]['r']._properties['traffic_MTT'][t] + relations[i]['r']._properties['traffic_SUN'][t]
        line_traffic.append(sum_of_line_periods)
        # Lines Sum
        for t in range(6):
            # people by hour
            traffics['MTT'][t+1] += relations[i]['r']._properties['traffic_MTT'][t] / periods_hours[t] # improve property traffic:{'day':[]}
            traffics['SUN'][t+1] += relations[i]['r']._properties['traffic_SUN'][t] / periods_hours[t]
            # vehicles by hour
            frequencies['MTT'][t+1] +=  relations[i]['r']._properties['frequency_MTT'][t] / periods_hours[t] # improve property frequency:{'day':[]}
            frequencies['SUN'][t+1] +=  relations[i]['r']._properties['frequency_SUN'][t] / periods_hours[t]

    # Day Sum in the period "0"
    for d in days:
        for t in range(1,7):
            traffics[d][0] += traffics[d][t]
            frequencies[d][0] += frequencies[d][t]


    # Lines Avg. Speed Weighted by Traffic
    speed = sum(x * y for x, y in zip(line_speeds, line_traffic)) / sum(line_traffic) if relations[i]['r']._properties['line'] != 'Out-of-Station' else 0
    return from_id, traffics, frequencies, speed, distance, to_id


BS="ABCDEFGHIJKLMNOPQRSTUVWXYZ"
def to_base(n, b):
    ''' Convert strint to number '''
    res = ""
    while n:
        res+=BS[n%b]
        n//= b
    return res[::-1] or "0"

def create_db(db):
    create_db_cypher = "CREATE DATABASE `"+db+"`"
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "TFLbst1608."))
    with driver.session() as session:
        result = session.run(create_db_cypher)
    session.close()
    driver.close()
    return


def generate_nodes(db, mode):
    path = "C:/buildbr/big-cities-transport/1.BaseGraph/"
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
            ids= id_pair.split('_')
            start, end = to_base(int(ids[0])+1,len(BS)), to_base(int(ids[1])+1,len(BS))
            kpi_value = dict[id_pair]
            seg = to_base(int(ids[0])+1,len(BS))+"_"+to_base(int(ids[1])+1,len(BS))

            create = "MATCH ({0}),({1}) WHERE ID({0})={2} AND ID({1})={3} CREATE ({0})-[{4}:TO{{{5}:{6}}}]->({1})".format(start, end, ids[0], ids[1], seg, kpi, kpi_value)
            result = session.run(create)

    session.close()
    driver.close()
    return


def minmax_dict(kpi):
    '''
    It normalizes dictionaire values or takes the percentag: https://developers.google.com/machine-learning/data-prep/transform/normalization
    '''
    minimum = min(kpi.values())
    maximum = max(kpi.values())
    factor=1.0/(maximum - minimum)
    for pair in kpi:
        kpi[pair] = (kpi[pair]-minimum)*factor
    return kpi


if __name__ == '__main__':
    '''
    Convert Base-Graph relation to list of dict(UDR) Kpis
    '''
    global 	days
    global periods
    global UDR
    # Granularity
    ods = [ 'overground', 'tube'] # 'dlr',
    days = ['MTT', 'SUN']
    # periods = ['Early', 'Morining']
    periods_hours = [2, 3, 6, 3, 3, 3] #number of hours in each period
    # hours = ['00', '01']

    # Connect to base-graph
    for mode in ods:
        driver = GraphDatabase.driver("bolt://localhost:7687", auth=('neo4j', "TFLbst1608."))
        with driver.session(database=mode+'-basegraph') as session:
            # get all directed pairs:
            pairs = _directed_pairs()

            # Normalized UDR
            UDR = _unique_rel_kpis(mode, pairs)
        session.close()
        driver.close()

        # Create a Graph for each KPI
        for kpi in UDR.keys():
            if isinstance(list(UDR[kpi].values())[0], float): # regardless of day
                db = mode+"-"+kpi
                minmax_dict(UDR[kpi])
                create_db(db)
                generate_nodes(db, mode) # day independent
                generate_edges(db, kpi, UDR[kpi]) # db, kpi_name, dictionaire
            else:
                for day in days:
                    db = mode+"-"+day.lower()+"-"+kpi
                    if kpi != 'distress':
                        for p in range(len(periods_hours)):
                            # normalize kpi
                            minmax_dict(UDR[kpi][day][p])
                        create_db(db)
                        generate_nodes(db, mode) # day independent
                        generate_edges(db, kpi, UDR[kpi][day][0]) # generate for the day sum p=0
                    if kpi == 'distress':
                        create_db(db)
                        generate_nodes(db, mode) # day independent
                        generate_edges(db, kpi, UDR[kpi][day][0]) # for each KPI an Db // inside create database

    # export graph in CSV for NetworkX
    print('==> Done! Now disparity ranks')



