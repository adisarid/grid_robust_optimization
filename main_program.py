#-------------------------------------------------------------------------------
# Name:        Robust optimiation
# Purpose:     Find optimal planning to minimize loss of load
#              Based on a callback procedure with lazy constraints
#              For edges exceeding their capacity
#
# Author:      Adi Sarid
#
# Created:     07/06/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------


# ************************************************
# ********* Import relevant libraries ************
# ************************************************
import cplex
from cplex.callbacks import LazyConstraintCallback # import class for lazy callbacks
from cplex.callbacks import HeuristicCallback
import sys
import os
import csv
import networkx as nx
from time import gmtime, strftime, clock, time # for placing timestamp on debug solution files, and checking run time


# ************************************************
# ******* Parse from command line args ***********
# ************************************************
import argparse
parser = argparse.ArgumentParser(description = "Run a Power Grid Robust Optimization of full cascade depth (PGRO2) with Lazy constraints callback.")
parser.add_argument('--instance_location', help = "Provide the location for instance files (directory name)", type = str, default = "case30")
parser.add_argument('--time_limit', help = "Set a time limit for CPLEX run (in hours)", type = float, default = 0.5)
parser.add_argument('--opt_gap', help = "Optimality gap for CPLEX run", type = float, default = 0.01) # 0.01 = 1%
parser.add_argument('--budget', help = "Budget constraint for optimization problem", type = float, default = 100.0)
parser.add_argument('--print_lp', help = "Export c:/temp/grid_cascade_output/tmp_robust_1_cascade.lp", action = "store_true")
parser.add_argument('--print_debug_function_tracking', help = "Print a message upon entering each function", action = "store_true")
parser.add_argument('--export_results_file', help = "Save the solution file with variable names", action = "store_true")
parser.add_argument('--disable_cplex_messages', help = "Disables CPLEX's log, warning, error and results message streams", action = "store_true")
parser.add_argument('--penalize_failures', help = "Attach penalization coefficient to first order cascade failures (specify value)", type = float, default = 0.0)
parser.add_argument('--use_benders', help = "Use Bender's decomposition", action = "store_true")
parser.add_argument('--scenario_variant', help = "*** NOT IMPLEMENTED YET *** Select a scenario variant for given instance, i.e. load scenario_failures_VARIANTNAME.csv and scenario_probabilities_VARIANTNAME.csv", type = str, default = "")
parser.add_argument('--print_debug', help = "Should I print the screen output to a file instead? (mainly used for debugging)", action = "store_true")
parser.add_argument('--print_debug_verbose', help = "Should I print out a verbose output of the lazy constraints steps?", action = "store_true")
parser.add_argument('--write_mid_run_results_files', help = "Should I track and save the results in each lazy iteration?", action = "store_true")
parser.add_argument('--print_CFE_mid_run_results', help = "Should I print each cfe simulation results - which edges failed and which survived?", action = "store_true")
parser.add_argument('--limit_lazy_add', help = "Should I limit the number of lazy constraints added? [-1 for unlimited]", type = float, default = -1)
parser.add_argument('--incumbent_display_frequency', help = "Frequency to show incumbent solution", type = float, default = 0.05)
parser.add_argument('--max_cascade_depth', help = "The maximal cascade depth to examine in the simulation", type = float, default = 100)
parser.add_argument('--percent_short_runs', help = 'What % of cases should have a "short run" (stop simulation after max_cascade_depth). When 0.0 then short runs are disabled',
                    type =  float, default = 0.0)
parser.add_argument('--set_dvar_priorities', help = "Should I set decision variable priorities?", action = "store_true")
parser.add_argument('--line_upgrade_cost_coef_scale', help = "Coefficient to add to transmission line capacity variable to scale cost for binary instead of continuouos",
                    type = float, default = 5.0)
parser_add_argument('--line_establish_cost_coef_scale', help = "Coefficient for scaling cost for establishing a transmission line",
                    type = float, default = 5.0)
parser.add_argument('--line_upgrade_capacity_coef_scale', help = "Capacity coefficient for new transmission lines and upgrades",
                    type = float, default = 5.0)
parser.add_argument('--line_establish_capacity_coef_scale', help = "Coefficient for scaling capacity of newely established transmission lines",
                    type = float, default = 5.0)

# ... add additional arguments as required here ..
args = parser.parse_args()



# **************************************************
# Define global variables related to debugging mode
# **************************************************
print_debug = args.print_debug
print_debug_function_tracking = args.print_debug_function_tracking
print_debug_verbose = args.print_debug_verbose
write_mid_run_res_files = args.write_mid_run_results_files
write_res_file = args.export_results_file
print_cfe_results = args.print_CFE_mid_run_results
limit_lazy_add = args.limit_lazy_add
incumbent_display_frequency = args.incumbent_display_frequency

# The following are used to track the time spent in solution tree (CPLEX) vs. cascade simulation
time_spent_total = 0 # total time spent on solving the problem
time_spent_cascade_sim = 0 # total time spent on cascade simulator


# ******************************************************************
# Define global variables related to global parameters and callbacks
# Based on input args and on global variabels
# ******************************************************************

# set location of data directory from input arguments:
instance_location = os.getcwd() + '\\' + args.instance_location + '\\'

from time import strftime, clock, gmtime
append_solution_statistics = "c:\\temp\\grid_cascade_output\\" + strftime('%d-%m-%Y %H-%M-%S-', gmtime()) + str(round(clock(), 3)) + ' - ' + args.instance_location + '_solution_statistics.csv'
with open(append_solution_statistics, 'ab') as f:
    writer = csv.writer(f)
    writer.writerow(["line_upgrade_cost_coef_scale", "line_establish_cost_coef_scale",
                     "line_upgrade_capacity_coef_scale", "line_establish_capacity_coef_scale",
                     "set_decision_var_priorities", "runtime", "net_runtime_simulations", "best_incumbent"])

best_incumbent = 0 # the best solution reached so far - to be used in the heuristic callback
run_heuristic_callback = False # default is not to run heuristic callback until the lazy callback indicates a new incumbent
incumbent_solution_from_lazy = {} # incumbent solution (dictionary): solution by cplex with failures.
epsilon = 1e-3
bigM = 1.0/epsilon
epgap = args.opt_gap # optimality gap target, e.g., 0.01 = 1%

