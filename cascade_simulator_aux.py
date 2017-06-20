# -*- coding: utf-8 -*-
"""
Created on Wed Jun 08 10:58:24 2016
Cascade simulator auxiliary functions
@author: Adi Sarid
"""

import numpy as np # numpy for matrix calculations
import networkx as nx # for using graph representation
import cplex # using cplex engine to solve flow problem
import sys
import csv



def write_sim_steps(filename, failed_edges, flow_per_stage):
    '''
    Given file name, variable names and values, write the solution to a csv file
    '''
    flow_write = [['f'] + [j[0], j[1], i, j[2]] for i in flow_per_stage.keys() for j in flow_per_stage[i]]
    overflow_fails = [['O'] + list(j) + [i, 1] for i in failed_edges.keys() for j in failed_edges[i]]
    name_val = flow_write + overflow_fails
    with open(filename, 'wb') as csvfile:
        solutionwriter = csv.writer(csvfile, delimiter = ',')
        solutionwriter.writerow(['type', 'par1', 'par2', 'par3', 'value'])
        solutionwriter.writerows(name_val)



def update_grid(G, failed_edges):
    """
    Function to update the existing graph by omitting failed_edges from it and re-computing demand and generation in each component.
    Modifies the graph G (a networkx object, with custom fields 'demand', 'gen_cap' and 'generated')
    """
    # First step, go over failed edges and omit them from G
    for edge in failed_edges:
        G.remove_edge(edge[0], edge[1])
    # Now adjust the total demand (supply) to equal the total supply (demand) within each connected component of G
    graphs = list(nx.connected_component_subgraphs(G))
    #print 'Total number of components is', len(graphs)
    # Here change this to an optimization problem for the CPLEX engine, instead of the current method
    for component in graphs:
        # computing the total demand and total generation capacity using list comprehention
        tot_demand = sum([component.node[i]['original_demand'] for i in component.node.keys()])
        tot_gen_cap = sum([component.node[i]['gen_cap'] for i in component.node.keys()])
        tot_generated = sum([component.node[i]['generated'] for i in component.node.keys()])
        #print 'Original data for component: tot_demand=', tot_demand, 'tot_cap=', tot_gen_cap, 'tot_generated=', tot_generated
        if tot_demand > tot_gen_cap:
            # in this case, demand in the connected component is above the capacity in the component
            # need to shed some of the demand.
            shedding_factor = tot_gen_cap/tot_demand
            for node in component.node.keys():
                G.node[node]['demand'] *= shedding_factor # lower demand so that total demand in component does not surpass the capacity in the component
                G.node[node]['generated'] = G.node[node]['gen_cap'] # generating maximum in order to reach capacity

        # case demand is lower than total generation capacity
        elif tot_demand < tot_generated:
            # we are generating too much and need to curtail some of the generation
            gen_factor = tot_demand/tot_generated
            for node in component.node.keys():
                G.node[node]['generated'] *= gen_factor
                #if G.node[node]['generated'] > G.node[node]['gen_cap']:
                    #print 'Opps! error here(2), generation increased capacit. Check me'
                    #print 'node', node, 'gen_factor', gen_factor
        elif tot_demand > tot_generated:
            # we are not generating enough, and we are able to increase demand (it is not bound to get us above capacity, since tot_demand < tot_gen_cap)
            gen_factor = tot_demand/tot_gen_cap
            for node in component.node.keys():
                G.node[node]['generated'] = G.node[node]['gen_cap']*gen_factor


def cfe(G, init_fail_edges, write_solution_file = False):
    """
    Simulates a cascade failure evolution (the CFE - algorithm 1 in paper)
    Input is an initial fail of edges (F),
    The graphic representation G (as a networkx object)
    and dicts of capacity and demand.
    Returns final state of the grid after cascading failure evolution is complete.
    """

    # initialize the list of failed edges at each iteration
    F = dict()
    F[0] = init_fail_edges

    # initialize flow dictionary for high resolution of solution (output of flow at each step)
    flowsteps = dict()
    # initialize flow
    #current_flow = compute_flow(G)
    # loop
    i = 0
    while F[i]:  # list of edges failed in iteration i is not empty
        #print i # for debugging purposes
        lpfilename = "c:/temp/grid_cascade_output/lp_form/single_type1_step" + str(i) + ".lp" # For debugging purpuses I added writing the lp files. Disable later on.
        tmp_grid_flow_update = grid_flow_update(G, F[i], lpfilename, False, True) # true for returning the cplex object - will enable us to retrive flow variabels
        F[i+1] =  tmp_grid_flow_update['failed_edges'] # lines 3-5 in algorithm - find new set of edge failures. Modified method for flow solution - using cplex engine.
        flowsteps[i] = tmp_grid_flow_update['flow_list']
        i += 1

    # Upon completion of simulation, write solution to file if requested
    if write_solution_file:
        write_sim_steps(write_solution_file, F, flowsteps)

    return({'F': F, 't':i, 'flowsteps': flowsteps})


