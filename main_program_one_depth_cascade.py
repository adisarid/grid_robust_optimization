#-------------------------------------------------------------------------------
# Name:        Robust optimization
# Purpose:     Find optimal planning to minimize loss of load
#              Based on a callback procedure with bender's decomposition
#              Limited to one depth cascade
#
# Author:      Adi Sarid
#
# Created:     004/01/2018
# Copyright:   (c) Adi Sarid 2018
# Licence:     <your licence>
#-------------------------------------------------------------------------------


# ************************************************
# ********* Import relevant libraries ************
# ************************************************
import cplex # for cplex
from cplex.callbacks import LazyConstraintCallback # import class for lazy callbacks
from cplex.callbacks import HeuristicCallback # heuristic callbacks
import sys # for outputing print to file stdout and for exiting run
import os # reading files
import csv # working with csv files (import/export)
import networkx as nx # important for cascade simulations
import time # for placing timestamps: use functions time.gmtime, time.strftime, time.clock, time.time


# ************************************************
# ******* Parse from command line args ***********
# ************************************************
import argparse
parser = argparse.ArgumentParser(description = "Run a Power Grid Robust Optimization of 1-cascade depth (PGRO1).")
parser.add_argument('--instance_location', help = "Provide the location for instance files (directory name)", type = str, default = "instance30")
parser.add_argument('--time_limit', help = "Set a time limit for CPLEX run (in hours)", type = float, default = 1)
parser.add_argument('--opt_gap', help = "Optimality gap for CPLEX run", type = float, default = 0.01) # 0.01 = 1%
parser.add_argument('--budget', help = "Budget constraint for optimization problem", type = float, default = 100.0)
parser.add_argument('--print_lp', help = "Export c:/temp/grid_cascade_output/tmp_robust_1_cascade.lp", action = "store_true")
parser.add_argument('--print_debug_function_tracking', help = "Print a message upon entering each function", action = "store_true")
parser.add_argument('--export_results_file', help = "Save the solution file with variable names", action = "store_true")
parser.add_argument('--disable_cplex_messages', help = "Disables CPLEX's log, warning, error and results message streams", action = "store_true")
parser.add_argument('--penalize_failures', help = "Attach penalization coefficient to first order cascade failures (specify value)", type = float, default = 0.0)
parser.add_argument('--use_benders', help = "Use Bender's decomposition", action = "store_true")
parser.add_argument('--scenario_variant', help = "*** NOT IMPLEMENTED YET *** Select a scenario variant for given instance, i.e. load scenario_failures_VARIANTNAME.csv and scenario_probabilities_VARIANTNAME.csv", type = str, default = "")
parser.add_argument('--load_capacity_factor', help = "The load capacity factor - "
                                                     "Change the existing capacity by this factor.",
                    type = float, default = 1.0)
parser.add_argument('--line_establish_capacity_coef_scale', help = "Nominal capacity established for new edges",
                    type = float, default = 0.0)
parser.add_argument('--line_upgrade_capacity_upper_bound', help = "Upper bound for edge capacity upgrade",
                    type = float, default = 10000.0)
parser.add_argument('--line_upgrade_cost_coef_scale', help = "Coefficient to add to transmission line capacity variable to scale cost for binary instead of continuouos",
                    type = float, default = 1.0)
parser.add_argument('--line_establish_cost_coef_scale', help = "Coefficient for scaling cost for establishing a transmission line",
                    type = float, default = 1.0)
parser.add_argument('--dump_file', help="Save the final objective outcome (number of run), "
                                          "saved to c:/temp/grid_cascade_output/dump.csv",
                    type=float, default=0.0)


# ... add additional arguments as required here ..
args = parser.parse_args()


# ******************************************************************
# ****** Define global variables related to global parameters ******
# ******************************************************************
epsilon = 1e-3
bigM = 10000
instance_location = os.getcwd() + '\\' + args.instance_location + '\\'


