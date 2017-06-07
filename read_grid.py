#-------------------------------------------------------------------------------
# Name:        read_grid
# Purpose:     Read data files and parameters of grid
#
# Author:      Adi Sarid
#
# Created:     07/06/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import csv
import os

def read_nodes(filename):
    dic = dict()
    with open(filename, 'rb') as nodesfile:
        nodes_reader = csv.reader(nodesfile, delimiter = ',')
        next(nodes_reader) # assuimng header, skip first line
        for row in nodes_reader:
            dic[('d', row[0])] = float(row[1]) # read demand
            dic[('c', row[0])] = float(row[2]) # read capacity
            dic[('gen_up_ub', row[0])] = float(row[3]) # max generation upgrade
            dic[('H', row[0])] = float(row[4]) # fixed cost
            dic[('h', row[0])] = float(row[5]) # variable cost
    return dic

def read_edges(filename):
    dic = dict()
    with open(filename, 'rb') as edgesfile:
        csv_reader = csv.reader(edgesfile, delimiter = ',')
        next(csv_reader) # assuimng header, skip first line
        for row in csv_reader:
            dic[('c', row[0], row[1])] = float(row[2]) # current capacity
            dic[('x', row[0], row[1])] = float(row[3]) # susceptance
            dic[('H', row[0], row[1])] = float(row[4]) # fixed cost
            dic[('h', row[0], row[1])] = float(row[4]) # variable cost
    return dic

def read_scenarios(filename_fail, filename_pr):
    dic = dict()
    with open(filename_pr, 'rb') as prfile:
        csv_reader = csv.reader(prfile, delimiter = ',')
        next(csv_reader) # assuming heade, skip first line
        for row in csv_reader:
            dic[('s_pr', row[0])] = float(row[1])

    with open(filename_fail, 'rb') as failurefile:
        csv_reader = csv.reader(failurefile, delimiter = ',')
        next(csv_reader) # assuimng header, skip first line
        for row in csv_reader:
            if ('s', row[0]) in dic.keys():
                dic[('s', row[0])] += [(row[1], row[2])] # failures
            else:
                dic[('s', row[0])] = [(row[1], row[2])] # first failure in this scenario
    return dic

def read_additional_param(filename):
    dic = dict()
    with open(filename, 'rb') as paramfile:
        csv_reader = csv.reader(paramfile, delimiter = ',')
        next(csv_reader) # assuming heade, skip first line
        for row in csv_reader:
            dic[(row[0])] = float(row[1])
    return dic

os.chdir('c:\\Users\\Adi Sarid\\Documents\\GitHub\\grid_robust_opt\\adi_simple1\\') #temporarily code for setting location
#a = read_nodes('grid_nodes.csv')
#b = read_edges('grid_edges.csv')
#c = read_scenarios('scenario_failures.csv', 'scenario_probabilities.csv')
d = read_additional_param('additional_params.csv')