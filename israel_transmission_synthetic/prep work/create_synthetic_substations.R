# Prep work for creating synthetic transmission substations using the CBS population data
setwd("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/israel_transmission_synthetic/prep work/")
# ==== Load libraries ====
library(tidyverse)
library(httr) # for handling http requests from google maps API

il.data <- readxl::read_xls("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/israel_transmission_synthetic/prep work/bycode.xls")

# filter for population > 1000 

il.data.ready <- il.data %>%
  filter(total_population >= 1000)

il.data.small <- il.data %>% filter(total_population<1000)

# ==== Geocoding work ====

# Use google geo-coding to extract the per settlement coordinates
# base URL https://maps.googleapis.com/maps/api/geocode/json?address=
get_coords <- function(address = "Tel Aviv", alternate.address = ""){
  geocode_result <- paste0("https://maps.googleapis.com/maps/api/geocode/json?address=", 
                           unique(address), ", Israel") %>% 
    parse_url() %>%
    build_url() %>%
    GET() %>%
    content()
  
  if (geocode_result$status == "OK"){
    lat.coord <- geocode_result$results[[1]]$geometry$location$lat
    lon.coord <- geocode_result$results[[1]]$geometry$location$lng
    formatted.address <- geocode_result$results[[1]]$formatted_address
  } else {
    geocode_result <- paste0("https://maps.googleapis.com/maps/api/geocode/json?address=", 
                             unique(alternate.address), ", Israel") %>% 
      parse_url() %>%
      build_url() %>%
      GET() %>%
      content()
    if (geocode_result$status == "OK") {
      lat.coord <- geocode_result$results[[1]]$geometry$location$lat
      lon.coord <- geocode_result$results[[1]]$geometry$location$lng
      formatted.address <- geocode_result$results[[1]]$formatted_address
    } else {
      lat.coord <- NA
      lon.coord <- NA
      formatted.address <- NA
    }
  }
  
  df <- data.frame(formatted.address, lat.coord, lon.coord)
  return(df)
}

# The following operation takes a long time. If file is present, simply load from:
# location_data_il.csv
il.data.w.geocoding <- read_csv("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/israel_transmission_synthetic/prep work/location_data_il.csv") %>%
  rbind(
    read_csv("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/israel_transmission_synthetic/prep work/location_data_il_small.csv")
  ) %>%
  filter(lon.coord >= 34 & lon.coord <= 36 & lat.coord >= 29.5 & lat.coord <= 33.3)

# il.data.w.geocoding <- il.data.ready %>% 
#   group_by(transcript) %>%
#   do(get_coords(address = .$transcript, alternate.address = .$place)) %>%
#   left_join(il.data.ready)
# il.data.w.geocoding.small <- il.data.small %>%
#   group_by(transcript) %>%
#   do(get_coords(address = .$transcript, alternate.address = .$place)) %>%
#   left_join(il.data.small)

# ggplot(il.data.w.geocoding, aes(x = lat.coord, y = lon.coord)) + geom_point(aes(size = total_population))



# ==== Plotting over Israel's map ====
library(ggmap)
library(mapproj)


isr.map <- get_map(location = "Israel", zoom = 7, maptype = "roadmap", color = "bw")

map1 <- 
  ggmap(isr.map) + xlim(c(34,36)) + ylim(c(29.5,33.3)) + 
  geom_point(data = il.data.w.geocoding, aes(x = lon.coord, y = lat.coord, size = total_population), alpha = 0.1) + 
  scale_colour_hue(l=60, c=100)


# ==== Clustering points ====
# use KMeans clustering to create 200 clusters
# Consider later on to change the clustering method to consider point weight
# Also consider converting to a haversine distance function
# Not sure this is required maybe the current approxmation is good enough
# See Birchfield, et al. 2017 (Grid Structural Characteristics)

set.seed(0)
k <- 150
kmeans1 <- kmeans(x = il.data.w.geocoding %>% ungroup() %>% select(lat.coord, lon.coord), centers = k)

map2 <- map1 + 
  geom_point(data = as.data.frame(kmeans1$centers), aes(x = lon.coord, y = lat.coord), color = "blue", alpha = 0.5)
map2

# Add the population size to the clustering
center.cluster <- data.frame(clust = 1:k, kmeans1$centers) %>%
  rename(clust.lat = lat.coord, clust.lon = lon.coord)

il.data.clustered <- il.data.w.geocoding %>%
  mutate(clust = kmeans1$cluster) %>%
  left_join(center.cluster) %>%
  group_by(clust, clust.lon, clust.lat) %>%
  select(clust, clust.lon, clust.lat, total_population) %>%
  summarize(total_population = sum(total_population)) %>%
  mutate(Name = as.character(clust))
  

map3 <- 
  ggmap(isr.map) + xlim(c(34,36)) + ylim(c(29.5,33.3)) + 
  geom_point(data = il.data.clustered, aes(x = clust.lon, y = clust.lat, size = total_population, color = factor(Name)), alpha = 0.7) + 
  guides(color = F)
  
# ==== Add generation data ====

generator.substation.data <- read_csv("generator data.csv") %>%
  mutate(tot_cap = `Num units`*Capacity) %>%
  group_by(Name, `Location X`, `Location Y`) %>%
  summarize(tot_cap = sum(tot_cap)) %>%
  rename(clust.lon = `Location X`, clust.lat = `Location Y`) %>%
  rbind(il.data.clustered) %>%
  mutate(node.type = ifelse(is.na(clust), "Generator", "Substation")) %>%
  mutate(total_population = ifelse(is.na(total_population), 60000, total_population)) %>%
  ungroup()
