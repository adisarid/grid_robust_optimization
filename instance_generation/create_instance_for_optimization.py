# -*- coding: utf-8 -*-
"""
Created on Tue Sep 20 13:05:47 2016

Creates a graph for cascade simulation tests

@author: Adi Sarid
"""

import networkx as nx
import sys
import csv # for reading the AC initial solution
import random
import math # for rounding up using ceil

# read instance files
import case24_ieee_rts as instance24
import case30 as instance30
import case39 as instance39
import case57 as instance57
import case118 as instance118
import case300 as instance300

# the following parameters control the size of the problem
total_edges_to_add_prc = 0.2 # proportion of newely tested edges (for establishment)
num_iters = 10 # generate up to num_iters failure scenarios

def main_program():
    run_grids = ['instance24', 'instance30', 'instance39', 'instance57', 'instance118', 'instance300']

    for current_instance in run_grids:
        # first, create the grid as a networkx object
        G = create_grid(current_instance)
        # export nodes and edges
        export_raw_csv_edges(G, '../' + current_instance + '/grid_edges.csv')
        export_raw_csv_nodes(G, '../' + current_instance + '/grid_nodes.csv')
        # export scenarios (two files - probabilities and failures)
        export_scenarios(G, '../' + current_instance + '/')
        # export budget constraint parameter
        export_params(G, '../' + current_instance + '/additional_params.csv')


def export_raw_csv_edges(G, filename):
    global total_edges_to_add_prc
    header_row = ['node1', 'node2', 'capacity', 'reactance', 'cost_fixed', 'cost_linear']
    content_list = [[edge[0], edge[1], G.edges[edge]['capacity'], G.edges[edge]['susceptance'], 0.0, 0.1] for edge in G.edges()] # existing edges
    # randomize new edges:
    random.seed(0)
    new_edges_to_add = [random.sample(G.nodes.keys(), 2) + [0, 1, 1.0, 0.1]
                        for i in range(int(math.ceil(G.number_of_edges()*total_edges_to_add_prc)))]
                        # node1, node2, capacity=0, suscenptance=1, fixed cost = 1, variable cost = 0.1
    # make sure that these are not repeating (old) edges in the new edges' list
    new_edges_to_add = [i for i in new_edges_to_add if not (i[0], i[1]) in G.edges()]
    data_export = [header_row] + content_list + new_edges_to_add
    with open(filename, 'wb') as fd:
        instance_writer = csv.writer(fd)
        instance_writer.writerows(data_export)



def export_raw_csv_nodes(G, filename):
    header_row = ['node','demand','gen_capacity','gen_upgrade_ub','gen_upgrade_cost_fixed','gen_upgrade_cost_linear']
    content_list = [[node, G.node[node]['demand'], G.node[node]['gen_cap'],
                     0, 0, 0] for node in G.nodes()] # node generation upgrade options are currently deactivated
    random.seed(0)
    data_export = [header_row] + content_list
    with open(filename, 'wb') as fd:
        instance_writer = csv.writer(fd)
        instance_writer.writerows(data_export)

