#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      Adi Sarid
#
# Created:     31/10/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import networkx as nx
from read_grid import *
import cplex
from cascade_simulator_aux import *

G = nx.Graph() # initialize empty graph

node_list = [node[1] for node in nodes.keys() if node[0] == 'd']
add_nodes = [(cur_node, {'demand': nodes[('d', cur_node)],'gen_cap':nodes[('c', cur_node)], 'generated':0, 'un_sup_cost':0, 'gen_cost':0, 'original_demand': nodes[('d', cur_node)]}) for cur_node in node_list]
G.add_nodes_from(add_nodes)

edge_list = [(min(edge[1], edge[2]), max(edge[1], edge[2])) for edge in edges.keys() if edge[0] == 'H']  # FIX BUG HERE TO GET THE RIGHT LIST OF EDGES!!!!!!!
add_edges = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge], 'susceptance': edges[('x',) + cur_edge]}) for cur_edge in edge_list if (edges[('c',) + cur_edge] > 0.001)]

G.add_edges_from(add_edges)

flow_solution = grid_flow_update(G, return_cplex_object = True)['cplex_object']

var_names = flow_solution.variables.get_names()
var_value = flow_solution.solution.get_values()

with open('c:/temp/temp_solution.csv', 'wb') as csvfile:
        solutionwriter = csv.writer(csvfile, delimiter = ',')
        solutionwriter.writerow(['name', 'value'])
        solutionwriter.writerows([[var_names[i], abs(var_value[i])] for i in range(len(var_names))])