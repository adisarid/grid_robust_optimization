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
    G.remove_edges_from([edge for edge in failed_edges])

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
        lpfilename = False #"c:/temp/grid_cascade_output/lp_form/single_type1_step" + str(i) + ".lp" # For debugging purpuses I added writing the lp files. Disable later on.
        tmp_grid_flow_update = grid_flow_update(G, F[i], lpfilename, False, True) # true for returning the cplex object - will enable us to retrive flow variabels
        F[i+1] =  tmp_grid_flow_update['failed_edges'] # lines 3-5 in algorithm - find new set of edge failures. Modified method for flow solution - using cplex engine.
        flowsteps[i] = tmp_grid_flow_update['flow_list']
        i += 1

    # Upon completion of simulation, write solution to file if requested
    if write_solution_file:
        write_sim_steps(write_solution_file, F, flowsteps)

    return({'F': F, 't':i, 'flowsteps': flowsteps})


def grid_flow_update(G, failed_edges = [], write_lp = False, return_cplex_object = False):
    """
    The following function modifies G after failure of edges in failed_edges,
    After which the function re-computes the flows, demand, and supply using CPLEX engine
    Eventually, the function returns a set of new failed edges.
    Adi, 21/06/2017.
    """

    # First step, go over failed edges and omit them from G, rebalance components with demand and generation
    update_grid(G, init_fail_edges) # Each component of G will balance demand and generation capacities after this line

    # Initialize cplex internal flow problem
    find_flow = cplex.Cplex() # create cplex instance
    find_flow.objective.set_sense(find_flow.objective.sense.minimize) # doesn't matter

    # Initialize decision variables (demand, supply, theta, and flow)
    dvar_pos_flow = dict() # position of variable
    counter = 0

    # define flow variables (continuous unbounded)
    obj = [0]*len(G.edges())
    types = 'C'*len(G.edges())
    lb = [-1e20]*len(G.edges())
    ub = [1e20]*len(G.edges())
    names = ['f' + str(curr_edge) for curr_edge in sorted_edges(G.edges())]
    dvar_pos_flow.update({('f', tuple(sorted(G.edges()[i]))):i+counter for i in range(len(G.edges()))})
    find_flow.variables.add(obj = obj, types = types, lb = lb, ub = ub, names = names)
    counter += len(dvar_pos_flow)

    # define theta variables (continouous unbounded)
    names = ['theta' + str(curr_node) for curr_node in G.nodes()]
    num_nodes = len(G.nodes())
    dvar_pos_flow.update({('theta', G.nodes()[i]):i+counter for i in range(len(G.nodes()))})
    find_flow.variables.add(obj = [0]*num_nodes, types = 'C'*num_nodes, lb = [-1e20]*num_nodes, ub = [1e20]*num_nodes, names = names)

    # Add phase angle (theta) flow constraints: theta_i-theta_j-x_{ij}f_{ij} = 0
    phase_constraints = [[[dvar_pos_flow[('theta', curr_edge[0])], dvar_pos_flow[('theta', curr_edge[1])], dvar_pos_flow[('f', curr_edge)]], [1.0, -1.0, -G.edge[curr_edge[0]][curr_edge[1]]['susceptance']]] for curr_edge in sorted_edges(G.edges())]
    find_flow.linear_constraints.add(lin_expr = phase_constraints, senses = "E"*len(phase_constraints), rhs = [0]*len(phase_constraints))

    # Add general flow constraints. formation is: incoming edges - outgoing edges + generation
    flow_conservation = [[[dvar_pos_flow[('f', edge)] for edge in get_associated_edges(node, G.edges())['in']] + [dvar_pos_flow[('f', edge)] for edge in get_associated_edges(node, G.edges())['out']], \
                          [1 for edge in get_associated_edges(node, G.edges())['in']] + [-1 for edge in get_associated_edges(node, G.edges())['out']]] for node in G.nodes()]
    flow_conservation_rhs = [G.node[curr_node]['demand']-G.node[curr_node]['generated'] for curr_node in G.nodes()]
    # clean up a bit for "empty" constraints
    flow_conservation_rhs = [flow_conservation_rhs[i] for i in range(len(flow_conservation_rhs)) if flow_conservation[i] != [[],[]]]
    flow_conservation = [const for const in flow_conservation if const != [[],[]]]
    find_flow.linear_constraints.add(lin_expr=flow_conservation, senses = "E"*len(flow_conservation), rhs = flow_conservation_rhs)

    # Suppress cplex messages
    find_flow.set_log_stream(None)
    find_flow.set_error_stream(None)
    find_flow.set_warning_stream(None)
    find_flow.set_results_stream(None) #Enabling by argument as file name, i.e., set_results_stream('results_stream.txt')

    # Solve problem
    find_flow.set_problem_type(find_flow.problem_type.LP) # This is a regular linear problem, avoid code 1017 error.
    find_flow.solve()

    # Check to make sure that an optimal solution has been reached or exit otherwise
    if find_flow.solution.get_status() != 1:
        find_flow.write('problem_infeasible.lp')
        sys.exit('Error: no optimal solution found while trying to solve flow problem. Writing into: problem_infeasible.lp')

    find_flow_vars = find_flow.solution.get_values()

    # Set the failed edges
    new_failed_edges = [edge for edge in sorted_edges(G.edges()) if abs(find_flow_vars[dvar_pos_flow[('f', edge)]]) > G.edge[edge[0]][edge[1]]['capacity']]

    # just in case you want an lp file - for debugging purposes.

    if write_lp:
        find_flow.write(write_lp)

    # Always return the failed edges
    return_object = {'failed_edges': new_failed_edges}
    # Should I return the CPLEX object?
    if return_cplex_object:
        return_object['cplex_object'] = find_flow

    # Return output and exit function
    return(return_object)



def get_associated_edges(node, edges):
    '''
    Get the associated edges leaving and coming into a specified (input) node
    Output is a dictionary with 'in' being the set of all incoming edges and 'out' the set of all outgoing edges
    '''
    edges_ordered = [tuple(sorted(edge)) for edge in edges]
    out_edge = [key for key in edges_ordered if node == key[0]] # use the dictionary to identify outgoing edges
    in_edge = [key for key in edges_ordered if node == key[1]] # use the dictionary to identify incoming edges
    out_dict = {'out': out_edge, 'in': in_edge}
    return(out_dict)


def sorted_edges(edges_list):
    """
    Gets a list of tuples (unsorted) and returns the same list of tuples only
    tuple pairs are sorted, i.e.:
    sorted_edges([(1,2), (10,6)]) = [(1,2), (6,10)]
    """
    sorted_edges_list = [tuple(sorted(i)) for i in edges_list]
    return(sorted_edges_list)



# I found myself using n choose k a few times to compute the number of different combinations so here it is:
from operator import mul    # or mul=lambda x,y:x*y
from fractions import Fraction

def nCk(n,k):
  return int( reduce(mul, (Fraction(n-i, i+1) for i in range(k)), 1) )