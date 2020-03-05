# Analyze sunken cost data for modified IEEE power grids
library(tidyverse)

instance_list <- paste0("instance", 
                        c(24, 30, 39, 57, 118, 300), "/grid_edges.csv")

all.data <- tibble(instance_list, instance = c(24, 30, 39, 57, 118, 300)) %>%
  group_by(instance_list) %>%
  mutate(edges = map(instance_list, read_csv)) %>%
  ungroup() %>%
  select(instance, 3) %>%
  unnest()

installed.edge.cap <- all.data %>%
  filter(cost_fixed == 0) %>%
  group_by(instance) %>%
  summarize(tot_cap_installed = sum(capacity),
            tot_edges_installed = n())

potential.edges <- all.data %>%
  filter(cost_fixed > 0) %>%
  group_by(instance) %>%
  summarize(tot_potential_edges = n())

instance.edge.costs <- tibble(instance = c(30, 57, 118, 300),
                             establish.cost = c(1, 1, 10, 10),
                             upgrade.cost = 0.1) %>%
  left_join(installed.edge.cap) %>%
  mutate(total.grid.cost = establish.cost*tot_edges_installed + upgrade.cost*tot_cap_installed,
         average.edge.capacity = tot_cap_installed/tot_edges_installed) %>%
  mutate(cap.upgrade.cost = average.edge.capacity/2)



# compute total demand
tot.demand <- tibble(instance.list = paste0("instance",
                     c(24, 30, 39, 57, 118, 300), "/grid_nodes.csv")) %>%
  mutate(instance = c(24, 30, 39, 57, 118, 300)) %>%
  group_by(instance.list, instance) %>%
  mutate(nodes = map(instance.list, read_csv)) %>%
  ungroup() %>%
  unnest() %>%
  group_by(instance) %>%
  summarize(tot.demand = sum(demand))
  

  