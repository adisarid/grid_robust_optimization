library(tidyverse)



setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")

source("analysis/grid_sunken_cost.R")

res <- read_csv("Nominal results/dump.csv", col_names = c("dump", "value", "runtime")) %>%
  full_join(readxl::read_excel("new.batch.parameters.xlsx"), by = c("dump" = "dump_file")) %>%
  mutate(percent_supplied = value/tot.demand) %>%
  mutate(algorithm.name = case_when(str_detect(runcommand, "robustness_heuristic_upper_bound.py") ~ "LNS",
                                       str_detect(runcommand, "main_program.py") ~ "Lazy",
                                       str_detect(runcommand, "one_depth") ~ "One.depth")) %>%
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


openxlsx::write.xlsx(res2.compare, file = "20-08-2018 - tmp - table4michal.xlsx")




# compare algorithms with half the cost for edge fixed cost
res_half_cost <- read_csv("Half cost coef scale results/dump.csv", col_names = c("dump", "value", "runtime")) %>%
  full_join(readxl::read_excel("22-08-2018-establish_cost_sensitivity.xlsx"), by = c("dump" = "dump_file")) %>%
  mutate(percent_supplied = value/tot.demand) %>%
  mutate(algorithm.name = case_when(str_detect(runcommand, "robustness_heuristic_upper_bound.py") ~ "LNS_half_cost",
                                    str_detect(runcommand, "main_program.py") ~ "Lazy_half_cost",
                                    str_detect(runcommand, "one_depth") ~ "One.depth_half_cost")) %>%
  left_join(potential.edges) %>%
  mutate(line_establish_cost = line_establish_cost_coef_scale + upgrade.cost*line_establish_capacity_coef_scale,
         line_upgrade_cost = upgrade.cost*line_upgrade_capacity_coef_scale) %>%
  mutate(max.expanse = 
           tot_potential_edges*line_establish_cost +
           (tot_edges_installed + tot_potential_edges)*line_upgrade_cost) %>%
  mutate(load_capacity_factor = load_capacity_factor*1.5)


res2_half_cost <- res_half_cost %>%
  select(algorithm.name, percent_supplied, tot.demand, instance, load_capacity_factor, 
         budget.factor, budget.constraint, max.expanse,
         line_upgrade_cost, line_establish_cost)

res2.compare_half_cost <- res2_half_cost %>% select(-tot.demand) %>%
  spread(algorithm.name, percent_supplied) %>%
  rename(line_establish_cost_half_cost = line_establish_cost) %>%
  select(-max.expanse)


# Joined table
res2_joined_tbl <- full_join(res2.compare, res2.compare_half_cost)

#openxlsx::write.xlsx(res2_joined_tbl, file = "27-08-2018 - tmp - table4michal.xlsx")





# compare 12 hour final runs
res_final <- read_csv("12 hours runs/dump.csv", col_names = c("dump", "value", "runtime")) %>%
  full_join(readxl::read_excel(""), by = c("dump" = "dump_file")) %>%
  mutate(percent_supplied = value/tot.demand) %>%
  mutate(algorithm.name = case_when(str_detect(runcommand, "robustness_heuristic_upper_bound.py") ~ "LNS_half_cost",
                                    str_detect(runcommand, "main_program.py") ~ "Lazy_half_cost",
                                    str_detect(runcommand, "one_depth") ~ "One.depth_half_cost")) %>%
  left_join(potential.edges) %>%
  mutate(line_establish_cost = line_establish_cost_coef_scale + upgrade.cost*line_establish_capacity_coef_scale,
         line_upgrade_cost = upgrade.cost*line_upgrade_capacity_coef_scale) %>%
  mutate(max.expanse = 
           tot_potential_edges*line_establish_cost +
           (tot_edges_installed + tot_potential_edges)*line_upgrade_cost) %>%
  mutate(load_capacity_factor = load_capacity_factor*1.5)


res2_final <- res_final %>%
  select(algorithm.name, percent_supplied, tot.demand, instance, load_capacity_factor, 
         budget.factor, budget.constraint, max.expanse,
         line_upgrade_cost, line_establish_cost)

res2_compare_final <- res2_final %>% select(-tot.demand) %>%
  spread(algorithm.name, percent_supplied) %>%
  rename(line_establish_cost_half_cost = line_establish_cost) %>%
  select(-max.expanse)
