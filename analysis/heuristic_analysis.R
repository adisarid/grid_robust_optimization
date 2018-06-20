# Analysis for the heuristic
heuristic <- read_csv("c:/temp/grid_cascade_output/heuristic_results.csv")

# total demands
total.demands <- heuristic %>%
  group_by(args.instance_location) %>%
  summarize(total.demand = max(total_demand)) %>%
  rename(instance = args.instance_location)

# show the objective attained per instance, per budget
best.obj.heuristic <- heuristic %>%
  group_by(args.instance_location, budget) %>%
  summarize(heuristic.obj = max(current_supply)) %>%
  rename(instance = args.instance_location)

# the following assumes that full.res and aggregated.full.cascade 
# has been loaded from file results_one_depth_analysis.R
opt.results.comp <- full.res %>%
  left_join(best.obj.heuristic) %>%
  left_join(total.demands) %>%
  rename(one.depth.obj = objective) %>%
  ungroup() %>%
  select(-filename) %>%
  filter(budget > 0) %>%
  mutate(heuristic.obj.prc = heuristic.obj/total.demand,
         one.depth.obj.prc = one.depth.obj/total.demand) %>%
  left_join(aggregated.full.cascade %>%
              select(instance, budget, mean.objective) %>%
              rename(one.depth.fullcascade.mean = mean.objective)) %>%
  mutate(one.depth.fullcascade.mean.prc = one.depth.fullcascade.mean/total.demand)

# chart it
opt.results.chartdata <- opt.results.comp %>%
  select(instance, budget, ends_with("prc")) %>%
  gather(measure, value, -instance, -budget) %>%
  mutate(measure = recode(measure,
                          `heuristic.obj.prc` = "LNS Heuristic",
                          `one.depth.fullcascade.mean.prc` = "One depth approx.\n(full cascade result)",
                          `one.depth.obj.prc` = "One depth approximation\n(1depth objective)")) %>%
  filter(measure != "One depth approximation\n(1depth objective)")

opt.method.compare <- ggplot(opt.results.chartdata, aes(x = budget, y = value, color = measure)) + facet_wrap(~ instance) + 
  geom_point() + geom_line() + scale_y_continuous(labels = scales::percent) + 
  guides(color = guide_legend("Optimization\nmethod")) + 
  xlab("Budget [$]") + ylab("% demand") + 
  coord_cartesian(ylim = c(0.75, 1))

ggsave(path = "C:\\Users\\Adi Sarid\\Documents\\GitHub\\MegaDraft-grid-design\\figures\\",
       filename = "optimization_method_compare.eps",
       plot = opt.method.compare, width = 18, height = 10, units = "cm")
