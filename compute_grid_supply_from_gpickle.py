# A very simple script used to load a gpickle power grid,
# load the failure scenarios, and then write the supply per scenario output.

from robustness_heuristic_upper_bound import read_scenarios, compute_current_supply

# ************************************************
# ********* Import relevant libraries ************
# ************************************************


import argparse
import os
import csv
import networkx as nx

parser = argparse.ArgumentParser(description="Load a gpickle power grid and compute supply")
parser.add_argument('--instance_location', help="Provide the location for instance files (directory name)",
                    type = str, default="instance24")
parser.add_argument('--gpickle_location', help="The location of a gpickle file",
                    type = str, default="")
parser.add_argument('--output_file', help="Where should I save a csv with the results?",
                    type = str, default = "c:/temp/grid_cascade_output/tmp_supply_gpickle.csv")

# ... add additional arguments as required here ..
args = parser.parse_args()

# read the scenarios
instance_location = os.getcwd() + '\\' + args.instance_location + '\\'

scenarios = read_scenarios(instance_location + 'scenario_failures.csv',
                           instance_location + 'scenario_probabilities.csv')

# load the gpickle file
G = nx.read_gpickle(os.getcwd() + '\\' + args.qpickle_location)

current_grid_outcome = compute_current_supply(G)

with open(args.output_file, 'wb') as scenario_stats_csv:
    writer = csv.writer(scenario_stats_csv)
    writer.writerow(['scenario', 'supply'])
    writer.writerows(current_grid_outcome['supply_per_scenario'])