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

def build_cplex_problem(nodes, edges, scenarios, params):

    # initialize variable vector with variable name
    dvar_name = []
    dvar_pos = dict() # I like having both the name as a string and the location in vector as a dictionary
    dvar_obj_coef = []
    dvar_lb = []
    dvar_ub = []
    dvar_type = []

    # epsilon
    epsilon = 1e-10 # depending on grid size, this constant can take various values 1e-10 is probably small enough for any practical situation
    bigM = 1.0/epsilon
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
                dvar_obj_coef.append(-scenarios[('s_pr', cur_node)]) # scenario relative weight
                dvar_lb.append(0)
                dvar_ub.append(nodes[('d', cur_node)])
                dvar_type.append('C')

            # phase angle (theta)
            dvar_name.append('theta' + cur_node + 's' + cur_scenario)
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
    robust_opt.objective.set_sense(robust_opt.objective.sense.minimize) # minimize expected loss of load

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
            robust_opt.linear_constraints.add(lin_expr = [[gen_cap_lhs, gen_cap_lhs_coef]], senses = "L", rhs = [nodes[('c', cur_node)]])

    # Last constraint - budget
    # Investment cost constraint sum(h_ij*cl_ij) + sum(h_i*cg_i + H_i*Z_i) + sum(H_ij*X_ij) <= C
    budget_lhs = [dvar_pos[('c', cur_edge)] for cur_edge in all_edges] + [dvar_pos[('c', cur_node)] for cur_node in all_nodes] + \
                 [dvar_pos[('Z', cur_node)] for cur_node in all_nodes if ('H', cur_node) in nodes.keys()] + \
                 [dvar_pos[('X_', (i[1], i[2]))] for i in edges.keys() if i[0] == 'H' and edges[i] > 0]
    budget_lhs_coef = [edges[('h',) + cur_edge] for cur_edge in all_edges] + [nodes[('h', cur_node)] for cur_node in all_nodes] + \
                 [nodes[('H',cur_node)] for cur_node in all_nodes if ('H',cur_node) in nodes.keys()] + \
                 [edges[('H',)+(i[1], i[2])] for i in edges.keys() if i[0] == 'H' and edges[i] > 0]
    robust_opt.linear_constraints.add(lin_expr = [[budget_lhs, budget_lhs_coef]], senses = "L", rhs = [params['C']])








    return robust_opt





# Build lazycallbacks
# This class is called when integer-feasible solution candidate has been identified
# at one of the B&B tree nodes.
##class MyLazy(LazyConstraintCallback):
##    # global var_names # TEMPORARY ADDED FOR DEBUGGING! DELETE LATER
##    def __call__(self): # read current integer solution and add violated valid inequality.
##        cur_row = []
##        sol1 = self.get_values()
##        cycle1 = GetCycle(sol1)
##        #print "***** Found cycle:", cycle1, "*****"
##        notincycle = [a for a in range(num_nodes) if (a not in cycle1)]
##        if len(cycle1) < num_nodes: # case we do have a cycle smaller than the entire graph
##            for i in cycle1:
##                for j in notincycle:
##                    cur_row.append(mapij(i,j))
##            cur_coef = [1]*len(cur_row)
##            # here we add the constraint:
##            #print "***** Trying to add...: *****"
##            #adding = []
##            #for a in cur_row:
##            #    adding.append(var_names[a])
##            #print adding
##            self.add(constraint = [cur_row, cur_coef], sense = "G", rhs = 1) #cplex.SparsePair(ind=cur_row, val=cur_coef)
##            #print "***** Successfully added *****"
##        else:
##            pass


def get_associated_edges(node, all_edges):
    associated_dic = dict()
    all_incoming = [(i[0], i[1]) for i in all_edges if i[1] == node]
    all_outgoing = [(i[0], i[1]) for i in all_edges if i[0] == node]
    associated_dic['in'] = all_incoming
    associated_dic['out'] = all_outgoing
    return(associated_dic)
