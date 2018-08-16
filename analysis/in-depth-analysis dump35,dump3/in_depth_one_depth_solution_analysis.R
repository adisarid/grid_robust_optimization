# In - depth analysis of 1depth approximation results
# Used to compare the scenarios and show the solution versus the equivalent solution of the heuristic
# I chose a specific instance, dump#35 (one depth approx) and dump#3 (heuristic upper bound)

library(tidyverse)

setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/analysis/in-depth-analysis dump35,dump3/")

# read the original grid
grid_coords <- read_csv("coordinates.csv")
original_grid <- read_csv("grid_edges.csv") %>%
  left_join(grid_coords %>% rename(x_start = x, y_start = y), by = c("node1" = "label")) %>%
  left_join(grid_coords %>% rename(x_end = x, y_end = y), by = c("node2" = "label"))

# heuristic supply per scenario
heuristic_supply_per_scenario <- read_csv("2018-08-15-19-55-21 - instance118heuristic_sol_per_scenario_statistics.csv") %>%
  rename(value = supply) %>%
  mutate(type = "heuristic")


# read the solution of the one depth approximation
one_depth_sol <- read_csv("13-08-2018 04-37-50-20822.785 - -35.0-temp_sol.csv")
one_depth_supply <- read_csv("13-08-2018 04-37-50-20822.785 - supply.csv") %>%
  bind_rows(heuristic_supply_per_scenario)

# compare the supply of 1depth and full cascade per scenario
one_depth_supply_tbl <- one_depth_supply %>%
  spread(type, value) %>%
  left_join(heuristic_supply_per_scenario %>% rename(`LNS heuristic` = value) %>% select(-type))


scenario_statistics <- ggplot(one_depth_supply, aes(fill = type, y = value, x = scenario)) + 
  geom_bar(color = "black", stat = "identity", position = "dodge") + 
  ggtitle("Per scenario statistics:\nOne-depth internal objective vs. supplied load after full cascade",
          subtitle = "Instance 118, run #35")

# visualize the different solutions using a mathematical graph
# The original
original_plot <- ggplot(original_grid, aes(x = x_start, y = y_start, xend = x_end, yend = y_end)) + 
  geom_segment(linetype = "dashed") + 
  geom_point(data = grid_coords, aes(x, y), inherit.aes = F) + 
  geom_label(data = grid_coords, aes(label = label, x, y), inherit.aes = F) + 
  ggtitle("The IEEE118 original power grid",
          subtitle = "Parameters: budget 515.94, load capacity factor 5%,\nline upgrade 35.2, line establishment 70.4")

# The one-depth solution
one_depth_concentrate <- one_depth_sol %>%
  filter(str_detect(name, "X|c")) %>%
  filter(str_detect(name, "_j")) %>% 
  mutate(var_type = case_when(str_detect(name, "X") ~ "X",
                              str_detect(name, "c") ~ "C")) %>%
  mutate(name = str_replace_all(name, "X_i|c|_i", "")) %>%
  separate(name, into = c("edge_i", "edge_j"), sep = fixed("_j")) %>%
  mutate(min_i = if_else(edge_i<edge_j, edge_i, edge_j),
         max_j = if_else(edge_i<edge_j, edge_j, edge_i)) %>%
  select(-edge_i,-edge_j) %>%
  mutate(edge_i = as.numeric(min_i),
         edge_j = as.numeric(max_j)) %>%
  filter(value > 0) %>%
  left_join(grid_coords %>% rename(x_start = x, y_start = y), by = c("edge_i" = "label")) %>%
  left_join(grid_coords %>% rename(x_end = x, y_end = y), by = c("edge_j" = "label")) %>%
  spread(var_type, value) %>%
  mutate(upgrade_type = case_when(is.na(X) ~ "upgrade existing",
                                  is.na(C) ~ "establish",
                                  !is.na(X) & !is.na(C) ~ "establish and upgrade"))

one_depth_plot <- original_plot + 
  geom_segment(data = one_depth_concentrate %>% 
                 add_row(x_start = 0.5, y_start = 0.5, 
                         x_end = 0.5, y_end = 0.5,
                         upgrade_type = "establish"), 
               aes(x = x_start, y = y_start,
                   xend = x_end, yend = y_end, color = upgrade_type)) + 
  ggtitle("The IEEE118 upgraded power grid,\nOne-depth approximation optimization",
          subtitle = "Run #35")

budget_used <- one_depth_concentrate %>%
  mutate(tot_cost = case_when(upgrade_type == "upgrade existing" ~ 3.52, 
                              upgrade_type == "establish" ~ 10,
                              upgrade_type == "establish and upgrade" ~ 13.52))
sum(budget_used$tot_cost)  # Budget is almost fully utilized


