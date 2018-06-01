# ------------------------------------------------------------------------------
# Name:        Robust Optimization using an ALNS heuristic
# Purpose:     Find optimal planning to minimize loss of load
#              Based on Adaptive Large Neighborhood Search (ALNS) heuristic
#              For edges exceeding their capacity
#
# Author:      Adi Sarid
#
# Created:     24/05/2018
# Copyright:   (c) Adi Sarid 2018
# ------------------------------------------------------------------------------

# ************************************************
# ********* Import relevant libraries ************
# ************************************************
import cplex
import sys
import os
import csv
import networkx as nx
import time
import collections
import random


# ************************************************
# ********* Parse from command line **************
# ************************************************
import argparse
parser = argparse.ArgumentParser(description="Run a Power Grid Robust Optimization with an ALNS heuristic operation.")
parser.add_argument('--instance_location', help="Provide the location for instance files (directory name)",
                    type=str, default="instance24")
parser.add_argument('--time_limit', help="Set a time limit (stopping criteria), in hours (default is 1 hour)",
                    type=float, default=1)
parser.add_argument('--budget', help="Budget constraint for optimization problem (default is 100)",
                    type=float, default=100.0)
parser.add_argument('--export_results_file', help="Location of solution output file "
                                                  "(default c:/temp/grid_robust_opt/heuristic_results.csv)",
                    type=str, default="c:/temp/grid_robust_opt/heuristic_results.csv")

# ... add additional arguments as required here ..
args = parser.parse_args()


# ****************************************************
# **************** Globals ***************************
# ****************************************************
instance_location = os.getcwd() + '\\' + args.instance_location + '\\'
global budget  # used to define the budget constraint's RHS
budget = args.budget


# ****************************************************
# ******* The main program ***************************
# ****************************************************
def main_program():
    # get the start time
    start_time = time.time()
    current_time = time.time()
    nodes = read_nodes(instance_location + 'grid_nodes.csv')
    edges = read_edges(instance_location + 'grid_edges.csv')

    scenarios = read_scenarios(instance_location + 'scenario_failures.csv',
                               instance_location + 'scenario_probabilities.csv')

    # compute the total demand in the grid
    total_demand = sum([nodes[node_key] for node_key in nodes.keys() if node_key[0] == 'd'])

    # build a basic networkx object which will be used to hold the solution, and serve as an initial solution
    current_grid = create_power_grid(nodes, edges)
    current_grid_outcome = compute_current_supply(current_grid.copy(), scenarios)
    current_supply = [current_grid_outcome['supply']]  # retains the history of objective function values
    continue_flag = True  # will be used as a flag when stopping criteria is matched

    # select upgrade/downgrade quants - mean of existing edge's capacity divided by 2 # TODO: something smarter
    existing_capacities = [edges[cur_edge] for cur_edge in edges.keys() if cur_edge[0] == 'c' and edges[cur_edge] > 0]
    global upgrade_downgrade_step  # user for defining the upgrade/downgrade steps
    upgrade_downgrade_step = (float(sum(existing_capacities)) / len(existing_capacities)) / 2

    # compute the remaining budget after th initial solution has been determined
    left_budget = compute_left_budget(current_grid.copy(), edges)  # for now, this should equal budget,
    # until a better initial solution is devised

    loop_counter = 0  # used to count the number of iterations
    num_improvements = 0  # number of times the algorithm fount a better incumbent
    # while criteria has not been met (we haven't exceeded time and solution hasn't improved in last x iterations):
    while current_time - start_time < args.time_limit*60*60 and continue_flag:
        # copy the current grid to a temporary solution
        temporary_grid = current_grid.copy()
        # "destroy" current solution: choose what to upgrade until the upgrades exceed budget constraints
        left_budget = upgrade(temporary_grid, current_grid_outcome['fail_count'], edges, left_budget)
        # TODO: add weights for methods.
        # "repair" the new grid: choose what to downgrade until the remaining upgrades are within the budget constrains
        left_budget = downgrade(temporary_grid, edges, left_budget)  # TODO: add weights for methods.
        # evaluate the performance of the temporary grid
        temporary_grid_outcome = compute_current_supply(temporary_grid, scenarios)
        # check value of current solution using the cascade simulator
        if temporary_grid_outcome['supply'] > current_supply[-1]:
            # a better solution was found - update current incumbent TODO: insert a simulated annealing like behaviour
            current_supply.append(temporary_grid_outcome['supply'])
            current_grid = temporary_grid.copy()
            current_grid_outcome = temporary_grid_outcome
            num_improvements += 1
        # TODO: do something with continue flag
        # TODO: add time counter
        loop_counter += 1
        current_time = time.time()  # to manage time stopping criteria
        if not (loop_counter % 1):
            elapsed_time = (current_time-start_time)/60
            print "\r>> Elapsed:", int(elapsed_time)/60, "hours,", int(elapsed_time % 60), "min",\
                round(elapsed_time * 60.0 % 60),  "sec. ", \
                "Total rounds", loop_counter,\
                "improved", num_improvements, "times", "("+ str(round(float(num_improvements)/loop_counter*100)), "\b%).",\
                "Obj.:", current_supply[-1],\
                "Gap:", 100-round(current_supply[-1]/total_demand*100), "\b%",
            sys.stdout.flush()
    # write the current solution current_grid to a csv file


