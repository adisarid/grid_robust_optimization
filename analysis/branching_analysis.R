# Analyze files related to the convergence when choosing various parameters

library(tidyverse)
setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")
case30 <- read_csv("case30_solution_statistics.csv") %>%
  mutate(opt_gap = (94.6-best_incumbent)/best_incumbent) %>%
  mutate(prop_sim_runs = (time_spent_cascade_sim)/time_spent_total)

# plot opt_gap as a function time
ggplot(case30, aes(x = time_spent_total, y = opt_gap, color = factor(prop_cascade_cut), shape = set_decision_var_priorities)) + 
  geom_point() + geom_line() + scale_y_continuous(labels = scales::percent) + 
  ggtitle("The optimality gap as a function of time")

ggplot(case30, aes(x = time_spent_total, y = prop_sim_runs, color = factor(prop_cascade_cut), shape = set_decision_var_priorities)) + 
  geom_point() + geom_line() + scale_y_continuous(labels = scales::percent) + 
  ggtitle("Time proportion spent on cascade simulation as a function of time")