def export_scenarios(G, directory):
    # Create scenarios by randomizing failing edges from G (for simplicity, only existing edges are considered)
    prc_fail = 0.1
    global num_iters
    random.seed(0)
    tabu_list_scenarios = [] # defined to avoid repeating scenarios
    internal_counter = 0
    while (internal_counter < num_iters):
        init_omit_num = random.randint(1, int(
            prc_fail * G.number_of_edges()))  # Set number of edges to fail in current batch under current instance
        tmp_rand = random.sample(G.edges(), init_omit_num)
        # make sure current starting conditions were not tested so far
        # WARNING: the counter increases only when new option is found.
        # in small instances * small choice of failures this might lead to an infinite loop
        # Also check that this scenario has an initial flow solution, i.e.,
        # the demand does not exceed generation capacity in each component
        omittedG = G.copy()
        omittedG.remove_edges_from(tmp_rand)
        component_wise_demand = [sum([omittedG.node[node_i]['demand'] for node_i in subGr]) <
                          sum([omittedG.node[node_i]['gen_cap'] for node_i in subGr])
                          for subGr in nx.connected_components(omittedG)]
        if not tmp_rand in tabu_list_scenarios and all(component_wise_demand):
            internal_counter += 1
            tabu_list_scenarios += [
                tmp_rand]  # update the tabu list to include the current iteration (represented as a tuple)
    # export scenario probabilities
    failure_probabilities = [[i, 1.0/len(tabu_list_scenarios)] for i in range(len(tabu_list_scenarios))]
    with open(directory + 'scenario_probabilities.csv', 'wb') as fd:
        instance_writer = csv.writer(fd)
        instance_writer.writerow(['scenario', 'probability'])
        instance_writer.writerows(failure_probabilities)
    # export scenario description
    header_failures = ['scenario', 'node1', 'node2']
    content_failures = [[cur_scenario]+list(cur_fail) for cur_scenario in range(len(tabu_list_scenarios)) for cur_fail in tabu_list_scenarios[cur_scenario]]
    with open(directory + 'scenario_failures.csv', 'wb') as fd:
        instance_writer = csv.writer(fd)
        instance_writer.writerow(header_failures)
        instance_writer.writerows(content_failures)

def export_params(G, filename):
    # Create parameters file (containing the budget constraint)
    # Each new edge costs 1 and capacity unit costs 0.1.
    # Lets take the budget constraint to be 10%*#num existing edges + 10% total edges capacity
    total_edges = G.number_of_edges()
    total_capacity = sum([G.edges[cur_edge]['capacity'] for cur_edge in G.edges])
    with open(filename, 'wb') as fd:
        instance_writer = csv.writer(fd)
        instance_writer.writerow(['param_name', 'param_value'])
        instance_writer.writerow(['C', (total_edges+0.1*total_capacity)*0.1])

