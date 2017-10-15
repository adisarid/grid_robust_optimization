# adi_simple2
A very simple instance comprised of one generator node and three consumer nodes.
This version is a discretization of version adi_simple1, only discrete values of capacity upgrade are feasible.

Existing edges: (G,1);(G,2);(G,3)

Demand for each node = 10

Initial capacity for each edge = 15

Edges considered for establishment: (1,2);(2,3)

Capacity upgrade optional for each edge: 15 (up to 30 for existing edges, up to 15 for new edges).

Susceptance is 1 across all edges

No backup capacity considered

Failure scenarios include: failure of (G,1) w.p. 0.1, failure of (G,2) w.p. 0.1, failure of (G,2) and (G,3) w.p. 0.05

Total investment cost upper bound is 30.

New edge costs 5 and one unit of capacity costs 1