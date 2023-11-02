import pandas as pd
import requests, http.client, urllib.request, urllib.parse, urllib.error, base64
import numpy as np
from ast import literal_eval
from tfl.client import Client
from tfl.api_token import ApiToken

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode


### REQUEST VALIDATION ###

def get_query_strings(params):
    if params is None:
        params = {}
    if api_token is not None:
        params.update(api_token)
    return urlencode(params)

def send_request(location, params=None):
    return requests.get(base_url + location + '?' + get_query_strings(params))

### GET ###

def get_stop_points_by_lineid(lineid):
    response = send_request(endpoints['stopPointByline'].format(lineid))
    data = response.json()
    return data

def get_stop_points_crowd_live(naptanid):
    response = send_request(endpoints['crowndingBynaptan'].format(naptanid))
    data = response.json()
    return data

def get_line_crowd_by_naptan(naptanid, lineid, direction):
    response = send_request(endpoints['crowndingByline'].format(naptanid, lineid, direction))
    data = response.json()
    return data

def get_timetable_by_line_naptan(lineid, fromnaptanid, tonaptanid):
    response = send_request(endpoints['timetable'].format(lineid, fromnaptanid, tonaptanid))
    data = response.json()
    return data

def get_timetable_by_line_s_naptan(lineid, naptanid):
    response = send_request(endpoints['timetable_s'].format(lineid, naptanid))
    data = response.json()
    return data

def get_stop_points_by_lineid2(lineid):
    response = send_request(endpoints['latLonByline'].format(lineid))
    data = response.json()
    return data

def get_stop_points_by_id(naptanid, lineid, direction):
    response = send_request(endpoints['stoptid'].format(naptanid, lineid, direction))
    data = response.json()
    return data

def get_time_by_id(origin, destiny, mode):
    response = send_request(endpoints['time'].format(origin, destiny, mode))
    data = response.json()
    return data

### TABLES ###

def modes():
    '''StepTable'''
    # DataFrames
    df_mode = pd.DataFrame(columns=['modeName', 'isTflService', 'isFarePaying', 'isScheduledService' ])
    # Collection
    for mode in client.get_line_meta_modes():
        if mode.is_tfs_service:
            df_mode = df_mode.append({'modeName': mode.mode_name,
                                    'isTflService': mode.is_tfs_service,
                                    'isFarePaying': mode.is_fare_paying,
                                    'isScheduledService': mode.is_scheduled_service},ignore_index = True)
    unique_modes = df_mode['modeName'].unique()
    # Export
    df_mode.to_csv(path+'/tbl_mode.csv', index=False)
    return unique_modes

def lines():
    '''StepTable: uses unique Modes'''
    # DataFrames
    df_line = pd.DataFrame(columns=['lineId',  'modeName', 'created', 'modified', 'Services'])
    # Collection
    errors_line = []
    for mode in unique_modes:
            mode_lines = client.get_route_by_mode(mode)
            for mode_line in mode_lines:
                try:
                    df_line = df_line.append({'lineId':mode_line.id,
                                            'modeName':mode_line.mode_name ,
                                            'created':mode_line.created,
                                            'modified':mode_line.modified,
                                            'Services': [service_type.name for service_type in mode_line.service_types]},ignore_index = True)
                except:
                    errors_line.append((mode,mode_line))
    unique_lines = df_line['lineId' ].unique()
    # Export
    df_line.to_csv(path+'/tbl_line.csv', index=False)
    return unique_lines

