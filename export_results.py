#-------------------------------------------------------------------------------
# Name:        export_results
# Purpose:     Export planning decision variables to a csv file
#
# Author:      Adi Sarid
#
# Created:     07/06/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import csv

def write_names_values(current_solution, variable_names, csvfilename):
    #if variable_names != []:
    var_row = [[variable_names[i], current_solution[i]] for i in range(len(variable_names))]
    #else:
    #    var_row = current_solution
    with open(csvfilename, 'wb') as csvfile:
        solutionwriter = csv.writer(csvfile, delimiter = ',')
        solutionwriter.writerow(['name', 'value'])
        solutionwriter.writerows(var_row)


