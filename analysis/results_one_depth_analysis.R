# Analyze one depth cascade approximation optimization results

library(tidyverse)

res.files <- dir("c:/temp/grid_cascade_output/", pattern = "*temp_sol.csv", full.names = T)

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

ggplot(full.res.w.prc, aes(x = budget, y = percent.objective, color = instance)) + 
  geom_point() + geom_line()
