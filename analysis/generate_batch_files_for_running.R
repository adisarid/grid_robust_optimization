# generate combinations to export to batch files
setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")
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
                          min_neighbors,
                          " --export_results_tracking c:\\temp\\grid_cascade_output\\hr_res_apollo.csv"))
write_csv(tibble(apollo$command), path = "apollo_batch.bat", col_names = F)


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
                          min_neighbors,
                          " --export_results_tracking c:\\temp\\grid_cascade_output\\hr_res_beatrix.csv"))
write_csv(tibble(beatrix$command), path = "beatrix_batch.bat", col_names = F)

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
                          min_neighbors,
                          " --export_results_tracking c:\\temp\\grid_cascade_output\\hr_res_gaya.csv"))
write_csv(tibble(gaya$command), path = "gaya_batch.bat", col_names = F)
