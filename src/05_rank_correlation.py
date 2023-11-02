
from scipy.stats import kendalltau
from networkx.readwrite import json_graph
import json
import sys
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import matplotlib.image as mpimg

import pickle

import matplotlib.pyplot as plt


### PICKLE FUNCTIONS ###
def dict_to_pickle(dict, savename):
    with open(savename, 'wb') as handle:
        pickle.dump(dict, handle, protocol=pickle.HIGHEST_PROTOCOL)

def load_pickle(filename):
    with open(filename, 'rb') as handle:
        loadedfile = pickle.load(handle)
    return loadedfile


#### CORRELATION FUNCTIONS ####
def rank_correlation_matrix(df):
    ''' Calculate Kendall & Spearman ranking metric '''
    # Get two lists for comparisson:
    days_against_days_list = []
    period_against_period_list = []

    # Day perspective: comparing periods
    for day in days:
        for period1, period2 in period_against_period_list:
            list1 = df[day][period1].to_list()
            list2 = df[day][period2].to_list()
            # Enter the two lists and store into Day Matrix 6x6
            tau, p_value = kendalltau(list1, list2)
            correlation = spearman_rank_correlation(list1, list2)
            # Output Kendall ranking
            print(f"Kendall Ranking Metric for {day}: {period1}x{period2} : tau: {tau} and P-value: {p_value}")
            print(f"Spearman Rank Correlation for {day}: {period1}x{period2}: {correlation}")

    # Period perspective: comparing day
    for period in periods:
        for day1, day2 in days_against_days_list:
            list1 = df[day1][period].to_list()
            list2 = df[day2][period].to_list()
            # Enter the two lists and store into Period Matrix 4x4
            tau, p_value = kendalltau(list1, list2)
            correlation = spearman_rank_correlation(list1, list2)
            # Output Kendall ranking
            print(f"Kendall Ranking Metric for {period}: {day1}x{day2} : tau: {tau} and P-value: {p_value}")
            print(f"Spearman Rank Correlation for {period}: {day1}x{day2}: {correlation}")

def rank_correlation_matrix(df):
    ''' Calculate Kendall & Spearman ranking metric '''
    # Get two lists for comparisson:
    days_against_days_list = []
    period_against_period_list = []

    # Day perspective: comparing periods
    for day in days:
        for period1, period2 in period_against_period_list:
            list1 = df[day][period1].to_list()
            list2 = df[day][period2].to_list()
            # Enter the two lists and store into Day Matrix 6x6
            tau, p_value = kendalltau(list1, list2)
            correlation = spearman_rank_correlation(list1, list2)
            # Output Kendall ranking
            print(f"Kendall Ranking Metric for {day}: {period1}x{period2} : tau: {tau} and P-value: {p_value}")
            print(f"Spearman Rank Correlation for {day}: {period1}x{period2}: {correlation}")

    # Period perspective: comparing day
    for period in periods:
        for day1, day2 in days_against_days_list:
            list1 = df[day1][period].to_list()
            list2 = df[day2][period].to_list()
            # Enter the two lists and store into Period Matrix 4x4
            tau, p_value = kendalltau(list1, list2)
            correlation = spearman_rank_correlation(list1, list2)
            # Output Kendall ranking
            print(f"Kendall Ranking Metric for {period}: {day1}x{day2} : tau: {tau} and P-value: {p_value}")
            print(f"Spearman Rank Correlation for {period}: {day1}x{day2}: {correlation}")

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

#### PLOTS ####




if __name__ == "__main__":

    global path
    global days
    global periods


# #### APPLY RANK CORRELATION ALGORTIHMS #### READY to Go
            # rank_correlation_matrix(df)

            # #### PLOT CORRELATIONS MATRIX ####


            # #### EFFICIENCY & DISTRESS COMPARISSON ####
            # rank_correlation_matrix(df)
