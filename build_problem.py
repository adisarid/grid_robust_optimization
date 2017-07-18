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
from cplex.callbacks import LazyConstraintCallback # import class for lazy callbacks
import compute_cascade # needed for the lazy call backs algorithm
from read_grid import nodes, edges, scenarios, params # using global variables for easy reading into lazy callback class
from export_results import write_names_values # imported for writing callback information - debugging purpuses
from time import gmtime, strftime, clock # for placing timestamp on debug solution files

epsilon = 1e-10
bigM = 1.0/epsilon

def build_cplex_problem():
    global dvar_pos # used as global to allow access across all functions
    global dvar_name

    # initialize variable vector with variable name
    dvar_name = []
    dvar_pos = dict() # I like having both the name as a string and the location in vector as a dictionary
    dvar_obj_coef = []
    dvar_lb = []
    dvar_ub = []
    dvar_type = []

    # epsilon
    global epsilon # depending on grid size, this constant can take various values 1e-10 is probably small enough for any practical situation
    global bigM
    tot_demand = sum([nodes[i] for i in nodes.keys() if i[0] == 'd'])

    # list scenarios
    all_scenarios = [i[1] for i in scenarios.keys() if i[0] == 's']

    # by nodes
    all_nodes = [i[1] for i in nodes.keys() if i[0] == 'd']
    for cur_node in all_nodes:
        for cur_scenario in all_scenarios:
            # generation variable (g)
            dvar_name.append('g_' + cur_node + 's' + cur_scenario)
            dvar_pos[('g', cur_node, cur_scenario)] = len(dvar_name)-1
            dvar_obj_coef.append(0)
            dvar_lb.append(0)
            dvar_ub.append(nodes[('c', cur_node)] + nodes[('gen_up_ub', cur_node)])
            dvar_type.append('C')

            # unsuppled demand variable (w)
            if nodes[('d', cur_node)] > 0:
                dvar_name.append('w_' + cur_node + 's' + cur_scenario)
                dvar_pos[('w', cur_node, cur_scenario)] = len(dvar_name)-1
                dvar_obj_coef.append(scenarios[('s_pr', cur_node)]) # scenario relative weight
                dvar_lb.append(0)
                dvar_ub.append(nodes[('d', cur_node)])
                dvar_type.append('C')

            # phase angle (theta)
            dvar_name.append('theta_' + cur_node + 's' + cur_scenario)
            dvar_pos[('theta', cur_node, cur_scenario)] = len(dvar_name)-1
            dvar_obj_coef.append(0)
            dvar_lb.append(0)
            dvar_ub.append(360)
            dvar_type.append('C')

        # capacity upgrade of node (independent of scenario)
        dvar_name.append('c_' + cur_node)
        dvar_pos[('c', cur_node)] = len(dvar_name)-1
        dvar_obj_coef.append(0)
        dvar_lb.append(0)
        dvar_ub.append(nodes[('gen_up_ub', cur_node)])
        dvar_type.append('C')

        # establish backup capacity at node i
        dvar_name.append('Z_' + cur_node)
        dvar_pos[('Z', cur_node)] = len(dvar_name)-1
        dvar_obj_coef.append(0)
        dvar_lb.append(0)
        dvar_ub.append(1)
        dvar_type.append('B')

    # by edges
    all_edges = [(min(i[1],i[2]), max(i[1],i[2])) for i in edges.keys() if i[0] == 'c']
    for cur_edge in all_edges:
        edge_str = str(cur_edge).replace(', ', '_').replace("'", "").replace('(', '').replace(')','')
        for cur_scenario in all_scenarios:
            # define flow variabels
            dvar_name.append('f_' + edge_str + 's' + cur_scenario)
            dvar_pos[('f', cur_edge, cur_scenario)] = len(dvar_name)-1
            dvar_obj_coef.append(0)
            dvar_lb.append(-tot_demand)
            dvar_ub.append(tot_demand)
            dvar_type.append('C')

            # define failed edges
            dvar_name.append('F_' + edge_str + 's' + cur_scenario)
            dvar_pos[('F', cur_edge, cur_scenario)] = len(dvar_name)-1
            dvar_obj_coef.append(0)
            dvar_lb.append(0)
            dvar_ub.append(1)
            dvar_type.append('B')


        # define capacity upgrade constraints
        dvar_name.append('c_' + edge_str)
        dvar_pos[('c', cur_edge)] = len(dvar_name)-1
        dvar_obj_coef.append(0)
        dvar_lb.append(0)
        dvar_ub.append(tot_demand)
        dvar_type.append('C')



        # establish new edge (only if upgrade cost > 0 otherwise this edge already exists, no need to add variable)
        if cur_edge in [(i[1], i[2]) for i in edges.keys() if i[0] == 'H' and edges[i] > 0]:
            dvar_name.append('X_' + edge_str)
            dvar_pos[('X_', cur_edge)] = len(dvar_name)-1
            dvar_obj_coef.append(0)
            dvar_lb.append(0)
            dvar_ub.append(1)
            dvar_type.append('B')


    # initialize cplex object
    robust_opt = cplex.Cplex()
    robust_opt.objective.set_sense(robust_opt.objective.sense.maximize) # maximize supplied energy "=" minimize expected loss of load

    # building the decision variables within object
    robust_opt.variables.add(obj = dvar_obj_coef, lb = dvar_lb, ub = dvar_ub, types = dvar_type, names = dvar_name)

    # build constraints (all except for cascade inducing constraints)

    for cur_node in all_nodes:
        flow_lhs = []
        flow_lhs_coef = []
        flow_rhs = []
        assoc_edges = get_associated_edges(cur_node, all_edges)
        for scenario in all_scenarios:
            # Conservation of flow sum(f_ji)- sum(f_ij) + g_i - w_i = 0 (total incoming - outgoing + generated - supplied = 0)
            flow_lhs = [dvar_pos[('f', edge, scenario)] for edge in assoc_edges['in']] + [dvar_pos[('f', edge, scenario)] for edge in assoc_edges['out']] + \
                       [dvar_pos[('g', cur_node, scenario)]]
            flow_lhs_coef = [1 for edge in assoc_edges['in']] + [-1 for edge in assoc_edges['out']] + [1]
            if nodes[('d', cur_node)] > 0:
                # case this node (has demand)
                flow_lhs += [dvar_pos[('w', cur_node, scenario)]]
                flow_lhs_coef += [-1]
            robust_opt.linear_constraints.add(lin_expr = [[flow_lhs, flow_lhs_coef]], senses = "E", rhs = [0])

            for cur_edge in assoc_edges['out']:
                # using only outgoing edges incoming will be covered as "outgoing" at a different node
                # First set failed edges according to input data
                # DEBUG HERE 05/07/2017.
                if cur_edge in scenarios[('s', scenario)]:
                    init_failures = [dvar_pos[('F', cur_edge, scenario)]]
                    init_failures_coef = [1]
                    robust_opt.linear_constraints.add(lin_expr = [[init_failures, init_failures_coef]], senses = "E", rhs = [1])


                # Phase angle constraints -M*F_ij <= theta_i-theta_j-x_ij*f_ij <= M*F_ij
                # Less than equal side
                phase_lhs = [dvar_pos[('theta', cur_node, scenario)], dvar_pos[('theta', cur_edge[1], scenario)], dvar_pos[('f', cur_edge, scenario)], dvar_pos[('F', cur_edge, scenario)]]
                phase_lhs_coef = [1, -1, -edges[('x', ) + (cur_edge)], -bigM]
                robust_opt.linear_constraints.add(lin_expr = [[phase_lhs, phase_lhs_coef]], senses = "L", rhs = [0])
                # Greater than equal side
                phase_lhs = [dvar_pos[('theta', cur_node, scenario)], dvar_pos[('theta', cur_edge[1], scenario)], dvar_pos[('f', cur_edge, scenario)], dvar_pos[('F', cur_edge, scenario)]]
                phase_lhs_coef = [1, -1, -edges[('x', ) + (cur_edge)], bigM]
                robust_opt.linear_constraints.add(lin_expr = [[phase_lhs, phase_lhs_coef]], senses = "G", rhs = [0])

                # Phase angle for potential edges -M*X_ij <= theta_i-theta_j-x_ij*f_ij <= M*X_ij     *** notice that X is not dependant in scenario but theta and f do depend
                if cur_edge in [(i[1], i[2]) for i in edges.keys() if i[0] == 'H' and edges[i] > 0]:
                    # only run if edge has a fixed establishment cost parameter (H)
                    # Less than equal side
                    phase_lhs = [dvar_pos[('theta', cur_node, scenario)], dvar_pos[('theta', cur_edge[1], scenario)], dvar_pos[('f', cur_edge, scenario)], dvar_pos[('X_', cur_edge)]]
                    phase_lhs_coef = [1, -1, -edges[('x', ) + (cur_edge)], -bigM]
                    robust_opt.linear_constraints.add(lin_expr = [[phase_lhs, phase_lhs_coef]], senses = "L", rhs = [0])
                    # Greater than equal side
                    phase_lhs = [dvar_pos[('theta', cur_node, scenario)], dvar_pos[('theta', cur_edge[1], scenario)], dvar_pos[('f', cur_edge, scenario)], dvar_pos[('X_', cur_edge)]]
                    phase_lhs_coef = [1, -1, -edges[('x', ) + (cur_edge)], bigM]
                    robust_opt.linear_constraints.add(lin_expr = [[phase_lhs, phase_lhs_coef]], senses = "G", rhs = [0])

                    # Transmission capacity for potential edges -M*X_ij <= f_ij <= M*X_ij
                    # Less than equal side
                    disable_flow_lhs = [dvar_pos[('f', cur_edge, scenario)], dvar_pos[('X_', cur_edge)]]
                    disable_flow_lhs_coef = [1, -bigM]
                    robust_opt.linear_constraints.add(lin_expr = [[disable_flow_lhs, disable_flow_lhs_coef]], senses = "L", rhs = [0])
                    # Greater than equal side
                    disable_flow_lhs = [dvar_pos[('f', cur_edge, scenario)], dvar_pos[('X_', cur_edge)]]
                    disable_flow_lhs_coef = [1, bigM]
                    robust_opt.linear_constraints.add(lin_expr = [[disable_flow_lhs, disable_flow_lhs_coef]], senses = "G", rhs = [0])

                # Don't use failed edges -M*(1-F_ij) <= f_ij <= M*(1-F_ij)
                # Less than equal side
                fail_lhs = [dvar_pos[('f', cur_edge, scenario)], dvar_pos[('F', cur_edge, scenario)]]
                fail_lhs_coef = [1, bigM]
                robust_opt.linear_constraints.add(lin_expr = [[fail_lhs, fail_lhs_coef]], senses = "L", rhs = [bigM])

                # Greater than equal side
                fail_lhs = [dvar_pos[('f', cur_edge, scenario)], dvar_pos[('F', cur_edge, scenario)]]
                fail_lhs_coef = [1, -bigM]
                robust_opt.linear_constraints.add(lin_expr = [[fail_lhs, fail_lhs_coef]], senses = "G", rhs = [-bigM])

            # Finished iterating over edges, continuing to iterate over scenarios, and nodes
            # Generation capacity g_i <= c0_i + cg_i
            gen_cap_lhs = [dvar_pos[('g', cur_node, scenario)], dvar_pos[('c', cur_node)]]
            gen_cap_lhs_coef = [1, -1]
            robust_opt.linear_constraints.add(lin_expr = [[gen_cap_lhs, gen_cap_lhs_coef]], senses = "L", rhs = [nodes[('c', cur_node)]])
            # Generation capacity g_i <= M*Z_i
            gen_cap_lhs = [dvar_pos[('g', cur_node, scenario)], dvar_pos[('Z', cur_node)]]
            gen_cap_lhs_coef = [1, -bigM]
            robust_opt.linear_constraints.add(lin_expr = [[gen_cap_lhs, gen_cap_lhs_coef]], senses = "L", rhs = [0])

    # Last constraint - budget
    # Investment cost constraint sum(h_ij*cl_ij) + sum(h_i*cg_i + H_i*Z_i) + sum(H_ij*X_ij) <= C
    budget_lhs = [dvar_pos[('c', cur_edge)] for cur_edge in all_edges] + [dvar_pos[('c', cur_node)] for cur_node in all_nodes] + \
                 [dvar_pos[('Z', cur_node)] for cur_node in all_nodes if ('H', cur_node) in nodes.keys()] + \
                 [dvar_pos[('X_', (i[1], i[2]))] for i in edges.keys() if i[0] == 'H' and edges[i] > 0]
    budget_lhs_coef = [edges[('h',) + cur_edge] for cur_edge in all_edges] + [nodes[('h', cur_node)] for cur_node in all_nodes] + \
                 [nodes[('H',cur_node)] for cur_node in all_nodes if ('H',cur_node) in nodes.keys()] + \
                 [edges[('H',)+(i[1], i[2])] for i in edges.keys() if i[0] == 'H' and edges[i] > 0]
    robust_opt.linear_constraints.add(lin_expr = [[budget_lhs, budget_lhs_coef]], senses = "L", rhs = [params['C']])

    # Finished defining the main problem - returning cplex object:
    return {'cplex_problem': robust_opt, 'cplex_location_dictionary': dvar_pos}



