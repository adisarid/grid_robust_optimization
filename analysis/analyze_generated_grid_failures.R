# analyze grids
setwd("c:\\Users\\Adi Sarid\\Documents\\GitHub\\grid_robust_opt\\analysis\\")

library(tidyverse)
library(GGally)
library(network)

generate.coordinates.distances <- function(graph.dir = "instance39", calc.dist.matrix = TRUE){
  base.dir <- "c:\\Users\\Adi Sarid\\Documents\\GitHub\\grid_robust_opt\\"
  
  edges <- read_csv(paste0(base.dir, graph.dir, "\\grid_edges.csv")) %>%  
    mutate(from_node = if_else(node1 < node2, node1, node2),
           to_node = if_else(node1 < node2, node2, node1)) %>%
    mutate(nodestr = paste0(from_node, ",", to_node))
  nodes <- read_csv(paste0(base.dir, graph.dir, "\\grid_nodes.csv")) %>%
    mutate(net.generation = gen_capacity-demand)
  
  instance.graph <- network(edges %>% select(node1, node2) %>% data.frame())
  
  set.vertex.attribute(instance.graph,
                       "demand",
                       nodes$demand)
  
  set.vertex.attribute(instance.graph,
                       "gen_capacity",
                       nodes$gen_capacity)
  
  set.vertex.attribute(instance.graph,
                       "net_capacity",
                       abs(nodes$net.generation))
  
  
  grid.plot <- ggnet2(instance.graph, size = "demand", node.label = "vertex.names") + ggtitle(graph.dir)
  
  if (calc.dist.matrix){
    # extract coordinates of a
    grid.distances <- grid.plot$data %>% 
      select(x, y) %>%
      as.matrix() %>%
      dist() %>%
      as.matrix() %>%
      as.data.frame() %>%
      rownames_to_column() %>% 
      gather(to_node, distance, -rowname) %>%
      as.matrix() %>%
      as.tibble() %>%
      mutate(node1 = as.numeric(rowname),
             node2 = as.numeric(to_node)) %>%
      mutate(from_node = if_else(node1 < node2, node1, node2),
             to_node = if_else(node1 < node2, node2, node1),
             distance = as.numeric(distance)) %>%
      filter(distance > 0.00001) %>%
      select(from_node, to_node, distance) %>%
      unique() %>%
      arrange(distance) %>% 
      left_join(edges %>% select(from_node, to_node, capacity)) %>%
      filter(is.na(capacity)) %>%
      select(-capacity)  
    
    write_csv(path = paste0(base.dir, graph.dir, "\\edges_distances.csv"),
              grid.distances)
  }
  
  
  write_csv(path = paste0(base.dir, graph.dir, "\\coordinates.csv"),
            x = grid.plot$data %>% select(label, x, y))
  
  return(grid.plot)  
}


# generate coordinates and distances for the 6 grids:
generate.coordinates.distances("instance24")
generate.coordinates.distances("instance30")
generate.coordinates.distances("instance39")
generate.coordinates.distances("instance57")
generate.coordinates.distances("instance118")
generate.coordinates.distances("instance300")




