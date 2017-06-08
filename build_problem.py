#-------------------------------------------------------------------------------
# Name:        build_problem
# Purpose:     Build a robust planning problem with cplex and lazy callbacks
#
# Author:      Adi Sarid
#
# Created:     07/06/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import cplex # for building and interfacing with cplex api
import compute_cascade # needed for the lazy call backs algorithm

def build_cplex_problem(nodes, edges, scenarios, params):

    # initialize variable vector with variable name
    dvar_name = []
    dvar_location = dict() # I like having both the name as a string and the location in vector as a dictionary
    dvar_obj_coef = []
    dvar_lb = []
    dvar_ub = []
    dvar_type = []

    # epsilon
    epsilon = 1e-10 # depending on grid size, this constant can take various values 1e-10 is probably small enough for any practical situation

    tot_demand = sum([nodes[i] for i in nodes.keys() if i[0] == 'd'])

    # list scenarios
    all_scenarios = [i[1] for i in scenarios.keys() if i[0] == 's']

    # by nodes
    all_nodes = [i[1] for i in nodes.keys() if i[0] == 'd']
    for cur_node in all_nodes:
        for cur_scenario in all_scenarios:
            # generation variable (g)
            dvar_name.append('g_' + cur_node + 's' + cur_scenario)
            dvar_location[('g', cur_node, cur_scenario)] = len(dvar_name)
            dvar_obj_coef.append(0)
            dvar_lb.append(0)
            dvar_ub.append(nodes[('c', cur_node)] + nodes[('gen_up_ub', cur_node)])
            dvar_type.append('C')

            # unsuppled demand variable (w)
            if nodes[('d', cur_node)] > 0:
                dvar_name.append('w_' + cur_node + 's' + cur_scenario)
                dvar_location[('w', cur_node, cur_scenario)] = len(dvar_name)
                dvar_obj_coef.append(-scenarios[('s_pr', cur_node)]) # scenario relative weight
                dvar_lb.append(0)
                dvar_ub.append(nodes[('d', cur_node)])
                dvar_type.append('C')

            # phase angle (theta)
            dvar_name.append('theta' + cur_node + 's' + cur_scenario)
            dvar_location[('theta', cur_node, cur_scenario)] = len(dvar_name)
            dvar_obj_coef.append(0)
            dvar_lb.append(0)
            dvar_ub.append(360)
            dvar_type.append('C')

        # capacity upgrade of node (independent of scenario)
        dvar_name.append('c_' + cur_node)
        dvar_location[('c', cur_node)] = len(dvar_name)
        dvar_obj_coef.append(0)
        dvar_lb.append(0)
        dvar_ub.append(nodes[('gen_up_ub', cur_node)])
        dvar_type.append('C')

        # establish backup capacity at node i
        dvar_name.append('Z_' + cur_node)
        dvar_location[('Z', cur_node)] = len(dvar_name)
        dvar_obj_coef.append(0)
        dvar_lb.append(0)
        dvar_ub.append(1)
        dvar_type.append('B')

    # by edges
    all_edges = [(i[1],i[2]) for i in edges.keys() if i[0] == 'c']
    for cur_edge in all_edges:
        edge_str = str(cur_edge).replace(', ', '_').replace("'", "").replace('(', '').replace(')','')
        for cur_scenario in all_scenarios:
            # define flow variabels
            dvar_name.append('f_' + edge_str + 's' + cur_scenario)
            dvar_location[('f', cur_edge, cur_scenario)] = len(dvar_name)
            dvar_obj_coef.append(0)
            dvar_lb.append(-tot_demand)
            dvar_ub.append(tot_demand)
            dvar_type.append('C')

        # define capacity upgrade constraints
        dvar_name.append('c_' + edge_str)
        dvar_location[('c', cur_edge)] = len(dvar_name)
        dvar_obj_coef.append(0)
        dvar_lb.append(0)
        dvar_ub.append(tot_demand)
        dvar_type.append('C')



        # establish new edge (only if upgrade cost > 0 otherwise this edge already exists, no need to add variable)
        if cur_edge in [(i[1], i[2]) for i in edges.keys() if i[0] == 'H' and edges[i] > 0]:
            dvar_name.append('X_' + edge_str)
            dvar_location[('X_', cur_edge)] = len(dvar_name)
            dvar_obj_coef.append(0)
            dvar_lb.append(0)
            dvar_ub.append(1)
            dvar_type.append('B')


    # initialize cplex object
    robust_opt = cplex.Cplex()
    robust_opt.objective.set_sense(robust_opt.objective.sense.minimize) # minimize expected loss of load

    # building the decision variables within object
    robust_opt.variables.add(obj = dvar_obj_coef, lb = dvar_lb, ub = dvar_ub, types = dvar_type, names = dvar_name)

    # build constraints

    return robust_opt



# Build lazycallbacks


