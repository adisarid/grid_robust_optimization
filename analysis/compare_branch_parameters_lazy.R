library(tidyverse)



setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/")

source("analysis/grid_sunken_cost.R")

res <- read_csv("c:/temp/grid_cascade_output/dump.csv", col_names = c("dump", "value", "runtime")) %>%
  full_join(read_csv("01-08-2018 - compare branch parameters.csv"), by = c("dump" = "dump_file")) %>%
  mutate(percent_supplied = value/tot.demand) %>% 
  arrange(desc(percent_supplied)) %>%
  left_join(readxl::read_xlsx("01-08-2018 -branch.param.explain.xlsx"))

branch_settings_explained <- readxl::read_xlsx("01-08-2018 -branch.param.explain.xlsx")

summary_file <- list(res = res, branch_settings = branch_settings_explained)

#openxlsx::write.xlsx(summary_file, file = "02-08-2018 - compare branch params.xlsx")
