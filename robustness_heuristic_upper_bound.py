# ------------------------------------------------------------------------------
# Name:        Robust Optimization using an LNS heuristic
# Purpose:     Find optimal planning to minimize loss of load
#              Based on Large Neighborhood Search (LNS) heuristic
#              For edges exceeding their capacity
#              See Pisinger and Ropke, Large Neighborhood Search in Handbook of Metaheuristics
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
import numpy


# ************************************************
# ********* Parse from command line **************
# ************************************************
import argparse
parser = argparse.ArgumentParser(description="Run a Power Grid Robust Optimization with an ALNS heuristic operation.")
parser.add_argument('--instance_location', help="Provide the location for instance files (directory name)",
                    type=str, default="instance24")
parser.add_argument('--time_limit', help="Set a time limit (stopping criteria), in hours [default 1 hour]",
                    type=float, default=1)
parser.add_argument('--budget', help="Budget constraint for optimization problem [default 100]",
                    type=float, default=100.0)
parser.add_argument('--export_results_tracking', help="Location of solution output file "
                                                      "(default c:/temp/grid_cascade_output/heuristic_results.csv)"
                                                      "To suppress set as False",
                    type=str, default="c:/temp/grid_cascade_output/heuristic_results.csv")
parser.add_argument('--export_final_grid', help="Location to which the final power grid will be saved, as a gpickle"
                                                "(default c:/temp/grid_cascade_output/"
                                                "YYYY-MM-DD-hh-mm_heuristic_sol_*instance*.gpickle"
                                                "Set as False to skip saving (default)",
                    type=str, default="False")
parser.add_argument('--opt_gap', help="Gap from full demand [default 0.01=1%%]",
                    type=float, default=0.01)
parser.add_argument('--local_improvement_ratio',
                    help="*** DEPRECATED *** Not used anymore. Instead, choose the number of neighbors which constitute"
                         "A 'jumping criteria' if no improvement was achieved. See parameter min_neighbors.",
                    type=float, default=0.05)
parser.add_argument('--full_destruct_probability',
                    help="Probability at which an edge will be fully destructed during the downgrade operations "
                         "[default 0.1=10%%]",
                    type=float, default=0.1)
parser.add_argument('--upgrade_selection_bias',
                    help="The probability for upgrade selection bias - Percent of cases in which the upgrade is "
                         "determined by edges which mostly failed, versus a completely random selection of edges"
                         "[default 0.5=50%%]",
                    type=float, default=0.5)
parser.add_argument('--min_neighbors',
                    help="The minimum number of iterations before jumping to a new neighborhood,"
                         "if not a single improvement was reached in this neighborhood, during the last"
                         "MIN_NEIGHBORS count [default 25]",
                    type=float, default=25)
parser.add_argument('--min_neighborhoods_total',
                    help="The minimal number of neighborhoods to search at, before deciding to stop the search."
                         "Search is stopped if MIN_NEIGHBORHOODS_TOTAL neighborhoods were searched, and"
                         "overall improvement ratio is under OVERALL_IMPROVEMENT_RATIO_THRESHOLD."
                         "[default for minimum 50 neighborhoods]",
                    type=float, default=50)
parser.add_argument('--overall_improvement_ratio_threshold',
                    help="If overall improvement ratio (number of incumbent found out of total solutions searched)"
                         "decreases under OVERALL_IMPROVEMENT_RATIO_THRESHOLD, and at least MIN_NEIGHBORHOODS_TOTAL"
                         "were searched, then a search criteria is met, and the search is stopped."
                         "The overall improvement ratio threshold's default [default 0.01 = 1%%]",
                    type=float, default=0.01)
parser.add_argument('--load_capacity_factor', help="The load capacity factor - "
                                                   "Change the existing capacity by this factor.",
                    type=float, default=1.0)
parser.add_argument('--line_upgrade_cost_coef_scale', help="Coefficient to add to transmission line capacity variable "
                                                           "to scale cost for binary instead of continuous",
                    type=float, default=1.0)
parser.add_argument('--line_establish_cost_coef_scale', help="Coefficient for scaling cost for "
                                                             "establishing a transmission line",
                    type=float, default=1.0)