# set runtime limit from input arguments (input argument should be in hours)
totruntime = args.time_limit*60*60

# *************************************************************************************************
# Define global variables related to the convergence:
# Should use shortrun simulation features?
# Should use decision variables priorities?
# *************************************************************************************************
# the following definitions control the maximum number of cascades which the simulation should check, in proportion of cases
max_cascade_depth = args.max_cascade_depth # where should the simulation be cut

# set proportion of short runs from input if given
prop_cascade_cut = args.percent_short_runs

# set decision variable priorities?
set_decision_var_priorities = args.set_dvar_priorities

# **********************************************************************
# Define some more parameters related to the problem size and difficulty
# **********************************************************************
line_upgrade_capacity_coef_scale = args.line_upgrade_capacity_coef_scale  # the value added by establishing an edge. initilized here temporarily. will be added later on to original data file (grid_edges.csv)
line_upgrade_cost_coef_scale = args.line_upgrade_cost_coef_scale  # the cost coefficient of adding an edge.
line_establish_cost_coef_scale = ars.line_establish_cost_coef_scale  # the cost coefficient for establishing an edge.
line_establish_capacity_coef_scale = args.line_establish_capacity_coef_scale # the capacity coefficient for newly established edges.

# ****************************************************
# ******* The main program ***************************
# ****************************************************
def main_program():
    timestamp = strftime('%d-%m-%Y %H-%M-%S-', gmtime()) + str(round(clock(), 3)) + ' - '

    if print_debug:
        import sys # for directing print output to a file instead of writing to screen
        orig_stdout = sys.stdout
        f = open('c:/TEMP/grid_cascade_output/callback debug/' + timestamp + 'print_output.txt', 'w')
        sys.stdout = f

    # Read required data and declare as global for use across module
    global nodes
    global edges
    global scenarios
    global params
    nodes = read_nodes(instance_location + 'grid_nodes.csv')
    edges = read_edges(instance_location + 'grid_edges.csv')
    scenarios = read_scenarios(instance_location + 'scenario_failures.csv', instance_location + 'scenario_probabilities.csv')
    params = {'C': args.budget}

    # build problem
    build_results = build_cplex_problem()
    robust_opt_cplex = build_results['cplex_problem']
    dvar_pos = build_results['cplex_location_dictionary'] # useful for debugging

    if print_debug:
        robust_opt_cplex.write("c:/temp/grid_cascade_output/tmp_robust_lp.lp")

    robust_opt_cplex.register_callback(MyLazy) # register the lazy callback
    robust_opt_cplex.register_callback(IncumbentHeuristic)

    time_spent_total = clock() # initialize solving time
    robust_opt_cplex.parameters.mip.tolerances.mipgap.set(epgap) # set target optimality gap
    robust_opt_cplex.parameters.timelimit.set(totruntime) # set run time limit

    # enable multithread search
    #robust_opt_cplex.parameters.threads.set(robust_opt_cplex.get_num_cores())

    robust_opt_cplex.solve()  #solve the model

    print "Solution status = " , robust_opt_cplex.solution.get_status(), ":",
    # the following line prints the corresponding status string
    print robust_opt_cplex.solution.status[robust_opt_cplex.solution.get_status()]
    if robust_opt_cplex.solution.get_status != 103:
        print "Objective value = " , robust_opt_cplex.solution.get_objective_value()
        print "User cuts applied: " + str(robust_opt_cplex.solution.MIP.get_num_cuts(robust_opt_cplex.solution.MIP.cut_type.user))

        # export the obtained solution to a file
        # compute total supply per scenario
        current_solution = robust_opt_cplex.solution.get_values() + [robust_opt_cplex.solution.get_objective_value(), robust_opt_cplex.solution.MIP.get_mip_relative_gap()]
        current_var_names = robust_opt_cplex.variables.get_names() + ['Objective', 'Opt. Gap.']

        tot_supply = [sum([current_solution[dvar_pos[wkey]] for wkey in dvar_pos.keys() if wkey[0] == 'w' if wkey[2] == cur_scenario[1]]) for cur_scenario in scenarios.keys() if cur_scenario[0] == 's_pr']
        tot_unsupplied = [scenarios[cur_scenario]*sum([nodes[('d', wkey[1])]-current_solution[dvar_pos[wkey]] for wkey in dvar_pos.keys() if wkey[0] == 'w' if wkey[2] == cur_scenario[1]]) for cur_scenario in scenarios.keys() if cur_scenario[0] == 's_pr']
        tot_supply_sce = ['supply_s' + cur_scenario[1] for cur_scenario in scenarios.keys() if cur_scenario[0] == 's_pr']
        tot_supply_missed = ['un_supplied_s' + cur_scenario[1] for cur_scenario in scenarios.keys() if cur_scenario[0] == 's_pr']

        # add some info to results
        current_solution = current_solution + tot_supply + tot_unsupplied
        current_var_names = current_var_names + tot_supply_sce + tot_supply_missed

        print "Current (real) objective value:", sum(tot_unsupplied), 'MW unsupplied'
        print "Supply per scenario:", {tot_supply_sce[i]: tot_supply[i] for i in xrange(len(tot_supply))}
        print "Supply missed per scenario:", {tot_supply_missed[i]: tot_unsupplied[i] for i in xrange(len(tot_supply_sce))}

        if write_res_file:
            timestamp = strftime('%d-%m-%Y %H-%M-%S-', gmtime()) + str(round(clock(), 3)) + ' - '
            write_names_values(current_solution, current_var_names, 'c:/temp/grid_cascade_output/' + timestamp + 'temp_sol.csv')


    # Cancel print to file (initiated for debug purposes).
    if print_debug:
        sys.stdout = orig_stdout
        f.close()


    # Add final line for results file
    if append_solution_statistics:
            with open(append_solution_statistics, 'ab') as f:
                best_incumbent = robust_opt_cplex.solution.get_objective_value()
                writer = csv.writer(f)
                writer.writerow([line_upgrade_cost_coef_scale, line_establish_cost_coef_scale,
                                 line_upgrade_capacity_coef_scale, line_establish_capacity_coef_scale,
                                 set_decision_var_priorities, clock(), "NA", best_incumbent])



