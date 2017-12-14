rem Runs the robustness optimization problem
rem Parameters:
rem CASE_LOCATION TOTAL_RUN_TIME PROPORTION_CASES_SHORTRUNS USE_PRIORITIES
python main_program.py case30 0.5 0.0 True
python main_program.py case30 0.5 0.0 False
python main_program.py case30 0.5 0.5 True
python main_program.py case30 0.5 0.75 True