parser.add_argument('--line_upgrade_capacity_coef_scale',
                    help = "Capacity coefficient for new transmission lines and upgrades",
                    type = float, default = 5.0)
parser.add_argument('--line_establish_capacity_coef_scale',
                    help = "Coefficient for scaling capacity of newely established transmission lines",
                    type = float, default = 5.0)
parser.add_argument('--dump_file', help="Save the final objective outcome (number of run), "
                                          "saved to c:/temp/grid_cascade_output/dump.csv",
                    type=float, default=0.0)
parser.add_argument('--create_registry_file', help="Create a registry file which tracks all actions of the algorithm,"
                                                   "Enter full path of file name, omit argument for no tracking.",
                    type=str, default = "False")

# ... add additional arguments as required here ..
args = parser.parse_args()


# ****************************************************
# **************** Globals ***************************
# ****************************************************
instance_location = os.getcwd() + '\\' + args.instance_location + '\\'
global budget  # used to define the budget constraint's RHS
budget = args.budget
global full_destruct_probability  # the probability for full destruction of an edge
full_destruct_probability = args.full_destruct_probability
global upgrade_selection_bias
upgrade_selection_bias = args.upgrade_selection_bias
global create_registry
create_registry = (args.create_registry_file != "False")


# ****************************************************
# **************** Track decisions *******************
# ****************************************************
def write_track(action_description, edge, derived_value):
    with open(args.create_registry_file + '.csv', 'ab') as registry_track_file:
        reg_writer = csv.writer(registry_track_file)
        if not os.path.isfile(args.export_results_tracking):
            reg_writer.writerow('act_desc', 'edge', 'derived_val', 'current_time')
        reg_writer.writerow([action_description, edge, derived_value, time.time()])


