# generate combinations to export to batch files
setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")

# new run batches after conversation w/ Michal.
# each run will be associated with a dump_serieal.
# All the rest of the parameters will be contained in this tibble.

source("analysis/grid_sunken_cost.R")

# use instance.edge.costs, tot.demand from the sourced file

prep.grid.data <- instance.edge.costs %>%
  select(instance, establish.cost, upgrade.cost, tot_cap_installed, tot_edges_installed)

base.batch.options <- expand.grid(instance = c(30, 57, 118, 300), 
                                  load_capacity_factor = c(0.7, 0.8),
                                  budget.factor = c(0.3, 0.5),
                                  algorithm = c("robustness_heuristic_upper_bound.py --time_limit 1",
                                                "main_program.py --mip_emphasis 1 --time_limit 1 --export_results_file",
                                                "main_program_one_depth_cascade.py --time_limit 1 --export_results_file --export_final_grid timestamped")) %>%
  left_join(prep.grid.data) %>%
  mutate(tot_cap_installed = tot_cap_installed*load_capacity_factor) %>%
  mutate(average.edge.capacity = tot_cap_installed/tot_edges_installed) %>%
  rename(line_establish_cost_coef_scale = establish.cost) %>%
  mutate(line_establish_capacity_coef_scale = average.edge.capacity,
         line_upgrade_capacity_coef_scale = average.edge.capacity*0.5) %>% 
  mutate(dump_file = seq_along(instance)) %>%
  left_join(tot.demand) %>%
  left_join(potential.edges) %>%
  mutate(line_establish_cost = line_establish_cost_coef_scale + upgrade.cost*line_establish_capacity_coef_scale,
         line_upgrade_cost = upgrade.cost*line_upgrade_capacity_coef_scale) %>%
  mutate(max.expanse = 
           tot_potential_edges*line_establish_cost +
           (tot_edges_installed + tot_potential_edges)*line_upgrade_cost) %>%
  mutate(budget.constraint = budget.factor*max.expanse) %>%
  mutate(runcommand = paste0("python ", algorithm,
                             " --instance_location instance", instance,
                             " --budget ", budget.constraint,
                             " --load_capacity_factor ", load_capacity_factor,
                             " --line_upgrade_capacity_coef_scale ", line_upgrade_capacity_coef_scale,
                             " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale,
                             " --line_establish_capacity_coef_scale ", line_establish_capacity_coef_scale,
                             " --dump_file ", dump_file))

write(base.batch.options$runcommand[base.batch.options$algorithm != 
                                      "main_program_one_depth_cascade.py --time_limit 1 --export_results_file --export_final_grid timestamped"], "../algorithm_comparison.bat")
openxlsx::write.xlsx(x = base.batch.options, file = "16-08-2018-new.batch.parameters.xlsx")


# lazy algorithm - to compare node select and variable select strategies
lazy.search.strategy.compare <- tibble(param = "node_select_strategy", param_value = c(0, 2:3)) %>%
  bind_rows(tibble(param = "variable_select_strategy", param_value = -1:4),
            tibble(param = "mip_emphasis", param_value = 1:4)) %>%
  mutate(dump_file = 100 + seq_along(param)) %>%
  mutate(runcommand = 
           paste0("python main_program.py --instance_location instance118 --budget 566.933899441341 --load_capacity_factor 0.8 --line_upgrade_capacity_coef_scale 40.2301675977654 --line_establish_cost_coef_scale 10 --line_establish_capacity_coef_scale 80.4603351955307", 
                  " --", param, " ", param_value,
                  " --dump_file ", dump_file),
         tot.demand = 4242)

write_csv(lazy.search.strategy.compare, "01-08-2018 - compare branch parameters.csv")

write(lazy.search.strategy.compare$runcommand, "../lazy_compare_strategies.bat")

lazy.search.strategy2.compare <- tibble(param = "node_select_strategy", param_value = c(0, 2:3)) %>%
  bind_rows(tibble(param = "variable_select_strategy", param_value = -1:4),
            tibble(param = "mip_emphasis", param_value = 1:4)) %>%
  mutate(dump_file = 120 + seq_along(param)) %>%
  mutate(runcommand = 
           paste0("python main_program.py --instance_location instance30 --budget 22.9226341463415 --load_capacity_factor 0.8 --line_upgrade_capacity_coef_scale 8.8390243902439 --line_establish_cost_coef_scale 1 --line_establish_capacity_coef_scale 17.6780487804878", 
                  " --", param, " ", param_value,
                  " --dump_file ", dump_file),
         tot.demand = 189.20)

write_csv(lazy.search.strategy2.compare, "02-08-2018 - compare branch parameters - instance30.csv")
write(lazy.search.strategy2.compare$runcommand, "../lazy_compare_strategies_instance30.bat")


# generating a table of costs to export to latex document
export_tbl <- base.batch.options %>% 
  filter(load_capacity_factor == 0.8) %>%
  select(instance, average.edge.capacity, tot_edges_installed, tot_potential_edges, line_establish_cost, line_upgrade_cost, max.expanse, load_capacity_factor) %>% 
    unique() %>% 
    mutate(load_capacity_factor = load_capacity_factor*1.5) %>% 
  select(-load_capacity_factor) %>%
  mutate(upgrade_establish_ratio = line_upgrade_cost/line_establish_cost) %>%
  mutate_at(.vars = c(2, 5:8), .funs = funs(round(., 2)))
knitr::kable(export_tbl, "latex", booktabs = T)






# generate batch file for comparing the effect of changing the parameter "cost coef scale",
# for the one-depth-cascade algorithm:
one_depth_cost_coef_comparison <- expand.grid(instance = c(30, 57, 118, 300), 
                                  load_capacity_factor = 0.7,
                                  budget.factor = 0.3,
                                  algorithm = "main_program_one_depth_cascade.py --time_limit 1 --export_results_file --export_final_grid timestamped",
                                  cost_coef_multiplier = c(0.5, 1)) %>%
  left_join(prep.grid.data) %>%
  mutate(tot_cap_installed = tot_cap_installed*load_capacity_factor) %>%
  mutate(average.edge.capacity = tot_cap_installed/tot_edges_installed) %>%
  mutate(line_establish_cost_coef_scale = establish.cost*cost_coef_multiplier) %>%
  mutate(line_establish_capacity_coef_scale = average.edge.capacity,
         line_upgrade_capacity_coef_scale = average.edge.capacity*0.5) %>% 
  mutate(dump_file = seq_along(instance)) %>%
  left_join(tot.demand) %>%
  left_join(potential.edges) %>%
  mutate(line_establish_cost = line_establish_cost_coef_scale + upgrade.cost*line_establish_capacity_coef_scale,
         line_upgrade_cost = upgrade.cost*line_upgrade_capacity_coef_scale) %>%
  mutate(max.expanse = 
           tot_potential_edges*line_establish_cost +
           (tot_edges_installed + tot_potential_edges)*line_upgrade_cost) %>%
  mutate(budget.constraint = budget.factor*max.expanse) %>%
  mutate(runcommand = paste0("python ", algorithm,
                             " --instance_location instance", instance,
                             " --budget ", budget.constraint,
                             " --load_capacity_factor ", load_capacity_factor,
                             " --line_upgrade_capacity_coef_scale ", line_upgrade_capacity_coef_scale,
                             " --line_establish_cost_coef_scale ", line_establish_cost_coef_scale,
                             " --line_establish_capacity_coef_scale ", line_establish_capacity_coef_scale,
                             " --dump_file ", dump_file))
