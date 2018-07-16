# generate combinations to export to batch files
setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")

# new run batches after conversation w/ Michal.
# each run will be associated with a dump_serieal.
# All the rest of the parameters will be contained in this tibble.

source("grid_sunken_cost.R")

# use instance.edge.costs from the sourced file
heuristic.batch <- instance.edge.costs %>%
  rename(line_establish_cost_coef_scale = establish.cost) %>%
  select(instance, line_establish_cost_coef_scale, total.grid.cost)
  
heuristic.batch.complete <- heuristic.batch %>%
  mutate(runcommand = paste0(
    "python robustness_heuristic_upper_bound.py --instance_location instance", instance,
    " --budget ", total.grid.cost*0.2, 
    " --load_capacity_factor ", 1,
    " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale
  ),
  budget = 0.2) %>%
  bind_rows(
    heuristic.batch %>%
      mutate(runcommand = paste0(
        "python robustness_heuristic_upper_bound.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.3, 
        " --load_capacity_factor ", 1,
        " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale),
        budget = 0.3),
    heuristic.batch %>%
      mutate(runcommand = paste0(
        "python robustness_heuristic_upper_bound.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.2, 
        " --load_capacity_factor ", 1.2/1.5,
        " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale),
        budget = 0.2),
    heuristic.batch %>%
      mutate(runcommand = paste0(
        "python robustness_heuristic_upper_bound.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.3, 
        " --load_capacity_factor ", 1.2/1.5,
        " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale),
        budget = 0.3)
  )


lazy.program.batch <- instance.edge.costs %>%
  rename(line_establish_cost_coef_scale = establish.cost) %>%
  mutate(line_establish_capacity_coef_scale = average.edge.capacity,
         line_upgrade_capacity_coef_scale = average.edge.capacity*0.5) %>%
  select(instance, line_establish_cost_coef_scale, total.grid.cost,
         contains("_capacity_coef_scale"))

lazy.program.batch.complete <- lazy.program.batch %>%
  mutate(runcommand = paste0(
    "python main_program.py --instance_location instance", instance,
    " --budget ", total.grid.cost*0.2, 
    " --load_capacity_factor ", 1,
    " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale,
    " --line_establish_capacity_coef_scale ", round(line_establish_capacity_coef_scale),
    " --line_upgrade_capacity_coef_scale ", round(line_upgrade_capacity_coef_scale)
  ),
  budget = 0.2) %>%
  bind_rows(
    lazy.program.batch %>%
      mutate(runcommand = paste0(
        "python main_program.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.3, 
        " --load_capacity_factor ", 1,
        " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale,
        " --line_establish_capacity_coef_scale ", round(line_establish_capacity_coef_scale),
        " --line_upgrade_capacity_coef_scale ", round(line_upgrade_capacity_coef_scale)
      ),
      budget = 0.3)
  ) %>%
  bind_rows(
    lazy.program.batch %>%
      mutate(runcommand = paste0(
        "python main_program.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.2, 
        " --load_capacity_factor ", 1.2/1.5,
        " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale,
        " --line_establish_capacity_coef_scale ", round(line_establish_capacity_coef_scale),
        " --line_upgrade_capacity_coef_scale ", round(line_upgrade_capacity_coef_scale)
      ),
      budget = 0.2)
  ) %>%
  bind_rows(
    lazy.program.batch %>%
      mutate(runcommand = paste0(
        "python main_program.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.3, 
        " --load_capacity_factor ", 1.2/1.5,
        " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale,
        " --line_establish_capacity_coef_scale ", round(line_establish_capacity_coef_scale),
        " --line_upgrade_capacity_coef_scale ", round(line_upgrade_capacity_coef_scale)
      ),
      budget = 0.3)
  )


one.depth.batch <- instance.edge.costs %>%
  mutate(line_upgrade_capacity_upper_bound = average.edge.capacity*0.5) %>%
  mutate(line_establish_capacity_coef_scale = average.edge.capacity) %>%
  rename(line_establish_cost_coef_scale = establish.cost)

one.depth.complete <- one.depth.batch %>%
  mutate(runcommand = paste0(
    "python main_program_one_depth_cascade.py --instance_location instance", instance,
    " --budget ", total.grid.cost*0.2, 
    " --load_capacity_factor ", 1,
    " --line_upgrade_capacity_upper_bound ", round(line_upgrade_capacity_upper_bound),
    " --line_establish_capacity_coef_scale ", round(line_establish_capacity_coef_scale),
    " --line_establish_cost_coef_scale ", round(line_establish_cost_coef_scale)
  ),
  budget = 0.2) %>%
  bind_rows(
    one.depth.batch %>%
      mutate(runcommand = paste0(
        "python main_program_one_depth_cascade.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.3, 
        " --load_capacity_factor ", 1,
        " --line_upgrade_capacity_upper_bound ", round(line_upgrade_capacity_upper_bound),
        " --line_establish_capacity_coef_scale ", round(line_establish_capacity_coef_scale),
        " --line_establish_cost_coef_scale ", round(line_establish_cost_coef_scale)
      ),
      budget = 0.3),
    one.depth.batch %>%
      mutate(runcommand = paste0(
        "python main_program_one_depth_cascade.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.2, 
        " --load_capacity_factor ", 1.2/1.5,
        " --line_upgrade_capacity_upper_bound ", round(line_upgrade_capacity_upper_bound),
        " --line_establish_capacity_coef_scale ", round(line_establish_capacity_coef_scale),
        " --line_establish_cost_coef_scale ", round(line_establish_cost_coef_scale)
      ),
      budget = 0.2),
    one.depth.batch %>%
      mutate(runcommand = paste0(
        "python main_program_one_depth_cascade.py --instance_location instance", instance,
        " --budget ", total.grid.cost*0.3, 
        " --load_capacity_factor ", 1.2/1.5,
        " --line_upgrade_capacity_upper_bound ", round(line_upgrade_capacity_upper_bound),
        " --line_establish_capacity_coef_scale ", round(line_establish_capacity_coef_scale),
        " --line_establish_cost_coef_scale ", round(line_establish_cost_coef_scale)
      ),
      budget = 0.3)
  )
  


complete.batch <- one.depth.complete %>%
  bind_rows(
    heuristic.batch.complete,
    lazy.program.batch.complete
  ) %>%
  select(runcommand, budget, instance) %>%
  mutate(load_capacity_factor = case_when(str_detect(runcommand, "--load_capacity_factor 1") ~ 1,
                                          TRUE ~ 0.8)) %>%
  left_join(instance.edge.costs %>%
              select(instance, total.grid.cost)) %>%
  mutate(algorithm = case_when(str_detect(runcommand, "robustness") ~ "LNS heuristic",
                               str_detect(runcommand, "one_depth") ~ "One depth approximation",
                               str_detect(runcommand, "main_program.py") ~ "Lazy callbacks"),
         dump = seq_along(instance)) %>%
  mutate(runcommand = paste0(runcommand, " --dump_file ", dump))
  
openxlsx::write.xlsx(complete.batch, "new.batch.parameters.xlsx")

write(complete.batch$runcommand, "16-07-2018-new batch.bat")



# # Apollo combinations
# apollo <- expand.grid(instance = c("instance24", "instance300"),
#                       budget = c(5, 15, 50, 100, 200),
#                       upgrade_selection_bias = c(0.25, 0.5),
#                       min_neighbors = c(10, 25, 50)) %>%
#   arrange(instance) %>%
#   mutate(command = paste0("python robustness_heuristic.py --instance_location ", 
#                           instance,
#                           " --budget ",
#                           budget,
#                           " --upgrade_selection_bias ",
#                           upgrade_selection_bias,
#                           " --min_neighbors ",
#                           min_neighbors,
#                           " --export_results_tracking c:\\temp\\grid_cascade_output\\hr_res_apollo.csv"))
# write_csv(tibble(apollo$command), path = "apollo_batch.bat", col_names = F)
# 
# 
# # Beatrix combinations
# beatrix <- expand.grid(instance = c("instance30", "instance118"),
#                        budget = c(5, 15, 50, 100, 200),
#                        upgrade_selection_bias = c(0.25, 0.5),
#                        min_neighbors = c(10, 25, 50)) %>%
#   arrange(instance) %>%
#   mutate(command = paste0("python robustness_heuristic.py --instance_location ", 
#                           instance,
#                           " --budget ",
#                           budget,
#                           " --upgrade_selection_bias ",
#                           upgrade_selection_bias,
#                           " --min_neighbors ",
#                           min_neighbors,
#                           " --export_results_tracking c:\\temp\\grid_cascade_output\\hr_res_beatrix.csv"))
# write_csv(tibble(beatrix$command), path = "beatrix_batch.bat", col_names = F)
# 
# # Gaya combinations
# gaya <- expand.grid(instance = c("instance39", "instance57"),
#                     budget = c(5, 15, 50, 100, 200),
#                     upgrade_selection_bias = c(0.25, 0.5),
#                     min_neighbors = c(10, 25, 50)) %>%
#   arrange(instance) %>%
#   mutate(command = paste0("python robustness_heuristic.py --instance_location ", 
#                           instance,
#                           " --budget ",
#                           budget,
#                           " --upgrade_selection_bias ",
#                           upgrade_selection_bias,
#                           " --min_neighbors ",
#                           min_neighbors,
#                           " --export_results_tracking c:\\temp\\grid_cascade_output\\hr_res_gaya.csv"))
# write_csv(tibble(gaya$command), path = "gaya_batch.bat", col_names = F)