# ****************************************************
# ******* The main program ***************************
# ****************************************************
def main_program():

    # Read required data and declare as global for use across module
    global nodes
    global edges
    global scenarios
    global params
    global current_solution

    nodes = read_nodes(instance_location + 'grid_nodes.csv')
    edges = read_edges(instance_location + 'grid_edges.csv')
    scenarios = read_scenarios(instance_location + 'scenario_failures.csv', instance_location + 'scenario_probabilities.csv')

    # build problem
    build_results = build_cplex_problem()
    robust_opt_cplex = build_results['cplex_problem']
    dvar_pos = build_results['cplex_location_dictionary'] # useful for debugging

    if args.print_lp:
        robust_opt_cplex.write("c:/temp/grid_cascade_output/tmp_robust_1_cascade.lp")

    time_spent_total = time.clock() # initialize solving time
    robust_opt_cplex.parameters.mip.tolerances.mipgap.set(args.opt_gap) # set target optimality gap
    robust_opt_cplex.parameters.timelimit.set(args.time_limit*60*60) # set run time limit

    # enable multithread search
    robust_opt_cplex.parameters.threads.set(robust_opt_cplex.get_num_cores())

    # set error stream
    if args.disable_cplex_messages:
        robust_opt_cplex.set_log_stream(None)
        robust_opt_cplex.set_error_stream(None)
        robust_opt_cplex.set_warning_stream(None)
        robust_opt_cplex.set_results_stream(None)

    # set Bender's decomposition, code adopted from benders.py example of cplex
    if args.use_benders:
        anno = robust_opt_cplex.long_annotations
        idx = anno.add(name=anno.benders_annotation, defval=anno.benders_mastervalue)
        ctypes = robust_opt_cplex.variables.get_types()
        objtype = anno.object_type.variable
        continuous = robust_opt_cplex.variables.type.continuous
        robust_opt_cplex.long_annotations.set_values(idx, objtype,
                                        [(i, anno.benders_mastervalue+1)
                                        for i, j
                                        in enumerate(ctypes)
                                        if j == continuous])

    start_time = time.time()
    robust_opt_cplex.solve()  #solve the model
    elapsed_time = time.time() - start_time

    print "Solution status = " , robust_opt_cplex.solution.get_status(), ":",
    # the following line prints the corresponding status string
    print robust_opt_cplex.solution.status[robust_opt_cplex.solution.get_status()]
    if robust_opt_cplex.solution.get_status() != 103:
        print "Objective value = " , robust_opt_cplex.solution.get_objective_value()
        #print "User cuts applied: " + str(robust_opt_cplex.solution.MIP.get_num_cuts(robust_opt_cplex.solution.MIP.cut_type.user))


        # compute total supply per scenario
        current_solution = robust_opt_cplex.solution.get_values() + \
                           [robust_opt_cplex.solution.get_objective_value(), robust_opt_cplex.solution.MIP.get_mip_relative_gap(), args.budget, args.penalize_failures, args.instance_location]
        current_var_names = robust_opt_cplex.variables.get_names() + \
                           ['Objective', 'Opt. Gap.', 'PARAMS_budget', 'PARAMS_penalize_failures', 'PARAMS_instance']


        # print some interesting statistics per scenario
        tot_supply_sce = {cur_scenario: sum([current_solution[dvar_pos['w_i' + cur_node + '_t2_s' + cur_scenario]] for cur_node in all_nodes]) for cur_scenario in all_scenarios}
        tot_missed_sce = {cur_scenario: sum([nodes[('d', cur_node)] - current_solution[dvar_pos['w_i' + cur_node + '_t2_s' + cur_scenario]] for cur_node in all_nodes]) for cur_scenario in all_scenarios}
        print "\n\nSupply and loss of load, according to optimization problem:"
        print     "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
        print "Supply per scenario:", tot_supply_sce
        print "Supply missed per scenario:", tot_missed_sce

        # for comparison, compute the "real" loss of load using the cascade simulation and the infrastructure
        init_grid = build_nx_grid(nodes, edges, current_solution, dvar_pos)
        cfe_dict_results = {cur_scenario: cfe(init_grid.copy(), scenarios[('s', cur_scenario)], write_solution_file = False, simulation_complete_run = True, fails_per_scenario = []) for cur_scenario in all_scenarios}

        print "\n\nComparison to cascade simulation:"
        print     "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
        tot_supply_sce_cascade = {cur_scenario: sum([cfe_dict_results[cur_scenario]['updated_grid_copy'].node[cur_node]['demand'] for cur_node in all_nodes]) for cur_scenario in all_scenarios}
        tot_missed_sce_cascade = {cur_scenario: sum([nodes[('d', cur_node)] - cfe_dict_results[cur_scenario]['updated_grid_copy'].node[cur_node]['demand'] for cur_node in all_nodes]) for cur_scenario in all_scenarios}
        print "Supply per scenario (simulation):", tot_supply_sce_cascade
        print "Supply missed per scenario (simulation):", tot_missed_sce_cascade


        # export the obtained solution to a file
        current_var_names += [name_to_add for cur_scenario in all_scenarios for name_to_add in ['RES_tot_supply_sce' + cur_scenario, 'RES_tot_missed_sce' + cur_scenario, 'RES_tot_supply_cascade_sce' + cur_scenario, 'RES_tot_missed_cascade_sce' + cur_scenario]]
        current_solution += [value_to_add for cur_scenario in all_scenarios for value_to_add in [tot_supply_sce[cur_scenario], tot_missed_sce[cur_scenario], tot_supply_sce_cascade[cur_scenario], tot_missed_sce_cascade[cur_scenario]]]

        # write results to a file
        if args.export_results_file:
            timestamp = time.strftime('%d-%m-%Y %H-%M-%S-', time.gmtime()) + str(round(time.clock(), 3)) + ' - '
            write_names_values(current_solution, current_var_names, 'c:/temp/grid_cascade_output/' + timestamp + 'temp_sol.csv')
            with open('c:/temp/grid_cascade_output/' + timestamp + 'supply.csv', 'wb') as csvfile:
                solutionwriter = csv.writer(csvfile, delimiter=',')
                solutionwriter.writerow(['scenario', 'type', 'value'])
                solutionwriter.writerows([[i, '1depth', tot_supply_sce[i]] for i in tot_supply_sce.keys()])
                solutionwriter.writerows([[i, 'fullcascade', tot_supply_sce_cascade[i]] for i in tot_supply_sce_cascade.keys()])


        # Finish
        print "*** Program completed ***"
        # objective in "total supplied average"
        objective_value_full_cascade = sum([tot_supply_sce_cascade[i] * scenarios[('s_pr', i)] for i in all_scenarios])
        with open("c:/temp/grid_cascade_output/dump.csv", 'ab') as dump_file:
            writer = csv.writer(dump_file)
            writer.writerow([args.dump_file, objective_value_full_cascade, elapsed_time])
        write_names_values(current_solution, current_var_names,
                           'c:/temp/grid_cascade_output/detailed_results/' + str(args.dump_file) + '.csv')
        return({'cfe_dict_results': cfe_dict_results, 'current_solution': current_solution})
    else:
        print "*** Program completed *** ERROR: No solution found."



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
            dic[('c',) + cur_edge] = float(row[2])*args.load_capacity_factor  # current capacity
            dic[('x',) + cur_edge] = float(row[3]) # susceptance
            dic[('H',) + cur_edge] = float(row[4])*args.line_establish_cost_coef_scale  # fixed cost
            dic[('h',) + cur_edge] = float(row[5])*args.line_upgrade_cost_coef_scale  # variable cost
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
        next(csv_reader) # assuming header, skip first line
        for row in csv_reader:
            if ('s', row[0]) in dic.keys():
                dic[('s', row[0])] += [arrange_edge_minmax(row[1], row[2])] # failures
            else:
                dic[('s', row[0])] = [arrange_edge_minmax(row[1], row[2])] # first failure in this scenario
    return dic

