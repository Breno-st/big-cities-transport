#########################################
# calculate the shortestPath in time *.py
#########################################

from stringprep import b1_set
from numpy import record
import pandas as pd
from neo4j import GraphDatabase
import pickle
import csv


def minmax_dict(kpi):
    '''
    It normalizes dictionaire values or takes the percentag: https://developers.google.com/machine-learning/data-prep/transform/normalization
    '''
    if not kpi.values():
        return

    minimum = min(kpi.values())
    maximum = max(kpi.values())
    factor=1.0/(maximum - minimum)
    for pair in kpi:
        kpi[pair] = (kpi[pair]-minimum)*factor
    return kpi

def percentage_dict(segments):
    ''' It convert dictionaire values into percentage '''
    for segment in segments.keys():
        segment_sums ={}
        for day in days:
            for period in periods:
                slot = f'{day}_{period}'
                for od in segments[segment]:
                    if segments[segment][od].get(day) is not None:
                        if segment_sums.get(slot) is not None:
                            segment_sums[slot] += segments[segment][od][day][period]
                        else:
                            segment_sums[slot] = {}
                            segment_sums[slot] = segments[segment][od][day][period]


        for od in segments[segment]:
            for day in days:
                if segments[segment][od].get(day) is not None:
                    for period in periods:
                        slot = f'{day}_{period}'
                        if segment_sums[slot]!= 0:
                            segments[segment][od][day][period] = segments[segment][od][day][period]/segment_sums[slot]
                        elif segments[segment][od][day][period] == 0:
                            pass
                        else:
                            print(f'something wrong at: {segment}, {od}, {day}, {period}')