# Build lazycallbacks
# This class is called when integer-feasible solution candidate has been identified
# at one of the B&B tree nodes.
# The function checks if given the installment decisions of X, C, and Z at each of the scenarios,
# if the failures are consistent with the failures in the solution.
# If there are inconsistencies then the violated constraints are added

class MyLazy(LazyConstraintCallback):
    def __call__(self): # read current integer solution and add violated valid inequality.
        #print "I'm in the lazy call back!"
        global dvar_pos # position variable is global
        global dvar_name # variable names for debugging
        global epsilon
        global bigM

        epsilon2 = 1e-5

        all_edges = [(min(i[1],i[2]), max(i[1],i[2])) for i in edges.keys() if i[0] == 'c']

        current_solution = self.get_values()

        timestampstr = strftime('%d-%m-%Y %H-%M-%S-', gmtime()) + str(round(clock(), 3)) + ' - '
        write_names_values(current_solution, dvar_name, 'c:/temp/grid_cascade_output/callback debug/' + timestampstr + 'current_callback_solution.csv')

        cfe_constraints = build_cfe_constraints(current_solution)

        # Adding lazy constraints one by one - currently don't know how to do this in batch
        for i in xrange(len(cfe_constraints['positions'])):
            curr_cut_debug = [str(cfe_constraints['coefficients'][i][j]) + '*' + dvar_name[cfe_constraints['positions'][i][j]] for j in xrange(len(cfe_constraints['positions'][i]))]
            print timestampstr, "Adding cut (failed but shouldn't)", curr_cut_debug, "<=", cfe_constraints['rhs'][i]
            self.add(constraint = cplex.SparsePair(cfe_constraints['positions'][i], cfe_constraints['coef'][i]), sense = "L", rhs = cfe_constraints['rhs'][i])