def routes():
    '''StepTable: uses unique Modes'''
    # DataFrames
    df_route = pd.DataFrame(columns=['lineId','modeName','name', 'direction','origination_name', 'destination_name', 'orig_naptan','dest_naptan'])
    # Collection
    errors_route = []
    for mode in unique_modes:
            mode_routes = client.get_route_by_mode(mode)
            for mode_route in mode_routes:
                for route_section in mode_route.route_sections:
                    try:
                        df_route = df_route.append({'lineId':route_section.id,
                                                        'modeName':route_section.mode_name,
                                                        'name':route_section.name,
                                                        'direction':route_section.direction,
                                                        'origination_name':route_section.origination_name,
                                                        'destination_name':route_section.destination_name,
                                                        'orig_naptan':route_section.originator,
                                                        'dest_naptan':route_section.destination},ignore_index = True)
                    except:
                        errors_route.append((mode,mode_route, route_section))
    # Export
    df_route.to_csv(path+'/tbl_route.csv', index=False)

def coordenates():
    '''EndTable: uses unique Modes '''
    # DataFrames
    df_coord= pd.DataFrame(columns=['naptanid', 'stopType', 'commonName', 'line', 'lat', 'lon'])
    #Collection
    errors_coord = []
    for line in unique_lines:
        for i in get_stop_points_by_lineid2(line):
            try:
                df_coord = df_coord.append({'naptanid':i['naptanId'],
                                            'stopType':i['stopType'],
                                            'commonName':i['commonName'],
                                            'line':line,
                                            'lat':i['lat'],
                                            'lon':i['lon']} ,ignore_index = True)
            except:
                errors_coord.append((line,i))
    # Export
    df_coord.to_csv(path+'/tbl_coord.csv', index=False)

def routes_seq():
    '''EndTable: uses unique Lines'''
    # DataFrames
    df_route_seq= pd.DataFrame(columns=['lineId','direction','isOutboundOnly','mode','routeName','serviceType','naptanIds'])
    # Collection
    errors_seq = []
    for line in unique_lines:
        stop_points = get_stop_points_by_lineid(line)
        for routes in stop_points['orderedLineRoutes']:
            try:
                df_route_seq = df_route_seq.append({'lineId':stop_points['lineId'],
                                            'direction':stop_points['direction'],
                                            'isOutboundOnly':stop_points['isOutboundOnly'],
                                            'mode':stop_points['mode'],
                                            'routeName':routes['name'],
                                            'serviceType':routes['serviceType'],
                                            'naptanIds':routes['naptanIds']},ignore_index = True)
            except:
                errors_seq.append((line, routes))
    # Export
    df_route_seq.to_csv(path+'/tbl_route_seq.csv', index=False)
    return df_route_seq