# ****************************************************
# ********** Read files ******************************
# ****************************************************
def read_nodes(filename):
    dic = dict()
    with open(filename, 'rb') as nodesfile:
        nodes_reader = csv.reader(nodesfile, delimiter = ',')
        next(nodes_reader) # assuimng header, skip first line
        for row in nodes_reader:
            dic[('d', row[0])] = float(row[1]) # read demand
            dic[('c', row[0])] = float(row[2]) # read capacity
            dic[('gen_up_ub', row[0])] = float(row[3]) # max generation upgrade
            dic[('H', row[0])] = float(row[4]) # fixed cost
            dic[('h', row[0])] = float(row[5]) # variable cost
    return dic

def read_edges(filename):
    dic = dict()
    with open(filename, 'rb') as edgesfile:
        csv_reader = csv.reader(edgesfile, delimiter = ',')
        next(csv_reader) # assuimng header, skip first line
        for row in csv_reader:
            cur_edge = arrange_edge_minmax(row[0], row[1])
            dic[('c',) + cur_edge] = float(row[2]) # current capacity
            dic[('x',) + cur_edge] = float(row[3]) # susceptance
            dic[('H',) + cur_edge] = float(row[4]) # fixed cost
            dic[('h',) + cur_edge] = float(row[5]) # variable cost
    return dic

def read_scenarios(filename_fail, filename_pr):
    dic = dict()
    with open(filename_pr, 'rb') as prfile:
        csv_reader = csv.reader(prfile, delimiter = ',')
        next(csv_reader) # assuming header, skip first line
        for row in csv_reader:
            dic[('s_pr', row[0])] = float(row[1])

    with open(filename_fail, 'rb') as failurefile:
        csv_reader = csv.reader(failurefile, delimiter = ',')
        next(csv_reader) # assuimng header, skip first line
        for row in csv_reader:
            if ('s', row[0]) in dic.keys():
                dic[('s', row[0])] += [arrange_edge_minmax(row[1], row[2])] # failures
            else:
                dic[('s', row[0])] = [arrange_edge_minmax(row[1], row[2])] # first failure in this scenario
    return dic

def read_additional_param(filename):
    dic = dict()
    with open(filename, 'rb') as paramfile:
        csv_reader = csv.reader(paramfile, delimiter = ',')
        next(csv_reader) # assuming heade, skip first line
        for row in csv_reader:
            dic[(row[0])] = float(row[1])
    return dic


def arrange_edge_minmax(edge_i, edge_j = []):
    if edge_j == []:
        # case edge_i contains a tuple
        edge_j = edge_i[1]
        edge_i = edge_i[0]
    tmp = (min(edge_i, edge_j), max(edge_i, edge_j))
    return tmp




# ****************************************************
# ****** Export files ********************************
# ****************************************************
def write_names_values(current_solution, variable_names, csvfilename):
    #if variable_names != []:
    var_row = [[variable_names[i], current_solution[i]] for i in range(len(variable_names))]
    #else:
    #    var_row = current_solution
    with open(csvfilename, 'wb') as csvfile:
        solutionwriter = csv.writer(csvfile, delimiter = ',')
        solutionwriter.writerow(['name', 'value'])
        solutionwriter.writerows(var_row)



# ****************************************************
# ****** Build CPLEX problem *************************
# ****************************************************

def build_cplex_problem():
    if print_debug_function_tracking:
        print "ENTERED: build_cplex_problem()"
    global dvar_pos # used as global to allow access across all functions
    global dvar_name
    global dvar_obj_coef
    global dvar_lb
    global dvar_ub
    global dvar_type
    global dvar_priority

    # initialize variable vector with variable name
    dvar_name = []
    dvar_pos = dict() # I like having both the name as a string and the location in vector as a dictionary
    dvar_obj_coef = []
    dvar_lb = []
    dvar_ub = []
    dvar_type = []

    # initialize lists: nodes, edges, scenarios
    global all_edges
    global all_nodes
    global all_scenarios

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
                dvar_obj_coef.append(scenarios[('s_pr', cur_scenario)]) # scenario relative weight
                dvar_lb.append(0)
                dvar_ub.append(nodes[('d', cur_node)])
                dvar_type.append('C')

            # phase angle (theta)
            dvar_name.append('theta_' + cur_node + 's' + cur_scenario)
            dvar_pos[('theta', cur_node, cur_scenario)] = len(dvar_name)-1
            dvar_obj_coef.append(0)
            dvar_lb.append(-10000)
            dvar_ub.append(10000)
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
        dvar_type.append('B') # changed to binary variable



        # establish new edge (only if upgrade cost > 0 otherwise this edge already exists and it is not upgradable, no need to add variable)
        if cur_edge in [(min(i[1],i[2]), max(i[1],i[2])) for i in edges.keys() if i[0] == 'H' and edges[i] > 0]:
            dvar_name.append('X_' + edge_str)
            dvar_pos[('X_', cur_edge)] = len(dvar_name)-1
            dvar_obj_coef.append(0)
            dvar_lb.append(0)
            dvar_ub.append(1)
            dvar_type.append('B')

    # create cplex object based on dvar_pos, dvar_obj_coef, dvar_lb, dvar_ub, dvar_type
    robust_opt = create_cplex_object()

    # Finished defining the main problem - returning cplex object:
    return {'cplex_problem': robust_opt, 'cplex_location_dictionary': dvar_pos}