generator.substation.data$vertice.num <- 1:NROW(generator.substation.data)


map4 <- ggmap(isr.map) + xlim(c(34,36)) + ylim(c(29.5,33.3)) +
  geom_point(data = generator.substation.data, 
             aes(x = clust.lon, y = clust.lat, shape = node.type, color = node.type, size = total_population), alpha = 0.8)

# ==== Add transmission lines using minimum spanning tree ====
# compute the minimum spanning tree of the graph represented by generators and substations

# create a distance matrix
# Consider changing to haversine distance function though Euclidean approximation might be good enough for us
vert.dist <- generator.substation.data %>%
  ungroup() %>%
  select(clust.lon, clust.lat) %>%
  as.matrix() %>%
  dist(method = "euclidean")
N <- NROW(generator.substation.data)

# create a minimum spanning tree and exteact it for work
library(igraph)
power.grid <- make_full_graph(n = N)
power.mst <- mst(power.grid, weights = as.vector(vert.dist))
plot(power.mst)

# yield a tibble with edges of power.mst (N-1 edges):
power.edge.adj <- as_edgelist(power.mst) %>%
  as_tibble() %>%
  rename(node1 = V1, node2 = V2) %>%
  left_join(generator.substation.data %>% 
              select(vertice.num, clust.lon, clust.lat),
            by = c("node1" = "vertice.num")) %>%
  rename(x1 = clust.lon, y1 = clust.lat) %>%
  left_join(generator.substation.data %>%
              select(vertice.num, clust.lon, clust.lat),
            by = c("node2" = "vertice.num")) %>%
  rename(x2 = clust.lon, y2 = clust.lat) %>%
  mutate(source = "power.mst")

map5 <- map4 + 
  geom_segment(data = power.edge.adj, aes(x = x1, xend = x2, y = y1, yend = y2), size = 1, alpha = 0.7)


# ==== Add optional transmission lines using a Delaunay graph ====
library("deldir")

power.deldir <- deldir(x = generator.substation.data$clust.lon, y = generator.substation.data$clust.lat)
power.delaunay <- power.deldir$delsgs %>%
  rename(node1 = ind1,
         node2 = ind2) %>%
  mutate(source = "delaunay")

map6 <- map5 + 
  geom_segment(data = power.delaunay, aes(x = x1, xend = x2, y = y1, yend = y2), size = 0.5, alpha = 0.7, linetype = 2)


# ==== Prep transmission line file ====
# for more meaningful distances I use the haversine approximation (maybe can also add earlier)
# Use: geosphere::distGeo()
# STILL NEED TO SETUP CAPACITY OF TRANSMISSION LINE (15/10/2017)
library(geosphere)
line.final <- power.edge.adj %>%
  rbind(power.delaunay) %>%
  mutate(geodist = distGeo(p1 = cbind(x1, y1), p2 = cbind(x2, y2))/1000) %>%
  mutate(cost_fixed = ifelse(source == "power.mst", 0, 0.1),
         cost_linear = geodist*0.01) %>%
  mutate(susceptance = 1) %>%
  mutate(capacity = 1500) %>% # CAPACITY TBD after initial solution tested (Mega Watt)
  filter(source == "power.mst" | geodist <= quantile(geodist, 0.5)) %>% # take min span tree or in closest 50%
  select(node1, node2, capacity, susceptance, cost_fixed, cost_linear)
write_excel_csv(path = "../grid_edges.csv", x = line.final)



# ==== Prep node file ====
# total capacity is 15,810.9 Mega Watts.
# Naively splitting the capacity per capita to a total of 80% (12,648.72 Mega Watts)
tot.cap.div <- sum(generator.substation.data$tot_cap[is.na(generator.substation.data$clust)])*0.8
node.final <- generator.substation.data %>%
  rename(node = vertice.num) %>%
  mutate(demand = ifelse(is.na(clust), 0, tot.cap.div/total_population)) %>%
  rename(gen_capacity = tot_cap) %>%
  replace_na(list(gen_capacity = 0)) %>%
  mutate(gen_upgrade_ub = 0,
         gen_upgrade_cost_fixed = 0,
         gen_upgrade_cost_linear = 0) %>% # for now disable generation capacity upgrades
  select(node, demand, gen_capacity, gen_upgrade_ub, gen_upgrade_cost_fixed, gen_upgrade_cost_linear)
write_excel_csv(path = "../grid_nodes.csv", x = node.final)
  
# ==== Prep additional parameters file ====
additional.params <- tibble(param_name = "C", param_value = 25)
write_excel_csv(path = "../additional_params.csv", x = additional.params)


# ==== Prep failure scenarios ====
# I'll prepare 5 scenarios:
#     1. Nominal (implicit): nothing fails, w.p. 90%
#     2. Northern extensive failures - 30% of edges fail, w.p. 2.5%
#     3. Southern extensive failures - 30% of edges fail, w.p. 2.5%
#     4. Eastern extensive failures - 30% of edges fail, w.p. 2.5%
#     5. Western extensive failures - 30% of edges fail, w.p. 2.5%