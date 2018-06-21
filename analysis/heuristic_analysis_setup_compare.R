# Analysis for the heuristic
# Compare search setupparameters
heuristic <- read_csv("c:/temp/grid_cascade_output/heuristic_results.csv")

heuristic.compare.starttime <- heuristic %>%
  group_by(args.instance_location, budget, upgrade_selection_bias, min_neighborhoods, min_neighbors_per_neighborhood) %>%
  summarize(starttime = min(current_time))


neighborhood.jumps <- heuristic %>%
  mutate(rundescription = paste0("(", upgrade_selection_bias*100, "%, ", min_neighborhoods,
                                 ", ", min_neighbors_per_neighborhood, ")")) %>%
  group_by(args.instance_location, budget, upgrade_selection_bias, 
           min_neighborhoods, min_neighbors_per_neighborhood,
           neighborhoods_searched, rundescription) %>%
  left_join(heuristic.compare.starttime) %>%
  mutate(runtime = (current_time - starttime)/60) %>%
  select(-starttime) %>%
  summarize(neighborhood.jump.time = min(runtime),
            current_time = min(current_time),
            current_supply = min(current_supply))


heuristic.compare <- heuristic %>%
  mutate(rundescription = paste0("(", upgrade_selection_bias*100, "%, ", min_neighborhoods,
                                 ", ", min_neighbors_per_neighborhood, ")")) %>%
  left_join(heuristic.compare.starttime) %>%
  mutate(runtime = (current_time - starttime)/60) %>%
  select(-starttime)


hr.comp.plot <- ggplot(heuristic.compare, aes(y = current_supply, x = runtime)) + 
  geom_line(aes(color = rundescription), size = 2, alpha = 0.5) + 
  guides(color = guide_legend("(Selection bias,\nmin neighborhoods,\nmin neighbors per neighborhood)")) +
  geom_point(data = neighborhood.jumps, aes(x = neighborhood.jump.time,
                                            y = current_supply,
                                            color = rundescription), size = 2) 
  


plotly::ggplotly(hr.comp.plot)  