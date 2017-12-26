rem Runs the robustness optimization problem
rem Parameters:
rem CASE_LOCATION TOTAL_RUN_TIME PROPORTION_CASES_SHORTRUNS USE_PRIORITIES LINE_CAPACITY_COEF_SCALE
python main_program.py case30 3 0.0 True 15
python main_program.py case30 3 0.0 False 15
python main_program.py case30 3 0.0 True 5
python main_program.py case30 3 0.0 True 10
python main_program.py case30 3 0.0 True 20