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
  bind_rows(read_csv("Half cost coef scale results/dump.csv", col_names = c("dump", "value", "runtime"))) %>%
  filter(dump>=701 | dump %in% (which(!(701:748 %in% dump)) + 600)) %>%
  mutate(dump = if_else(dump < 700, dump + 100, dump)) %>%
  full_join(readxl::read_excel("11-09-2018-final_runs.xlsx"), by = c("dump" = "dump_file")) %>%
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

#openxlsx::write.xlsx(res2_compare_final, file = "25-10-2018 - tmp - table4michal.xlsx")


# plot the final results in a summarizing chart. 
# The facets will contain load capacity and budget factor
# The y-axis is algorithm performance. Fill is algorithm. x is the IEEE instance.

res2_final_for_plot <- res2_final %>%
  mutate(`Algorithm` = recode(algorithm.name,
                              `Lazy_half_cost` = "Lazy\nConstraints\n",
                              `LNS_half_cost` = "LNS\nHeuristic\n",
                              `One.depth_half_cost` = "1-depth\nApproximation\n")) %>%
  mutate(load_capacity_factor = case_when(load_capacity_factor <= 1.06 ~ "Capacity Tolerance +5%",
                                          TRUE ~ "Capacity Toloerance +20%")) %>%
  mutate(budget.factor = case_when(budget.factor == 0.3 ~ "Budget 30%",
                                   budget.factor == 0.5 ~ "Budget 50%"))

ggplot(res2_final_for_plot, 
       aes(y = percent_supplied, 
           x = factor(instance, levels = c(30, 57, 118, 300)),
           fill = Algorithm)) + 
  geom_bar(stat = "identity", position = "dodge", color = "black") + 
  facet_grid(load_capacity_factor ~ budget.factor) + 
  scale_y_continuous(labels = scales::percent) + 
  scale_fill_brewer(palette="YlGnBu") +
  geom_text(aes(label = paste0(round(percent_supplied*100), "%"),
                y = percent_supplied - 0.1),
             position = position_dodge(1),
            angle = -45) + 
  xlab("IEEE Instance") + 
  ylab("Percent Supplied [%]") -> summarizing_chart

ggsave(summarizing_chart, 
       filename = "c:\\Users\\Adi Sarid\\Documents\\GitHub\\git_robustness_2nd_paper\\figures\\12hour_instance_results.eps", 
       width = 28, height = 17, units = "cm")


# comparison table of averages
res2_final_for_plot %>% 
  select(algorithm.name, percent_supplied, instance) %>%
  group_by(algorithm.name, instance) %>%
  summarize(avg_supplied = round(mean(percent_supplied)*100, 1)) %>%
  spread(instance, avg_supplied) %>%
  knitr::kable(format = "latex")

res2_final_for_plot %>% 
  select(algorithm.name, percent_supplied, instance) %>%
  group_by(algorithm.name) %>%
  summarize(avg_supplied = round(mean(percent_supplied)*100, 1))