def shortest_path(passenger, db):
    ''' Input:
            - Passenger is a dictionary with the number of passengers by OD
        Output:
            - List of OD by segments with percental values of passengers (probability)
            - List of OD by travel time
    '''
    segments_ods_shortest_paths ={}

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=('neo4j', "TFLbst1608."))
    with driver.session(database=db+'-basegraph') as session:

        # Handling graph-projection exist
        result = session.run("CALL gds.graph.exists('"+db+"')")

        session.run("CALL gds.graph.drop('"+db+"') YIELD graphName")
        graphprojection = "CALL gds.graph.project('"+db+"', '"+db+"Station', 'TO', {relationshipProperties: 'time'})"
        results = session.run(graphprojection)

        # Put mode in the beginning of the dictionary
        segments_ods_shortest_paths[db] = {}

        # IMPORT Find Segments and respectives OD's time before
        for start_end in passenger.keys():
            mode, x, y = start_end.split('_')[0], start_end.split('_')[1], start_end.split('_')[2]

            #shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE source.naptanid='{1}' AND target.naptanid='{2}' CALL gds.shortestPath.dijkstra.stream('{3}',{{sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode.naptanid, targetNode.naptanid, totalCost, nodeIds, costs, path".format(mode, x, y, db) #NaptanID to test
            shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE source.naptanid='{1}' AND target.naptanid='{2}' CALL gds.shortestPath.dijkstra.stream('{3}',{{sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path".format(mode, x, y, db) #ID
            # run it in session
            results = session.run(shortestPath_cypher) # outputs OD nodes and its respectives time
            records = [record for record in results]
            time = records[0][3] # list of sequential costs = time spent
            via = records[0][4] # list of sequential nodes
            segments = list(zip(via[:-1], via[1:])) # list of sequential pair of nodes
            o_d = str(via[0])+"_"+str(via[-1]) # key values
            # transverse O_D dictionary into Segments' dictionary

            for segment in segments:
                if segment not in segments_ods_shortest_paths[mode].keys():
                    segments_ods_shortest_paths[mode][segment] = {}
                    segments_ods_shortest_paths[mode][segment][o_d] = {}
                    segments_ods_shortest_paths[mode][segment][o_d]['time'] = time
                else:
                    segments_ods_shortest_paths[mode][segment][o_d] = {}
                    segments_ods_shortest_paths[mode][segment][o_d]['time'] = time


        # df = pd.DataFrame(segments_ods_shortest_paths)
        # df.to_csv('segments_ods_shortest_paths.csv', index=False)

        # for Disrupt Segments in segments_ods_shortest_paths[mode]
        walk_speed = 6
        for mode in segments_ods_shortest_paths.keys():
            for segment in segments_ods_shortest_paths[mode]:
                a, b = segment[0], segment[1]
                # Consult segment
                #cypher_time = "MATCH (O:{2}Station)-[R]->(D:{2}Station) WHERE O.naptanid={0} AND D.naptanid={1} RETURN R.time, R.distance".format(a, b, mode) #NaptanID
                cypher_time = "MATCH (O:{2}Station)-[R]->(D:{2}Station) WHERE id(O)={0} AND id(D)={1} RETURN R.time, R.distance".format(a, b, mode) #ID
                results = session.run(cypher_time)
                record = [record for record in results]
                time, distance = record[0][0], record[0][1]
                walk_time = 60*distance/walk_speed # in minnutes
                # Cause disruption
                #cypher_disrupt = "MATCH (O:{3}Station)-[R]->(D:{3}Station) WHERE O.naptanid={0} AND D.naptanid={1} SET R.time={2}".format(a, b, walk_time, mode) #NaptanID
                cypher_disrupt = "MATCH (O:{3}Station)-[R]->(D:{3}Station) WHERE id(O)={0} AND id(D)={1} SET R.time={2}".format(a, b, walk_time, mode) #ID
                session.run(cypher_disrupt)
                session.run("CALL gds.graph.drop('"+db+"') YIELD graphName")
                session.run("CALL gds.graph.project('"+db+"', '"+db+"Station', 'TO', {relationshipProperties: 'time'})")
                # Calculate shortest path time for OD in segments_ods_shortest_paths[mode][segment]
                for o_d in segments_ods_shortest_paths[mode][segment]:
                    x, y = o_d.split('_')[0], o_d.split('_')[1]
                    #shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE id(source)={1} AND id(target)={2}  CALL gds.shortestPath.dijkstra.stream({{graphName: '{0}', nodeProjection: '{0}Station', relationshipProjection:'TO', relationshipProperties: ['time'], sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path".format(mode, x, y) # wait for Neo4j
                    # shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE source.naptanid={1} AND target.naptanid={2} CALL gds.shortestPath.dijkstra.stream('{3}',{{sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path".format(mode, x, y, db) #ID
                    shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE id(source)={1} AND id(target)={2} CALL gds.shortestPath.dijkstra.stream('{3}',{{sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path".format(mode, x, y, db) #NaptanID to test
                    results = session.run(shortestPath_cypher)
                    records = [record for record in results]
                    time_d = records[0][3] # list of sequential costs = time spent
                    segments_ods_shortest_paths[mode][segment][o_d]['time_d'] = time_d
                # Repair disruption
                cypher_repair = "MATCH (O:{3}Station)-[R]->(D:{3}Station) WHERE id(O)={0} AND id(D)={1} SET R.time={2}".format(a, b, time, mode)
                session.run(cypher_repair)
                session.run("CALL gds.graph.drop('"+db+"') YIELD graphName")
                session.run("CALL gds.graph.project('"+db+"', '"+db+"Station', 'TO', {relationshipProperties: 'time'})")

    # Close connection
    session.close()
    driver.close()

    return  segments_ods_shortest_paths

def calc_distress(segments):

    periods_null = {'Early': 0.0, 'Morning': 0.0, 'AM Peak': 0.0, 'Midday': 0.0, 'PM Peak': 0.0, 'Evening': 0.0, 'Late': 0.0, 'Night': 0.0, 'Total': 0.0}

    segments_distress = {}
    for segment in segments:
        segments_distress[segment] = {}
        for day in days:
            segments_distress[segment][day] = {}
            segments_distress[segment][day] = periods_null.copy()
            for period in periods:
                for od in segments[segment]:
                    delta_time = segments[segment][od]['time_d'] - segments[segment][od]['time']
                    if segments[segment][od].get(day) is not None:
                        segments_distress[segment][day][period] += delta_time*segments[segment][od][day][period]


    return segments_distress

def dict_to_pickle(filename, savename):
    with open(savename, 'wb') as handle:
        pickle.dump(filename, handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_pickle(filename):
    with open(filename, 'rb') as handle:
        loadedfile = pickle.load(handle)
    return loadedfile


if __name__ == '__main__':

    global 	days
    global periods
    csv.field_size_limit(50000000)

    modes = ['overground'] #'overground', 'dlr', 'tube'
    days = [ 'SUN', 'FRI', 'SAT', 'MTT']
    periods = ['Early', 'Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late', 'Night', 'Total']
    #periods = ['Total', 'Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']

    # input a csv with all origin and destiny => OD has two columns s.t. key is start_end
    path = "C:/buildbr/big-cities-transport/02.Distress/01.Input/"

    for mode in modes:

    # 1.Import file "od_mode" to calclulate shortest paths:
        df = pd.read_csv(path+'od_'+mode+'.csv',delimiter=';')
        df['o_d'] = df.apply (lambda row: row['Mode']+'_'+row['naptanid_o']+'_'+row['naptanid_d'], axis=1)
        df.set_index(['o_d'], inplace=True) # set o_d index
        df = df.drop(['Mode', 'name_o', 'name_d', 'naptanid_o', 'naptanid_d'], axis=1) # set o_d index

        od_dict = {}
        for index, row in df.iterrows():
            row_data = {}
            for column in df.columns:
                if column != 'index_col':
                    row_data[column] = row[column]
            od_dict[index] = row_data

        # Call SorthestPath on imported file "od_mode":
        segments_ods_shortest_paths = shortest_path(od_dict, mode) # [mode][segment][o_d]['time'/'dtime']
        dict_to_pickle(segments_ods_shortest_paths, f'shortest_paths_{mode}_segments_od.pickle')

    # 1*.Loadind file "od_mode" to calclulate shortest paths:
        segments_ods_shortest_paths = load_pickle(f'shortest_paths_{mode}_segments_od.pickle')

    # 2.Adding OD traffic information into SorthestPath dictionary: NEW
        periods_seq = {1:'Early', 2: 'Morning', 3:'AM Peak', 4:'Midday', 5:'PM Peak', 6:'Evening', 7:'Late', 8:'Night', 9:'Total'}
        with open(path+'od_'+mode+'_traf.csv', mode='r') as file: #200K times
            lines = file.readlines()
            for line in lines[2:]:
                cols = line.strip().split(';')
                day, od = cols[0].split('-')[0], cols[0].split('-')[1]
                for segment in segments_ods_shortest_paths[mode]:  #600 times
                    if segments_ods_shortest_paths[mode][segment].get(od) is not None:
                        segments_ods_shortest_paths[mode][segment][od][day] = {} #days exist only for there
                        for i in periods_seq:
                            aux = cols[i].replace(',', '')
                            segments_ods_shortest_paths[mode][segment][od][day][periods_seq[i]] = float(aux)

        dict_to_pickle(segments_ods_shortest_paths, f'shortest_paths_{mode}_segments_od_traffic.pickle') # shortest_paths_ods_segments__traf

    # 2*.Loading OD traffic information
        segments_ods_shortest_paths = load_pickle(f'shortest_paths_{mode}_segments_od_traffic.pickle')

    # 3.Normalizing OD traffic information
        percentage_dict(segments_ods_shortest_paths[mode]) # Norm based on the total od_traf of the edge
        segments_ods_shortest_paths_norm = segments_ods_shortest_paths
        dict_to_pickle(segments_ods_shortest_paths_norm, f'shortest_paths_{mode}_segments_od_traffic_norm.pickle')

    # 3*.Loadind OD traffic Normalized information
        segments_ods_shortest_paths_norm = load_pickle(f'shortest_paths_{mode}_segments_od_traffic_norm.pickle')

    # 4.Form distress KPI
        segments_distress = calc_distress(segments_ods_shortest_paths_norm[mode]) # Seems ok
        dict_to_pickle(segments_distress, f'distress_segments_{mode}.pickle')

    # 4*.Loadind Segments Distress
        segments_distress = load_pickle(f'distress_segments_{mode}.pickle') # goes to another another code




