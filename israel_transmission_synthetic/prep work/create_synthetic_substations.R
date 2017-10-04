# Prep work for creating synthetic transmission substations using the CBS population data

library(tidyverse)
library(httr) # for handling http requests from google maps API

il.data <- readxl::read_xls("c:/Users/Adi Sarid/Documents/GitHub/grid_robust_opt/israel_transmission_synthetic/prep work/bycode.xls")

# filter for population > 1000 

il.data.ready <- il.data %>%
  filter(total_population >= 1000)

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

il.data.w.geocoding <- il.data.ready %>% 
  group_by(transcript) %>%
  do(get_coords(address = .$transcript, alternate.address = .$place)) %>%
  left_join(il.data.ready)

il.data.complete <- il.data.w.geocoding %>%
  filter(lat.coord >= 29 & lat.coord <= 34 & lon.coord <= 36 & lon.coord >= 34)

sum(il.data.complete$total_population)

il.data.w.geocoding[which(!(il.data.w.geocoding$transcript %in% il.data.complete$transcript)),] %>%
  View()

# il.data.w.geocoding.add <- il.data.w.geocoding %>%
#   filter(is.na(lat.coord)) %>%
#   select(-lat.coord, -lon.coord, -formatted.address) %>%
#   group_by(transcript) %>% 
#   do(get_coords(address = .$place)) %>%
#   left_join(il.data.ready) %>%
#   ungroup()
# 
# il.data.w.geocoding %>%
#   ungroup() %>%
#   filter(!is.na(formatted.address)) %>%
#   rbind(il.data.w.geocoding.add) -> il.data.complete

# View(il.data.complete)
