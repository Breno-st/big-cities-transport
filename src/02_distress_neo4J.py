#########################################
# calculate the shortestPath in time *.py
#########################################

from stringprep import b1_set
from numpy import record
import pandas as pd
from neo4j import GraphDatabase, basic_auth
from pip import main
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

def percentage_dict(kpi):
    ''' It convert dictionaire values into percentage '''
    den = 0
    for o_d in kpi:
        den += kpi[o_d]['weight']

    factor=1.0/den
    for o_d in kpi:
        kpi[o_d]['weight'] = kpi[o_d]['weight']*factor
    return kpi

# TODO: remove the passenger weight from this function
def shortest_path(passenger, db):
    ''' Input:
            - Passenger is a dictionary with the number of passengers by OD
        Output:
            - List of OD by segments with percental values of passengers (probability)
            - List of OD by travel time
    '''
    shortest_paths_mode_segments_od ={}

    driver = GraphDatabase.driver("bolt://localhost:7687", auth=('neo4j', "TFLbst1608."))
    with driver.session(database=db+'-basegraph') as session:
        shortest_paths_mode_segments_od[db] = {}


        # CALL gds.graph.list() YIELD graphName

        session.run("CALL gds.graph.drop('"+db+"') YIELD graphName")

        graphprojection = "CALL gds.graph.project('"+db+"', '"+db+"Station', 'TO', {relationshipProperties: 'time'})"
        results = session.run(graphprojection)

        # IMPORT Find Segments and respectives OD's time before
        for start_end in passenger.keys():
            x, y, mode = start_end.split('_')[0], start_end.split('_')[1], start_end.split('_')[2]

            #shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE source.naptanid='{1}' AND target.naptanid='{2}' CALL gds.shortestPath.dijkstra.stream({{graphName: '{0}', nodeProjection: '{0}Station', relationshipProjection:'TO', relationshipProperties: ['time'], sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path".format(mode, x, y, db) # wait for Neo4j
            shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE source.naptanid='{1}' AND target.naptanid='{2}' CALL gds.shortestPath.dijkstra.stream('{3}',{{sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path".format(mode, x, y, db)
            # run it in session
            results = session.run(shortestPath_cypher) # outputs OD nodes and its respectives time
            records = [record for record in results]
            time = records[0][3] # list of sequential costs = time spent
            via = records[0][4] # list of sequential nodes
            segments = list(zip(via[:-1], via[1:])) # list of sequential pair of nodes
            o_d = str(via[0])+"_"+str(via[-1]) # key values
            # transverse O_D dictionary into Segments' dictionary
            for segment in segments:
                if segment not in shortest_paths_mode_segments_od[mode].keys():
                    shortest_paths_mode_segments_od[mode][segment] = {}
                    shortest_paths_mode_segments_od[mode][segment][o_d] = {}
                    shortest_paths_mode_segments_od[mode][segment][o_d]['time'] = time
                else:
                    shortest_paths_mode_segments_od[mode][segment][o_d] = {}
                    shortest_paths_mode_segments_od[mode][segment][o_d]['time'] = time

        # for Disrupt Segments in shortest_paths_mode_segments_od[mode]
        walk_speed = 6
        for mode in shortest_paths_mode_segments_od.keys():
            for segment in shortest_paths_mode_segments_od[mode]:
                a, b = segment[0], segment[1]
                # Consult segment
                cypher_time = "MATCH (O:{2}Station)-[R]->(D:{2}Station) WHERE id(O)={0} AND id(D)={1} RETURN R.time, R.distance".format(a, b, mode)
                results = session.run(cypher_time)
                record = [record for record in results]
                time, distance = record[0][0], record[0][1]
                walk_time = 60*distance/walk_speed # in minnutes
                # Cause disruption
                cypher_disrupt = "MATCH (O:{3}Station)-[R]->(D:{3}Station) WHERE id(O)={0} AND id(D)={1} SET R.time={2}".format(a, b, walk_time, mode)
                session.run(cypher_disrupt)
                session.run("CALL gds.graph.drop('"+db+"') YIELD graphName")
                session.run("CALL gds.graph.project('"+db+"', '"+db+"Station', 'TO', {relationshipProperties: 'time'})")
                # Calculate shortest path time for OD in shortest_paths_mode_segments_od[mode][segment]
                for o_d in shortest_paths_mode_segments_od[mode][segment]:
                    x, y = o_d.split('_')[0], o_d.split('_')[1]
                    #shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE id(source)={1} AND id(target)={2}  CALL gds.shortestPath.dijkstra.stream({{graphName: '{0}', nodeProjection: '{0}Station', relationshipProjection:'TO', relationshipProperties: ['time'], sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path".format(mode, x, y) # wait for Neo4j
                    shortestPath_cypher = "MATCH (source:{0}Station), (target:{0}Station) WHERE id(source)={1} AND id(target)={2} CALL gds.shortestPath.dijkstra.stream('{3}',{{sourceNode: source, targetNode: target, relationshipWeightProperty: 'time'}}) YIELD index, sourceNode, targetNode, totalCost, nodeIds, costs, path RETURN index, sourceNode, targetNode, totalCost, nodeIds, costs, path".format(mode, x, y, db)
                    results = session.run(shortestPath_cypher)
                    records = [record for record in results]
                    time_d = records[0][3] # list of sequential costs = time spent
                    shortest_paths_mode_segments_od[mode][segment][o_d]['time_d'] = time_d
                # Repair disruption
                cypher_repair = "MATCH (O:{3}Station)-[R]->(D:{3}Station) WHERE id(O)={0} AND id(D)={1} SET R.time={2}".format(a, b, time, mode)
                session.run(cypher_repair)
                session.run("CALL gds.graph.drop('"+db+"') YIELD graphName")
                session.run("CALL gds.graph.project('"+db+"', '"+db+"Station', 'TO', {relationshipProperties: 'time'})")

    # Close connection
    session.close()
    driver.close()



    return  shortest_paths_mode_segments_od


def weigthed_time(shortest_paths_mode_segments_od):

    weighted_time_by_segment = {}
    for mode in shortest_paths_mode_segments_od:
        weighted_time_by_segment[mode] = {}
        for segment in shortest_paths_mode_segments_od[mode]:
            weighted_time_by_segment[mode][segment] = 0
            for o_d in shortest_paths_mode_segments_od[mode][segment]:
                delta_time = shortest_paths_mode_segments_od[mode][segment][o_d]['time_d'] - shortest_paths_mode_segments_od[mode][segment][o_d]['time']
                weighted_time_by_segment[mode][segment] += delta_time*shortest_paths_mode_segments_od[mode][segment][o_d]['weight']
    return weighted_time_by_segment


if __name__ == '__main__':

    global 	days
    global periods

    ods = ['overground', 'tube'] #'dlr',
    days = ['MTT', 'SUN'] #,
    periods = ['Total'] #, 'Early', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late'] -> remove in ***

    # input a csv with all origin and destiny => OD has two columns s.t. key is start_end
    path = "C:/buildbr/big-cities-transport/2.Distress/1.Input/"

    for mode in ods:

        # IF cost (time) independ from day and period, the delta time matrix is calculated once
        ##  import od table (formated by hand)
        df = pd.read_csv(path+'od_'+mode+'.csv')
        df['o_d'] = df.apply (lambda row: row['name_o']+'_'+row['name_d']+'_'+row['mode'], axis=1)
        df.set_index(['o_d'], inplace=True) # set o_d index

        ori_dest_traf = df.to_dict('dict') # TODO re-create dictionaire to input the shortest_path

        shortest_paths_mode_segments_od = shortest_path(ori_dest_traf, mode) # [mode][segment][o_d]['time'/'dtime']

        # THE traffic depends on day and period, so it needs to loop
        for day in days:
            ### TODO: create a dictionary for o_d traffic values per day/period
            traffic_mode_od_day_period = df[df['day']==day].to_dict('dict')

            for period in periods: # maybe one day really loop through periords ;)
                # create a dictionary for the perid
                ## od = df[df['day']==day].to_dict('dict')
                od_passengers = ori_dest_traf[period]

                # TODO:
                # 1: Acess "shortest_paths_mode_segments_od" and retrive ['time'/'dtime'] using [mode][segment][o_d]
                # 2: Acess "traffic_mode_od_day_period" and retrive ['traffic'] using [mode][o_d]
                # 3: For each segments, it normalize its OD's weigths accordint to Day/Period

                for mode in shortest_paths_mode_segments_od:
                    for segment in shortest_paths_mode_segments_od[mode].keys():
                        percentage_dict(shortest_paths_mode_segments_od[mode][segment]) # OD_i_passenger_percent // never change

                # with open('shortest_paths_mode_segments_od_'+day+'_'+period+'.pickle', 'wb') as handle:
                #             pickle.dump(shortest_paths_mode_segments_od, handle, protocol=pickle.HIGHEST_PROTOCOL)

                # saves time, import **
                # with open('shortest_paths_mode_segments_od_'+mode+'_'+day+'_'+period+'.pickle', 'rb') as handle:
                #     shortest_paths_mode_segments_od = pickle.load(handle)

                # Weighted distress time for segments
                weighted_time_by_segment= weigthed_time(shortest_paths_mode_segments_od)

                # EXPORT weighted_time_by_segment to Pickle
                with open('weighted_time_by_segment_'+mode+'_'+day+'_'+period+'.pickle', 'wb') as handle:
                    pickle.dump(weighted_time_by_segment, handle, protocol=pickle.HIGHEST_PROTOCOL)

                # EXPORT weighted_time_by_segment to CSV
                csv_columns = ['Mode','Segment','Distress']
                csv_file = 'weighted_time_by_segment_'+mode+'_'+day+'_'+period+'.csv'
                try:
                    with open(csv_file, 'w') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                        writer.writeheader()
                        for mode in weighted_time_by_segment:
                            for segment in weighted_time_by_segment[mode]:
                                line = {'Mode':mode,'Segment': segment, 'Distress': weighted_time_by_segment[mode][segment]}
                                writer.writerow(line)
                except IOError:
                    print("I/O error")

                # NORMALIZE values
                for mode in weighted_time_by_segment:
                    minmax_dict(weighted_time_by_segment[mode])

                # EXPORT NORMALIZED weighted_time_by_segment to Pickle
                with open('norm_weighted_time_by_segment_'+mode+'_'+day+'_'+period+'.pickle', 'wb') as handle:
                    pickle.dump(weighted_time_by_segment, handle, protocol=pickle.HIGHEST_PROTOCOL)

                # EXPORT NORMALIZED weighted_time_by_segment to CSV
                csv_columns = ['Mode','Segment','Distress']
                csv_file = 'norm_weighted_time_by_segment_'+mode+'_'+day+'_'+period+'.csv'
                try:
                    with open(csv_file, 'w') as csvfile:
                        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                        writer.writeheader()
                        for mode in weighted_time_by_segment:
                            for segment in weighted_time_by_segment[mode]:
                                line = {'Mode':mode,'Segment': segment, 'Distress': weighted_time_by_segment[mode][segment]}
                                writer.writerow(line)
                except IOError:
                    print("I/O error")


            # evaluate a->b == b->a, if not, why? Although the walk_speed, distance anternatives to bridge the disruption are the same,
            # they mitgh have different speed and traffic




