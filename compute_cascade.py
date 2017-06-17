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
import cascade_simulator_aux # for computing the cascades

def compute_failed_inconsistent(nodes, edges, scenarios, current_solution, dvar_pos):
    """
    Function builds grid based on original grid and infrastructure decisions from dvar_pos
    Then the cfe algorithm is run to determine which edges should fail in each scenario
    These are compared to the failed edges in dvar_pos
    Inconsistencies are returned by the function
    If no inconsistencies are found then the function returns an empty list
    """

    init_grid = build_nx_grid(nodes, edges, current_solution, dvar_pos) # build initial grid
    scenario_list = [cur_sce[1] for cur_sce in scenarios.keys() if cur_sce[0] == 's_pr'] # get scenario list
    end_game_failed = dict() # initialize edge failure dictionary
    for cur_scenario in scenario_list:
        init_fail_edges = scenarios[('s', cur_scenario)]
        G = init_grid.copy() # the cfe command runs over the grid so this is why I create a copy
        end_game_failed[cur_scenario] = cascade_simulator_aux.cfe(G, init_fail_edges, write_solution_file = False)




def build_nx_grid(nodes, edges, current_solution, dvar_pos):
    """
    Create the initial grid as an networkx object.
    Used to build the grid, consistent with function create_grid from previous work under cascade simulator.
    Function has been optimized to add the nodes and edges as a bunch, using a single command and doing the prep work
    via list comprehension of the edges and nodes.
    """

    G = nx.Graph() # initialize empty graph

    # add all nodes
    node_list = [node[1] for node in nodes.keys() if node[0] == 'd']
    add_nodes = [(cur_node, {'demand': nodes[('d', cur_node)],'gen_cap':nodes[('c', cur_node)] + current_solution[dvar_pos[('c', cur_node)]], 'generated':0, 'un_sup_cost':0, 'gen_cost':0, 'original_demand': nodes[('d', cur_node)]}) for cur_node in node_list]
    G.add_nodes_from(add_nodes)

    # add all edges
    edge_list = [(edge[1], edge[2]) for edge in edges if edge[0] == 'c']
    add_edges = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge] + current_solution[dvar_pos[('c', cur_edge)]], 'susceptance': edges[('x',) + cur_edge]}) for cur_edge in edge_list if (edges[('c',) + cur_edge] > 0 or current_solution[dvar_pos[('X_', cur_edge)]> 0.01])]
    G.add_edges_from(add_edges)

    return(G)


