# Script for generating a batch file for computation of an upper bound using compute_grid_supply_from_gpickle

library(tidyverse)

setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")

source("analysis/grid_sunken_cost.R")

prep.grid.data <- instance.edge.costs %>%
  select(instance, establish.cost, upgrade.cost, tot_cap_installed, tot_edges_installed)

base.batch.options <- expand.grid(instance = c(30, 57, 118, 300), 
                                  load_capacity_factor = c(0.7, 0.8)) %>%
  left_join(prep.grid.data) %>%
  mutate(tot_cap_installed = tot_cap_installed*load_capacity_factor) %>%
  mutate(average.edge.capacity = tot_cap_installed/tot_edges_installed) %>%
  rename(line_establish_cost_coef_scale = establish.cost) %>%
  mutate(line_establish_capacity_coef_scale = average.edge.capacity,
         line_upgrade_capacity_coef_scale = average.edge.capacity*0.5) %>% 
  mutate(dump_file = seq_along(instance)+500) %>%
  left_join(tot.demand) %>%
  left_join(potential.edges) %>%
  mutate(line_establish_cost = line_establish_cost_coef_scale + upgrade.cost*line_establish_capacity_coef_scale,
         line_upgrade_cost = upgrade.cost*line_upgrade_capacity_coef_scale) %>%
  mutate(max.expanse = 
           tot_potential_edges*line_establish_cost +
           (tot_edges_installed + tot_potential_edges)*line_upgrade_cost) %>%
  mutate(runcommand = paste0("python compute_grid_supply_from_gpickle.py",
                             " --brute_force_upper_bound",
                             " --instance_location instance", instance,
                             " --load_capacity_factor ", load_capacity_factor,
                             " --line_upgrade_capacity_coef_scale ", line_upgrade_capacity_coef_scale,
                             " --line_establish_capacity_coef_scale ", line_establish_capacity_coef_scale,
                             " --output_file c:/temp/grid_cascade_output/upper_bound/", dump_file, ".csv"))

# write(base.batch.options$runcommand, "../compute_upper_bound.bat")
# openxlsx::write.xlsx(x = base.batch.options %>%
#                        mutate(load_capacity_factor = load_capacity_factor*1.5), 
#                      file = "22-08-2018-match_upper_bound_new.batch.parameters.xlsx")


# read the results after running the upper bound computation
upper_bounds <- map_df(.f = function(filename){
  scenario_res <- read_csv(filename) %>%
    summarize(upper_bound = mean(supply)) %>%
    mutate(dump_file = str_replace_all(filename, "c:/temp/grid_cascade_output/upper_bound/|.csv", ""))
  return(scenario_res)
  },
  .x = paste0("c:/temp/grid_cascade_output/upper_bound/", base.batch.options$dump_file, ".csv")) %>%
  mutate(dump_file = as.numeric(dump_file)) %>%
  left_join(base.batch.options) %>%
  select(instance, load_capacity_factor, 
         line_upgrade_capacity_coef_scale, line_establish_capacity_coef_scale, 
         upper_bound) %>%
  mutate_at(.vars = vars(ends_with("_scale")), .funs = funs(round(., 2))) %>%
  right_join(readxl::read_excel("new.batch.parameters.xlsx") %>%
              select(instance, load_capacity_factor, 
                     line_upgrade_capacity_coef_scale, line_establish_capacity_coef_scale,
                     tot.demand, budget.constraint) %>%
               mutate_at(.vars = vars(ends_with("_scale")), .funs = funs(round(., 2)))) %>%
  arrange(instance, load_capacity_factor, budget.constraint) %>%
  unique() %>%
  mutate(pseudo_upper_bound_prcnt = upper_bound/tot.demand)

write.csv(upper_bounds$pseudo_upper_bound_prcnt, file = "clipboard", row.names = FALSE)
  
