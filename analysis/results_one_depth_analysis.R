# Analyze one depth cascade approximation optimization results

library(tidyverse)
library(stringr)

scenarios.test.set <- "50 failure scenarios/"
res.files <- dir(paste0("c:/temp/grid_cascade_output/", scenarios.test.set), pattern = "*temp_sol.csv", full.names = T)

loadres <- function(path){
  tmp.file <- read_csv(path, col_types = "cc")
  instance <- tmp.file$value[tmp.file$name == "PARAMS_instance"]
  budget <- as.numeric(tmp.file$value[tmp.file$name == "PARAMS_budget"])
  objective <- as.numeric(tmp.file$value[tmp.file$name == "Objective"])
  
  res.tibble <- tibble(instance, budget, objective)
  
  return(res.tibble)
}

full.res <- tibble(filename = res.files) %>%
  group_by(filename) %>%
  mutate(res = map(.x = filename, .f = loadres)) %>%
  unnest()

max.obj <- full.res %>%
  group_by(instance) %>%
  summarize(max.objective.value = max(objective))

full.res.w.prc <- full.res %>%
  left_join(max.obj, by = "instance") %>% 
  mutate(percent.objective = objective/max.objective.value)

# ==== Comparison of objective value by budget, aggregated ====

ggplot(full.res.w.prc, aes(x = budget, y = percent.objective, color = instance)) + 
  geom_point() + geom_line() + scale_x_continuous(breaks = c(5, 10, 15, 25, 50, 100, 150, 200)) +
  #coord_cartesian(ylim = c(0.9,1)) + 
  scale_y_continuous(labels = scales::percent) + 
  ggtitle("Comparison of 1depth approx objective by budget, aggregated\nPortion of maximal value")

# individual scenario analysis:
load.sce.res <- function(path){
  tmp.file <- read_csv(path, col_types = "cc")
  instance <- tmp.file$value[tmp.file$name == "PARAMS_instance"]
  budget <- as.numeric(tmp.file$value[tmp.file$name == "PARAMS_budget"])
  objective <- as.numeric(tmp.file$value[tmp.file$name == "Objective"])
  
  tmp.file %>% 
    filter(str_detect(name, fixed("RES_tot_supply"))) %>%
    mutate(simulator.type = if_else(str_detect(name, fixed("RES_tot_supply_cascade_sce")),
                                    "full cascade",
                                    "1depth approx")) %>%
    mutate(scenario_num = str_replace(name, "RES_tot_supply_cascade_sce", "") %>%
             str_replace(., "RES_tot_supply_sce", "")) %>%
    mutate(instance = instance, budget = budget, objective = objective) %>%
    select(instance, budget, objective, scenario_num, simulator.type, value) %>%
    mutate(scenario.supply = as.numeric(value)) %>%
    select(-value) %>% 
    spread(key = simulator.type, value = scenario.supply) %>%
    mutate(full.cascade.prop = (`1depth approx` - `full cascade`)/`full cascade`) -> res.tibble
  
  return(res.tibble)
}

# ==== Full comparison by budget, instance,
# and the two types of cascade (full + approx), on a scenario resolution ====

full.res.scenarios <- tibble(filename = res.files) %>%
  group_by(filename) %>%
  mutate(res = map(.x = filename, .f = load.sce.res)) %>%
  unnest() 

ggplot(full.res.scenarios, aes(x = budget, y = full.cascade.prop)) + 
  geom_point(alpha = 0.5) +
  facet_wrap(~ instance) + 
  scale_x_continuous(breaks = c(5, 10, 15, 25, 50, 100, 150, 200)) +
  scale_y_continuous(labels = scales::percent) + 
  ylab("(1depth - full) / full") + 
  ggtitle("Distribution of points\nDifference between 1depth approx to full cascade")

aggregated.full.cascade <- full.res.scenarios %>%
  group_by(instance, budget) %>%
  select(objective, scenario_num, `1depth approx`, `full cascade`, instance, budget) %>%
  summarize(mean.objective = mean(`full cascade`)) %>%
  left_join(max.obj) %>%
  mutate(mean.objective.prc = mean.objective/max.objective.value)
  

ggplot(aggregated.full.cascade, aes(x = budget, y = mean.objective.prc, color = instance)) + 
  geom_point() + 
  geom_line() + 
  ggtitle("Objective value (relative to max)\nShowing full cascade, optimization based on 1depth approx")


# ==== Sumarizing comparison full cascade and 1depth approximation
full.compare.tmp <- full.res.scenarios %>%
  ungroup() %>%
  select(instance:`full cascade`) %>%
  select(-objective) %>%
  group_by(instance, budget) %>%
  summarize(`1depth` = mean(`1depth approx`),
            `full` = mean(`full cascade`)) %>%
  gather(type, value, -instance, -budget)

maximum.value <- full.compare.tmp %>%
  group_by(instance) %>%
  summarize(maximum.value = max(value))

full.compare <- full.compare.tmp %>%
  left_join(maximum.value) %>%
  mutate(normalized.value = value/maximum.value)

compare.plot <- 
  ggplot(full.compare, 
       aes(x = budget, y = normalized.value, linetype = type, color = instance)) + 
  geom_point(size = 2, color = "black") + 
  geom_line(size = 1) + 
  facet_wrap(~instance) + 
  scale_y_continuous(labels = scales::percent) +
  ylab("Objective\n% relative to max supply") +
  xlab("Budget [$]") #+ 
  #ggtitle("Optimization by 1-depth approximation and results of full cascade, as a function of budget")

if (scenarios.test.set == "50 failure scenarios/"){
  ggsave(path = "C:\\Users\\Adi Sarid\\Documents\\GitHub\\Draft-design-robustness\\figures\\",
         filename = "optimization_50_scenarios_1depth_full_comparison.eps",
         plot = compare.plot, width = 18, height = 10, units = "cm")
} else if (scenarios.test.set == "10 failure scenarios/"){
  ggsave(path = "C:\\Users\\Adi Sarid\\Documents\\GitHub\\Draft-design-robustness\\figures\\",
         filename = "optimization_10_scenarios_1depth_full_comparison.eps",
         plot = compare.plot, width = 18, height = 10, units = "cm")
} else if (scenarios.test.set == "50 failure scenarios with failure penalty 1/"){
  ggsave(path = "C:\\Users\\Adi Sarid\\Documents\\GitHub\\Draft-design-robustness\\figures\\",
         filename = "optimization_50_scenarios_1depth_full_comparison_with_penalty.eps",
         plot = compare.plot, width = 18, height = 10, units = "cm")
} else if (scenarios.test.set == "50 failure scenarios with failure penalty 0.1/"){
  ggsave(path = "C:\\Users\\Adi Sarid\\Documents\\GitHub\\Draft-design-robustness\\figures\\",
         filename = "optimization_50_scenarios_1depth_full_comparison_with_penalty.eps",
         plot = compare.plot, width = 18, height = 10, units = "cm")
}

