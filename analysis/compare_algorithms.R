library(tidyverse)



setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")

source("analysis/grid_sunken_cost.R")

res <- read_csv("c:/temp/grid_cascade_output/dump.csv", col_names = c("dump", "value", "runtime")) %>%
  full_join(readxl::read_excel("new.batch.parameters.xlsx"), by = c("dump" = "dump_file")) %>%
  mutate(percent_supplied = value/tot.demand) %>%
  left_join(tibble(algorithm = c("robustness_heuristic_upper_bound.py",
                                 "main_program.py",
                                 "main_program_one_depth_cascade.py"),
                   algorithm.name = c("LNS",
                                      "Lazy",
                                      "One.depth"))) %>%
  left_join(potential.edges) %>%
  mutate(line_establish_cost = line_establish_cost_coef_scale + upgrade.cost*line_establish_capacity_coef_scale,
         line_upgrade_cost = upgrade.cost*line_upgrade_capacity_coef_scale) %>%
  mutate(max.expanse = 
           tot_potential_edges*line_establish_cost +
           (tot_edges_installed + tot_potential_edges)*line_upgrade_cost) %>%
  mutate(load_capacity_factor = load_capacity_factor*1.5)

glimpse(res)

res2 <- res %>%
  select(algorithm.name, percent_supplied, tot.demand, instance, load_capacity_factor, 
         budget.factor, budget.constraint, max.expanse,
         line_upgrade_cost, line_establish_cost)

res2.compare <- res2 %>% select(-tot.demand) %>%
  spread(algorithm.name, percent_supplied)


openxlsx::write.xlsx(res2.compare, file = "25-07-2018 - tmp - table4michal.xlsx")
