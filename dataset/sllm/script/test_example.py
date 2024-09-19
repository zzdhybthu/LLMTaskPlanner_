import json
import shutil

import sys
sys.path.insert(0, '.')

from src.sllm.sllm_env import MultiAgentEnv, Action

columns = shutil.get_terminal_size().columns
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'


if __name__ == '__main__':
    avail_robots = json.load(open('./dataset/sllm/resource/robots.json', 'r'))
    env = MultiAgentEnv(time_scale=100, all_robots=avail_robots)
    floor_plan = 9
    # robot_list = ['Habib_N1M1000']
    #         # "OpenObject",
    #         # "CloseObject",
    #         # "ToggleOnObject",
    #         # "ToggleOffObject",
    #         # "BreakObject",
    #         # "SliceObject",
    #         # "CleanObject",
    #         # "DirtyObject",
    #         # "FillObjectWithLiquid",
    #         # "EmptyLiquidFromObject"
            
    # robot_list = ['Barney_N1M100000', 'Bailey_N1M10']
    # #         "FillObjectWithLiquid",
    # #         "EmptyLiquidFromObject"
            
    # #         "ToggleOnObject",
    # #         "ToggleOffObject"
    
    # robot_list = ['Aaron_N1M1000', 'Eileen_N1M1000', 'Babette_N1M10']
    
    #         "ToggleOnObject",
    #         "ToggleOffObject",
    #         "SliceObject",
    #         "CleanObject",
    #         "DirtyObject"
            
    #         "OpenObject",
    #         "CloseObject"
    
    solution = [
        "GoToObject(robots[1],'Bread')",
        "PickUpObject(robots[1],'Bread')",
        "GoToObject(robots[1],'Fridge')",
        "GoToObject(robots[2],'Fridge')",
        "OpenObject(robots[2],'Fridge')",
        "PutObject(robots[1],'Bread','Fridge')",
        "CloseObject(robots[2],'Fridge')",
        "OpenObject(robots[2],'Fridge')",
        "GoToObject(robots[0],'Bread')",
        "PickUpObject(robots[0],'Bread')",
        "CloseObject(robots[2],'Fridge')",
        "GoToObject(robots[0],'Countertop')",
        "PutObject(robots[0],'Bread','CounterTop')"
    ]
    task_desc = "Chill the bread, freeze it, then put it on the counter."
    
    # horizontal_line = f"{GREEN}{'#' * columns}{RESET}"
    print(f'Task: {task_desc}\n\n')
    
    env.Reset(floor_plan=floor_plan, rbt_list=robot_list, final_states=[])
    
    # horizontal_line = f"{RED}{'=' * columns}{RESET}"
    for action in solution:
        print(f'Action: {Action.from_str(action)}')
        obs, reward, done, info = env.Step(Action.from_str(action))
        print(f'Observation: {obs}\n')
    
    
