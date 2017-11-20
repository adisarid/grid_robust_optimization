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
from time import gmtime, strftime, clock # for placing timestamp on debug solution files
from global_definitions import line_capacity_coef_scale
from global_definitions import best_incumbent
from debug_output_specs import *

def compute_failures(nodes, edges, scenarios, current_solution, dvar_pos):
    """
    Function builds grid based on original grid and infrastructure decisions from dvar_pos
    Then the cfe algorithm is run to determine which edges should fail in each scenario
    cfe results are returned by the function as a dictionary with scenario keys for later use.
    """
    global best_incumbent

    if print_debug_function_tracking:
        print "ENTERED: compute_casecade.compute_failure()"
    init_grid = build_nx_grid(nodes, edges, current_solution, dvar_pos) # build initial grid
    #print "DEBUG: Feeding into cfe algorithm (compute_cascade.compute_failed_inconsistent()) - edges:", init_grid.edges()
    scenario_list = [cur_sce[1] for cur_sce in scenarios.keys() if cur_sce[0] == 's_pr'] # get scenario list
    initial_failures_to_cfe = {cur_scenario: scenarios[('s', cur_scenario)] for cur_scenario in scenario_list}

    cfe_dict_results = {cur_scenario: cascade_simulator_aux.cfe(init_grid.copy(), initial_failures_to_cfe[cur_scenario], write_solution_file = False) for cur_scenario in scenario_list}
    tmpGs = {cur_scenario: cfe_dict_results[cur_scenario]['updated_grid_copy'] for cur_scenario in scenario_list}

    # computing the unsupplied demand (objective value) and updating best incumbent if needed
    unsup_demand = [scenarios[('s_pr', cur_scenario)]*sum([result_grid.node[cur_node]['original_demand']-result_grid.node[cur_node]['demand'] for cur_node in result_grid.nodes()]) for (cur_scenario, result_grid) in tmpGs.iteritems()]
    best_incumbent = min(unsup_demand, best_incumbent)

    # print the best incumbent for tenth cases (if tick is < 6 sec).
    if gmtime()[5] <= 6:
        print "Incumbent objective =", sum(unsup_demand)
        # consider later on to add: write incumbent solution to file.

    return(cfe_dict_results)




def build_nx_grid(nodes, edges, current_solution, dvar_pos):
    """
    Create the initial grid as an networkx object.
    Used to build the grid, consistent with function create_grid from previous work under cascade simulator.
    Function has been optimized to add the nodes and edges as a bunch, using a single command and doing the prep work
    via list comprehension of the edges and nodes.
    """
    if print_debug_function_tracking:
        print "ENTERED: compute_casecade.build_nx_grid()"
    G = nx.Graph() # initialize empty graph

    # add all nodes
    node_list = [node[1] for node in nodes.keys() if node[0] == 'd']
    add_nodes = [(cur_node, {'demand': nodes[('d', cur_node)],'gen_cap':nodes[('c', cur_node)] + current_solution[dvar_pos[('c', cur_node)]], 'generated':0, 'un_sup_cost':0, 'gen_cost':0, 'original_demand': nodes[('d', cur_node)]}) for cur_node in node_list]
    G.add_nodes_from(add_nodes)

    # add all edges
    # note an important change from the continuous case to the discrete case: the use of: current_solution[dvar_pos[('c', cur_edge)]]*line_capacity_coef_scale
    # this means that the capacity can grow by line_capacity_coef_scale
    # should later on be introduced as part of the input.
    edge_list = [(min(edge[1], edge[2]), max(edge[1], edge[2])) for edge in edges if edge[0] == 'c']

    # The next line introduces a bug where dvar_pos[('X_', cur_edge)] does not exist but is called for. FIX THIS!!
    add_edges = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge] + current_solution[dvar_pos[('c', cur_edge)]]*line_capacity_coef_scale, 'susceptance': edges[('x',) + cur_edge]}) for cur_edge in edge_list if (edges[('c',) + cur_edge] > 0 or current_solution[dvar_pos[('X_', cur_edge)]]> 0.01)]

    # Debugging
    #timestampstr = strftime('%d-%m-%Y %H-%M-%S - ', gmtime()) + str(round(clock(), 3)) + ' - '
    #print timestampstr, "Currently inside compute_cascade.build_nx_grid(). Adding edges:", add_edges
    # Check if X are installed here
    # installed_edges = {('X_', cur_edge): current_solution[dvar_pos[('X_', cur_edge)]> 0.01] for cur_edge in edge_list}

    G.add_edges_from(add_edges)

    return(G)