def create_grid(gridname):
    '''
    Function receives grid name (as a string) and returns a graph object (networkx) containing that graph
    gridname can be: instance24, instance30, adisimple
    '''
    G=nx.Graph() # initialize a graph using the networkx library
    
    if gridname == "instance24":
        case_ieee = instance24.case24_ieee_rts() # read data from the case24_ieee_rts case
        case_flow_csv = 'case24_ieee_flow_solution.csv' #'case24_ieee_flow_solution.csv'
        case_bus_csv = 'case24_ieee_bus_solution.csv' #'case24_ieee_bus_solution.csv'
    elif gridname == "instance30":
        case_ieee = instance30.case30()
        case_flow_csv = 'case30_ieee_flow_solution.csv'
        case_bus_csv = 'case30_ieee_bus_solution.csv'
    elif gridname == "instance6":
        case_ieee = instance6.case6ww()
        case_flow_csv = 'case6_ieee_flow_solution.csv'
        case_bus_csv = 'case6_ieee_bus_solution.csv'
    elif gridname == "instance39":
        case_ieee = instance39.case39()
        case_flow_csv = 'case39_ieee_flow_solution.csv'
        case_bus_csv = 'case39_ieee_bus_solution.csv'
    elif gridname == "instance57":
        case_ieee = instance57.case57()
        case_flow_csv = 'case57_ieee_flow_solution.csv'
        case_bus_csv = 'case57_ieee_bus_solution.csv'
    elif gridname == "instance118":
        case_ieee = instance118.case118()
        case_flow_csv = 'case118_ieee_flow_solution.csv'
        case_bus_csv = 'case118_ieee_bus_solution.csv'
    elif gridname == "instance300":
        case_ieee = instance300.case300()
        case_flow_csv = 'case300_ieee_flow_solution.csv'
        case_bus_csv = 'case300_ieee_bus_solution.csv'
    
    # Initialize some constants
    gen_cost = 0.02 # later on can be part of the networkx object, for now more simple like this
    un_sup_cost = 2.0 #gen_cost*100 # cost of unsupplied energy. Placing this as two orders of the gen_cost. can also be adapted to the networkx object    
    
    # read the node list, edges, demands and generation capacities
    node_list = [case_ieee["bus"][i][0] for i in range(len(case_ieee["bus"]))] # retrieve node names (though this is simply a list of 1:n_nodes)
    edge_list = [(case_ieee["branch"][i][0], case_ieee["branch"][i][1]) for i in range(len(case_ieee["branch"]))] # some duplicates but add_edges_from takes care of that.
    demand = {case_ieee["bus"][node_i][0]: \
    max(case_ieee["bus"][node_i][2],0) for node_i in range(len(case_ieee["bus"]))} # make sure no negative demand (for non-generators, some occurrances at case300 and case39)
    # according to Alex Shtof, non-generators with negative load are generators with constant power (no ability to control power, hence are set as consumers with constant demand)
    
    # add up the generation capacities
    gen_cap = {case_ieee["gen"][i][0]: 0 for i in range(len(case_ieee["gen"]))}
    for i in range(len(case_ieee["gen"])):
        gen_cap[case_ieee["gen"][i][0]] += case_ieee["gen"][i][1]
        
    # read initial AC solution on branches from file
    capacity_factor = 1.5 # each line has capacity_factor as much as nominal value at solution
    cap = {i: 0 for i in edge_list} # set as default 200 MW capacity on each line, now update according to nominal demand
    with open(case_flow_csv, 'rb') as csvfile:
        solreader = csv.reader(csvfile, delimiter=',')
        solreader.next() # avoid header line
        for row in solreader:
            if row[3] == '': # make sure not trying to typecast an empty string
                tmp_val = 0
            else:
                tmp_val = float(row[3])
            cap[(int(row[1]), int(row[2]))] += abs(tmp_val*capacity_factor) # in case of duplicates, sum up the flow
    
    for i in cap.keys():
        cap[i] *= capacity_factor
        #if cap[i] < 25: # if for some reason, capacity is smaller than 25, make it 25.
        #    cap[i] = 25
    
    # read initial AC solution on generation from file
    gen = {i: 0 for i in node_list}
    with open(case_bus_csv, 'rb') as csvfile:
        solreader = csv.reader(csvfile, delimiter = ',')
        solreader.next() # avoid header line
        for row in solreader:
            if row[3] == '': #make sure not trying to typecast an empty string
                tmp_gen = 0
            else:
                tmp_gen = float(row[3])
            gen[int(row[0])] += tmp_gen
    
    # Add nodes with their respective demand, generation and generation capacity (gen when applies)
    for i in node_list:
        if i in gen_cap.keys():
            # this is a generation node
            G.add_node(i, demand = demand[i], original_demand = demand[i], gen_cap = math.ceil(max(gen_cap[i], gen[i])),
                       generated = gen[i], un_sup_cost = un_sup_cost, gen_cost = gen_cost)
            # note the use of "max", since I noticed that some nodes had initial amount of generation > capacity
            # probably some discrepancies with the AC flow solution... go figure.
        else:
            # simply a consumer
            G.add_node(i, demand = demand[i], original_demand = demand[i], gen_cap = 0, generated = 0,
                       un_sup_cost = un_sup_cost)
    
    # Add edges with their respective capacity,
    # I prefer to put the capacity as an attribute of G to minimize the objects passed down to functions
    for i in edge_list:
        G.add_edge(i[0], i[1], capacity = math.ceil(cap[(i[0], i[1])]), susceptance = 1.0) # currently using
        # susceptance x_{uv} = 1 for all u<->v, and initializing flow as = 0

    return(G)

def nCk(n,k):
  return int( reduce(mul, (Fraction(n-i, i+1) for i in range(k)), 1) )

# run the program
if __name__ == '__main__':
    main_program()