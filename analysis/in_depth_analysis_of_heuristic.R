# In depth analysis of heuristic results

library(tidyverse)

setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")

source("analysis/grid_sunken_cost.R")

res <- read_csv("Nominal results/dump.csv", col_names = c("dump", "value", "runtime")) %>%
  full_join(readxl::read_excel("new.batch.parameters.xlsx"), by = c("dump" = "dump_file")) %>%
  mutate(percent_supplied = value/tot.demand) %>%
  mutate(algorithm.name = case_when(str_detect(runcommand, "robustness_heuristic_upper_bound.py") ~ "LNS",
                                    str_detect(runcommand, "main_program.py") ~ "Lazy",
                                    str_detect(runcommand, "one_depth") ~ "One.depth")) %>%
  left_join(potential.edges) %>%
  mutate(line_establish_cost = line_establish_cost_coef_scale + upgrade.cost*line_establish_capacity_coef_scale,
         line_upgrade_cost = upgrade.cost*line_upgrade_capacity_coef_scale) %>%
  mutate(max.expanse = 
           tot_potential_edges*line_establish_cost +
           (tot_edges_installed + tot_potential_edges)*line_upgrade_cost) %>%
  mutate(load_capacity_factor = load_capacity_factor*1.5)


# isolate the heuristic results 
heuristic_res <- res %>%
  filter(algorithm.name == "LNS")

# load all existing edges' data into existing_edges tibble
existing_edges <- map_df(.f = function(instance_num){
  base_instance_edges <- read_csv(paste0("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/instance", instance_num, "/grid_edges.csv")) %>%
    mutate(instance = instance_num)
  return(base_instance_edges)
  }, .x = c(30, 57, 118, 300))

# function to compute upgrade types and summarize them as a tibble
summarize_upgrade_type <- function(dump_num){
  
  # get the instance's capacity factor and instance number from dump_number
  heuristic_res %>%
    filter(dump == dump_num) %>%
    select(load_capacity_factor, instance) -> instance_capacity
  
  # from dump_num load the proper instance
  existing_edges_filtered <- existing_edges %>%
    filter(instance == instance_capacity$instance) %>%
    mutate(capacity = capacity*instance_capacity$load_capacity_factor/1.5) %>%
    mutate(node_i = ifelse(node1<node2, node1, node2),
           node_j = ifelse(node1<node2, node2, node1)) %>%
    mutate(node1 = node_i,
           node2 = node_j) %>%
    select(-node_i, -node_j) %>%
    rename(original_capacity = capacity) %>%
    select(instance, node1, node2, original_capacity)
  
  # load solution data from file
  solution_data <- read_csv(paste0("Nominal results/detailed_results/grid_edges_heuristic_solution", dump_num, ".csv")) %>%
    mutate(node1 = ifelse(edge_i<edge_j, edge_i, edge_j),
           node2 = ifelse(edge_i<edge_j, edge_j, edge_i)) %>%
    select(-edge_i, -edge_j) %>%
    rename(updated_capacity = capacity)
  
  # combined data
  combined_origin_solution <- existing_edges_filtered %>%
    left_join(solution_data) %>%
    mutate(capacity_diff = updated_capacity - original_capacity)
  
}