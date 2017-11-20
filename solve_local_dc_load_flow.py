#-------------------------------------------------------------------------------
# Name:        solve_local_dc_load_flow.py
# Purpose:
#
# Author:      Adi Sarid
#
# Created:     20/11/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

# This file is used to load data and locally solve a dc load flow problem.

from read_grid import nodes, edges, scenarios, params

import networkx as nx

def build_init_nx_grid(nodes, edges):
    """
    Create the initial grid as an networkx object. Adaptation of build_nx_grid from compute_cascade.py
    """

    G = nx.Graph() # initialize empty graph

    # add all nodes
    node_list = [node[1] for node in nodes.keys() if node[0] == 'd']
    add_nodes = [(cur_node, {'demand': nodes[('d', cur_node)],'gen_cap':nodes[('c', cur_node)], 'generated':0, 'un_sup_cost':0, 'gen_cost':0, 'original_demand': nodes[('d', cur_node)]}) for cur_node in node_list]
    G.add_nodes_from(add_nodes)

    # add all edges
    edge_list = [(min(edge[1], edge[2]), max(edge[1], edge[2])) for edge in edges if edge[0] == 'c']
    add_edges = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge], 'susceptance': edges[('x',) + cur_edge]}) for cur_edge in edge_list if (edges[('c',) + cur_edge] > 0)]

    G.add_edges_from(add_edges)

    return(G)


initial_G = build_init_nx_grid(nodes, edges)

from cascade_simulator_aux import grid_flow_update

flow_results = grid_flow_update(initial_G, failed_edges = [], write_lp = False, return_cplex_object = True)

from export_results import write_names_values

write_names_values(variable_names = flow_results['cplex_object'].variables.get_names(), current_solution = flow_results['cplex_object'].solution.get_values(), csvfilename = "initial_flow_solution.csv")