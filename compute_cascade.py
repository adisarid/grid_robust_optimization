#-------------------------------------------------------------------------------
# Name:        compute_cascade
# Purpose:     Computes grid cascade based on the Sultan and Zussman algorithm.
#
# Author:      Adi Sarid
#
# Created:     08/06/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import networkx as nx

def compute_failed_inconsistent(nodes, edges, current_solution, dvar_pos):
    """
    Function builds grid based on original grid and infrastructure decisions from dvar_pos
    Then the cfe algorithm is run to determine which edges should fail in each scenario
    These are compared to the failed edges in dvar_pos
    Inconsistencies are returned by the function
    If no inconsistencies are found then the function returns an empty list
    """

    grid = build_nx_grid(nodes, edges)




# create the initial grid as an networkx object


def build_nx_grid(nodes, edges, current_solution, dvar_pos):
    """
    Used to build the grid, consistent with function create_grid from previous work under cascade simulator
    """

    G = nx.Graph() # initialize empty graph

    # CODE CAN BE OPTIMIZED BY:
    # Use list comprehention to load all nodes and edges
    # by add_nodes_from and add_edges_from
    # For now, continuouing with regular loops - easier to read:

    # add all nodes
    node_list = [node[1] for node in nodes.keys() if node[0] == 'd']
    for cur_node in node_list:
        # first check for upgrades
        cap_upgrade = current_solution[dvar_pos[('c', cur_node)]]
        # create the updated node
        G.add_node(cur_node, demand = nodes[('d', cur_node)], gen_cap = nodes[('c', cur_node)] + cap_upgrade, generated = 0) # initialize generated as 0.

    # add all edges
    edge_list = [(edge[1], edge[2]) for edge in edges if edge[0] == 'c']
    for cur_edge in edge_list:
        # first check for edge upgrades
        cap_upgrade = current_solution[dvar_pos[('c', cur_edge)]]
        if (edges[('c',) + cur_edge] > 0 or cap_upgrade > 0):
            # if edge exists or was established and upgraded
            G.add_edge(cur_edge[0], cur_edge[1], capacity = edges[('c',) + cur_edge] + cap_upgrade , susceptance = edges[('x',) + cur_edge])