# ****************************************************
# ****** Append solution statistics file *************
# ****************************************************
# if file does not exist open the file and write the header
if not os.path.isfile(args.export_results_tracking):
    with open(args.export_results_tracking, 'ab') as tracking_file:
        writer = csv.writer(tracking_file)
        writer.writerow([
            "time_stamp_str", "current_time",
            "args.instance_location", "budget",
            "full_destruct_probability", "upgrade_selection_bias",
            "left_budget", "loop_counter", "num_improvements",
            "current_supply", "total_demand",
            "neighborhoods_searched", "min_neighbors_per_neighborhood", "current_incumbent",
            "min_neighborhoods", "local_improvement_ratio", "overall_improvement_ratio", "temporary_grid_outcome"
        ])


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
    global establish_step  # step used when establishing a new edges - the average of existing edges
    upgrade_downgrade_step = args.line_upgrade_capacity_coef_scale
    establish_step = args.line_establish_capacity_coef_scale

    # compute the remaining budget after the initial solution has been determined
    left_budget = compute_left_budget(current_grid.copy(), edges)  # for now, this should equal budget,
    # until a better initial solution is devised

    loop_counter = 0  # used to count the number of iterations
    loops_local = 0  # number of loops in current area
    local_area_jumps = 0  # number of times the algorithm jumps to a new search area
    num_improvements = 0  # number of times the algorithm found a better incumbent
    num_improvements_local = 0  # number of time the algorithm found a better incumbent, in current search area
    local_no_improve = 0  # number of neighbors examined in the current neighborhood since last improvement

    # copy the current grid to a temporary solution
    temporary_grid = current_grid.copy()
    original_grid = current_grid.copy()
    current_incumbent = True  # The initial solution is also the incumbent solution

    # while criteria has not been met (we haven't exceeded time and solution hasn't improved in last x iterations):
    while current_time - start_time < args.time_limit*60*60 and continue_flag:
        # "destroy" current solution: choose what to upgrade until the upgrades exceed budget constraints
        left_budget = upgrade(temporary_grid, current_grid_outcome['fail_count'], edges, left_budget)
        # TODO: add weights for methods.
        # "repair" the new grid: choose what to downgrade until the remaining upgrades are within the budget constrains
        left_budget = downgrade(temporary_grid, edges, left_budget)  # TODO: add weights for methods.
        # evaluate the performance of the temporary grid
        temporary_grid_outcome = compute_current_supply(temporary_grid, scenarios)
        # check value of current solution using the cascade simulator
        if temporary_grid_outcome['supply'] > current_supply[-1] or loop_counter == 0:
            last_optimal_sol_time = time.time()
            # a better solution was found - update current incumbent TODO: insert a simulated annealing like behaviour
            current_supply.append(temporary_grid_outcome['supply'])
            current_grid = temporary_grid.copy()
            current_grid_outcome = temporary_grid_outcome.copy()
            num_improvements += 1
            num_improvements_local += 1
            current_incumbent = True
            local_no_improve = -1  # update local neighborhood since last improvement (the "-1" is increased in a bit)
            if create_registry:
                write_track("Found new incumbent", "NA", current_supply[-1])
        else:
            current_incumbent = False
            if create_registry:
                write_track("Dropping solution", "NA", temporary_grid_outcome['supply'])
        # export current grid statistics to file
        if args.export_results_tracking != "False":
            time_stamp = time.gmtime(current_time)
            time_stamp_str = str(time_stamp[0]) + '-' + str(time_stamp[1]).zfill(2) + '-' +\
                             str(time_stamp[2]).zfill(2) + '-' + str(time_stamp[3]).zfill(2) + '-' + \
                             str(time_stamp[4]).zfill(2) + '-' +\
                             str(time_stamp[5]).zfill(2)
            line_to_write = [time_stamp_str, current_time,
                             args.instance_location, args.budget,
                             full_destruct_probability, upgrade_selection_bias,
                             left_budget, loop_counter, num_improvements,
                             current_supply[-1], total_demand,
                             local_area_jumps, args.min_neighbors, current_incumbent,
                             args.min_neighborhoods_total, args.local_improvement_ratio,
                             args.overall_improvement_ratio_threshold, temporary_grid_outcome['supply']]
            with open(args.export_results_tracking, 'ab') as tracking_file:
                writer = csv.writer(tracking_file)
                writer.writerow(line_to_write)
        # TODO: do something with continue flag
        # TODO: add time counter
        loop_counter += 1
        loops_local += 1
        local_no_improve += 1
        current_time = time.time()  # to manage time stopping criteria
        if not (loop_counter % 1):
            elapsed_time = (current_time-start_time)/60
            print "\r>> Elapsed:", str(int(elapsed_time)/60) + "hr,", str(int(elapsed_time % 60)) + "m",\
                str(round(elapsed_time * 60.0 % 60, 1)) + "s.", \
                "Round", loop_counter,\
                "Improved", num_improvements, "time(s)", \
                "(" + str(round(float(num_improvements)/loop_counter*100, 1)), "\b%).",\
                "| Neighborhood", str(local_area_jumps+1) + ",",\
                "Neighbor", str(loops_local) + ",", "improve rate", \
                str(round(float(num_improvements_local)/loops_local*100, 1)) + "%.",\
                "| Overall Obj.:", current_supply[-1], '(of ' + str(total_demand) + ').',\
                "Gap:", 100-round(current_supply[-1]/total_demand*100, 1), "\b%",
            sys.stdout.flush()
        if args.opt_gap >= 1-current_supply[-1]/total_demand:
            continue_flag = False
            if create_registry:
                write_track("Halting - reached opt gap", "NA", current_supply[-1])
        if local_no_improve >= args.min_neighbors:
            local_area_jumps += 1
            loops_local = 0
            local_no_improve = 0
            num_improvements_local = 0  # TODO: Something smarter to decide on "jumping" to a different solution
            if create_registry:
                write_track("Jumping neighborhood", "NA", current_supply[-1])
            # reset grid to original state and start over the search - jumps to a new neighborhood
            temporary_grid = original_grid.copy()
        else:
            # return back to the best solution found so far
            temporary_grid = current_grid.copy()
            if create_registry:
                write_track("Reset to incumbent", "NA", current_supply[-1])
        if args.overall_improvement_ratio_threshold >= float(num_improvements)/loop_counter and \
                local_area_jumps >= args.min_neighborhoods_total-1:
            # in this case the overall ratio is so low, that probably nothing can be done with the heuristic
            continue_flag = False

    # write the current solution current_grid to a gpickle file
    if args.export_final_grid != "False":
        if args.export_final_grid == "timestamped" and 'last_optimal_sol_time' in locals():
            time_stamp = time.gmtime(last_optimal_sol_time)
            filename = "c:/temp/grid_cascade_output/" + str(time_stamp[0]) + '-' + str(time_stamp[1]).zfill(2) + \
                       '-' + str(time_stamp[2]).zfill(2) + '-' + str(time_stamp[3]).zfill(2) + '-' + \
                       str(time_stamp[4]).zfill(2) + '-' + \
                       str(time_stamp[5]).zfill(2) + ' - ' + args.instance_location + 'heuristic_sol'
        else:
            filename = args.export_final_grid
        nx.write_gpickle(current_grid, filename + '.gpickle')
        # export the per scenario statistics
        with open(filename + '_per_scenario_statistics.csv', 'wb') as scenario_stats_csv:
            writer = csv.writer(scenario_stats_csv)
            writer.writerow(['scenario', 'supply'])
            writer.writerows(current_grid_outcome['supply_per_scenario'])

    with open("c:/temp/grid_cascade_output/dump.csv", 'ab') as dump_file:
        writer = csv.writer(dump_file)
        writer.writerow([args.dump_file, max(current_supply), elapsed_time*60])
    nx.write_gpickle(current_grid, "c:/temp/grid_cascade_output/detailed_results/" + str(args.dump_file) + '.gpickle')
    print "Program complete."


