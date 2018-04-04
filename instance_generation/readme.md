# Instance (optimization problem) generation

The files in this directory are used to generate optimization problems out of the standard IEEE base instances comprising various number of nodes.

Run the code in the following order:

   1. Use `create_instance_for_optimization.py` to create raw csv files of base instance
   2. Use generate_random_instance.R to add potential edges to the problem and generate final files that will be used as input to the optimization.


## Todo

Consider moving the code completely to R using the `reticulate` package.