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
    end_game_failed = {cur_scenario: cascade_simulator_aux.cfe(init_grid.copy(), scenarios[('s', cur_scenario)], write_solution_file = False)['all_failed']  for cur_scenario in scenario_list}

    # Find inconsistencies of failures by end_game_failed versus current_solution
    F_keys = [key for key in dvar_pos.keys() if key[0] == 'F']
    failed_in_solution = {cur_scenario: [key for key in F_keys if current_solution[dvar_pos[key]] > 0.999 and key[2] == cur_scenario] for cur_scenario in scenario_list}
    not_failed_in_solution = {cur_scenario: [key for key in F_keys if current_solution[dvar_pos[key]] < 0.001 and key[2] == cur_scenario] for cur_scenario in scenario_list}

    # Edges which did not fail in current solution but should fail according to the simulation
    not_failed_should_fail = {cur_scenario: [edge for edge in not_failed_in_solution[cur_scenario] if edge[1] in end_game_failed[cur_scenario]] for cur_scenario in scenario_list}
    # Edges which failed in current solution but shouldn't fail according to the simulation
    failed_shouldnt_fail = {cur_scenario: [edge for edge in failed_in_solution[cur_scenario] if edge[1] not in end_game_failed[cur_scenario]] for cur_scenario in scenario_list}

    inconsistencies = {'should_fail': not_failed_should_fail, 'shouldnt_fail': failed_shouldnt_fail}

    return(inconsistencies)




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
    edge_list = [(min(edge[1], edge[2]), max(edge[1], edge[2])) for edge in edges if edge[0] == 'c']
    add_edges = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge] + current_solution[dvar_pos[('c', cur_edge)]], 'susceptance': edges[('x',) + cur_edge]}) for cur_edge in edge_list if (edges[('c',) + cur_edge] > 0 or current_solution[dvar_pos[('X_', cur_edge)]> 0.01])]
    G.add_edges_from(add_edges)

    return(G)