def create_cplex_object():
    """
    Create cplex object, along with all variables, constraints, objective, ets.
    Based on dvar_pos, dvar_obj_coef, dvar_lb, dvar_ub, dvar_type, dvar_name, dvar_priorities
    This is a service function called by build_cplex_problem, and also by the Heuristic callback
    """
    if print_debug_function_tracking:
        print "ENTERED: create_cplex_object()"
    # initialize cplex object
    robust_opt = cplex.Cplex()
    robust_opt.objective.set_sense(robust_opt.objective.sense.maximize) # maximize supplied energy "=" minimize expected loss of load

    # building the decision variables within object
    robust_opt.variables.add(obj = dvar_obj_coef, lb = dvar_lb, ub = dvar_ub, types = dvar_type, names = dvar_name)

    if set_decision_var_priorities:
        # set priorities for all infrastructure variables (c, X, Z)
        high_priority_list = [(cur_var, 100, robust_opt.order.branch_direction.up) for cur_var in dvar_name if 'X' in cur_var or 'c' in cur_var or 'Z' in cur_var]
        # all other variables will have priority 0 by default (https://www.ibm.com/support/knowledgecenter/en/SSSA5P_12.6.0/ilog.odms.cplex.help/refdotnetcplex/html/M_ILOG_CPLEX_Cplex_SetPriorities.htm)
        robust_opt.order.set(high_priority_list)  # a list of tuple triplets (variable, priority, direction)
        #print "NOTE: Setting branch priorities for decision variables X, Z, c"

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

                # w_i^s <= d_i
                max_sup_lhs = [dvar_pos[('w', cur_node, scenario)]]
                max_sup_lhs_coef = [1]
                robust_opt.linear_constraints.add(lin_expr = [[max_sup_lhs, max_sup_lhs_coef]], senses = "L", rhs = [nodes[('d', cur_node)]])


            robust_opt.linear_constraints.add(lin_expr = [[flow_lhs, flow_lhs_coef]], senses = "E", rhs = [0])

            for cur_edge in assoc_edges['out']:
                # using only outgoing edges incoming will be covered as "outgoing" at a different node
                # First set failed edges according to input data
                if cur_edge in scenarios[('s', scenario)]:
                    init_failures = [dvar_pos[('F', cur_edge, scenario)]]
                    init_failures_coef = [1]
                    robust_opt.linear_constraints.add(lin_expr = [[init_failures, init_failures_coef]], senses = "E", rhs = [1])


                # Phase angle constraints -M*F_ij <= theta_i-theta_j-x_ij*f_ij <= M*F_ij   only for existing edges
                if not (cur_edge in [(i[1], i[2]) for i in edges.keys() if i[0] == 'H' and edges[i] > 0]):
                    # Less than equal side
                    phase_lhs = [dvar_pos[('theta', cur_node, scenario)], dvar_pos[('theta', cur_edge[1], scenario)], dvar_pos[('f', cur_edge, scenario)], dvar_pos[('F', cur_edge, scenario)]]
                    phase_lhs_coef = [1, -1, -edges[('x', ) + (cur_edge)], -bigM]
                    robust_opt.linear_constraints.add(lin_expr = [[phase_lhs, phase_lhs_coef]], senses = "L", rhs = [0])
                    # Greater than equal side
                    phase_lhs = [dvar_pos[('theta', cur_node, scenario)], dvar_pos[('theta', cur_edge[1], scenario)], dvar_pos[('f', cur_edge, scenario)], dvar_pos[('F', cur_edge, scenario)]]
                    phase_lhs_coef = [1, -1, -edges[('x', ) + (cur_edge)], bigM]
                    robust_opt.linear_constraints.add(lin_expr = [[phase_lhs, phase_lhs_coef]], senses = "G", rhs = [0])

                # Phase angle for potential edges -M*(1-X_ij)-M*F_ij <= theta_i-theta_j-x_ij*f_ij <= M*(1-X_ij) + M*F_ij     *** notice that X is not dependent in scenario but theta and f do depend
                if cur_edge in [(i[1], i[2]) for i in edges.keys() if i[0] == 'H' and edges[i] > 0]:
                    # only run if edge has a fixed establishment cost parameter (H)
                    # Less than equal side
                    phase_lhs = [dvar_pos[('theta', cur_node, scenario)], dvar_pos[('theta', cur_edge[1], scenario)], dvar_pos[('f', cur_edge, scenario)], dvar_pos[('X_', cur_edge)], dvar_pos[('F', cur_edge, scenario)]]
                    phase_lhs_coef = [1, -1, -edges[('x', ) + (cur_edge)], bigM, -bigM]
                    robust_opt.linear_constraints.add(lin_expr = [[phase_lhs, phase_lhs_coef]], senses = "L", rhs = [bigM])
                    # Greater than equal side
                    phase_lhs = [dvar_pos[('theta', cur_node, scenario)], dvar_pos[('theta', cur_edge[1], scenario)], dvar_pos[('f', cur_edge, scenario)], dvar_pos[('X_', cur_edge)], dvar_pos[('F', cur_edge, scenario)]]
                    phase_lhs_coef = [1, -1, -edges[('x', ) + (cur_edge)], -bigM, bigM]
                    robust_opt.linear_constraints.add(lin_expr = [[phase_lhs, phase_lhs_coef]], senses = "G", rhs = [-bigM])

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

    # Make sure that the establishment of edge ('X_', cur_edge) is directly linked to the decision ('c', cur_edge)
    # If edge was upgraded than it has necessarily been established
    [robust_opt.linear_constraints.add(lin_expr = [[[dvar_pos[('X_', cur_edge)], dvar_pos[('c', cur_edge)]], [1, -1]]], senses = "G", rhs = [epsilon]) for cur_edge in all_edges if ('X_', cur_edge) in dvar_pos.keys()]

    # Last constraint - budget
    # Investment cost constraint sum(h_ij*cl_ij) + sum(h_i*cg_i + H_i*Z_i) + sum(H_ij*X_ij) <= C
    budget_lhs = [dvar_pos[('c', cur_edge)] for cur_edge in all_edges] + [dvar_pos[('c', cur_node)] for cur_node in all_nodes] + \
                 [dvar_pos[('Z', cur_node)] for cur_node in all_nodes if ('H', cur_node) in nodes.keys()] + \
                 [dvar_pos[('X_', (i[1], i[2]))] for i in edges.keys() if i[0] == 'H' and edges[i] > 0]
    budget_lhs_coef = [line_upgrade_cost_coef_scale*edges[('h',) + cur_edge] for cur_edge in all_edges] + [nodes[('h', cur_node)] for cur_node in all_nodes] + \
                 [nodes[('H',cur_node)] for cur_node in all_nodes if ('H',cur_node) in nodes.keys()] + \
                 [line_establish_cost_coef_scale*edges[('H',)+(i[1], i[2])] for i in edges.keys() if i[0] == 'H' and edges[i] > 0]
    robust_opt.linear_constraints.add(lin_expr = [[budget_lhs, budget_lhs_coef]], senses = "L", rhs = [params['C']])

    return robust_opt