# ****************************************************
# ******* Downgrade and upgrade grid *****************
# ****************************************************
def compute_left_budget(power_grid, original_edges):
    """
    Function to compute the remaining budget after grid upgrades
    :param power_grid: Upgraded power grid to compute
    :param original_edges: Edges in the original power grid (pre-upgrade)
    :param budget: Total budget allocation
    :return: The remaining budget to allocate (can be negative if upgrades exceed budget)
    """
    current_edges = [arrange_edge_minmax(edge[0], edge[1])
                     for edge in power_grid.edges()]
    upgrade_costs = sum(
        [(power_grid.edges[cur_edge]['capacity'] - original_edges[('c',) + cur_edge]) * original_edges[
            ('h',) + cur_edge]
         for cur_edge in current_edges])
    establishment_costs = sum(
        [(power_grid.edges[cur_edge]['capacity'] > 0 and original_edges[('c',) + cur_edge] == 0) * original_edges[
            ('H',) + cur_edge]
         for cur_edge in current_edges])
    left_budget = budget - upgrade_costs + establishment_costs
    return left_budget


def upgrade(power_grid, fail_count, original_edges, left_budget):
    """
    Upgrade a power grid until upgrades exceed the budget
    :param power_grid: The power grid to upgrade
    :param fail_count: Dictionary of fail count of every edge in the power grid (relating to scenarios)
    :param original_edges: The edges and capacities in the original power grid
    :param left_budget: remaining budget for upgrades (should be positive)
    :return: The amount of exceeding budget after upgrades (the function also updates power_grid)
    """
    while left_budget > 0:
        edge_to_upgrade = random.choice([(edge[1], edge[2]) for edge in original_edges if edge[0] == 'c'])
        if not power_grid.has_edge(edge_to_upgrade[0], edge_to_upgrade[1]):
            # edge does not exist, establish it by adding upgrade_downgrade_step
            power_grid.add_edge(edge_to_upgrade[0], edge_to_upgrade[1],
                                capacity=upgrade_downgrade_step,
                                susceptance=original_edges[('x',) + edge_to_upgrade])
            left_budget = left_budget - original_edges[('H',) + edge_to_upgrade] + \
                          original_edges[('h',) + edge_to_upgrade]*upgrade_downgrade_step
        else:  # edge exists, do an upgrade
            power_grid.edges[edge_to_upgrade]['capacity'] += upgrade_downgrade_step
            left_budget = left_budget - original_edges[('h',) + edge_to_upgrade] * upgrade_downgrade_step
    return left_budget


