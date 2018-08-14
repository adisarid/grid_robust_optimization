import networkx as nx

# load the gpickle file
G = nx.read_gpickle("3.0.gpickle")

all_edges_with_info = [[cur_edge[0], cur_edge[1], G.edges[cur_edge]['capacity']] for cur_edge in G.edges]

import csv
with open("grid_edges_heuristic_solution.csv", "wb") as fp:
    wr = csv.writer(fp, dialect='excel')
    wr.writerow(['edge_i','edge_j', 'capacity'])
    wr.writerows(all_edges_with_info)