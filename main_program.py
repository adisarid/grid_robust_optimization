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

# build problem

build_results = build_problem.build_cplex_problem()
robust_opt_cplex = build_results['cplex_problem']
dvar_pos = build_results['cplex_location_dictionary'] # useful for debugging

robust_opt_cplex.write("c:/temp/tmp_robust_lp.lp")

robust_opt_cplex.register_callback(build_problem.MyLazy) # register the lazy callback

robust_opt_cplex.solve()




robust_opt_cplex.solve()  #solve the model
print "Solution status = " , robust_opt_cplex.solution.get_status(), ":",
# the following line prints the corresponding status string
print robust_opt_cplex.solution.status[robust_opt_cplex.solution.get_status()]
print "Objective value = " , robust_opt_cplex.solution.get_objective_value()
print "User cuts applied: " + str(robust_opt_cplex.solution.MIP.get_num_cuts(robust_opt_cplex.solution.MIP.cut_type.user))

# export the obtained solution to a file
current_solution = robust_opt_cplex.solution.get_values() + [robust_opt_cplex.solution.get_objective_value()]
current_var_names = robust_opt_cplex.variables.get_names() + ['Objective']

from time import gmtime, strftime
timestamp = strftime('%d-%m-%Y %H-%M-%S - ', gmtime())
export_results.write_names_values(current_solution, current_var_names, 'c:/temp/grid_cascade_output/' + timestamp + 'temp_sol.csv')