def downgrade(power_grid, original_edges, left_budget):
    """
    The inverse function to upgrade, it randomly chooses what edges to downgrade until
    the solution becomes feasible again (not exceeding budget)
    :param power_grid: The power grid to upgrade
    :param original_edges: The edges and capacities in the original power grid
    :param left_budget: remaining budget for upgrades (should be negative)
    :return: The amount of exceeding budget after upgrades (the function also updates power_grid)
    """
    while left_budget < 0:
        edge_to_downgrade = random.choice([(edge[1], edge[2]) for edge in original_edges if edge[0] == 'c' and
                                           power_grid.has_edge(edge[1], edge[2]) and
                                           original_edges[edge] < power_grid.edges[(edge[1], edge[2])]['capacity']])
        power_grid.edges[edge_to_downgrade]['capacity'] -= upgrade_downgrade_step
        left_budget += original_edges[('h',) + edge_to_downgrade]*upgrade_downgrade_step
        if power_grid.edges[edge_to_downgrade]['capacity'] <= 0:
            # if this edge should not exist - remove it and add back establishment cost
            left_budget += original_edges[('H',) + edge_to_downgrade]
            power_grid.remove_edge(edge_to_downgrade[0], edge_to_downgrade[1])
    return left_budget

# ****************************************************
# ******* Reading and writing files ******************
# ****************************************************
def read_nodes(filename):
    dic = dict()
    with open(filename, 'rb') as nodes_file:
        nodes_reader = csv.reader(nodes_file, delimiter=',')
        next(nodes_reader)  # assuming header, skip first line
        for row in nodes_reader:
            dic[('d', row[0])] = float(row[1])  # read demand
            dic[('c', row[0])] = float(row[2])  # read capacity
            dic[('gen_up_ub', row[0])] = float(row[3])  # max generation upgrade
            dic[('H', row[0])] = float(row[4])  # fixed cost
            dic[('h', row[0])] = float(row[5])  # variable cost
    return dic


def read_edges(filename):
    dic = dict()
    with open(filename, 'rb') as edges_file:
        csv_reader = csv.reader(edges_file, delimiter=',')
        next(csv_reader)  # assuming header, skip first line
        for row in csv_reader:
            cur_edge = arrange_edge_minmax(row[0], row[1])
            dic[('c',) + cur_edge] = float(row[2])  # current capacity
            dic[('x',) + cur_edge] = float(row[3])  # reactance
            dic[('H',) + cur_edge] = float(row[4])  # fixed cost
            dic[('h',) + cur_edge] = float(row[5])  # variable cost
    return dic


def read_scenarios(filename_fail, filename_pr):
    dic = dict()
    with open(filename_pr, 'rb') as pr_file:
        csv_reader = csv.reader(pr_file, delimiter=',')
        next(csv_reader)  # assuming header, skip first line
        for row in csv_reader:
            dic[('s_pr', row[0])] = float(row[1])

    with open(filename_fail, 'rb') as failure_file:
        csv_reader = csv.reader(failure_file, delimiter=',')
        next(csv_reader)  # assuming header, skip first line
        for row in csv_reader:
            if ('s', row[0]) in dic.keys():
                dic[('s', row[0])] += [arrange_edge_minmax(row[1], row[2])]  # failures
            else:
                dic[('s', row[0])] = [arrange_edge_minmax(row[1], row[2])]  # first failure in this scenario
    return dic


def arrange_edge_minmax(edge_i, edge_j=None):
    if edge_j is None:
        # case edge_i contains a tuple
        edge_j = edge_i[1]
        edge_i = edge_i[0]
    tmp = (min(edge_i, edge_j), max(edge_i, edge_j))
    return tmp


# ****************************************************
# ******* Create power grid as networkx object *******
# ****************************************************
def create_power_grid(nodes, edges):
    """
    Build a power grid as a networkx object with customized keys
    :param nodes: a dictionary of nodes, as read and output by read_nodes() function
    :param edges: a dictionary of edges, as read and output by read_edges() function
    :return: grid an nx.Graph() object with the proper nodes and edges.
    """

    # initialize empty graph
    grid = nx.Graph()
    # add all the nodes
    node_list = [node[1] for node in nodes.keys() if node[0] == 'd']
    add_nodes = [(cur_node, {'demand': nodes[('d', cur_node)],
                             'gen_cap': nodes[('c', cur_node)], 'generated': 0,
                             'un_sup_cost': 0, 'gen_cost': 0, 'original_demand': nodes[('d', cur_node)]})
                 for cur_node in node_list]
    grid.add_nodes_from(add_nodes)

    # add all the edges
    edge_list = [(min(edge[1], edge[2]), max(edge[1], edge[2])) for edge in edges if edge[0] == 'c']
    add_edges_1 = [(cur_edge[0], cur_edge[1], {
        'capacity': edges[('c',) + cur_edge],
        'susceptance': edges[('x',) + cur_edge],
        'establish_cost': edges[('H',) + cur_edge],
        'upgrade_cost': edges[('h',) + cur_edge]})
                   for cur_edge in edge_list if (edges[('c',) + cur_edge] > 0)]
    grid.add_edges_from(add_edges_1)

    return grid


