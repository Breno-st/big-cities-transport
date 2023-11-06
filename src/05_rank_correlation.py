

from scipy.stats import kendalltau
import pandas as pd
import plotly.graph_objs as go
import pickle
import numpy as np

import plotly.graph_objs as go


### PICKLE FUNCTIONS ###
def dict_to_pickle(dict, savename):
    with open(savename, 'wb') as handle:
        pickle.dump(dict, handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_pickle(filename):
    with open(filename, 'rb') as handle:
        loadedfile = pickle.load(handle)
    return loadedfile


#### CORRELATION FUNCTIONS ####

def spearman_rank_correlation(rank_seq1, rank_seq2):
    """
    Calculate the Spearman Rank Correlation Coefficient between two rank sequences.

    Parameters:
    rank_seq1 (list): The first rank sequence.
    rank_seq2 (list): The second rank sequence.

    Returns:
    float: The Spearman Rank Correlation Coefficient, ranging from -1 to 1.
    """
    if len(rank_seq1) != len(rank_seq2):
        raise ValueError("Both rank sequences must have the same length")

    n = len(rank_seq1)

    # Calculate the rank differences squared
    d_squared = [(rank_seq1[i] - rank_seq2[i]) ** 2 for i in range(n)]

    # Calculate the Spearman Rank Correlation Coefficient
    r = 1 - (6 * sum(d_squared)) / (n * (n ** 2 - 1))

    return r


def period_rank_correlation_matrix(od, kpi):
    ''' Calculate Kendall & Spearman ranking metric '''

    df = pd.read_csv(f'{path}/04.Disparity/{od}/{od}-{kpi}.csv', header=[0, 1,2], index_col=[0])

    for day in days:

        sp_matrix = [[0] * len(periods) for _ in range(len(periods))]
        kd_matrix = [[0] * len(periods) for _ in range(len(periods))]
        sp_matrix_alpha = [[0] * len(periods) for _ in range(len(periods))]
        kd_matrix_alpha = [[0] * len(periods) for _ in range(len(periods))]

        for i, period1 in enumerate(periods):
            for j, period2 in enumerate(periods):

                list1 = df.loc[:, (day, period1, f'{kpi}_rnk')].values
                list2 = df.loc[:, (day, period2, f'{kpi}_rnk')].values

                list3 = df.loc[:, (day, period1, f'alpha_rnk')].values
                list4 = df.loc[:, (day, period2, f'alpha_rnk')].values

                sp_matrix[i][j] = spearman_rank_correlation(list1, list2)
                sp_matrix_alpha[i][j] = spearman_rank_correlation(list3, list4)
                kd_matrix[i][j], p_value = kendalltau(list1, list2)
                kd_matrix_alpha[i][j], p_value = kendalltau(list3, list4)

        title_alpha_sp = f'Alpha {kpi.title()} Ranks Correlation across {days_[day]} (Spearman)'
        title_alpha_kd = f'Alpha {kpi.title()} Ranks Correlation across {days_[day]} (Kendall)'
        title_sp = f'{kpi.title()} Ranks Correlation across {days_[day]} (Spearman)'
        title_kd = f'{kpi.title()} Ranks Correlation across {days_[day]} (Kendall)'

        heat_map(sp_matrix, od, title_sp)
        heat_map(sp_matrix_alpha, od, title_alpha_sp)
        heat_map(kd_matrix, od, title_kd)
        heat_map(kd_matrix_alpha, od, title_alpha_kd)


#### PLOTS ####
def heat_map(data, od, title):

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

    X         = [period for period in periods]
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

    #### Defining variables  ####
    ods = [ 'tube'] # 'overground', 'dlr', 'tube'
    days = ['fri', 'sat', 'mtt', 'sun']
    days_ = {'fri': 'Friday', 'sat':'Saturday', 'mtt':'Mon-Thu', 'sun': 'Sunday'}
    periods = ['Morning', 'AM Peak', 'Midday', 'PM Peak', 'Evening', 'Late']
    kpis = ['traffic']# 'distress' review distress graphs 'distance', 'speed', 'traffic', 'traffic_distances', 'loads',
    path = "C:/buildbr/big-cities-transport"

    for od in ods:
        for kpi in kpis:
            # Loadind file "od_mode" to calclulate shortest paths:
            period_rank_correlation_matrix(od, kpi)



    # #### EFFICIENCY & DISTRESS COMPARISSON ####
    # rank_correlation_matrix(df)


## Run 5h/3, Bike 10h/4, Gym 5h (back, chest, leg, core, core)
## week:1   12-12-21 free
## week:2   16-12-24 free
## week:3   14-14-30 speed
## week:4   16-16-10-26 transition
## week:5   16-16-12-30 transition
## week:6   16-8-16-8-10-24 transition
## week:7   14-8-14-8-21-28 volume
## week:8   10-10

# # run, bike, gym: 4/4/5
# # proj,lang, read,
# # cook, clea, clot, mrkt

# ## Lundi:      5h: ----, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: legs, 21h: lang, 22h: read		>>>
# ## Mardi:      5h: ru16, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: core, 21h: proj, 22h: read		>>>
# ## Mecredi:    5h: bike, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: chst, 21h: ----, 22h: read		>>>
# ## Jeudi:      5h: ru12, 8h: Work, 12h:lunch, 14h: Work, 18h: cook, 20h: proj, 21h: proj, 22h: read		>>>
# ## Vendredi:   5h: bike, 8h: work, 12h: work, 14h: work, 18h: ----, 20h: back, 21h: ----, 22h: read		>>>
# ## Samedi:     5h: bike, 8h: room, 12h: mrkt, 14h: proj, 18h: proj, 20h: ----, 21h: ----, 22h: ----   	>>>
# ## Dimache:    5h: bike, 8h: clot, 12h: cook, 14h: proj, 18h: ru24, 20h: ----, 21h: ----, 22h: ----		>>>

# ## TODO PLAN
# ## UCL pay, My Trip, Camila Trip, Laptop,

# ## TODO SHORT
# ### 11 Nov: Athens
# ### 18 Nov: Farewell NE
# ### 25 Nov: Farewell ML
# ### 02 Dec: Farewell LU
# ### 10 Dec: ??

# ### 01 Dec: Breda xxx€ normal   (RENT - fillup car)
# ### 15 Dec: BE>IT  45€ remote   (5 days IT)
# ### 20 Dec: IT>SP 464€ unpaid   (23 days BR)
# ### 09 Jan: SP>BE 680€ holidays (5 days PT) Exam 11/01
# ### 17 Jan: PT>BE  62€ holidays (13 days HAL) thesis, resignation (give back the car and unpaid leaves), domiciliation, Basic-fit
# ### 30 Jan: BE>BE 375€ holidays (7 days HAL)
# ### 30 Jan: BE>?? xxx€ --------------------------------------------------------------------
# ### TOTAL:  1726€

# ### DEP:    1700€
# ### DEZ:    2500€
# ### 13o:    3000€
# ### JAN:    3000€
# ### TOTAL: 11098€

# ### UCL:   -4300€

# ### Bal:    6798€


# ## TODO Code before writting:
#4h### Compare diff periods within a day, resulting in 3 correlation matrix 23/10
#4h### Compare same period through out days, resultion table periods (6) x days (3)

# ## TODO Writting:
#8h### Write Results part 5 06/11
#8h### Write Modeling KPIs part 4 13/11
#4h### Write Methodology Distress part 2
#4h### Write Methodology Disparity part 2 20/11
#4h### Write Data Collections part
#4h### Write Conclusion part 7  by 27/11
#8h### Generate all results vizualizations by 04/12
#4h### Write Following Steps part 6
#4h### Re-Write Introduction part 1  11/12
#68###

# ## TODO Code while writting:

# ### Genrate edge graph plots
# ### Create statistic plots data
# ### Create edge graph plots
# ### Turn big-citis-transpot into App:
# ### Connect and improve codes to build an app (example 2)
# ### Example 2: Application Development (Databases, Django)
# ### Create code for GloSS

# ### Desing Finance Application
