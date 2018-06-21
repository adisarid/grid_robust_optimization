# Analysis for the heuristic
# Compare search setupparameters
heuristic <- read_csv("c:/temp/grid_cascade_output/heuristic_results.csv")

heuristic.compare.starttime <- heuristic %>%
  group_by(args.instance_location, budget, upgrade_selection_bias, min_neighborhoods, min_neighbors_per_neighborhood) %>%
  summarize(starttime = min(current_time))

heuristic.compare <- heuristic %>%
  mutate(rundescription = paste0("sl: ", upgrade_selection_bias, "min_nbrhds: ", min_neighborhoods,
                                "min_nbrs_per: ", min_neighbors_per_neighborhood)) %>%
  left_join(heuristic.compare.starttime) %>%
  mutate(runtime = (current_time - starttime)/60) %>%
  select(-starttime)

neighborhood.jumps <- heuristic %>%
  group_by(args.instance_location, budget, upgrade_selection_bias, min_neighborhoods, min_neighbors_per_neighborhood) %>%
  
             

hr.comp.plot <- ggplot(heuristic.compare, aes(y = current_supply, x = runtime)) + 
  geom_line(aes(color = rundescription), size = 2, alpha = 0.5)
plotly::ggplotly(hr.comp.plot)  

hr.comp.plot2 <- ggplot(heuristic.compare, aes(y = current_supply, x = neighborhoods_searched)) + 
  geom_line(aes(color = rundescription), size = 2, alpha = 0.5)