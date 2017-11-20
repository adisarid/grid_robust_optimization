#-------------------------------------------------------------------------------
# Name:        module1
# Purpose:
#
# Author:      Adi Sarid
#
# Created:     20/11/2017
# Copyright:   (c) Adi Sarid 2017
# Licence:     <your licence>
#-------------------------------------------------------------------------------

# Export matpower files to csv format

basename = "case30"
from case30 import case30
import csv

data_dict = case30()

# set the row headers, taken from caseformat: http://www.pserc.cornell.edu/matpower/docs/ref/matpower5.0/caseformat.html

# export to raw csv files

row_header = {'bus': ['bus number', 'bus type', 'Pd real power demand MW', 'Qd reactive power demand MVAr', 'Gs shunt conductance', 'Bs shunt susceptance', 'area number', 'Vm voltage magnitude', 'Va voltage angle', 'baseKV', 'zone', 'maxVm', 'minVm'], \
    'baseMVA': [], \
    'gencost': [], \
    'version':[], \
    'branch':['from node', 'to node', 'resistance','reactance','susceptance','rateA','rateB','rateC','ratio','angle','init branch status','min ang diff','max ang diff'], \
    'gen':['bus number', 'Pg real power output MW', 'Qg reactive power output MVAr', 'Qmax maximum reactive', 'Qmin minimum reactive', 'Vg','mBase','status','Pmax','Pmin','Pc1','Pc2','Qc1min','Qc1max','Qc2min','Qc2max','ramp rate','ramp 10 min','ramp30 min','ramp reactive','AFP'], \
    'areas': []}

for data_type in ['bus', 'branch', 'gen']:
    with open(basename + "_" + data_type + ".csv", 'wb') as csvfile:
        solutionwriter = csv.writer(csvfile, delimiter = ',')
        solutionwriter.writerow(row_header[data_type])
        solutionwriter.writerows(data_dict[data_type])