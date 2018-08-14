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


# read the solution of the heuristic
heuristic_solution <- read_csv("grid_edges_heuristic_solution.csv")

# read the solution of the one depth approximation
one_depth_sol <- read_csv("13-08-2018 04-37-50-20822.785 - -35.0-temp_sol.csv")
one_depth_supply <- read_csv("13-08-2018 04-37-50-20822.785 - supply.csv")

# compare the supply of 1depth and full cascade per scenario
one_depth_supply_tbl <- one_depth_supply %>%
  spread(type, value) %>%
  mutate(percent_full = fullcascade/`1depth`)

ggplot(one_depth_supply, aes(fill = type, y = value, x = scenario)) + 
  geom_bar(color = "black", stat = "identity", position = "dodge")

# visualize the different solutions using a mathematical graph
# The original
original_plot <- ggplot(original_grid, aes(x = x_start, y = y_start, xend = x_end, yend = y_end)) + 
  geom_segment(linetype = "dashed") + 
  geom_point(data = grid_coords, aes(x, y), inherit.aes = F) + 
  geom_label(data = grid_coords, aes(label = label, x, y), inherit.aes = F)

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
                   xend = x_end, yend = y_end, color = upgrade_type))

budget_used <- one_depth_concentrate %>%
  mutate(tot_cost = case_when(upgrade_type == "upgrade existing" ~ 3.52, 
                              upgrade_type == "establish" ~ 10,
                              upgrade_type == "establish and upgrade" ~ 13.52))
sum(budget_used$tot_cost)  # Budget is almost fully utilized


# The heuristic solution - ***IMPORTANT*** old capacity is factored by 0.7 this is for dump#3
load_capacity_factor <- 0.7
heuristic_solution %>% 
  mutate(new_capacity = capacity) %>%
  full_join(original_grid %>% 
              rename(edge_i = node1, 
                     edge_j = node2) %>%
              mutate(old_capacity = capacity*load_capacity_factor)) %>% View()

            