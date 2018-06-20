python "robustness_heuristic.py" --instance_location "instance24" --time_limit 1.0 --budget 50 --upgrade_selection_bias 0.25
python "robustness_heuristic.py" --instance_location "instance24" --time_limit 1.0 --budget 50 --upgrade_selection_bias 0.5
python "robustness_heuristic.py" --instance_location "instance24" --time_limit 1.0 --budget 50 --upgrade_selection_bias 0.75

python "robustness_heuristic.py" --instance_location "instance24" --time_limit 1.0 --budget 50 --min_neighbors 10
python "robustness_heuristic.py" --instance_location "instance24" --time_limit 1.0 --budget 50 --min_neighbors 25
python "robustness_heuristic.py" --instance_location "instance24" --time_limit 1.0 --budget 50 --min_neighbors 50

python "robustness_heuristic.py" --instance_location "instance24" --time_limit 1.0 --budget 50 --min_neighborhoods_total 50
