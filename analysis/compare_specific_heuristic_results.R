datatmp <- read_csv("c:/temp/grid_cascade_output/detailed_results/19.0.csv", skip = 1,
                    col_names = c("name", "val19")) %>%
  left_join(
    read_csv("c:/temp/grid_cascade_output/detailed_results/27.0.csv", skip = 1,
             col_names = c("name", "val27"))
  ) %>%
  mutate(diff = val19 != val27)

datatmpcost <- datatmp %>%
  filter(str_detect(name, "c_|X_")) %>%
  mutate(new_edge = str_detect(name, "X_")*(val27>0),
         upgrade_edge = str_detect(name, "c_")*(val27>0)) %>%
  arrange(name)

colSums(datatmpcost %>% select(new_edge, upgrade_edge))
