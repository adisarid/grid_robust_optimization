# A very simple script used to load a gpickle power grid,
# load the failure scenarios, and then write the supply per scenario output.

from robustness_heuristic_upper_bound import read_scenarios, compute_current_supply, read_nodes, read_edges
from robustness_heuristic_upper_bound import create_power_grid

# ************************************************
# ********* Import relevant libraries ************
# ************************************************


import argparse
import os
import csv
import networkx as nx
import warnings

parser = argparse.ArgumentParser(description="Load a gpickle power grid and compute supply")
parser.add_argument('--instance_location', help="Provide the location for instance files (directory name)",
                    type = str, default="instance24")
parser.add_argument('--gpickle_location', help="The location of a gpickle file",
                    type = str, default="")
parser.add_argument('--output_file', help="Where should I save a csv with the results?",
                    type = str, default = "c:/temp/grid_cascade_output/tmp_supply_gpickle.csv")
parser.add_argument('--brute_force_upper_bound', help = "Compute a brute force upper bound by exhausting all"
                                                        "installments. Ignores the gpickle_location.",
                    action = "store_true")
parser.add_argument('--line_upgrade_capacity_coef_scale',
                    help = "Capacity coefficient for new transmission lines and upgrades",
                    type = float, default = 5.0)
parser.add_argument('--line_establish_capacity_coef_scale',
                    help = "Coefficient for scaling capacity of newely established transmission lines",
                    type = float, default = 5.0)

# ... add additional arguments as required here ..
args = parser.parse_args()

# read the scenarios
instance_location = os.getcwd() + '\\' + args.instance_location + '\\'

scenarios = read_scenarios(instance_location + 'scenario_failures.csv',
                           instance_location + 'scenario_probabilities.csv')

if (args.gpickle_location <> "") and args.brute_force_upper_bound:
    warnings.warn("I have received both gpickle location and a brute force computation request."
                  "Ignoring gpickle_location.")

if not args.brute_force_upper_bound:
    # load the gpickle file
    G = nx.read_gpickle(os.getcwd() + '\\' + args.qpickle_location)
else:
    # load the grid from original files and install everything
    nodes = read_nodes(instance_location + 'grid_nodes.csv')
    original_edges = read_edges(instance_location + 'grid_edges.csv')
    G = create_power_grid(nodes, original_edges)
    # edges for establishment
    establishable_edges = [(edge[1], edge[2]) for edge in original_edges if edge[0] == 'H' and original_edges[edge] > 0
                           and not G.has_edge(edge[1], edge[2])]
    # list all edges which are upgradable
    upgradable_edges = [(edge[1], edge[2]) for edge in original_edges if edge[0] == 'H' and original_edges[edge] == 0]

    add_edges_1 = [(cur_edge[0], cur_edge[1], {
        'capacity': args.line_upgrade_capacity_coef_scale + args.line_establish_capacity_coef_scale,
        'susceptance': original_edges[('x',) + cur_edge],
        'establish_cost': original_edges[('H',) + cur_edge],
        'upgrade_cost': original_edges[('h',) + cur_edge]})
                   for cur_edge in establishable_edges]
    G.add_edges_from(add_edges_1)

    for edge_to_upgrade in upgradable_edges:
        G.edges[edge_to_upgrade]['capacity'] += args.line_upgrade_capacity_coef_scale

current_grid_outcome = compute_current_supply(G)

with open(args.output_file, 'wb') as scenario_stats_csv:
    writer = csv.writer(scenario_stats_csv)
    writer.writerow(['scenario', 'supply'])
    writer.writerows(current_grid_outcome['supply_per_scenario'])