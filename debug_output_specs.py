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

print_debug = True
print_degub_verbose = True
write_mid_run_res_files = False
write_res_file = True
write_lp_file = False #"c:/temp/grid_cascade_output/lp_form/single_type1_step" + str(i) + ".lp" # For debugging purpuses I added writing the lp files. Disabled by default
limit_lazy_add = -1 # should I limit the number of lazy constraints added at each iteration. Use -1 for unlimited.
