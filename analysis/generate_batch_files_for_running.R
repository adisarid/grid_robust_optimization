# generate combinations to export to batch files

# Apollo combinations
apollo <- expand.grid(instance = c("instance24", "instance300"),
                      budget = c(5, 15, 50, 100, 200),
                      upgrade_selection_bias = c(0.25, 0.5),
                      min_neighbors = c(10, 25, 50)) %>%
  arrange(instance) %>%
  mutate(command = paste0("python robustness_heuristic.py --instance_location ", 
                          instance,
                          " --budget ",
                          budget,
                          " --upgrade_selection_bias ",
                          upgrade_selection_bias,
                          " --min_neighbors ",
                          min_neighbors))



# Beatrix combinations
beatrix <- expand.grid(instance = c("instance30", "instance118"),
                       budget = c(5, 15, 50, 100, 200),
                       upgrade_selection_bias = c(0.25, 0.5),
                       min_neighbors = c(10, 25, 50)) %>%
  arrange(instance) %>%
  mutate(command = paste0("python robustness_heuristic.py --instance_location ", 
                          instance,
                          " --budget ",
                          budget,
                          " --upgrade_selection_bias ",
                          upgrade_selection_bias,
                          " --min_neighbors ",
                          min_neighbors))

# Gaya combinations
gaya <- expand.grid(instance = c("instance39", "instance57"),
                    budget = c(5, 15, 50, 100, 200),
                    upgrade_selection_bias = c(0.25, 0.5),
                    min_neighbors = c(10, 25, 50)) %>%
  arrange(instance) %>%
  mutate(command = paste0("python robustness_heuristic.py --instance_location ", 
                          instance,
                          " --budget ",
                          budget,
                          " --upgrade_selection_bias ",
                          upgrade_selection_bias,
                          " --min_neighbors ",
                          min_neighbors))
