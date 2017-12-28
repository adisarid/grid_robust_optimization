rem Runs the robustness optimization problem
rem Parameters:
rem CASE_LOCATION TOTAL_RUN_TIME PROPORTION_CASES_SHORTRUNS USE_PRIORITIES LINE_CAPACITY_COEF_SCALE LINE_COST_COEF_SCALE
python main_program.py case30 5 0.0 True 5 0.1
python main_program.py case30 5 0.0 True 5 0.5
python main_program.py case30 5 0.0 True 5 0.75
python main_program.py case30 5 0.0 True 5 0.25
python main_program.py case30 5 0.0 True 5 0.8





rem OLD (previous runs)
rem python main_program.py case30 3 0.0 True 5
rem python main_program.py case30 3 0.0 False 5
rem python main_program.py case30 3 0.0 True 7.5
rem python main_program.py case30 3 0.0 True 10
rem python main_program.py case30 3 0.0 True 15