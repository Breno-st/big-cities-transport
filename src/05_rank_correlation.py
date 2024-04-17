from scipy.stats import kendalltau
import pandas as pd
import plotly.graph_objs as go
import pickle
import numpy as np


### PICKLE FUNCTIONS ###
def dict_to_pickle(dict, savename):
    with open(savename, 'wb') as handle:
        pickle.dump(dict, handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_pickle(filename):
    with open(filename, 'rb') as handle:
        loadedfile = pickle.load(handle)
    return loadedfile


#### CORRELATION FUNCTIONS ####
def period_rank_correlation_matrix(df):
    ''' Calculate Kendall ranking metric '''

    for day in days:
        # Build matrixex
        kd_matrix_kpi = [[0] * len(periods) for _ in range(len(periods))]
        kd_matrix_alpha = [[0] * len(periods) for _ in range(len(periods))]
        kd_matrix_method = [[0] * len(periods) for _ in range(len(periods))]


        # Populate the matrix
        for i, period1 in enumerate(periods):
            for j, period2 in enumerate(periods):

                list1 = df.loc[:, (day, period1, f'{kpi}_rnk')].values # kpi 1
                list2 = df.loc[:, (day, period2, f'{kpi}_rnk')].values # kpi 2

                list3 = df.loc[:, (day, period1, f'alpha_rnk')].values # alpha 1
                list4 = df.loc[:, (day, period2, f'alpha_rnk')].values # alpha 2

                kd_matrix_kpi[i][j], p_value = kendalltau(list1, list2) # kpi 1 x kpi 2 (period)
                kd_matrix_alpha[i][j], p_value = kendalltau(list3, list4) # alpha 1 x alpha 2 (periods)
                kd_matrix_method[i][j], p_value = kendalltau(list3, list1) # alpha 1 x kpi 2 (method)


        title_method_kd = f'{od.upper()} ALP & THR {kpi.title()} Ranks Correlation across {days_[day]}'
        title_alpha_kd = f'{od.upper()} ALP {kpi.title()} Ranks Correlation across {days_[day]}'
        title_kd = f'{od.upper()} THR {kpi.title()} Ranks Correlation across {days_[day]}'

        # Plot the matrix
        heat_map(kd_matrix_kpi, od, title_kd, periods)
        heat_map(kd_matrix_alpha, od, title_alpha_kd, periods)
        heat_map(kd_matrix_method, od, title_method_kd, periods)


def day_rank_correlation_matrix(df):
    ''' Calculate Kendall ranking metric '''

    for period in periods:

        kd_matrix = [[0] * len(days) for _ in range(len(days))]
        kd_matrix_alpha = [[0] * len(days) for _ in range(len(days))]

        for i, day1 in enumerate(days):
            for j, day2 in enumerate(days):

                list1 = df.loc[:, (day1, period, f'{kpi}_rnk')].values
                list2 = df.loc[:, (day2, period, f'{kpi}_rnk')].values

                list3 = df.loc[:, (day1, period, f'alpha_rnk')].values
                list4 = df.loc[:, (day2, period, f'alpha_rnk')].values

                kd_matrix[i][j], p_value = kendalltau(list1, list2)
                kd_matrix_alpha[i][j], p_value = kendalltau(list3, list4)

        title_alpha_kd = f'{od.upper()} ALP {kpi.title()} Ranks Correlation across {period}'
        title_kd = f'{od.upper()} THR {kpi.title()} Ranks Correlation across {period}'

        heat_map(kd_matrix, od, title_kd, days)
        heat_map(kd_matrix_alpha, od, title_alpha_kd, days)

def kpis_rank_correlation_matrix(df1, df2):
    ''' Calculate Kendall ranking metric '''

    for day in days:

        kd_matrix_kpis = [[0] * len(periods) for _ in range(len(periods))]

        for i, period1 in enumerate(periods):
            for j, period2 in enumerate(periods):


                list3 = df1.loc[:, (day, period1, f'alpha_rnk')].values
                list4 = df2.loc[:, (day, period2, f'alpha_rnk')].values


                kd_matrix_kpis[i][j], p_value = kendalltau(list3, list4)

        title_kpis_kd = f'{od.upper()} ALP Eff & Robust Correlation across {days_[day]}'

        heat_map(kd_matrix_kpis, od, title_kpis_kd, periods)

#### PLOTS ####
def heat_map(data, od, title, array):

    data = np.array(data)

    sns_colorscale = [[0.0, '#3f7f93'],
    [0.071, '#5890a1'],
    [0.143, '#72a1b0'],
    [0.214, '#8cb3bf'],
    [0.286, '#a7c5cf'],
    [0.357, '#c0d6dd'],
    [0.429, '#dae8ec'],
    [0.5, '#f2f2f2'],
    [0.571, '#f7d7d9'],
    [0.643, '#f2bcc0'],
    [0.714, '#eda3a9'],
    [0.786, '#e8888f'],
    [0.857, '#e36e76'],
    [0.929, '#de535e'],
    [1.0, '#d93a46']]

    X         = [col.title() for col in array]
    N         = data.shape[1]

    hovertext = [[f'corr({X[i]}, {X[j]})= {data[i][j]:.2f}' for j in range(N)] for i in range(N)]

    heat = go.Heatmap(z=data,
                    x=X,
                    y=X,
                    zmin=-1,
                    zmax=1,
                    xgap=1, ygap=1,
                    colorscale=sns_colorscale,
                    colorbar_thickness=20,
                    colorbar_ticklen=3,
                    hovertext=hovertext,
                    hoverinfo='text'
                    )

    layout = go.Layout(title_text=title, title_x=0.5,
                    width=600, height=600,
                    xaxis_showgrid=False,
                    yaxis_showgrid=False,
                    yaxis_autorange='reversed'
                    ,xaxis_side='top'
                    )

    fig=go.Figure(data=[heat], layout=layout)
    fig.write_image(f'{path}/05.Rankings/{od}/img/{title}.png')

if __name__ == "__main__":

    global path
    global days
    global days_
    global periods
    global od

    #### Defining variables  ####
    ods = ['dlr', 'overground', 'tube'] # 'overground', 'dlr', 'tube'
    days = ['mtt', 'fri', 'sat', 'sun']
    days_ = {'fri': 'Friday', 'sat':'Saturday', 'mtt':'Mon-Thu', 'sun': 'Sunday'}
    periods = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']
    kpis = ['distress'] # 'distress',  'traffic', # 'distance', 'speed',
    path = "/mnt/c/buildbr/big-cities-transport"

    for od in ods:
        for kpi in kpis:

            df = pd.read_csv(f'{path}/04.Disparity/02.Output/{kpi}/ranks/rank-{od}-{kpi}.csv', header=[0, 1,2], index_col=[0])

            if kpi in ['speed', 'distance']:

                list_thr = df.loc[:, (f'{kpi}_rnk')].values
                list_alp = df.loc[:, (f'alpha_rnk')].values

                coef = kendalltau(list_thr, list_alp)

                print(f'the corf relation values for {kpi} in {od}: {coef}')

            else:

                # Rank 6 by 6: period against period
                period_rank_correlation_matrix(df)

                # Rank 4 by 4: day against day HERE!!
                day_rank_correlation_matrix(df)

        # Rank 6 by 6: kpi against kpi

        df1 = pd.read_csv(f'{path}/04.Disparity/02.Output/efficiencies/ranks/rank-{od}-efficiencies.csv', header=[0, 1,2], index_col=[0])
        df2 = pd.read_csv(f'{path}/04.Disparity/02.Output/distress/ranks/rank-{od}-distress.csv', header=[0, 1,2], index_col=[0])
        kpis_rank_correlation_matrix(df1, df2)