# ****************************************************
# ************ Test power grid failures **************
# ****************************************************
def cfe(power_grid, init_fail_edges):
    """
    Simulates a cascade failure evolution.
    :param power_grid: The original power grid to be tested
    :param init_fail_edges:  Which edges to fail initially (i.e., failure sceanrio)
    :return: Final state of the grid after cascading failure evolution is complete.
    """

    # initialize the list of failed edges at each iteration
    F = dict()
    F[0] = init_fail_edges
    # initialize flow dictionary for high resolution of solution (output of flow at each step)
    tot_failed = [] + init_fail_edges  # include initial failures in all_failed
    # loop
    i = 0
    tmp_grid_flow_update = {'cplex_object': None}  # initialize an empty object
    # The loop continues to recompute the flow only as long as there are more cascades and if this current
    # simulation has a max depth then it has not been reached (i<max_cascade_depth)
    while F[i]:  # list of edges failed in iteration i is not empty
        tmp_grid_flow_update = grid_flow_update(power_grid, F[i], False, True)
        F[i+1] = tmp_grid_flow_update['failed_edges']
        tot_failed += F[i+1]
        i += 1
    failed_grid = power_grid.copy()
    return {'F': F, 't': i, 'all_failed': tot_failed, 'updated_grid_copy': failed_grid}