# The heuristic solution - ***IMPORTANT*** old capacity is factored by 0.7 this is for dump#3
load_capacity_factor <- 0.7
heuristic_solution <- read_csv("grid_edges_heuristic_solution.csv") %>% 
  rename(new_capacity = capacity) %>%
  mutate(min_i = if_else(edge_i<edge_j, edge_i, edge_j),
         max_j = if_else(edge_i<edge_j, edge_j, edge_i)) %>%
  select(-edge_i,-edge_j) %>%
  rename(edge_i = min_i,
         edge_j = max_j) %>%
  full_join(original_grid %>% 
              rename(edge_i = node1, 
                     edge_j = node2) %>%
              mutate(min_i = if_else(edge_i<edge_j, edge_i, edge_j),
                     max_j = if_else(edge_i<edge_j, edge_j, edge_i)) %>%
              select(-edge_i,-edge_j) %>%
              rename(edge_i = min_i,
                     edge_j = max_j) %>%
              mutate(old_capacity = capacity*load_capacity_factor) %>%
              select(-capacity)) %>% 
  mutate(new_capacity = ifelse(is.na(new_capacity), old_capacity, new_capacity)) %>%
  mutate(added_capacity = new_capacity - old_capacity) %>%
  mutate(added_capacity = ifelse(added_capacity < 0.01, 0, added_capacity)) %>%
  select(edge_i, edge_j, starts_with("cost"),
         starts_with("x_"), starts_with("y_"), old_capacity, new_capacity, added_capacity) %>%
  mutate(upgrade_type = case_when(old_capacity == 0 & added_capacity >= 100 ~ "establish and upgrade",
                                  old_capacity == 0 & added_capacity < 100 ~ "establish",
                                  old_capacity > 0 & added_capacity > 0 ~ "upgrade existing"))

heuristic_plot <- original_plot + 
  geom_segment(data = heuristic_solution %>%
                 filter(!is.na(upgrade_type)), 
               aes(x = x_start, y = y_start,
                   xend = x_end, yend = y_end, color = upgrade_type))+ 
  ggtitle("The IEEE118 upgraded power grid,\nLNS heuristic optimization",
          subtitle = "Run #3")

# all plots generated in this script:
p = list(scenario_statistics, original_plot, one_depth_plot, heuristic_plot)

ggsave(p[[1]], file = "c:/temp/1.png", width = 14, height = 7, units = "in")
ggsave(p[[2]], file = "c:/temp/2.png")
ggsave(p[[3]], file = "c:/temp/3.png")
ggsave(p[[4]], file = "c:/temp/4.png")

# specific tables generated in this script:
one_depth_supply_tbl
one_depth_concentrate
heuristic_solution





# check in all one depth solutions if there are edges which are established but not upgraded:
dump_file <- 33:48

create_one_depth_tibble <- function(dump_file){
  one_depth_concentrate_tmp <- read_csv(paste0("c:/temp/grid_cascade_output/detailed_results/", dump_file, ".0.csv")) %>%
    filter(str_detect(name, "X|c")) %>%
    filter(str_detect(name, "_j")) %>% 
    mutate(var_type = case_when(str_detect(name, "X") ~ "X",
                                str_detect(name, "c") ~ "C")) %>%
    mutate(name = str_replace_all(name, "X_i|c|_i", "")) %>%
    separate(name, into = c("edge_i", "edge_j"), sep = fixed("_j")) %>%
    mutate(min_i = if_else(edge_i<edge_j, edge_i, edge_j),
           max_j = if_else(edge_i<edge_j, edge_j, edge_i)) %>%
    select(-edge_i,-edge_j) %>%
    mutate(edge_i = as.numeric(min_i),
           edge_j = as.numeric(max_j)) %>%
    filter(value > 0) %>%
    spread(var_type, value) %>%
    mutate(upgrade_type = case_when(is.na(X) ~ "upgrade existing",
                                    is.na(C) ~ "establish",
                                    !is.na(X) & !is.na(C) ~ "establish and upgrade")) %>%
    mutate(dump_file = dump_file)
  return(one_depth_concentrate_tmp)
}

one_depth_upgrades <- map_df(.f = create_one_depth_tibble, .x = 33:48) %>%
  left_join(readxl::read_xlsx("../new.batch.parameters.xlsx") %>% 
              select(dump_file, instance))

one_depth_upgrades_plot <- ggplot(one_depth_upgrades %>% mutate(instance_type = paste0(instance, "_", dump_file)), 
       aes(x = factor(instance_type), fill = upgrade_type)) + 
  geom_bar(stat = "count", position = "fill") +
   scale_y_continuous(labels = scales::percent)

ggsave(one_depth_upgrades_plot, file = "c:/temp/5.png", width = 14, height = 7, units = "in")
