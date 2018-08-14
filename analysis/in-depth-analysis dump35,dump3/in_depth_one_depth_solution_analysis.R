# In - depth analysis of 1depth approximation results
# Used to compare the scenarios and show the solution versus the equivalent solution of the heuristic
# I chose a specific instance, dump#35 (one depth approx) and dump#3 (heuristic upper bound)

library(tidyverse)
library(GGally)
library(network)
library(sna)

net = rgraph(10, mode = "graph", tprob = 0.5)
net = network(net, directed = FALSE)

network.vertex.names(net) = letters[1:10]
ggnet2(net)