# ****************************************************
# ****** Add CPLEX lazy constraints ******************
# ****************************************************

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
        global print_debug
        global print_cfe_results
        global run_heuristic_callback
        global incumbent_solution_from_lazy

        # The following should work in CPLEX version > 12.6
        #print self.get_solution_source()

        all_edges = [(min(i[1],i[2]), max(i[1],i[2])) for i in edges.keys() if i[0] == 'c']

        current_solution = self.get_values()

        timestampstr = strftime('%d-%m-%Y %H-%M-%S-', gmtime()) + str(round(clock(), 3)) + ' - '

        if write_mid_run_res_files:
            write_names_values(current_solution, dvar_name, 'c:/temp/grid_cascade_output/callback debug/' + timestampstr + 'current_callback_solution.csv')

        if not print_cfe_results==False:
            print_cfe_results = timestampstr

        cfe_constraints = build_cfe_constraints(current_solution, timestampstr = print_cfe_results)

        [self.add(constraint = cplex.SparsePair(cfe_constraints['positions'][i], cfe_constraints['coefficients'][i]), sense = "L", rhs = cfe_constraints['rhs'][i]) for i in xrange(len(cfe_constraints['positions']))]


def build_cfe_constraints(current_solution, timestampstr):
    """
    The function uses input from the cfe simulation (simulation_failures) and the grid, to build
    a set of constraints which will make sure that simulation results and constraints are aligned
    This is the main function which generates the lazy callbacks.
    The function returns the constraints as a dictionary
    {'positions': [[],[],[],...], 'coefficients': [[],[],[],...], 'rhs': [a,b,c,...]}

    if the input timestampstr is not False then a csv file with the failed and survivde edges will be saved

    """
    if print_debug_function_tracking:
        print "ENTERED: build_problem.build_cfe_constraints()"
    global epsilon
    global dvar_name
    global dvar_pos

    epsilon2 = 1e-5

    # initialize position and coefficient lists
    positions_list = []
    coefficient_list = []
    rhs_list = []


    # build new grid based on solution and return the inconsistent failures
    simulation_failures = compute_failures(nodes, edges, scenarios, current_solution, dvar_pos)
    if not timestampstr == False:
        # print simlation results as a file with timestampstr in the filename
        current_failures = [[sce, edge_failed[0], edge_failed[1]] for sce in simulation_failures.keys() for edge_failed in simulation_failures[sce]['all_failed']]
        sim_fail_filename = 'c:/temp/grid_cascade_output/simulation_failures/' + timestampstr + 'current_simulation_failures.csv'
        with open(sim_fail_filename, 'wb') as csvfile:
            simulation_fail_out = csv.writer(csvfile, delimiter = ',')
            simulation_fail_out.writerow(['scenario', 'edge_1', 'edge_2'])
            simulation_fail_out.writerows(current_failures)

    # set the X variables
    X_established = [cur_pos for xkey, cur_pos in dvar_pos.iteritems() if xkey[0] == 'X_' and current_solution[dvar_pos[xkey]] > 0.999]
    X_not_established = [cur_pos for xkey, cur_pos in dvar_pos.iteritems() if xkey[0] == 'X_' and current_solution[dvar_pos[xkey]] < 0.001]
    X_established_coef = [1]*len(X_established)
    X_not_established_coef = [-1]*len(X_not_established)
    c_upgraded = [cur_pos for ckey, cur_pos in dvar_pos.iteritems() if ckey[0] == 'c' and current_solution[dvar_pos[ckey]] > 0.999]
    c_not_upgraded = [cur_pos for ckey, cur_pos in dvar_pos.iteritems() if ckey[0] == 'c' and current_solution[dvar_pos[ckey]] < 0.001]

    all_edges = [(min(i[1],i[2]), max(i[1],i[2])) for i in edges.keys() if i[0] == 'c']
    if print_debug_verbose:
        print "Simulation results:", simulation_failures
    for cur_scenario, failure_dict in simulation_failures.iteritems():
        add_constraint_limit = limit_lazy_add*1
        # Add failed edges
        for cur_cascade_iter in xrange(1, failure_dict['t']): # <- split to iterations, can be used for sensitivity analysis (to number of iterations used to create the lazy constratins)
            if print_debug_verbose:
                print "Simulation results: scenario", cur_scenario, " failures:", failure_dict['F'][cur_cascade_iter], " at cascade_iter", cur_cascade_iter
            for curr_failed_edge in failure_dict['F'][cur_cascade_iter]: # <- convert later on to list comprehention
                str_flag = "ok"
                if current_solution[dvar_pos[('F', curr_failed_edge, cur_scenario)]] < 0.001:
                    if print_debug_verbose:
                        str_flag = "CONTRADICTION (survived but should have failed)"
                    if add_constraint_limit != 0:
                        add_constraint_limit -= 1
                        if print_debug_verbose and add_constraint_limit > 0:
                            print "Limiting number of lazy constraints per scenario: only", add_constraint_limit, "of", limit_lazy_add, "left (scenario", cur_scenario, ")"
                        tmp_position = X_established + X_not_established + c_upgraded + c_not_upgraded + [dvar_pos[('F', curr_failed_edge, cur_scenario)]]
                        tmp_coeff = [1]*len(X_established) + [-1]*len(X_not_established) + [1]*len(c_upgraded) + [-1]*len(c_not_upgraded) + [-1]
                        tmp_rhs = len(X_established) + len(c_upgraded) - epsilon
                        positions_list += [tmp_position]
                        coefficient_list += [tmp_coeff]
                        rhs_list += [tmp_rhs]
                if print_debug_verbose:
                    print ('F', curr_failed_edge, cur_scenario), '=', current_solution[dvar_pos[('F', curr_failed_edge, cur_scenario)]], "<--", str_flag

        # Add non-failed edges (by end of simulation did not fail at all) - should be retained
        # the non failed edges are all the edges which are not in prev_failures
        # another condition is that the simulation that this is based on was not a "short run" (short run = only first cascade)
        if simulation_complete_run:
            non_failed_edges = [cur_edge for cur_edge in all_edges if cur_edge not in failure_dict['all_failed']]
            for curr_non_failed_edge in non_failed_edges: # <- convert later on to list comprehention
                str_flag = "ok"
                if current_solution[dvar_pos[('F', curr_non_failed_edge, cur_scenario)]] > 0.999:
                    if print_debug_verbose:
                        str_flag = "CONTRADICTION (failed but should not have)"
                    if add_constraint_limit != 0:
                        add_constraint_limit -= 1
                        if print_debug_verbose and add_constraint_limit > 0:
                            print "Limiting number of lazy constraints per scenario: only", add_constraint_limit, "of", limit_lazy_add, "left (scenario", cur_scenario, ")"
                        tmp_position = X_established + X_not_established + c_upgraded + c_not_upgraded + [dvar_pos[('F', curr_non_failed_edge, cur_scenario)]]
                        tmp_coeff = [1]*len(X_established) + [-1]*len(X_not_established) + [1]*len(c_upgraded) + [-1]*len(c_not_upgraded) + [1]
                        tmp_rhs = len(X_established) + len(c_upgraded) + 1 - epsilon #+1 for the 1-F on the right hand side of the equation
                        positions_list += [tmp_position]
                        coefficient_list += [tmp_coeff]
                        rhs_list += [tmp_rhs]
                if print_debug_verbose:
                    print ('F', curr_non_failed_edge, cur_scenario), '=', current_solution[dvar_pos[('F', curr_non_failed_edge, cur_scenario)]], "<--", str_flag

    cfe_constraints = {'positions': positions_list, 'coefficients': coefficient_list, 'rhs': rhs_list, 'sim_failures': simulation_failures}

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
    if print_debug_function_tracking:
        print "ENTERED: cascade_simulator_aux.update_grid()"
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
            # need to shed some of the demand. Make sure there is no devision by 0
            if tot_demand == 0:
                shedding_factor = 0
            else:
                shedding_factor = tot_gen_cap/tot_demand
            for node in component.node.keys():
                G.node[node]['demand'] = G.node[node]['original_demand']*shedding_factor # lower demand so that total demand in component does not surpass the capacity in the component
                G.node[node]['generated'] = G.node[node]['gen_cap'] # generating maximum in order to reach capacity

        # case demand is lower than total generation capacity
        elif tot_demand <= tot_gen_cap:
            # we are generating too much and need to curtail some of the generation
            # make sure that there is no division by 0
            if tot_gen_cap == 0:
                gen_factor = 0
            else:
                gen_factor = tot_demand/tot_gen_cap
            for node in component.node.keys():
                G.node[node]['generated'] = G.node[node]['gen_cap']*gen_factor
                G.node[node]['demand'] = G.node[node]['original_demand']
                #if G.node[node]['generated'] > G.node[node]['gen_cap']:
                    #print 'Opps! error here(2), generation increased capacit. Check me'
                    #print 'node', node, 'gen_factor', gen_factor

        tot_demand = sum([G.node[i]['original_demand'] for i in component.node.keys()])
        tot_gen_cap = sum([G.node[i]['gen_cap'] for i in component.node.keys()])
        tot_generated = sum([G.node[i]['generated'] for i in component.node.keys()])


