#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      Adi Sarid
#
# Created:     17/10/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

instance_location = 'c:\\Users\\Adi Sarid\\Documents\\GitHub\\grid_robust_opt\\case30\\' #adi_simple2_discrete\\'
line_cost_coef_scale = 1 #15 # coefficient to add to transmission line capacity variable to scale cost for binary instead of continuouos
line_capacity_coef_scale = 10 # the value added by establishing an edge. initilized here temporarily. will be added later on to original data file (grid_edges.csv)
best_incumbent = 0