# ****************************************************
# ******* Downgrade and upgrade grid *****************
# ****************************************************
def compute_left_budget(power_grid, original_edges):
    """
    Function to compute the remaining budget after grid upgrades
    :param power_grid: Upgraded power grid to compute
    :param original_edges: Edges in the original power grid (pre-upgrade)
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

    # list all edges which have a setup cost H and are also not in the current solution
    establishable_edges = [(edge[1], edge[2]) for edge in original_edges if edge[0] == 'H' and original_edges[edge] > 0
                           and not power_grid.has_edge(edge[1], edge[2])]

    # list all edges which are still upgradable
    upgradable_edges = [(edge[1], edge[2]) for edge in original_edges if edge[0] == 'H' and original_edges[edge] > 0
                        and power_grid.has_edge(edge[1], edge[2])
                        and power_grid.get_edge_data(edge[1], edge[2])['capacity'] <
                        upgrade_downgrade_step + establish_step] + \
                       [(edge[1], edge[2]) for edge in original_edges if edge[0] == 'H' and original_edges[edge] == 0
                        and power_grid.has_edge(edge[1], edge[2])
                        and power_grid.get_edge_data(edge[1], edge[2])['capacity'] <
                        original_edges[('c',) + (edge[1], edge[2])] + upgrade_downgrade_step]

    while left_budget > 0:
        selected_operation = random.uniform(0, 1)  # used to randomly select the upgrade method
        if selected_operation <= upgrade_selection_bias and len(upgradable_edges) > 0:  # upgrade an edge according to failure counts
            existing_edges = fail_count.keys()
            tot_fails = sum([fail_count[cur_edge] for cur_edge in existing_edges])
            edge_selection_probability = [float(fail_count[cur_edge])/tot_fails for cur_edge in upgradable_edges]
            edge_to_upgrade = upgradable_edges[
                numpy.random.choice(range(len(upgradable_edges)), 1, edge_selection_probability)[0]
            ]
        if establishable_edges == [] and upgradable_edges == []:
            print 'STOPPING: Reached full upgrade situation. Cannot upgrade further.'
            sys.exit()
        else:  # upgrade a regular edge without applying selection bias
            edge_to_upgrade = random.choice(upgradable_edges+establishable_edges)
        if edge_to_upgrade in establishable_edges:
            # edge does not exist, establish it by adding upgrade_downgrade_step
            power_grid.add_edge(edge_to_upgrade[0], edge_to_upgrade[1],
                                capacity=establish_step,
                                susceptance=original_edges[('x',) + edge_to_upgrade])
            left_budget = left_budget - original_edges[('H',) + edge_to_upgrade] - \
                          original_edges[('h',) + edge_to_upgrade]*establish_step
            # Remove edge from establishable edges:
            establishable_edges.remove(edge_to_upgrade)
            if create_registry:
                write_track("Upgrade new edge", edge_to_upgrade, "NA")
        else:  # edge exists, do an upgrade
            power_grid.edges[edge_to_upgrade]['capacity'] += upgrade_downgrade_step
            left_budget = left_budget - original_edges[('h',) + edge_to_upgrade] * upgrade_downgrade_step
            # Remove edge from upgradable_edges
            upgradable_edges.remove(edge_to_upgrade)
            if create_registry:
                write_track("Upgrade existing edge", edge_to_upgrade, "NA")

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
    # TODO: Add an adaptive way to decide on a small downgrade versus edge elimination
    while left_budget < 0:
        selected_operation = random.uniform(0, 1)  # used to randomly select the downgrade method
        new_edges = [(edge[1], edge[2]) for edge in original_edges if edge[0] == 'c' and
                     power_grid.has_edge(edge[1], edge[2]) and
                     original_edges[edge] == 0]
        if selected_operation < full_destruct_probability and new_edges != []:
            # select a new edge and completely destruct it
            edge_to_downgrade = random.choice(new_edges)
            # compute the capacity to remove (cannot exceed the line's capacity)
            # currently the step is constant so this not needed, but later on will be important
            remove_capacity = power_grid.edges[edge_to_downgrade]['capacity']  # remove entire capacity
            if create_registry:
                write_track("Destruct edge", edge_to_downgrade, "NA")
        else:  # don't destruct, just make minor changes to edges (may destruct if small capacity exists)
            edge_to_downgrade = random.choice([(edge[1], edge[2]) for edge in original_edges if edge[0] == 'c' and
                                               power_grid.has_edge(edge[1], edge[2]) and
                                               original_edges[edge] < power_grid.edges[(edge[1], edge[2])]['capacity'] - 0.01])
            # compute the capacity to remove (cannot exceed the line's original capacity)
            if original_edges[('c',) + edge_to_downgrade] == 0 and \
                    power_grid.edges[edge_to_downgrade]['capacity'] \
                    >= upgrade_downgrade_step + establish_step - 0.01:
                # in this case the edge does not exist in the original grid and
                # in the current solution it was established and upgraded
                remove_capacity = upgrade_downgrade_step
            elif original_edges[('c',) + edge_to_downgrade] == 0 and \
                power_grid.edges[edge_to_downgrade]['capacity'] >= establish_step - 0.01:
                # For readability, I'm slightly more explicit than what I have to be.
                # In this case the edge does not exist in the original grid and
                # in the current solution it was established (with no additional upgrades)
                remove_capacity = establish_step
            else:
                # The edge did exist in the original grid, but was upgraded in the current solution
                remove_capacity = upgrade_downgrade_step
            if create_registry:
                write_track("Downgrade edge", edge_to_downgrade, "NA")
        # do the actual modification to the power grid networkx object
        power_grid.edges[edge_to_downgrade]['capacity'] -= remove_capacity
        left_budget += original_edges[('h',) + edge_to_downgrade] * remove_capacity
        if power_grid.edges[edge_to_downgrade]['capacity'] <= 0.01:
            # if this edge should not exist - remove it and add back establishment cost
            left_budget += original_edges[('H',) + edge_to_downgrade]
            power_grid.remove_edge(edge_to_downgrade[0], edge_to_downgrade[1])
            if create_registry:
                write_track("Destruct edge", edge_to_downgrade, "NA")

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
            dic[('c',) + cur_edge] = float(row[2])*args.load_capacity_factor  # current capacity
            dic[('x',) + cur_edge] = float(row[3])  # reactance
            dic[('H',) + cur_edge] = float(row[4])*args.line_establish_cost_coef_scale  # fixed cost
            dic[('h',) + cur_edge] = float(row[5])*args.line_upgrade_cost_coef_scale  # variable cost
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
    # Todo: consider turning cfe into a onetime function which already considers all scenarios (instead of per scenario)
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
    result = {'supply': sum(supplied_per_scenario), 'fail_count': failed_count,
              'supply_per_scenario':
                  [[cur_scenario[1], sum([failed_grids[cur_scenario]['updated_grid_copy'].nodes[cur_node]['demand']
                        for cur_node in power_grid.nodes])]
                   for cur_scenario in failed_grids.keys()]}
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