def od_intervalid():
    '''EndTable: uses unique Lines'''
    # DataFrames
    df_orig_dest_time_by_intervalid = pd.DataFrame(columns=['lineId', 'orig', 'dest', 'stationInterval_id', 'time'])
    df_orig_intervalId = pd.DataFrame(columns=['lineId','orig','day','start','end','Interval_0','Interval_1','Interval_2','Interval_3','Interval_4','Interval_5','Interval_6','Interval_7','Interval_8','Interval_9','Interval_10','Interval_11','Interval_12','Interval_13'])
    # Collection
    segments = []
    error_segments = []
    for index, row in df_route_seq.iterrows(): # change samples for eveything
        line, naptanIds = row['lineId'], literal_eval(row['naptanIds'])
        for i in range(1, len(naptanIds)):
            orig, dest  = naptanIds[i-1], naptanIds[i]
            segment ={(row['lineId'], orig, dest)}
            if segment.issubset(set(segments)):
                next
            else:
                try:
                    timetable = get_timetable_by_line_naptan(line, orig, dest)
                    for route in timetable['timetable']['routes']:
                        for stationInterval in route['stationIntervals']:
                            for interval in stationInterval['intervals']:
                                if interval['stopId'] == dest:
                                    df_orig_dest_time_by_intervalid = df_orig_dest_time_by_intervalid.append({'lineId': row['lineId'],
                                                                                                                'orig': timetable['timetable']['departureStopId'],
                                                                                                                'dest': interval['stopId'],
                                                                                                                'stationInterval_id': stationInterval['id'],
                                                                                                                'time': interval['timeToArrival']},ignore_index = True)
                                    segments.append((row['lineId'], orig, dest))
                                    break


                    for schedule in route['schedules']:

                        dic = {'0': 0,'1': 0,'2': 0,'3': 0,'4': 0,'5': 0,'6': 0,'7': 0, '8': 0,'9': 0,'10': 0,'11': 0,'12': 0,'13': 0}

                        for kj in schedule['knownJourneys']: # KNOWNS JOURNEYS
                            key = str(kj['intervalId'])
                            dic[key] += 1
                        start_hour, start_minute, end_hour, end_minute = None, None, None, None

                        for period in schedule['periods']:  # PERIOD
                            if not start_hour:
                                start_hour, start_minute  = period['fromTime']['hour'], period['fromTime']['minute']
                            end_hour, end_minute  = period['toTime']['hour'], period['toTime']['minute']

                        start_time = start_hour + ":" + start_minute
                        end_time = end_hour + ":" + end_minute

                        df_orig_intervalId = df_orig_intervalId.append({'lineId': row['lineId'],
                                                                        'orig': timetable['timetable']['departureStopId'],
                                                                        'day': schedule['name'],
                                                                        'start': start_time,
                                                                        'end': end_time,
                                                                        'Interval_0': dic['0'],
                                                                        'Interval_1': dic['1'],
                                                                        'Interval_2': dic['2'],
                                                                        'Interval_3': dic['3'],
                                                                        'Interval_4': dic['4'],
                                                                        'Interval_5': dic['5'],
                                                                        'Interval_6': dic['6'],
                                                                        'Interval_7': dic['7'],
                                                                        'Interval_8': dic['8'],
                                                                        'Interval_9': dic['9'],
                                                                        'Interval_10': dic['10'],
                                                                        'Interval_11': dic['11'],
                                                                        'Interval_12': dic['12'],
                                                                        'Interval_13': dic['13']},ignore_index = True)

                except:
                    error_segments.append((line, orig, dest))
                    next

    # Export
    cols = ['Interval_0','Interval_1','Interval_2','Interval_3','Interval_4','Interval_5','Interval_6', 'Interval_7','Interval_8','Interval_9','Interval_10','Interval_11','Interval_12','Interval_13']
    df_orig_intervalId[cols] = df_orig_intervalId[cols].div(df_orig_intervalId[cols].sum(axis=1), axis=0)
    # Export
    df_orig_intervalId.to_csv(path+'/tbl_df_orig_intervalId.csv', index=False)
    df_orig_dest_time_by_intervalid.to_csv(path+'/tbl_orig_dest_time_by_intervalid.csv', index=False)


if __name__ == '__main__':
    global unique_modes
    global unique_lines
    global df_route_seq

    # Credentials TFL
    app_id = 'ae744e0a05c74ef5b2bbfac2a7ea5f06'
    app_key = '00024e328b23438496db36a939fe090b'

    # API TFL (https://github.com/dhilmathy/TfL-python-api)
    base_url = 'https://api.tfl.gov.uk/'
    endpoints = {'stopPointByline': 'Line/{0}/Route/Sequence/all',
                'crowndingBynaptan': 'crowding/{0}/Live',
                'crowndingByline': 'StopPoint/{0}/Crowding/{1}?direction={2}&',
                'timetable': 'Line/{0}/Timetable/{1}/to/{2}',
                'timetable_s': 'Line/{0}/Timetable/{1}',
                'latLonByline': 'Line/{0}/StopPoints',
                'stoptid': '/StopPoint/{0}/Crowding/{1}?direction={2}&',
                'time': '/Journey/JourneyResults/{0}/to/{1}?mode={2}&'}

    # API Client
    token = ApiToken(app_id, app_key)
    client = Client(token)
    api_token = { app_id: token.app_id, app_key: token.app_key }

    path = r'/home/soaresbr/data_projects/big-cities-transport/01.BaseGraph/API'

    unique_modes = modes()
    unique_lines = lines()
    # routes()
    # coordenates()
    df_route_seq = routes_seq()
    od_intervalid()

















