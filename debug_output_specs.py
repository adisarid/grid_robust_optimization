#-------------------------------------------------------------------------------
# Name:        Debug output specs
# Purpose:     Define debug global variables
#
# Author:      Adi Sarid
#
# Created:     18/09/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

print_debug = True # should I print the output to a file?
print_debug_verbose = True # should I print out verbose steps of lazy constraints?
print_debug_function_tracking = False # should I print location when entering each subroutine?
write_mid_run_res_files = False # should I write the lazy iterations' solutions
write_res_file = False # # should I write the solution to a file (when the process completes)
write_lp_file = False #"c:/temp/grid_cascade_output/lp_form/single_type1_step" + str(i) + ".lp" # For debugging purpuses I added writing the lp files. Disabled by default
print_cfe_results = True # should I print each cfe simulation results - which edges failed and which survived?
limit_lazy_add = -1 # should I limit the number of lazy constraints added at each iteration. Use -1 for unlimited.
