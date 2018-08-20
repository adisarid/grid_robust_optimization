import networkx as nx
import csv

# load the gpickle file
for grid_num in range(1, 17):
    G = nx.read_gpickle('C:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/analysis/Nominal results/detailed_results/' + str(grid_num) + '.0.gpickle')
    all_edges_with_info = [[cur_edge[0], cur_edge[1], G.edges[cur_edge]['capacity']] for cur_edge in G.edges]
    with open("C:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/analysis/Nominal results/detailed_results/grid_edges_heuristic_solution" + str(grid_num) + ".csv", "wb") as fp:
        wr = csv.writer(fp, dialect='excel')
        wr.writerow(['edge_i','edge_j', 'capacity'])
        wr.writerows(all_edges_with_info)