def cfe(G, init_fail_edges, write_solution_file = False, simulation_complete_run = True, fails_per_scenario = []):
    """
    Simulates a cascade failure evolution (the CFE - algorithm 1 in paper)
    Input is an initial fail of edges (F),
    The graphic representation G (as a networkx object)
    and dicts of capacity and demand.
    Returns final state of the grid after cascading failure evolution is complete.
    """

    if print_debug_function_tracking:
        print "ENTERED: cascade_simulator_aux.cfe()"
    # initialize the list of failed edges at each iteration
    F = dict()
    F[0] = init_fail_edges

    # initialize flow dictionary for high resolution of solution (output of flow at each step)
    tot_failed = [] + init_fail_edges # iniclude initial failures in all_failed
    # initialize flow
    #current_flow = compute_flow(G)
    # loop
    i = 0

    tmp_grid_flow_update = {'cplex_object': None} # initialize an empty object

    contradiction_found = False # is there a contradiction between current_solution and latest simulation found


    # The loop continues to recompute the flow only as long as there are more cascades and if this current simulation has a max depth then it has not been reached (i<max_cascade_depth)
    while (F[i] and simulation_complete_run) or (not simulation_complete_run and not contradiction_found): # list of edges failed in iteration i is not empty
        #print "simulation_complete_run =", simulation_complete_run
        #print "contradiction_found =", contradiction_found
        #print i # for debugging purposes
        tmp_grid_flow_update = grid_flow_update(G, F[i], False, True, tmp_grid_flow_update['cplex_object'])
        F[i+1] =  tmp_grid_flow_update['failed_edges']
        tot_failed += F[i+1]
        i += 1
        # update if a contradiction has been found, but only contradctions of the following type:
        # "did not fail in the current solution but should have failed according to the iterations so far"
        #print "fails_per_scenario =", fails_per_scenario
        should_fail_contradictions = [sim_failed_edge for sim_failed_edge in tot_failed if sim_failed_edge not in fails_per_scenario]
        #print "should_fail_contradictions =", should_fail_contradictions
        if (should_fail_contradictions != []) and (not simulation_complete_run):
            contradiction_found = True
            #print"setting contradiction_found =", contradiction_found

    tmpG = G.copy()
    #print "returning tot_failed =", tot_failed
    # return computed values and exit function
    return({'F': F, 't':i, 'all_failed': tot_failed, 'updated_grid_copy': tmpG})#, 'tot_supplied': tot_unsupplied})


