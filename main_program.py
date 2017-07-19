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


import cplex
import sys
import os
import csv
## os.chdir("c:\\Users\\Adi Sarid\\Documents\\GitHub\\grid_robust_opt\\")
# custom procedures
from read_grid import * # read grid and parameters from csv file
import build_problem # build the cplex problem object and set the lazy callback function
import export_results # export solution results into csv file for later handling

# using global variables for easy reading into lazy callback class
from read_grid import nodes, edges, scenarios, params

from time import gmtime, strftime, clock
timestamp = strftime('%d-%m-%Y %H-%M-%S-', gmtime()) + str(round(clock(), 3)) + ' - '

# DEBUG PURPOSES - output to text file instead of screen:
global print_debug
print_debug = False

if print_debug:
    import sys # for directing print output to a file instead of writing to screen
    orig_stdout = sys.stdout
    f = open('c:/TEMP/grid_cascade_output/callback debug/' + timestamp + 'print_output.txt', 'w')
    sys.stdout = f

# build problem

build_results = build_problem.build_cplex_problem()
robust_opt_cplex = build_results['cplex_problem']
dvar_pos = build_results['cplex_location_dictionary'] # useful for debugging

if print_debug:
    robust_opt_cplex.write("c:/temp/grid_cascade_output/tmp_robust_lp.lp")

robust_opt_cplex.register_callback(build_problem.MyLazy) # register the lazy callback

# DEBUG - forcing specific solution
#robust_opt_cplex.linear_constraints.add(lin_expr = [[[48], [1]], [[70], [1]], [[77],[1]], [[69],[1]], [[62],[1]], [[55],[1]], [[47],[1]]], senses = "E"*7, rhs = [1, 1, 25, 20, 25, 25, 20])

robust_opt_cplex.solve()  #solve the model
print "Solution status = " , robust_opt_cplex.solution.get_status(), ":",
# the following line prints the corresponding status string
print robust_opt_cplex.solution.status[robust_opt_cplex.solution.get_status()]
print "Objective value = " , robust_opt_cplex.solution.get_objective_value()
print "User cuts applied: " + str(robust_opt_cplex.solution.MIP.get_num_cuts(robust_opt_cplex.solution.MIP.cut_type.user))

# export the obtained solution to a file
# compute total supply per scenario
current_solution = robust_opt_cplex.solution.get_values() + [robust_opt_cplex.solution.get_objective_value()]
current_var_names = robust_opt_cplex.variables.get_names() + ['Objective']

tot_supply = [sum([current_solution[dvar_pos[wkey]] for wkey in dvar_pos.keys() if wkey[0] == 'w' if wkey[2] == cur_scenario[1]]) for cur_scenario in scenarios.keys() if cur_scenario[0] == 's_pr']
tot_unsupplied = [scenarios[cur_scenario]*sum([nodes[('d', wkey[1])]-current_solution[dvar_pos[wkey]] for wkey in dvar_pos.keys() if wkey[0] == 'w' if wkey[2] == cur_scenario[1]]) for cur_scenario in scenarios.keys() if cur_scenario[0] == 's_pr']
tot_supply_sce = ['supply_s' + cur_scenario[1] for cur_scenario in scenarios.keys() if cur_scenario[0] == 's_pr']
tot_supply_missed = ['un_supplied_s' + cur_scenario[1] for cur_scenario in scenarios.keys() if cur_scenario[0] == 's_pr']

# add some info to results
current_solution = current_solution + tot_supply + tot_unsupplied
current_var_names = current_var_names + tot_supply_sce + tot_supply_missed

print "Current (real) objective value:", sum(tot_unsupplied), 'MW unsupplied'

timestamp = strftime('%d-%m-%Y %H-%M-%S-', gmtime()) + str(round(clock(), 3)) + ' - '
export_results.write_names_values(current_solution, current_var_names, 'c:/temp/grid_cascade_output/' + timestamp + 'temp_sol.csv')


# Cancel print to file (initiated for debug purposes).
if print_debug:
    sys.stdout = orig_stdout
    f.close()