def build_cfe_constraints(current_solution):
    """
    The function uses input from the cfe simulation (simulation_failures) and the grid, to build
    a set of constraints which will make sure that simulation results and constraints are aligned
    This is the main function which generates the lazy callbacks.
    The function returns the constraints as a dictionary
    {'positions': [[],[],[],...], 'coefficients': [[],[],[],...], 'rhs': [a,b,c,...]}

    """

    global epsilon
    global dvar_name
    global dvar_pos

    epsilon2 = 1e-5

    # initialize position and coefficient lists
    positions_list = []
    coefficient_list = []
    rhs_list = []


    # build new grid based on solution and return the inconsistent failures
    simulation_failures = compute_cascade.compute_failures(nodes, edges, scenarios, current_solution, dvar_pos)

    # set the X variables
    X_established = [cur_pos for xkey, cur_pos in dvar_pos.iteritems() if xkey[0] == 'X_' and current_solution[dvar_pos[xkey]] > 0.999]
    X_not_established = [cur_pos for xkey, cur_pos in dvar_pos.iteritems() if xkey[0] == 'X_' and current_solution[dvar_pos[xkey]] < 0.001]
    X_established_coef = [1]*len(X_established)
    X_not_established_coef = [-1]*len(X_not_established)

    for cur_scenario, failure_dict in simulation_failures.iteritems():
        cur_cascade_iter = 1
        prev_failures = [] # accumulate previous failures for use within the constraints
        while failure_dict['F'][cur_cascade_iter] != []:
            # as long as failure_dict['F'][step] contains failures - continue to add constraints
            for curr_failed_edge in failure_dict['F'][cur_cascade_iter]: # <- convert later on to list comprehention
                tmp_position = X_established + X_not_established + [dvar_pos[('F',failed_edge, cur_scenario)] for failed_edge in prev_failures] + [dvar_pos[('c', curr_failed_edge)]] + [dvar_pos[('F', curr_failed_edge, cur_scenario)]]
                tmp_coeff = [1]*len(X_established) + [-1]*len(X_not_established) + [1]*len(prev_failures) + [-epsilon] + [-1]
                temp_rhs = sum([1]*len(X_established)) + sum([1]*len(prev_failures)) - epsilon*abs(current_solution[dvar_pos[('f', curr_failed_edge, cur_scenario)]]) - epsilon2 + epsilon*edges[('c',) + curr_failed_edge]
                positions_list += [tmp_position]
                coefficient_list += [tmp_coeff]
                rhs_list += [temp_rhs]
            prev_failures += failure_dict['F'][cur_cascade_iter] # add to previous failures
            cur_cascade_iter += 1

    cfe_constraints = {'positions': positions_list, 'coefficients': coefficient_list, 'rhs': rhs_list}

    return(cfe_constraints)




def get_associated_edges(node, all_edges):
    associated_dic = dict()
    all_incoming = [(i[0], i[1]) for i in all_edges if i[1] == node]
    all_outgoing = [(i[0], i[1]) for i in all_edges if i[0] == node]
    associated_dic['in'] = all_incoming
    associated_dic['out'] = all_outgoing
    return(associated_dic)


def sign_n0(number):
    if number >=0:
        return(1)
    else:
        return(-1)