def grid_flow_update(G, failed_edges = [], write_lp = False, return_cplex_object = False, previous_find_flow = None):
    """
    The following function modifies G after failure of edges in failed_edges,
    After which the function re-computes the flows, demand, and supply using CPLEX engine
    Eventually, the function returns a set of new failed edges.
    Adi, 21/06/2017.
    """

    # INSIGHT (6/12/2017): Use the existing model previous_find_flow instead of rebuilding the entire model!
    # Then, use previous_find_flow.linear_constraints.delete
    # and previous_find_flow.variables.delete
    # to delete the unnecessary variables and constraints, then call solve() again
    if print_debug_function_tracking:
        print "ENTERED: cascade_simulator_aux.grid_flow_update()"
    # First step, go over failed edges and omit them from G, rebalance components with demand and generation
    update_grid(G, failed_edges) # Each component of G will balance demand and generation capacities after this line
    if print_debug_function_tracking:
        print "Number of connected components in G = ", nx.number_connected_components(G)
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
    dvar_pos_flow.update({('f', tuple(sorted(list(G.edges)[i]))):i+counter for i in range(len(G.edges()))})
    find_flow.variables.add(obj = obj, types = types, lb = lb, ub = ub, names = names)
    counter += len(dvar_pos_flow)

    # define theta variables (continouous unbounded)
    names = ['theta' + str(curr_node) for curr_node in G.nodes()]
    num_nodes = len(G.nodes())
    dvar_pos_flow.update({('theta', list(G.nodes)[i]):i+counter for i in range(len(G.nodes()))})
    find_flow.variables.add(obj = [0]*num_nodes, types = 'C'*num_nodes, lb = [-1e20]*num_nodes, ub = [1e20]*num_nodes, names = names)

    # Add phase angle (theta) flow constraints: theta_i-theta_j-x_{ij}f_{ij} = 0
    phase_constraints = [[[dvar_pos_flow[('theta', curr_edge[0])], dvar_pos_flow[('theta', curr_edge[1])], dvar_pos_flow[('f', curr_edge)]], [1.0, -1.0, -G.edges[curr_edge[0],curr_edge[1]]['susceptance']]] for curr_edge in sorted_edges(G.edges())]
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

    # Add a warm start from the previous_find_flow, if exists
    # I'm not sure this helps accelerate the process. Not noticeable anyway.
    # Should probably be better if I use the primal<->dual suggestion by Tal
    #if previous_find_flow != None:
    #    previous_names = previous_find_flow.variables.get_names()
    #    previous_values = previous_find_flow.solution.get_values()
    #    tmp_prev_sol = {previous_names[i]:previous_values[i] for i in range(len(previous_names))}
    #    initial_vals = [tmp_prev_sol[curr_var] for curr_var in find_flow.variables.get_names()]
    #    #print [find_flow.variables.get_names(),initial_vals]
    #    find_flow.MIP_starts.add([find_flow.variables.get_names(),initial_vals], find_flow.MIP_starts.effort_level.repair)
    #    find_flow.solution.



    # Solve problem
    find_flow.set_problem_type(find_flow.problem_type.LP) # This is a regular linear problem, avoid code 1017 error.
    find_flow.solve()

    # Check to make sure that an optimal solution has been reached or exit otherwise
    if find_flow.solution.get_status() != 1:
        find_flow.write('problem_infeasible.lp')
        print "I'm having difficulty with a flow problem - please check"
        nx.write_gexf(G, "c:/temp/exported_grid_err.gexf")
        sys.exit('Error: no optimal solution found while trying to solve flow problem. Writing into: problem_infeasible.lp and c:/temp/exported_grid_err.gexf')

    find_flow_vars = find_flow.solution.get_values()

    # Set the failed edges
    new_failed_edges = [edge for edge in sorted_edges(G.edges()) if abs(find_flow_vars[dvar_pos_flow[('f', edge)]]) > G.edges[edge[0],edge[1]]['capacity']]

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