def grid_flow_update(power_grid, failed_edges=[], write_lp=False, return_cplex_object=False):
    """
    Modifies power_grid after failure of edges in failed_edges,
    After which the function re-computes the flows, demand, and supply using CPLEX engine
    Eventually, the function returns a set of new failed edges.
    :param power_grid: Current networkx representation of power grid
    :param failed_edges: Edges which should fail initially
    :param write_lp: Write .lp file? (specify location or False)
    :param return_cplex_object: Should the function return the cplex object? Boolean
    :return: Dictionary including the failed edges and the cplex object (if return_cplex_object is True)
    """

    # INSIGHT (6/12/2017): Use the existing model previous_find_flow instead of rebuilding the entire model!
    # Then, use previous_find_flow.linear_constraints.delete
    # and previous_find_flow.variables.delete
    # to delete the unnecessary variables and constraints, then call solve() again
    # First step, go over failed edges and omit them from power_grid, rebalance components with demand and generation
    update_grid(power_grid, failed_edges)  # Each component of power_grid will balance demand and generation
    # capacities after this line
    # Initialize cplex internal flow problem
    find_flow = cplex.Cplex() # create cplex instance
    find_flow.objective.set_sense(find_flow.objective.sense.minimize)  # doesn't matter

    # Initialize decision variables (demand, supply, theta, and flow)
    dvar_pos_flow = dict() # position of variable
    counter = 0

    # define flow variables (continuous unbounded)
    obj = [0] * power_grid.number_of_edges()
    types = 'C' * power_grid.number_of_edges()
    lb = [-1e20] * power_grid.number_of_edges()
    ub = [1e20] * power_grid.number_of_edges()
    names = ['flow' + str(curr_edge) for curr_edge in sorted_edges(power_grid.edges())]
    dvar_pos_flow.update({('flow', tuple(sorted(power_grid.edges().keys()[i]))): i + counter for i in range(power_grid.number_of_edges())})
    find_flow.variables.add(obj = obj, types = types, lb = lb, ub = ub, names = names)
    counter += len(dvar_pos_flow)

    # define theta variables (continouous unbounded)
    names = ['theta' + str(curr_node) for curr_node in power_grid.nodes()]
    num_nodes = power_grid.number_of_nodes()
    dvar_pos_flow.update({('theta', power_grid.nodes().keys()[i]): i + counter for i in range(power_grid.number_of_nodes())})
    find_flow.variables.add(obj = [0]*num_nodes, types = 'C'*num_nodes, lb = [-1e20]*num_nodes, ub = [1e20]*num_nodes, names = names)

    # Add phase angle (theta) flow constraints: theta_i-theta_j-x_{ij}f_{ij} = 0
    phase_constraints = [[[dvar_pos_flow[('theta', curr_edge[0])], dvar_pos_flow[('theta', curr_edge[1])], dvar_pos_flow[('flow', curr_edge)]], [1.0, -1.0, -power_grid.edges[curr_edge]['susceptance']]] for curr_edge in sorted_edges(power_grid.edges().keys())]
    find_flow.linear_constraints.add(lin_expr = phase_constraints, senses = "E"*len(phase_constraints), rhs = [0]*len(phase_constraints))

    # Add general flow constraints. formation is: incoming edges - outgoing edges + generation
    flow_conservation = [[[dvar_pos_flow[('flow', edge)] for edge in get_associated_edges(node, power_grid.edges())['in']] + [dvar_pos_flow[('flow', edge)] for edge in get_associated_edges(node, power_grid.edges())['out']], \
                          [1 for edge in get_associated_edges(node, power_grid.edges())['in']] + [-1 for edge in get_associated_edges(node, power_grid.edges())['out']]] for node in power_grid.nodes()]
    flow_conservation_rhs = [power_grid.node[curr_node]['demand'] - power_grid.node[curr_node]['generated'] for curr_node in power_grid.nodes()]
    # clean up a bit for "empty" constraints
    flow_conservation_rhs = [flow_conservation_rhs[i] for i in range(len(flow_conservation_rhs)) if flow_conservation[i] != [[],[]]]
    flow_conservation = [const for const in flow_conservation if const != [[],[]]]
    find_flow.linear_constraints.add(lin_expr=flow_conservation, senses = "E"*len(flow_conservation), rhs = flow_conservation_rhs)

    # Suppress cplex messages
    find_flow.set_log_stream(None)
    find_flow.set_error_stream(None)
    find_flow.set_warning_stream(None)
    find_flow.set_results_stream(None)  #Enabling by argument as file name, i.e., set_results_stream('results_stream.txt')

    # Solve problem
    find_flow.set_problem_type(find_flow.problem_type.LP) # This is a regular linear problem, avoid code 1017 error.
    find_flow.solve()

    # Check to make sure that an optimal solution has been reached or exit otherwise
    if find_flow.solution.get_status() != 1:
        find_flow.write('problem_infeasible.lp')
        print "I'm having difficulty with a flow problem - please check"
        nx.write_gexf(power_grid, "c:/temp/exported_grid_err.gexf")
        sys.exit('Error: no optimal solution found while trying to solve flow problem. Writing into: '
                 'problem_infeasible.lp and c:/temp/exported_grid_err.gexf')

    find_flow_vars = find_flow.solution.get_values()

    # Set the failed edges
    new_failed_edges = [edge for edge in sorted_edges(power_grid.edges().keys()) if abs(find_flow_vars[dvar_pos_flow[('flow', edge)]]) > power_grid.edges[edge]['capacity']]

    # just in case you want an lp file - for debugging purposes.

    if write_lp:
        find_flow.write(write_lp)

    # Always return the failed edges
    return_object = {'failed_edges': new_failed_edges}
    # Should I return the CPLEX object?
    if return_cplex_object:
        return_object['cplex_object'] = find_flow

    # Return output and exit function
    return return_object


