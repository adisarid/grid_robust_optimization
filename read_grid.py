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

import csv # to import csv files
import os
import networkx as nx # to build a grid networkx object

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

def build_nx_grid(nodes, edges):
    G = nx.Graph() # initialize graph using networkx library
    for node in [i[1] for i in nodes.keys() if i[0] == 'd']:
        G.add_node(node,
                   demand = max(0, nodes[('d', node)]),
                   original_demand = max(0, nodes[('d', node)]),
                   gen_cap = nodes[('c', node)],
                   generated = min(0, nodes[('d', node)]),
                   un_sup_cost = 0)
    for edge in [(i[1],i[2]) for i in edges.keys() if i[0] == 'c' and edges[i]>0]:
        G.add_edge(edge[0], edge[1], capacity = edges[('c',) + edge],
                   susceptance = edges[('x',) + edge])
    return G