def grid_flow_update(G, failed_edges = [], write_lp = False, return_cplex_object = False, return_flow_list = False):
    """
    The following function modifies G after failure of edges in failed_edges,
    After which the function re-computes the flows, demand, and supply using CPLEX engine
    Eventually, the function returns a set of new failed edges.
    This function replaces the previous update_grid and compute_flow
    Adi, 31/07/2016.
    """

    # First step, go over failed edges and omit them from G
    G.remove_edges_from(failed_edges)

    # Initialize decision variables (demand, supply, theta, and flow)
    dvar_name = [] # name of variable
    dvar_type = [] # type of variable
    dvar_obj_coef = [] # objective function coefficient
    dvar_lb = [] # lower bound
    dvar_ub = [] # upper bound
    dvar_pos = dict() # position of variable
    counter = 0

    # define flow variables (continuous non-negative)
    for curr_edge in G.edges():
        dvar_name.append('f' + str(curr_edge))
        dvar_name.append('f' + str(curr_edge[::-1])) # the directed edge (other way around)
        dvar_lb += [0,0]
        dvar_ub += [G.edge[curr_edge[0]][curr_edge[1]]['capacity']*10**5 + 1e5]*2 # CHANGE HERE! - If you want to enable/disable capacities for edges. To disable capacities multiplie curr_edge[1]]['capacity'] by a factor, i.e., *10**3
        dvar_type += ['C', 'C']
        dvar_obj_coef += [0, 0]
        dvar_pos[('f', curr_edge)] = counter
        dvar_pos[('f', curr_edge[::-1])] = counter + 1
        counter += 2

    # define unsupplied demand, generation, and theta variables (continuous, non-negative)
    for curr_node in G.nodes():
        # unsupplied demand variable
        dvar_name.append('ud' + str(curr_node))
        dvar_obj_coef += [G.node[curr_node]['un_sup_cost']]
        dvar_type += 'C'
        dvar_pos[('ud', curr_node)] = counter
        dvar_lb += [0]
        dvar_ub += [10**4] # [G.node[curr_node]['original_demand']] # no need for an unsupplied demand upper bound - also made some problems
        counter += 1
        # theta variable
        dvar_name.append('theta' + str(curr_node))
        dvar_obj_coef += [0]
        dvar_type += 'C'
        dvar_pos[('theta', curr_node)] = counter
        dvar_lb += [-10**6] # no need for a theta lower bound
        dvar_ub += [10**6] # no need for a theta upper bound
        counter += 1
        # generation variables (continouous non-negative)
        if G.node[curr_node]['gen_cap'] > 0:
            dvar_name.append('g' + str(curr_node))
            dvar_obj_coef += [G.node[curr_node]['gen_cost']]
            dvar_type += 'C'
            dvar_pos[('g', curr_node)] = counter
            dvar_lb += [0]
            dvar_ub += [G.node[curr_node]['gen_cap']]
            counter += 1

    # Initialize cplex engine
    find_flow = cplex.Cplex() # create cplex instance
    find_flow.objective.set_sense(find_flow.objective.sense.minimize) # minimize costs
    find_flow.variables.add(obj = dvar_obj_coef, lb = dvar_lb, ub = dvar_ub, types = dvar_type, names = dvar_name) # define variables and objective function

    # Add theta-flow constraints: theta_i-theta_j-x_{ij}f_{ij} = 0
    for curr_edge in G.edges():
        theta_lhs = [dvar_pos[('theta', curr_edge[0])], dvar_pos[('theta', curr_edge[1])], dvar_pos[('f', curr_edge)], dvar_pos[('f', curr_edge[::-1])]]
        theta_lhs_coef = [1, -1, -G.edge[curr_edge[0]][curr_edge[1]]['susceptance'], G.edge[curr_edge[0]][curr_edge[1]]['susceptance']]
        find_flow.linear_constraints.add(lin_expr = [[theta_lhs, theta_lhs_coef]], senses = "E", rhs = [0])

    # Add general flow constraints
    for node in G.nodes():
        assoc_edges = get_associated_edges(node, G.edges())
        # formation is: incoming edges - outgoing edges + generation
        flow_lhs = [dvar_pos[('f', edge)] for edge in assoc_edges['in']] + [dvar_pos[('f', edge)] for edge in assoc_edges['out']]
        flow_lhs_coef = [1 for edge in assoc_edges['in']] + [-1 for edge in assoc_edges['out']]
        flow_lhs += [dvar_pos[('ud', node)]]
        flow_lhs_coef += [1]
        if G.node[node]['gen_cap'] > 0:
            flow_lhs += [dvar_pos[('g', node)]]
            flow_lhs_coef += [1]
        find_flow.linear_constraints.add(lin_expr = [[flow_lhs, flow_lhs_coef]], senses = "E", rhs = [G.node[node]['original_demand']])


    # Suppress cplex messages
    find_flow.set_log_stream(None)
    find_flow.set_error_stream(None)
    find_flow.set_warning_stream(None)
    find_flow.set_results_stream(None) #Enabling by argument as file name, i.e., set_results_stream('results_stream.txt')

    # Solve problem
    find_flow.set_problem_type(find_flow.problem_type.LP) # This is a regular linear problem, avoid code 1017 error.
    find_flow.solve()

    # Check to make sure that an optimal solution has been reached or exit outherwise
    if find_flow.solution.get_status() != 1:
        find_flow.write('problem_infeasible.lp')
        sys.exit('Error: no optimal solution found while trying to solve flow problem. Writing into: problem_infeasible.lp')

    find_flow_vars = find_flow.solution.get_values()
    # Set the generation and demand
    for curr_node in G.nodes():
        G.node[curr_node]['demand'] = G.node[curr_node]['original_demand'] - find_flow_vars[dvar_pos[('ud', curr_node)]]
        if G.node[curr_node]['gen_cap'] > 0:
            G.node[curr_node]['generated'] = find_flow_vars[dvar_pos[('g', curr_node)]]

    # Set the failed edges
    new_failed_edges = []
    flow_list = []
    for curr_edge in G.edges():
        if (find_flow_vars[dvar_pos[('f', curr_edge)]] > G.edge[curr_edge[0]][curr_edge[1]]['capacity']) or \
        (find_flow_vars[dvar_pos[('f', curr_edge[::-1])]] > G.edge[curr_edge[0]][curr_edge[1]]['capacity']):
            new_failed_edges += [curr_edge]
        flow_list += [[curr_edge[0], curr_edge[1], find_flow_vars[dvar_pos[('f', curr_edge)]]]]
        flow_list += [[curr_edge[1], curr_edge[0], find_flow_vars[dvar_pos[('f', curr_edge[::-1])]]]]

    # print 'failed_edges:', new_failed_edges, '(*should always be an empty set)'
    # just in case you want an lp file - for debugging purposes.

    if write_lp:
        find_flow.write(write_lp)

    # Always return the failed edges
    return_object = {'failed_edges': new_failed_edges}
    # Should I return the CPLEX object?
    if return_cplex_object:
        return_object['cplex_object'] = find_flow
    # Should I return a list with the flow variables
    if return_flow_list:
        flow_list = [flow_list[i] for i in range(len(flow_list)) if flow_list[i][2] > 0.0001] # filter to only positive flow
        flow_dict = {tuple(i[0:2]) : i[2] for i in flow_list}
        return_object['flow_list'] = flow_list # I'm still leaving this for backwards compatability with function cfe. Consider revising later on (modify function cfe)
        return_object['flow_dict'] = flow_dict

    # Return output and exit function
    return(return_object)



def get_associated_edges(node, edges):
    '''
    Get the associated edges leaving and coming into a specified (input) node
    Output is a dictionary with 'in' being the set of all incoming edges and 'out' the set of all outgoing edges
    '''
    out_edge = [key for key in edges if node == key[0]] # use the dictionary to identify outgoing edges
    in_edge = [key for key in edges if node == key[1]] # use the dictionary to identify incoming edges
    all_out = out_edge + [edge[::-1] for edge in in_edge] # all outgoing (needed since dictionary keys are always ordered tuples)
    all_in = in_edge + [edge[::-1] for edge in out_edge] # all incoming
    out_dict = {'out': all_out, 'in': all_in}
    return(out_dict)



# I found myself using n choose k a few times to compute the number of different combinations so here it is:
from operator import mul    # or mul=lambda x,y:x*y
from fractions import Fraction

def nCk(n,k):
  return int( reduce(mul, (Fraction(n-i, i+1) for i in range(k)), 1) )