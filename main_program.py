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
import read_grid # read grid and parameters from csv file
import build_problem # build the cplex problem object and set the lazy callback function
import export_results # export solution results into csv file for later handling

# set intance to solve as a robust planning problem
instance_name = 'adi_simple1'

# read parameters of grid
grid = read_grid.read(instance_name)

# build problem
cplex_problem = build_problem.build(grid)

try:  # Exception handling just in case something goes wrong with the solver

    cplex_problem.solve()  #solve the model
    # solution.get_status() returns an integer code
    print "Solution status = " , cplex_problem.solution.get_status(), ":",
    # the following line prints the corresponding status string
    print cplex_problem.solution.status[cplex_problem.solution.get_status()]

    print "Objective value = " , cplex_problem.solution.get_objective_value()
    print "User cuts applied: " + str(cplex_problem.solution.MIP.get_num_cuts(cplex_problem.solution.MIP.cut_type.user))

    # export the obtained solution to a file
    export_results.write_results(cplex_problem)

except CplexError, exc:
    print exc