def update_grid(power_grid, failed_edges):
    """
    Function to update the existing graph by omitting failed_edges from it and re-computing demand and generation in
    each component.
    Modifies the graph power_grid (a networkx object, with custom fields 'demand', 'gen_cap', and 'generated'
    :param power_grid:
    :param failed_edges:
    :return: an updated power grid (networkx) after edge failures.
    """
    # First step, go over failed edges and omit them from power_grid
    power_grid.remove_edges_from([edge for edge in failed_edges])

    # Now adjust the total demand (supply) to equal the total supply (demand) within each connected component of power_grid
    graphs = list(nx.connected_component_subgraphs(power_grid))
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
            # need to shed some of the demand. Make sure there is no devision by 0
            if tot_demand == 0:
                shedding_factor = 0
            else:
                shedding_factor = tot_gen_cap/tot_demand
            for node in component.node.keys():
                power_grid.node[node]['demand'] = power_grid.node[node]['original_demand'] * shedding_factor # lower demand so that total demand in component does not surpass the capacity in the component
                power_grid.node[node]['generated'] = power_grid.node[node]['gen_cap'] # generating maximum in order to reach capacity

        # case demand is lower than total generation capacity
        elif tot_demand <= tot_gen_cap:
            # we are generating too much and need to curtail some of the generation
            # make sure that there is no division by 0
            if tot_gen_cap == 0:
                gen_factor = 0
            else:
                gen_factor = tot_demand/tot_gen_cap
            for node in component.node.keys():
                power_grid.node[node]['generated'] = power_grid.node[node]['gen_cap'] * gen_factor
                power_grid.node[node]['demand'] = power_grid.node[node]['original_demand']
                #if power_grid.node[node]['generated'] > power_grid.node[node]['gen_cap']:
                    #print 'Opps! error here(2), generation increased capacit. Check me'
                    #print 'node', node, 'gen_factor', gen_factor

        tot_demand = sum([power_grid.node[i]['original_demand'] for i in component.node.keys()])
        tot_gen_cap = sum([power_grid.node[i]['gen_cap'] for i in component.node.keys()])
        tot_generated = sum([power_grid.node[i]['generated'] for i in component.node.keys()])


def compute_current_supply(power_grid, scenarios):
    """
    Uses scenarios to compute the current supply (per scenario).
    :param power_grid: power grid as a networkx object with special properties (e.g. capacity, demand).
    :param scenarios: failure (initial) scenarios
    :return: A dictionary {'supply': The weighted supplied electricity,
                           'num_failed': dict with the number of times each edge failed}
    """
    # Extract scenario list
    scenario_list = [key[1] for key in scenarios.keys() if key[0] == 's']
    # Extract list of edges
    edge_list = [edge for edge in power_grid.edges()]
    # Generate the supplied vector using cfe
    failed_grids = {cur_scenario: cfe(power_grid.copy(), scenarios[cur_scenario]) for
                    cur_scenario in scenarios.keys() if cur_scenario[0] == 's'}
    supplied_per_scenario = [sum([failed_grids[cur_scenario]['updated_grid_copy'].nodes[cur_node]['demand']
                                  for cur_node in power_grid.nodes])*scenarios[('s_pr', cur_scenario[1])]
                             for cur_scenario in failed_grids.keys()]
    # count the number of times each edge in edge_list failed (not including initial failures)
    failed_edges = [failed_grids[('s', curr_scenario)]['F'][cascade_step+1]
                    for curr_scenario in scenario_list
                    for cascade_step in range(failed_grids[('s', curr_scenario)]['t'])]
    flatten_failed_edges = [l for sublist in failed_edges for l in sublist]
    failed_count = collections.Counter(flatten_failed_edges)
    result = {'supply': sum(supplied_per_scenario), 'fail_count': failed_count}
    return result


def get_associated_edges(node, edges):
    """
    Get the associated edges leaving and coming into a specified (input) node
    Output is a dictionary with 'in' being the set of all incoming edges and 'out' the set of all outgoing edges
    :param node: The node for which to look for associated edges
    :param edges: List of all edges in the grid
    :return:
    """
    edges_ordered = [tuple(sorted(edge)) for edge in edges]
    out_edge = [key for key in edges_ordered if node == key[0]] # use the dictionary to identify outgoing edges
    in_edge = [key for key in edges_ordered if node == key[1]] # use the dictionary to identify incoming edges
    out_dict = {'out': out_edge, 'in': in_edge}
    return out_dict


def sorted_edges(edges_list):
    """
    Gets a list of tuples (unsorted) and returns the same list of tuples only
    tuple pairs are sorted, i.e.:
    sorted_edges([(1,2), (10,6)]) = [(1,2), (6,10)]
    :param edges_list:  a list of all edges
    :return: Sorted tuple pairs of edges.
    """
    sorted_edges_list = [tuple(sorted(i)) for i in edges_list]
    return sorted_edges_list


# ****************************************************
# *************** Run the program ********************
# ****************************************************
if __name__ == '__main__':
    main_program()
