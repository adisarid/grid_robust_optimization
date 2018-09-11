# Compare nominal infrastructure decisions to infrastructure decisions with 1/2 establish cost
library(tidyverse)
setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/analysis/")

source("grid_sunken_cost.R")

# soft equality for avoiding rounding errors
soft_equality <- function(a, b, thresh_sensitivity = 0.01){
  is_equal <- a < b + thresh_sensitivity & a > b - thresh_sensitivity
  return(is_equal)
}

# first, load the batch configurations
batch_details <- read_csv("Nominal results/dump.csv", col_names = c("dump", "value", "runtime")) %>%
  full_join(readxl::read_excel("new.batch.parameters.xlsx"), by = c("dump" = "dump_file")) %>%
  mutate(batch_type = "nominal") %>%
  bind_rows(read_csv("Half cost coef scale results/dump.csv", col_names = c("dump", "value", "runtime")) %>%
              full_join(readxl::read_excel("22-08-2018-establish_cost_sensitivity.xlsx"),
                        by = c("dump" = "dump_file")) %>%
              mutate(batch_type = "half establish cost")) %>% 
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

# load all existing edges' data into existing_edges tibble
existing_edges <- map_df(.f = function(instance_num){
  base_instance_edges <- read_csv(paste0("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/instance", instance_num, "/grid_edges.csv")) %>%
    mutate(instance = instance_num)
  return(base_instance_edges)
}, .x = c(30, 57, 118, 300))

# read infrastructure data for all heuristic solutions
# function to compute upgrade types and summarize them as a tibble
summarize_upgrade_type <- function(dump_num){
  
  # get the instance's capacity factor and instance number from dump_number
  batch_details %>%
    filter(dump == dump_num) %>%
    select(load_capacity_factor, instance, contains("capacity_coef_scale"),
           contains("factor")) -> instance_capacity
  
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
    select(instance, node1, node2, original_capacity, cost_fixed)
  
  # load solution data from file
  solution_data <- read_csv(paste0("Half cost coef scale results/detailed_results/grid_edges_heuristic_solution", dump_num, ".csv")) %>%
    mutate(node1 = ifelse(edge_i<edge_j, edge_i, edge_j),
           node2 = ifelse(edge_i<edge_j, edge_j, edge_i)) %>%
    select(-edge_i, -edge_j) %>%
    rename(updated_capacity = capacity)
  
  # combined data
  combined_origin_solution <- existing_edges_filtered %>%
    left_join(solution_data) %>%
    mutate_at(.vars = vars(updated_capacity, original_capacity), 
              .funs = funs(ifelse(is.na(.), 0, .))) %>%
    mutate(capacity_diff = updated_capacity - original_capacity) %>%
    mutate(upgrade_type = case_when(soft_equality(capacity_diff, instance_capacity$line_establish_capacity_coef_scale) ~ "Establish",
                                    soft_equality(capacity_diff, instance_capacity$line_upgrade_capacity_coef_scale) ~ "Upgrade",
                                    soft_equality(capacity_diff, 
                                                  instance_capacity$line_upgrade_capacity_coef_scale +
                                                    instance_capacity$line_establish_capacity_coef_scale) ~ "Establish and upgrade",
                                    soft_equality(capacity_diff, 0) ~ "No change",
                                    TRUE ~  "Opps")) %>%
    mutate(budget_factor = instance_capacity$budget.factor + 1,
           capacity_factor = instance_capacity$load_capacity_factor) %>%
    mutate_at(.vars = vars(budget_factor, capacity_factor),
              .funs = funs(paste0(round((. - 1)*100), "%"))) %>%
    mutate(budget_factor = paste0("Budget ", budget_factor),
           capacity_factor = paste0("Capacity ", capacity_factor)) %>% 
    mutate(edge_old_status = ifelse(cost_fixed == 1, "new", "existing")) %>%
    select(instance, capacity_factor, budget_factor, upgrade_type, edge_old_status) %>%
    mutate(dump = dump_num)
}

all_heuristic_results <- map_df(.f = summarize_upgrade_type, .x = c(1:16, 601:616)) %>%
  mutate(algorithm = "LNS")


