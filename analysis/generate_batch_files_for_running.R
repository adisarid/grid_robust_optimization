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
                                  algorithm = c("robustness_heuristic_upper_bound.py",
                                                "main_program.py",
                                                "main_program_one_depth_cascade.py")) %>%
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

write(base.batch.options$runcommand, "../algorithm_comparison.bat")
openxlsx::write.xlsx(x = base.batch.options, file = "new.batch.parameters.xlsx")


# lazy algorithm - to compare node select and variable select strategies
lazy.search.strategy.compare <- tibble(param = "node_select_strategy", param_value = c(0, 2:3)) %>%
  bind_rows(tibble(param = "variable_select_strategy", param_value = -1:4),
            tibble(param = "mip_emphasis", param_value = 1:4)) %>%
  mutate(dump_file = 100 + seq_along(param)) %>%
  mutate(runcommand = 
           paste0("python main_program.py --instance_location instance118 --budget 566.933899441341 --load_capacity_factor 0.8 --line_upgrade_capacity_coef_scale 40.2301675977654 --line_establish_cost_coef_scale 10 --line_establish_capacity_coef_scale 80.4603351955307", 
                  " --", param, " ", param_value,
                  " --dump_file ", dump_file))
write(lazy.search.strategy.compare$runcommand, "../lazy_compare_strategies.bat")
