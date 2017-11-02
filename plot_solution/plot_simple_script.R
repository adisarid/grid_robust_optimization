# Code to plot step-by-step grid solution
# Used for the private case of simple1 and simple2 instances
# G-1, G-2, G-3, 2-3 (optional), 1-2 (optional) and upgrades.

setwd("c:\\Users\\Adi Sarid\\Documents\\GitHub\\grid_robust_opt\\plot_solution\\")

library(tidyverse)
library(stringr)
library(cowplot)

# ==== load solution steps from available csv files ====
read_and_ref <- function(csvfilename){
  tmp_data <- read_csv(csvfilename) %>%
    mutate(source = str_sub(csvfilename, start = 64)) %>%
    mutate(source = str_replace(source, pattern = " - current_callback_solution.csv", replacement = "")) %>%
    mutate(source = str_replace(source, pattern = " - current_simulation_failures.csv", replacement = ""))
  return(tmp_data)
}

csv_batch_dir <- "c:\\temp\\grid_cascade_output\\callback debug\\" # <-- MAKE SURE ONLY ONE BATCH IN DIRECTORY!
csv_batch_names <- paste0(csv_batch_dir, dir(pattern = "current_callback_solution.csv", path = csv_batch_dir))

run.results <- csv_batch_names %>% 
  map_df( ~ read_and_ref(csvfilename = .)) %>%
  mutate(variable.type = str_sub(name, start = 0, end = 1)) %>%
  mutate(scenario = ifelse(str_detect(name, "s[0-9]"),
                           as.numeric(str_sub(name, start = -1L)),
                           NA)) %>%
  mutate(x = ifelse(str_detect(name, "_1_"),
                    0,
                    ifelse(str_detect(name, "_2_"),
                           1,
                           ifelse(str_detect(name, "_3_"),
                                  2, NA)))) %>%
  mutate(y = ifelse(is.na(x), NA, 0)) %>%
  mutate(xend = ifelse(str_detect(name, "_[0-9]_G"),
                       1,
                       ifelse(str_detect(name, "_[0-9]_2"),
                              1,
                              ifelse(str_detect(name, "_[0-9]_3"),
                                     2, NA)))) %>%
  mutate(yend = ifelse(str_detect(name, "_[0-9]_G"),
                       1,
                       ifelse(str_detect(name, "_[0-9]_2"),
                              0,
                              ifelse(str_detect(name, "_[0-9]_3"),
                                     0, NA)))) %>%
  filter(value != 0)

# ==== Get the simulation failure data ====

csv_batch_dir <- "c:\\temp\\grid_cascade_output\\simulation_failures\\" # <-- MAKE SURE ONLY ONE BATCH IN DIRECTORY!
csv_batch_names <- paste0(csv_batch_dir, dir(pattern = "current_simulation_failures.csv", path = csv_batch_dir))

base.grid.points <- tibble(node = c(1:3, "G"),
                           x = c(0,1,2,1),
                           y = c(0,0,0,1))

sim.results <- csv_batch_names %>% 
  map_df( ~ read_and_ref(csvfilename = .)) %>%
  mutate(source = str_sub(source, start = 6)) %>%
  mutate(edge_1 = as.character(edge_1)) %>%
  left_join(base.grid.points, by = c("edge_2" = "node")) %>%
  rename(xend = x, yend = y) %>%
  left_join(base.grid.points, by = c("edge_1" = "node"))

  
# ==== Plot grid function ====

base.grid.segments <- tibble(x = c(0, 1, 2),
                             y = c(0, 0, 0),
                             xend = c(1, 1, 1),
                             yend = c(1, 1, 1))

plot.power.step <- function(step.character){
  # filter infrastructure to current step
  infrastructure.est <- run.results %>%
    filter(variable.type == "c" & !is.na(x) | variable.type == "X") %>%
    filter(source == step.character)
  
  base.grid.plot <- ggplot(base.grid.points, aes(x, y, label = node)) + geom_point(size = 2) + 
    geom_label(nudge_x = 0.05, nudge_y = 0.05) + 
    geom_segment(data = base.grid.segments, aes(x = x, y = y, xend = xend, yend = yend), inherit.aes = FALSE) + 
    ggtitle("Base grid") + 
    theme(
      axis.text.x = element_blank(),
      axis.text.y = element_blank(),
      axis.ticks = element_blank())
  
  infrastructure.plot.c <- base.grid.plot + 
    geom_segment(data = infrastructure.est %>% filter(variable.type == "c"), 
                 aes(x = x, y = y, xend = xend, yend = yend), inherit.aes = FALSE,
                 color = "purple", size = 2, linetype = 2) + 
    ggtitle("Capacity upgrades") + 
    theme(
      axis.text.x = element_blank(),
      axis.text.y = element_blank(),
      axis.ticks = element_blank())
  
  infrastructure.plot.X <- base.grid.plot + 
    geom_segment(data = infrastructure.est %>% filter(variable.type == "X"), 
                 aes(x = x, y = y, xend = xend, yend = yend), inherit.aes = FALSE,
                 color = "blue", size = 2, linetype = 3) + 
    ggtitle("Edges established") + 
    theme(
      axis.text.x = element_blank(),
      axis.text.y = element_blank(),
      axis.ticks = element_blank())
  
  optimization.failures <- run.results %>%
    filter(variable.type == "F" & source == step.character)
  
  opt.res.failure.plot <- ggplot(optimization.failures, aes(x = x, y = y, xend = xend, yend = yend, scenario)) + 
    geom_segment(color = "red", size = 1.5) + 
    facet_grid(. ~ scenario) + 
    ggtitle("Optimization failures") + 
    theme(
      axis.text.x = element_blank(),
      axis.text.y = element_blank(),
      axis.ticks = element_blank())
  
  simulation.failures <- sim.results %>%
    filter(source == step.character)
  
  sim.res.failure.plot <- ggplot(simulation.failures, aes(x = x, y = y, xend = xend, yend = yend, scenario)) + 
    geom_segment(color = "red", size = 1.5) + 
    facet_grid(. ~ scenario) + 
    ggtitle("Simulation failures") + 
    theme(
      axis.text.x = element_blank(),
      axis.text.y = element_blank(),
      axis.ticks = element_blank())
  
  final.grid.plot <- plot_grid(base.grid.plot, infrastructure.plot.X, infrastructure.plot.c, NULL,
                               opt.res.failure.plot, sim.res.failure.plot,
                               ncol = 2,
                               labels = "auto")
  
  ggsave(filename = paste0("c:/temp/grid_cascade_output/plot_output/",
                           str_sub(lubridate::now(), start = 0, end = 10), " - ", step.character, ".jpg"),
         plot = final.grid.plot)
  return(0)
}

# ==== create mass figures ====
# This takes a while
# Saves all steps into charts
sim.results %>%
  select(source) %>%
  unique() %>%
  group_by(source) %>%
  do(tmp = plot.power.step(step.character = .$source))


# ==== create a pptx with the images ====
library(officer)
res_pres <- read_pptx() %>%
  add_slide(layout = "Title and Content", master = "Office Theme") %>%
  ph_with_text(type = "body", str = "Blah 123") %>%
  print(target = "tmp.pptx") %>%
  invisible()