# read infrastructure data for one-depth and lazy algorithm
read_grid_solution <- function(dump_num){
  current_instance <- batch_details$instance[batch_details$dump == dump_num]
  
  batch_details %>%
    filter(dump == dump_num) %>%
    select(load_capacity_factor, instance, contains("capacity_coef_scale"),
           contains("factor")) -> instance_capacity
  
  tmp_sol <- read_csv(paste0("Half cost coef scale results\\detailed_results\\",dump_num, ".0.csv")) %>%
    mutate(name = str_replace_all(name, "_i|_j", "_")) %>%
    filter(str_detect(name, "X|C|c")) %>%
    filter(str_detect(name, "X|.0_")) %>%
    separate(name, into = c("var_type", "edge_i", "edge_j"), sep = "_") %>%
    mutate(edge_i = as.numeric(edge_i),
           edge_j = as.numeric(edge_j)) %>%
    mutate(node1 = ifelse(edge_i<edge_j, edge_i, edge_j),
           node2 = ifelse(edge_i<edge_j, edge_j, edge_i)) %>%
    select(-edge_i, -edge_j) %>%
    spread(var_type, value) %>% 
    mutate(dump = dump_num) %>%
    mutate(upgrade_type = case_when(!is.na(X) & soft_equality(X, 1) & soft_equality(c, 0) ~ "Establish",
                                    !is.na(X) & soft_equality(X, 1) & soft_equality(c, 1) ~ "Establish and upgrade",
                                    is.na(X) & soft_equality(c, 1) ~ "Upgrade",
                                    soft_equality(c, 0) ~ "No change",
                                    TRUE ~ "Opps")) %>%
    left_join(batch_details %>% 
                select(dump, instance, load_capacity_factor, budget.factor, line_establish_cost,
                       algorithm.name), 
              by = "dump") %>%
    full_join(existing_edges %>%
                filter(instance == current_instance) %>%
                mutate(capacity = capacity*instance_capacity$load_capacity_factor/1.5) %>%
                mutate(node_i = ifelse(node1<node2, node1, node2),
                       node_j = ifelse(node1<node2, node2, node1)) %>%
                mutate(node1 = node_i,
                       node2 = node_j) %>%
                select(-node_i, -node_j) %>%
                rename(original_capacity = capacity) %>%
                select(instance, node1, node2, original_capacity, cost_fixed))
    
}

# read all data from current solutions
one_depth_lazy <- map_df(.f = read_grid_solution, .x = c(17:19, 21:23, 25:27, 29:31, 33:48, 
                                                         617:619, 621:623, 625:627, 629:631, 633:648)) %>%
  mutate(capacity_factor = paste0("Capacity ", round((load_capacity_factor-1)*100), "%")) %>%
  mutate(budget_factor = paste0("Budget ", round(budget.factor*100), "%")) %>%
  mutate(edge_old_status = ifelse(cost_fixed <= 0.01, "existing", "new")) %>%
  rename(algorithm = algorithm.name) %>%
  select(names(all_heuristic_results))


# Combined data
all_results <- one_depth_lazy %>%
  bind_rows(all_heuristic_results)


potential.edges
existing_edges %>% 
  group_by(instance) %>% 
  filter(cost_fixed == 0) %>%
  tally() %>%
  rename(tot_existing_edges = n) -> existing_edges_clean


results_summary <- all_results %>%
  mutate(upgrade_type = case_when(upgrade_type == "No change" & edge_old_status == "existing" ~ "No change-existing",
                                  upgrade_type == "No change" & edge_old_status == "new" ~ "No change-new",
                                  TRUE ~ upgrade_type)) %>%
  filter(upgrade_type != "Opps") %>%
  group_by(instance, capacity_factor, budget_factor, algorithm, dump, upgrade_type) %>%
  tally() %>%
  spread(upgrade_type, n) %>%
  mutate(cost_case = ifelse(dump >= 600, "Half", "Nominal")) %>%
  mutate_at(.vars = vars(Establish:Upgrade), .funs = funs(ifelse(is.na(.), 0, .))) %>%
  left_join(potential.edges) %>%
  left_join(existing_edges_clean) %>%
  mutate_at(.vars = vars(Establish, `Establish and upgrade`, `No change-new`),
            .funs = funs(./tot_potential_edges)) %>%
  mutate_at(.vars = vars(`No change-existing`, Upgrade),
            .funs = funs(./tot_existing_edges))

#openxlsx::write.xlsx(results_summary, "04-09-2018 - summary of upgrade decisions.xlsx")

# plot the type of upgrades nominal cost vs. half cost
results_summary_forplot <- results_summary %>%
  ungroup() %>%
  select(dump, algorithm, cost_case, Establish:Upgrade) %>%
  gather(type_upgrade, value, -dump, -algorithm, -cost_case) %>%
  filter(type_upgrade %in% c("Establish", "Establish and upgrade", "Upgrade")) %>%
  mutate(dump = dump %% 600)

ggplot(results_summary_forplot %>% filter(algorithm == "Lazy"), 
       aes(x = as.factor(dump),
           y = value, 
           fill = type_upgrade)) + 
  geom_bar(stat = "identity", position = "dodge") + 
  facet_grid(rows = vars(cost_case)) + 
  ggtitle("Decision distribution of Lazy algorithm") + 
  xlab("batch-run#")


ggplot(results_summary_forplot %>% filter(algorithm == "One.depth"), 
       aes(x = as.factor(dump),
           y = value, 
           fill = type_upgrade)) + 
  geom_bar(stat = "identity", position = "dodge") + 
  facet_grid(rows = vars(cost_case)) + 
  ggtitle("Decision distribution of one depth algorithm") +
  xlab("batch-run#")

ggplot(results_summary_forplot %>% filter(algorithm == "LNS"), 
       aes(x = as.factor(dump),
           y = value, 
           fill = type_upgrade)) + 
  geom_bar(stat = "identity", position = "dodge") + 
  facet_grid(rows = vars(cost_case)) + 
  ggtitle("Decision distribution of LNS algorithm") +
  xlab("batch-run#")
