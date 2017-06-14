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

# custom procedures
from read_grid import * # read grid and parameters from csv file
import build_problem # build the cplex problem object and set the lazy callback function
import export_results # export solution results into csv file for later handling

# set intance to solve as a robust planning problem
instance_location = 'c:\\Users\\Adi Sarid\\Documents\\GitHub\\grid_robust_opt\\adi_simple1\\'

# read parameters of grid
nodes = read_nodes(instance_location + 'grid_nodes.csv')
edges = read_edges(instance_location + 'grid_edges.csv')
scenarios = read_scenarios(instance_location + 'scenario_failures.csv', instance_location + 'scenario_probabilities.csv')
params = read_additional_param(instance_location + 'additional_params.csv')

# create the initial grid as an networkx object
grid = build_nx_grid(nodes, edges)


# build problem
cplex_problem = build_problem.build_cplex_problem(nodes, edges, scenarios, params)
cplex_problem.write("c:/temp/tmp_robust_lp.lp")
#robust_opt_cplex.register_callback(MyLazy) # register the lazy callback

##try:  # Exception handling just in case something goes wrong with the solver
##
##    robust_opt_cplex.solve()  #solve the model
##    # solution.get_status() returns an integer code
##    print "Solution status = " , robust_opt_cplex.solution.get_status(), ":",
##    # the following line prints the corresponding status string
##    print robust_opt_cplex.solution.status[robust_opt_cplex.solution.get_status()]
##
##    print "Objective value = " , robust_opt_cplex.solution.get_objective_value()
##    print "User cuts applied: " + str(robust_opt_cplex.solution.MIP.get_num_cuts(robust_opt_cplex.solution.MIP.cut_type.user))
##
##    # export the obtained solution to a file
##    export_results.write_results(robust_opt_cplex)
##
##except CplexError, exc:
##    print exc