def read_additional_param(filename):
    """
    Read additional parameters. Deprecated.
    """
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
    """
    The function builds all the required decision variables,
    creates global variables like variables names, coefficients, bounds, and types
    Finally it calls the create_cplex_object function (for the creation of constraints).
    The function returns the completed cplex object with all variables and constraints, and a dictionary
    for the location of each variable (in the variable vector).
    """
    if args.print_debug_function_tracking:
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
    global new_edges
    global existing_edges

    # epsilon
    global epsilon # depending on grid size, this constant can take various values 1e-10 is probably small enough for any practical situation
    global bigM
    tot_demand = sum([nodes[i] for i in nodes.keys() if i[0] == 'd'])

    # list scenarios
    all_scenarios = [i[1] for i in scenarios.keys() if i[0] == 's']

    # by nodes
    all_nodes = [i[1] for i in nodes.keys() if i[0] == 'd']

    # generation variables (g_i_t_s)
    dvar_name = ['g_i' + str(i) + '_t' + str(t) + '_s' + str(s) for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_obj_coef = [0 for i in dvar_name]
    dvar_lb = [0 for i in dvar_name]
    dvar_ub = [nodes[('c', i)] + nodes[('gen_up_ub', i)] for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_type = ['C' for i in dvar_name]

    # un-supplied demand variable (w_i_t_s)
    tmp_f = lambda t, s: scenarios[('s_pr', s)] if t==2 else 0
    dvar_name += ['w_i' + str(i) + '_t' + str(t) + '_s' + str(s) for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_obj_coef += [tmp_f(t,s) for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_lb += [0 for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_ub += [nodes[('d', i)] for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_type += ['C' for i in all_nodes for t in [1,2] for s in all_scenarios]

    # phase angle (theta_i_t_s) variables
    dvar_name += ['theta_i' + str(i) + '_t' + str(t) + '_s' + str(s) for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_obj_coef += [0 for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_lb += [-10000000 for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_ub += [10000000 for i in all_nodes for t in [1,2] for s in all_scenarios]
    dvar_type += ['C' for i in all_nodes for t in [1,2] for s in all_scenarios]

    # capacity upgrade of node
    dvar_name += ['c_i' + str(i) for i in all_nodes]
    dvar_obj_coef += [0 for i in all_nodes]
    dvar_lb += [0 for i in all_nodes]
    dvar_ub += [nodes[('gen_up_ub', i)] for i in all_nodes]
    dvar_type += ['C' for i in all_nodes]

    # establish backup capacity at node i
    dvar_name += ['Z_i' + str(i) for i in all_nodes]
    dvar_obj_coef += [0 for i in all_nodes]
    dvar_lb += [0 for i in all_nodes]
    dvar_ub += [1 for i in all_nodes]
    dvar_type += ['B' for i in all_nodes]

    # by edges
    all_edges = [(min(i[1],i[2]), max(i[1],i[2])) for i in edges.keys() if i[0] == 'c']
    new_edges = [(min(i[1],i[2]), max(i[1],i[2])) for i in edges.keys() if i[0] == 'H' and edges[i] > 0]
    existing_edges = [cur_edge for cur_edge in all_edges if cur_edge not in new_edges]

    # define flow variables
    dvar_name += ['flow_i' + str(edge[0]) + '_j' + str(edge[1]) + '_t' + str(t) + '_s' + str(s) for edge in all_edges for t in [1,2] for s in all_scenarios]
    dvar_obj_coef += [0 for edge in all_edges for t in [1,2] for s in all_scenarios]
    dvar_lb += [-tot_demand for edge in all_edges for t in [1,2] for s in all_scenarios]
    dvar_ub += [tot_demand for edge in all_edges for t in [1,2] for s in all_scenarios]
    dvar_type += ['C' for egge in all_edges for t in [1,2] for s in all_scenarios]

    # define failed edges (only at the first cascade)
    dvar_name += ['F_i' + str(edge[0]) + '_j' + str(edge[1]) + '_t1' + '_s' + str(s) for edge in all_edges for s in all_scenarios]
    dvar_obj_coef += [-1*(args.penalize_failures) for edge in all_edges for s in all_scenarios]
    dvar_lb += [0 for edge in all_edges for s in all_scenarios]
    dvar_ub += [1 for edge in all_edges for s in all_scenarios]
    dvar_type += ['B' for edge in all_edges for s in all_scenarios]

    # define capacity upgrade variables
    dvar_name += ['c_i' + edge[0] + '_j' + edge[1] for edge in all_edges]
    dvar_obj_coef += [0 for edge in all_edges]
    dvar_lb += [0 for edge in all_edges]
    dvar_ub += [args.line_upgrade_capacity_upper_bound for edge in all_edges]
    dvar_type += ['C' for edge in all_edges]

    # define variables for establishing a new edge (only if upgrade cost > 0 otherwise the edge already exists)
    dvar_name += ['X_i' + edge[0] + '_j' + edge[1] for edge in all_edges if edges[('H',) + edge] > 0]
    dvar_obj_coef += [0 for edge in all_edges if (('H',) + edge) in edges.keys() and edges[('H',) + edge] > 0]
    dvar_lb += [0 for edge in all_edges if (('H',) + edge) in edges.keys() and edges[('H',) + edge] > 0]
    dvar_ub += [1 for edge in all_edges if (('H',) + edge) in edges.keys() and edges[('H',) + edge] > 0]
    dvar_type += ['B' for edge in all_edges if (('H',) + edge) in edges.keys() and edges[('H',) + edge] > 0]

    # as final step: define the dvar_pos dictionary as
    dvar_pos = {dvar_name[i]:i for i in range(len(dvar_name))}

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
    if args.print_debug_function_tracking:
        print "ENTERED: create_cplex_object()"
    # initialize cplex object
    robust_opt = cplex.Cplex()
    robust_opt.objective.set_sense(robust_opt.objective.sense.maximize) # maximize supplied energy "=" minimize expected loss of load

    # building the decision variables within object
    robust_opt.variables.add(obj = dvar_obj_coef, lb = dvar_lb, ub = dvar_ub, types = dvar_type, names = dvar_name)

    # *** build constraints ***
    # auxiliary lambda function: outputs a list of edges going out or incoming into node
    assoc_edges = lambda i,direction: get_associated_edges(i, all_edges)['in'] if direction == "in" else get_associated_edges(i, all_edges)['out']

    # conservation of flow for t=1:
    # sum(f_j_i_t=1_s) + sum(f_i_j_t=1_s) + g_i = d_i (total incoming - outgoing + generated - supplied = 0):
    flow_lhs = [[dvar_pos['flow_i' + in_edge[0] + '_j' + in_edge[1] + '_t1' + '_s' + s] for in_edge in assoc_edges(i, 'in')] + \
                [dvar_pos['flow_i' + out_edge[0] + '_j' + out_edge[1] + '_t1' + '_s' + s] for out_edge in assoc_edges(i, 'out')] + \
                [dvar_pos['g_i' + i + '_t1' + '_s' + s]] for i in all_nodes for s in all_scenarios]
    flow_lhs_coef = [[1 for in_edge in assoc_edges(i, 'in')] + \
                     [-1 for out_edge in assoc_edges(i, 'out')] + \
                     [1] for i in all_nodes for s in all_scenarios]
    flow_constraints = [[flow_lhs[constraint], flow_lhs_coef[constraint]] for constraint in range(len(flow_lhs))]
    flow_rhs = [nodes[('d', i)] for i in all_nodes for s in all_scenarios]
    robust_opt.linear_constraints.add(lin_expr = flow_constraints, senses = "E"*len(flow_constraints), rhs = flow_rhs)

    # reactive power constraints for t=1, existing (non-failed) edges:
    reactive_lhs = [[dvar_pos['theta_i' + cur_edge[0] + '_t1' + '_s' + s],\
                     dvar_pos['theta_i' + cur_edge[1] + '_t1' + '_s' + s], \
                     dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1' + '_s' + s]] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s',s)] and edges[('H', ) + cur_edge] > 0]
    reactive_lhs_coef = [[1, -1, -edges[('x',) + cur_edge]] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s', s)] and edges[('H', ) + cur_edge] > 0]
    reactive_constraints = [[reactive_lhs[constraint], reactive_lhs_coef[constraint]] for constraint in range(len(reactive_lhs))]
    robust_opt.linear_constraints.add(lin_expr = reactive_constraints, senses = "E"*len(reactive_constraints), rhs = [0]*len(reactive_constraints))

    # reactive power constraints for t=1, upgradable (non-failed) edges:
    reactive_new_lhs = [[dvar_pos['theta_i' + cur_edge[0] + '_t1' + '_s' + s],\
                     dvar_pos['theta_i' + cur_edge[1] + '_t1' + '_s' + s], \
                     dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1' + '_s' + s], \
                     dvar_pos['X_i' + cur_edge[0] + '_j' + cur_edge[1]]] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s',s)] and edges[('H', ) + cur_edge] > 0]
    reactive_new_lhs_coef = [[1, -1, -edges[('x',) + cur_edge], bigM] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s', s)] and edges[('H', ) + cur_edge] > 0]
    reactive_new2_lhs_coef = [[1, -1, -edges[('x',) + cur_edge], -bigM] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s', s)] and edges[('H', ) + cur_edge] > 0]
    reactive_new_constraints = [[reactive_new_lhs[constraint], reactive_new_lhs_coef[constraint]] for constraint in range(len(reactive_new_lhs))]
    reactive_new2_constraints = [[reactive_new_lhs[constraint], reactive_new2_lhs_coef[constraint]] for constraint in range(len(reactive_new_lhs))]
    robust_opt.linear_constraints.add(lin_expr = reactive_new_constraints, senses = "L"*len(reactive_new_constraints), rhs = [bigM]*len(reactive_new_constraints))
    robust_opt.linear_constraints.add(lin_expr = reactive_new2_constraints, senses = "G"*len(reactive_new_constraints), rhs = [-bigM]*len(reactive_new2_constraints))

    # cascade effects occurring at t=1 (for existing edges):
    cascade_lhs = [[dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1_s' + s],\
                    dvar_pos['c_i' + cur_edge[0] + '_j' + cur_edge[1]],\
                    dvar_pos['F_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1_s' + s]] for cur_edge in existing_edges for s in all_scenarios]
    cascade_lhs_coef = [[1, -1, -bigM] for cur_edge in existing_edges for s in all_scenarios]
    cascade_lhs_coef2 = [[-1, -1, -bigM] for cur_edge in existing_edges for s in all_scenarios] # flow direction to the other side
    cascade_rhs = [edges[('c',) + cur_edge] for cur_edge in existing_edges for s in all_scenarios]*2
    cascade_constraints = [[cascade_lhs[i],cascade_lhs_coef[i]] for i in range(len(cascade_lhs))] + \
                          [[cascade_lhs[i],cascade_lhs_coef2[i]] for i in range(len(cascade_lhs))]
    robust_opt.linear_constraints.add(lin_expr = cascade_constraints, senses = "L"*len(cascade_rhs), rhs = cascade_rhs)

    # cascade effects occurring at t=1 (for new edges - add initial capacity factor):
    cascade_lhs = [[dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1_s' + s], \
                    dvar_pos['c_i' + cur_edge[0] + '_j' + cur_edge[1]], \
                    dvar_pos['F_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1_s' + s],
                    dvar_pos['X_i' + cur_edge[0] + '_j' + cur_edge[1]]] for cur_edge in new_edges for s in all_scenarios]
    cascade_lhs_coef = [[1, -1, -bigM, -args.line_establish_capacity_coef_scale] for cur_edge in new_edges
                        for s in all_scenarios]
    cascade_lhs_coef2 = [[-1, -1, -bigM, -args.line_establish_capacity_coef_scale] for cur_edge in new_edges
                         for s in all_scenarios]  # flow direction to the other side
    cascade_rhs = [edges[('c',) + cur_edge] for cur_edge in new_edges for s in all_scenarios] * 2
    cascade_constraints = [[cascade_lhs[i], cascade_lhs_coef[i]] for i in range(len(cascade_lhs))] + \
                          [[cascade_lhs[i], cascade_lhs_coef2[i]] for i in range(len(cascade_lhs))]
    robust_opt.linear_constraints.add(lin_expr=cascade_constraints, senses="L" * len(cascade_rhs), rhs=cascade_rhs)

    # transmission capacity - established edges:
    trans_cap_lhs = [[dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t' + str(t) + '_s' + s], dvar_pos['X_i' + cur_edge[0] + '_j' + cur_edge[1]]] for cur_edge in all_edges for t in [1,2] for s in all_scenarios if edges[('H', ) + cur_edge] > 0]*2
    trans_cap_lhs_coef = [[1, -bigM] for cur_edge in all_edges for t in [1,2] for s in all_scenarios if edges[('H', ) + cur_edge] > 0] + \
                         [[1, bigM] for cur_edge in all_edges for t in [1,2] for s in all_scenarios if edges[('H', ) + cur_edge] > 0]
    trans_cap_constraints = [[trans_cap_lhs[i],trans_cap_lhs_coef[i]] for i in range(len(trans_cap_lhs_coef))]
    robust_opt.linear_constraints.add(lin_expr = trans_cap_constraints, senses = "L"*(len(trans_cap_lhs)/2) + "G"*(len(trans_cap_lhs)/2), rhs = [0]*len(trans_cap_lhs))

    # transmission capacity - disabled failed edges
    trans_init_failed_lhs = [[[dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t' + str(t) + '_s' + s]],[1]] for cur_edge in all_edges for t in [1,2] for s in all_scenarios if cur_edge in scenarios[('s',s)]]
    robust_opt.linear_constraints.add(lin_expr = trans_init_failed_lhs, senses = "E"*len(trans_init_failed_lhs), rhs = [0]*len(trans_init_failed_lhs))


    # transmission capacity - failed edges after first cascade:
    trans_fail_lhs = [[dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t2' + '_s' + s], dvar_pos['F_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1_s' + s]] for cur_edge in all_edges for s in all_scenarios]*2
    trans_fail_lhs_coef = [[1, bigM] for cur_edge in all_edges for s in all_scenarios] + \
                          [[1, -bigM] for cur_edge in all_edges for s in all_scenarios]
    trans_fail_constraints = [[trans_fail_lhs[i], trans_fail_lhs_coef[i]] for i in range(len(trans_fail_lhs))]
    trans_fail_rhs = [bigM]*(len(trans_fail_lhs)/2) + [-bigM]*(len(trans_fail_lhs)/2)
    trans_fail_sign = "L"*(len(trans_fail_lhs)/2) + "G"*(len(trans_fail_lhs)/2)
    robust_opt.linear_constraints.add(lin_expr = trans_fail_constraints, senses = trans_fail_sign, rhs = trans_fail_rhs)

    # limit supply (do not exceed demand at t=2) (*different from previous approach - not strict '-' here)
    max_supply_lhs = [[dvar_pos['w_i' + cur_node + '_t2_s' + s] for cur_node in all_nodes] + [dvar_pos['g_i' + cur_node + '_t2_s' + s] for cur_node in all_nodes] for s in all_scenarios]
    max_supply_lhs_coef = [[1]*len(all_nodes) + [-1]*len(all_nodes) for s in all_scenarios]
    max_supply_constraints = [[max_supply_lhs[i], max_supply_lhs_coef[i]] for i in range(len(max_supply_lhs))]
    robust_opt.linear_constraints.add(lin_expr = max_supply_constraints, senses = "L"*len(max_supply_constraints), rhs = [0]*len(max_supply_constraints))

    # limit supply (demand = supply) at t=1
    max_supply1_lhs = [[dvar_pos['w_i' + cur_node + '_t1_s' + s] for cur_node in all_nodes] + [dvar_pos['g_i' + cur_node + '_t1_s' + s] for cur_node in all_nodes] for s in all_scenarios]
    max_supply1_lhs_coef = [[1]*len(all_nodes) + [-1]*len(all_nodes) for s in all_scenarios]
    max_supply1_constraints = [[max_supply1_lhs[i], max_supply1_lhs_coef[i]] for i in range(len(max_supply1_lhs))]
    robust_opt.linear_constraints.add(lin_expr = max_supply1_constraints, senses = "E"*len(max_supply1_constraints), rhs = [0]*len(max_supply1_constraints))

    # limit demand at each node - not required since this is already defined as an upper bound to w_i_t_s.

    # generation capacity t=1,2:
    gen_cap_constraints = [[[dvar_pos['g_i' + cur_node + '_t' + str(t) + '_s' + s], dvar_pos['c_i' + cur_node]],[1, -1]] for cur_node in all_nodes for t in [1,2] for s in all_scenarios]
    gen_cap_rhs = [nodes[('c', cur_node)] for cur_node in all_nodes for t in [1,2] for s in all_scenarios]
    robust_opt.linear_constraints.add(lin_expr = gen_cap_constraints, senses = "L"*len(gen_cap_constraints), rhs = gen_cap_rhs)

    # establish generator
    gen_est_constraints = [[[dvar_pos['c_i' + cur_node], dvar_pos['Z_i' + cur_node]], [1, -bigM]] for cur_node in all_nodes]
    robust_opt.linear_constraints.add(lin_expr = gen_est_constraints, senses = "L"*len(gen_est_constraints), rhs = [0]*len(gen_est_constraints))

    # conservation of flow for t=2:
    flow_lhs = [[dvar_pos['flow_i' + in_edge[0] + '_j' + in_edge[1] + '_t2' + '_s' + s] for in_edge in assoc_edges(i, 'in')] + \
                [dvar_pos['flow_i' + out_edge[0] + '_j' + out_edge[1] + '_t2' + '_s' + s] for out_edge in assoc_edges(i, 'out')] + \
                [dvar_pos['g_i' + i + '_t2' + '_s' + s]] + \
                [dvar_pos['w_i' + i + '_t2' + '_s' + s]] for i in all_nodes for s in all_scenarios]
    flow_lhs_coef = [[1 for in_edge in assoc_edges(i, 'in')] + \
                     [-1 for out_edge in assoc_edges(i, 'out')] + \
                     [1, -1] for i in all_nodes for s in all_scenarios]
    flow_constraints = [[flow_lhs[constraint], flow_lhs_coef[constraint]] for constraint in range(len(flow_lhs))]
    robust_opt.linear_constraints.add(lin_expr = flow_constraints, senses = "E"*len(flow_constraints), rhs = [0]*len(flow_constraints))

    # reactive power constraints for t=2, upgradable edges
    reactive_new_lhs = [[dvar_pos['theta_i' + cur_edge[0] + '_t2_s' + s],\
                         dvar_pos['theta_i' + cur_edge[1] + '_t2_s' + s], \
                         dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t2_s' + s], \
                         dvar_pos['F_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1_s' + s], \
                         dvar_pos['X_i' + cur_edge[0] + '_j' + cur_edge[1]]] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s',s)] and edges[('H',) + cur_edge] > 0]
    reactive_new_lhs_coef = [[1, -1, -edges[('x',) + cur_edge], -bigM, bigM] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s', s)] and edges[('H',) + cur_edge] > 0]
    reactive_new2_lhs_coef = [[1, -1, -edges[('x',) + cur_edge], bigM, -bigM] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s', s)] and edges[('H',) + cur_edge] > 0]
    reactive_new_constraints = [[reactive_new_lhs[constraint], reactive_new_lhs_coef[constraint]] for constraint in range(len(reactive_new_lhs))]
    reactive_new2_constraints = [[reactive_new_lhs[constraint], reactive_new2_lhs_coef[constraint]] for constraint in range(len(reactive_new_lhs))]
    robust_opt.linear_constraints.add(lin_expr = reactive_new_constraints, senses = "L"*len(reactive_new_constraints), rhs = [bigM]*len(reactive_new_constraints))
    robust_opt.linear_constraints.add(lin_expr = reactive_new2_constraints, senses = "G"*len(reactive_new_constraints), rhs = [-bigM]*len(reactive_new2_constraints))

    # reactive power constraints for t=2, existing edges (X_i omitted)
    reactive_new_lhs = [[dvar_pos['theta_i' + cur_edge[0] + '_t2_s' + s],\
                         dvar_pos['theta_i' + cur_edge[1] + '_t2_s' + s], \
                         dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t2_s' + s], \
                         dvar_pos['F_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t1_s' + s]] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s',s)] and edges[('H',) + cur_edge] == 0]
    reactive_new_lhs_coef = [[1, -1, -edges[('x',) + cur_edge], -bigM, bigM] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s', s)] and edges[('H',) + cur_edge] == 0]
    reactive_new2_lhs_coef = [[1, -1, -edges[('x',) + cur_edge], bigM, -bigM] for cur_edge in all_edges for s in all_scenarios if cur_edge not in scenarios[('s', s)] and edges[('H',) + cur_edge] == 0]
    reactive_new_constraints = [[reactive_new_lhs[constraint], reactive_new_lhs_coef[constraint]] for constraint in range(len(reactive_new_lhs))]
    reactive_new2_constraints = [[reactive_new_lhs[constraint], reactive_new2_lhs_coef[constraint]] for constraint in range(len(reactive_new_lhs))]
    robust_opt.linear_constraints.add(lin_expr = reactive_new_constraints, senses = "L"*len(reactive_new_constraints), rhs = [bigM]*len(reactive_new_constraints))
    robust_opt.linear_constraints.add(lin_expr = reactive_new2_constraints, senses = "G"*len(reactive_new_constraints), rhs = [-bigM]*len(reactive_new2_constraints))


    # transmission capacity - within capacity after 1st cascade, i.e., t=2 (*different from previous approach*)
    capacity_round2_lhs = [[dvar_pos['flow_i' + cur_edge[0] + '_j' + cur_edge[1] + '_t2_s' + s], dvar_pos['c_i' + cur_edge[0] + '_j' + cur_edge[1]]] for cur_edge in all_edges for s in all_scenarios]*2
    capacity_round2_lhs_coef = [[1, -1] for cur_edge in all_edges for s in all_scenarios] + \
                               [[1, 1] for cur_edge in all_edges for s in all_scenarios]
    capacity_round2_rhs = [edges[('c',) + cur_edge] for cur_edge in all_edges for s in all_scenarios] + \
                          [-edges[('c',) + cur_edge] for cur_edge in all_edges for s in all_scenarios]
    capacity_round2_constraint = [[capacity_round2_lhs[i], capacity_round2_lhs_coef[i]] for i in range(len(capacity_round2_lhs))]
    robust_opt.linear_constraints.add(lin_expr = capacity_round2_constraint, senses = "L"*(len(capacity_round2_lhs)/2)+"G"*(len(capacity_round2_lhs)/2), rhs = capacity_round2_rhs)

    # investment cost constraint
    budget_lhs = [dvar_pos['c_i' + cur_edge[0] + '_j' + cur_edge[1]] for cur_edge in all_edges] + \
                  [dvar_pos['X_i' + cur_edge[0] + '_j' + cur_edge[1]] for cur_edge in all_edges if edges[('H',) + cur_edge] > 0] + \
                  [dvar_pos['c_i' + cur_node] for cur_node in all_nodes] + \
                  [dvar_pos['Z_i' + cur_node] for cur_node in all_nodes]
    budget_lhs_coef = [edges[('h',) + cur_edge] for cur_edge in all_edges] + \
                       [edges[('H',) + cur_edge] for cur_edge in all_edges if edges[('H',) + cur_edge] > 0] + \
                       [nodes[('h', cur_node)] for cur_node in all_nodes] + \
                       [nodes[('H', cur_node)] for cur_node in all_nodes]
    robust_opt.linear_constraints.add(lin_expr = [[budget_lhs, budget_lhs_coef]], senses = "L", rhs = [args.budget])

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
    if args.print_debug_function_tracking:
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
    flow_write = [['flow'] + [j[0], j[1], i, j[2]] for i in flow_per_stage.keys() for j in flow_per_stage[i]]
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
    if args.print_debug_function_tracking:
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

    if args.print_debug_function_tracking:
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
    if args.print_debug_function_tracking:
        print "ENTERED: cascade_simulator_aux.grid_flow_update()"
    # First step, go over failed edges and omit them from G, rebalance components with demand and generation
    update_grid(G, failed_edges) # Each component of G will balance demand and generation capacities after this line
    if args.print_debug_function_tracking:
        print "Number of connected components in G = ", nx.number_connected_components(G)
    # Initialize cplex internal flow problem
    find_flow = cplex.Cplex() # create cplex instance
    find_flow.objective.set_sense(find_flow.objective.sense.minimize) # doesn't matter

    # Initialize decision variables (demand, supply, theta, and flow)
    dvar_pos_flow = dict() # position of variable
    counter = 0

    # define flow variables (continuous unbounded)
    obj = [0]*G.number_of_edges()
    types = 'C'*G.number_of_edges()
    lb = [-1e20]*G.number_of_edges()
    ub = [1e20]*G.number_of_edges()
    names = ['flow' + str(curr_edge) for curr_edge in sorted_edges(G.edges())]
    dvar_pos_flow.update({('flow', tuple(sorted(G.edges().keys()[i]))): i + counter for i in range(G.number_of_edges())})
    find_flow.variables.add(obj = obj, types = types, lb = lb, ub = ub, names = names)
    counter += len(dvar_pos_flow)

    # define theta variables (continouous unbounded)
    names = ['theta' + str(curr_node) for curr_node in G.nodes()]
    num_nodes = G.number_of_nodes()
    dvar_pos_flow.update({('theta', G.nodes().keys()[i]):i+counter for i in range(G.number_of_nodes())})
    find_flow.variables.add(obj = [0]*num_nodes, types = 'C'*num_nodes, lb = [-1e20]*num_nodes, ub = [1e20]*num_nodes, names = names)

    # Add phase angle (theta) flow constraints: theta_i-theta_j-x_{ij}f_{ij} = 0
    phase_constraints = [[[dvar_pos_flow[('theta', curr_edge[0])], dvar_pos_flow[('theta', curr_edge[1])], dvar_pos_flow[('flow', curr_edge)]], [1.0, -1.0, -G.edges[curr_edge]['susceptance']]] for curr_edge in sorted_edges(G.edges().keys())]
    find_flow.linear_constraints.add(lin_expr = phase_constraints, senses = "E"*len(phase_constraints), rhs = [0]*len(phase_constraints))

    # Add general flow constraints. formation is: incoming edges - outgoing edges + generation
    flow_conservation = [[[dvar_pos_flow[('flow', edge)] for edge in get_associated_edges(node, G.edges())['in']] + [dvar_pos_flow[('flow', edge)] for edge in get_associated_edges(node, G.edges())['out']], \
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
    new_failed_edges = [edge for edge in sorted_edges(G.edges().keys()) if abs(find_flow_vars[dvar_pos_flow[('flow', edge)]]) > G.edges[edge]['capacity']]

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

    if args.print_debug_function_tracking:
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
                writer.writerow([line_cost_coef_scale, line_capacity_coef_scale, set_decision_var_priorities, time_spent_total, time_spent_cascade_sim, best_incumbent])
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
    if args.print_debug_function_tracking:
        print "ENTERED: compute_casecade.build_nx_grid()"
    G = nx.Graph() # initialize empty graph

    # add all nodes
    def add_cur_sol_cap(node_key):
        if node_key in dvar_pos.keys():
            return(current_solution[dvar_pos[node_key]])
        else:
            return(0)

    # TODO: update the "generated" values later on to make sure that the initial state considers additional installations, if there were any (which are generators, not necessarily backups)
    node_list = [node[1] for node in nodes.keys() if node[0] == 'd']
    add_nodes = [(cur_node, {'demand': nodes[('d', cur_node)],'gen_cap':nodes[('c', cur_node)] + add_cur_sol_cap('c_i' + cur_node), 'generated':0, 'un_sup_cost':0, 'gen_cost':0, 'original_demand': nodes[('d', cur_node)]}) for cur_node in node_list]
    G.add_nodes_from(add_nodes)

    # add all edges
    # should later on be introduced as part of the input.
    edge_list = [(min(edge[1], edge[2]), max(edge[1], edge[2])) for edge in edges if edge[0] == 'c']

    add_edges_1 = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge] + current_solution[dvar_pos['c_i' + cur_edge[0] + '_j' + cur_edge[1]]], 'susceptance': edges[('x',) + cur_edge]}) for cur_edge in edge_list if (edges[('c',) + cur_edge] > 0)]
    add_edges_2 = [(cur_edge[0], cur_edge[1], {'capacity': edges[('c',) + cur_edge] + current_solution[dvar_pos['c_i' + cur_edge[0] + '_j' + cur_edge[1]]], 'susceptance': edges[('x',) + cur_edge]}) for cur_edge in edge_list if ('X_i' + cur_edge[0] + '_j' + cur_edge[1] in dvar_pos.keys()) and (current_solution[dvar_pos['X_i' + cur_edge[0] + '_j' + cur_edge[1]]]> 0.01)]

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
    res_dict = main_program()