def compute_failures(nodes, edges, scenarios, current_solution, dvar_pos):
    """
    Function builds grid based on original grid and infrastructure decisions from dvar_pos
    Then the cfe algorithm is run to determine which edges should fail in each scenario
    cfe results are returned by the function as a dictionary with scenario keys for later use.
    """

    global time_spent_cascade_sim
    global time_spent_total
    global run_heuristic_callback
    global incumbent_solution_from_lazy
    global best_incumbent
    global simulation_complete_run

    if print_debug_function_tracking:
        print "ENTERED: compute_casecade.compute_failure()"
    init_grid = build_nx_grid(nodes, edges, current_solution, dvar_pos) # build initial grid
    #print "DEBUG: Feeding into cfe algorithm (compute_cascade.compute_failed_inconsistent()) - edges:", init_grid.edges()
    scenario_list = [cur_sce[1] for cur_sce in scenarios.keys() if cur_sce[0] == 's_pr'] # get scenario list
    initial_failures_to_cfe = {cur_scenario: scenarios[('s', cur_scenario)] for cur_scenario in scenario_list}

    # determine if CFE should run completely or partially (i.e., only first cascade)
    import random
    if random.random() < prop_cascade_cut: # prop_cascade_cut is defined as a global variable at the top
        simulation_complete_run = False # the simulation is going to be partial
    else:
        simulation_complete_run = True # the simulation is going to be complete

    # extract all failed edges per scenario
    all_failures_per_scenario = {cur_scenario: [cur_edge for cur_edge in all_edges if current_solution[dvar_pos[('F', cur_edge, cur_scenario)]] > 0.99] for cur_scenario in scenario_list}

    cfe_time_start = clock() # measure time spent on cascade simulation

    # Run the CFE
    cfe_dict_results = {cur_scenario: cfe(init_grid.copy(), initial_failures_to_cfe[cur_scenario], write_solution_file = False, simulation_complete_run = simulation_complete_run, fails_per_scenario = all_failures_per_scenario[cur_scenario]) for cur_scenario in scenario_list}

    # finish up time measurement
    cfe_time_total = clock() - cfe_time_start
    time_spent_cascade_sim += cfe_time_total

    tmpGs = {cur_scenario: cfe_dict_results[cur_scenario]['updated_grid_copy'] for cur_scenario in scenario_list}

    # computing the unsupplied demand (objective value) and updating best incumbent if needed
    sup_demand = [scenarios[('s_pr', cur_scenario)]*sum([result_grid.node[cur_node]['demand'] for cur_node in result_grid.nodes()]) for (cur_scenario, result_grid) in tmpGs.iteritems()]
    if (sum(sup_demand) > best_incumbent) and (simulation_complete_run):
        best_incumbent = sum(sup_demand) # update best incumbent solution
        run_heuristic_callback = True
        incumbent_solution_from_lazy = {'current_solution': current_solution, 'simulation_results': cfe_dict_results}

    # print the best incumbent for incumbent_display_frequency% cases (if tick is < display frequency).
    if random.random() <= incumbent_display_frequency:
        time_spent_total = clock()
        if append_solution_statistics:
            with open(append_solution_statistics, 'ab') as f:
                writer = csv.writer(f)
                writer.writerow([line_upgrade_cost_coef_scale, line_establish_cost_coef_scale,
                                 line_upgrade_capacity_coef_scale, line_establish_capacity_coef_scale,
                                 set_decision_var_priorities, time_spent_total, time_spent_cascade_sim, best_incumbent])
        print "Curr sol=", sum(sup_demand), "Incumb=", best_incumbent, "Time on sim=", round(time_spent_cascade_sim), "Tot time", round(time_spent_total), "(", round(time_spent_cascade_sim/time_spent_total*100), "%) on sim"
        print "   Node  Left     Objective  IInf  Best Integer    Cuts/Bound    ItCnt     Gap         Variable B NodeID Parent  Depth"
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
    # note an important change from the continuous case to the discrete case: the use of: current_solution[dvar_pos[('c', cur_edge)]]*line_upgrade_capacity_coef_scale
    # this means that the capacity can grow by line_upgrade_capacity_coef_scale
    # should later on be introduced as part of the input.
    edge_list = [(min(edge[1], edge[2]), max(edge[1], edge[2])) for edge in edges if edge[0] == 'c']

    add_edges_1 = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge] +
                                                           current_solution[dvar_pos[('c', cur_edge)]] * line_upgrade_capacity_coef_scale,
                                               'susceptance': edges[('x',) + cur_edge]})
                   for cur_edge in edge_list if (('X_', cur_edge) not in dvar_pos.keys()) and (edges[('c',) + cur_edge] > 0)]
    add_edges_2 = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge] +
                                                           current_solution[dvar_pos[('c', cur_edge)]] * line_upgrade_capacity_coef_scale +
                                                           current_solution[dvar_pos[('X_', cur_edge)]] * line_establish_capacity_coef_scale,
                                               'susceptance': edges[('x',) + cur_edge]})
                   for cur_edge in edge_list if (('X_', cur_edge) in dvar_pos.keys())]

    # Debugging
    #timestampstr = strftime('%d-%m-%Y %H-%M-%S - ', gmtime()) + str(round(clock(), 3)) + ' - '
    #print timestampstr, "Currently inside compute_cascade.build_nx_grid(). Adding edges:", add_edges
    # Check if X are installed here
    # installed_edges = {('X_', cur_edge): current_solution[dvar_pos[('X_', cur_edge)]> 0.01] for cur_edge in edge_list}

    G.add_edges_from(add_edges_1)
    G.add_edges_from(add_edges_2)

    return(G)


# ****************************************************
# *******Define the incumbent heuristic **************
# ****************************************************
class IncumbentHeuristic(HeuristicCallback):
    def __call__(self):
        global run_heuristic_callback
        if run_heuristic_callback:
            # start building the heuristic solution from current solution (incumbent_solution_from_lazy)
            # the infrastructure part:
            heuristic_solution_var_infra = [pos for name, pos in dvar_pos.iteritems() if name[0] in ['X_', 'c']]
            heuristic_solution_val_infra = [incumbent_solution_from_lazy['current_solution'][i] for i in heuristic_solution_var_infra]

            # the failures/non-failures part:
            # extract all failed equivalent to keys of the dvar_pos
            all_failed_keys = [('F', cur_edge, cur_scenario) for cur_scenario in incumbent_solution_from_lazy['simulation_results'].keys() for cur_edge in incumbent_solution_from_lazy['simulation_results'][cur_scenario]['all_failed']]
            heuristic_solution_failures = [[pos, (name in all_failed_keys)*1] for name, pos in dvar_pos.iteritems() if name[0]=='F']
            heuristic_sol_var_fail = [i[0] for i in heuristic_solution_failures]
            heuristic_sol_val_fail = [i[1] for i in heuristic_solution_failures]

            # prep for insertion into the cplex
            heuristic_vars = heuristic_solution_var_infra + heuristic_sol_var_fail
            heuristic_vals = map(round, heuristic_solution_val_infra + heuristic_sol_val_fail)
            heuristic_lin_expr = [[[cur_var], [1.0]] for cur_var in heuristic_vars]
            N_preset = len(heuristic_vars)

            # create a new problem, equivalent to the main problem:
            sub_problem_heuristic = create_cplex_object()

            # add constraints to preset infrastructure values:
            sub_problem_heuristic.linear_constraints.add(lin_expr = heuristic_lin_expr, senses = "E"*N_preset, rhs = heuristic_vals)

            # supress subproblem's output stream
            sub_problem_heuristic.set_log_stream(None)
            sub_problem_heuristic.set_results_stream(None)

            # find sub problem's solution
            sub_problem_heuristic.solve()

            heuristic_solution_push = sub_problem_heuristic.solution.get_values()
            heuristic_solution_objective = sub_problem_heuristic.solution.get_objective_value()

            # note about inserting solutions into cplex using heuristic callback
            # From linke: https://www.ibm.com/support/knowledgecenter/SSSA5P_12.5.1/ilog.odms.cplex.help/refpythoncplex/html/cplex.callbacks.HeuristicCallback-class.html#set_solution
            # "Variables whose indices are not specified remain unchanged."
            # This means that I must solve the problem completely and feed in the theta and flow variables
            # otherwise this solution is not feasible (and probably that's why it isn't inserted).

            self.set_solution([range(len(heuristic_solution_push)), heuristic_solution_push], objective_value = heuristic_solution_objective)

            run_heuristic_callback = False # deactivate the heuristic callback flag until lazy finds a better solution





# ****************************************************
# *************** Run the program ********************
# ****************************************************

if __name__ == '__main__':
    main_program()