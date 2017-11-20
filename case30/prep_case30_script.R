# prep the case30 ieee test node feeder for the PGRO2 algorithm run
setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/case30/")

# prep grid nodes
nodes.raw <- read_csv("case30_bus.csv") %>%
  select(`bus number`,
         `Pd real power demand MW`)

nodes.gen.raw <- read_csv("case30_gen.csv") %>%
  select(`bus number`, Pmax)

grid_nodes <- nodes.raw %>%
  full_join(nodes.gen.raw) %>%
  replace_na(list(`Pd real power demand MW` = 0, Pmax = 0)) %>%
  mutate(gen_upgrade_ub = 0, gen_upgrade_cost_fixed = 0, gen_upgrade_cost_linear = 0) %>%
  rename(node = `bus number`,
         demand = `Pd real power demand MW`,
         gen_capacity = Pmax)
write_excel_csv(x = grid_nodes, path = "grid_nodes.csv")

edges.raw <- read_csv("case30_branch.csv") %>%
  mutate(node1 = ifelse(`from node`<`to node`, `from node`, `to node`),
         node2 = ifelse(`from node`<`to node`, `to node`, `from node`)) %>%
  select(-`from node`, -`to node`) %>%
  mutate(cost_fixed = 0, cost_linear = 0, capacity = 100) %>% # TBD update capacity later on
  select(node1, node2, capacity, reactance, cost_fixed, cost_linear)

write_excel_csv(edges.raw, path = "grid_edges.csv")

set.seed(1) # create random failure scenarios:
scenario_failures <- 1:5 %>%
  map_df(~ cbind(.,sample_n(size = 4, edges.raw[,1:3]))) # randomize failure scenarios

write_excel_csv(scenario_failures, "scenario_failures.csv")

scenario_probabilies <- tibble(scenario = 1:5, probability = 0.1) # each scenario with a probability of 10%
write_excel_csv(scenario_probabilies, "scenario_probabilities.csv")

additional_params <- tibble(param_name = "C", param_value = 5)  # add up to 5 new edges
write_excel_csv(additional_params, "additional_params.csv")

# this part is used to update the edge capacities, AFTER initial solution was found to the previous version
# (previous version had capacity = 100 set arbitrarily)
# I will arbitrarily set max capacity as 30% above nominal

NOMINAL.FACTOR = 1.3

library(stringr)

extract.to.df <- function(list2) {
  data.frame(node1 = list2[[1]][1], node2 = list2[[1]][2])
}

grid.solution <- read_csv("initial_flow_solution.csv") %>%
  mutate(prep.name = str_replace(name, fixed("f('"), "")) %>%
  mutate(prep.name = str_replace(prep.name, fixed("')"), "")) %>%
  mutate(prep.name = str_replace(prep.name, fixed("', '"), "|")) %>%
  filter(!str_detect(prep.name, fixed("theta"))) %>%
  mutate(nodes = str_split(prep.name, fixed("|"))) %>%
  mutate(node1 = NA, node2 = NA)

# fuck me. I don't know how to do this with purrr or do
for (i in 1:NROW(grid.solution)){
  grid.solution$node1[i] <- grid.solution$nodes[[i]][1]
  grid.solution$node2[i] <- grid.solution$nodes[[i]][2]
}

grid.solution <- grid.solution %>%
  select(node1, node2, value) %>%
  mutate(capacity = ceiling(abs(value)*NOMINAL.FACTOR)) %>%
  select(-value) %>%
  mutate(node1 = as.numeric(node1),
         node2 = as.numeric(node2))

edges.updated <- edges.raw %>%
  select(-capacity) %>% 
  left_join(grid.solution) %>%
  left_join(grid.solution,
            by = c("node1" = "node2", "node2" = "node1")) %>%
  mutate(capacity = ifelse(is.na(capacity.x), capacity.y, capacity.x)) %>%
  select(node1, node2, capacity, reactance, cost_fixed, cost_linear)

# Randomize 15 new edges to be examined. First create all possible pairs
possible.pairs <- expand.grid(node1 = 1:max(grid_nodes$node), node2 = 1:max(grid_nodes$node)) %>%
  unique() %>%
  filter(node1 < node2) %>% left_join(edges.updated) %>%
  filter(is.na(capacity)) %>%
  sample_n(size = 15) %>%
  mutate(capacity = 0, reactance = 1, cost_fixed = 0.1, cost_linear = 0.9) %>%
  bind_rows(edges.updated)

write_excel_csv(possible.pairs, path = "grid_edges.csv")
