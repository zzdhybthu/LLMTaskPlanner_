import json


def single_robot_solution(tasks):
    for task in tasks:
        new_solution = []
        for action in task["solution"]:
            idx = action.find("(")
            new_solution.append(action[:idx+1] + "robots[0], " + action[idx+1:])
        task["solution"] = new_solution


def multi_robots_solution(tasks, avail_robots, avail_objects):
    for task in tasks:
        floorplan = task["floorplan"]
        robots = [avail_robots[robot_name] for robot_name in task['robot_list']]
        
        new_solution = []
        
        actions_filtered = [action for action in task["solution"] if not (action.startswith("GoToObject") or action.startswith("PickUpObject"))]
        
        if len(actions_filtered) == 0:  # only GoToObject and PickUpObject, single robot solution
            for action in task["solution"]:
                idx = action.find("(")
                new_solution.append(action[:idx+1] + "robots[0], " + action[idx+1:])
            task["solution"] = new_solution
            continue
        
        
        robot_locating = [None for _ in robots]
        robot_holding = [None for _ in robots]
        
        close_action = []
        while len(actions_filtered) > 0:
            action = actions_filtered.pop(0)
            idx = action.find("(")
            skill = action[:idx]
            
            if skill == 'PutObject':  # obj must be holding and recep must be locating
                obj = action.split("\'")[1]
                recep = action.split("\'")[3]
                robot_idx = -1
                for i, hold in enumerate(robot_holding):
                    if hold == obj:
                        robot_idx = i
                        break
                if robot_idx == -1:
                    for i, locate in enumerate(robot_locating):
                        if locate == obj:
                            robot_idx = i
                            break
                    if robot_idx == -1:
                        skill_num_filtered = [len(robot['skill_set_idx']) if robot_holding[idx] is None else 100 for idx, robot in enumerate(robots)]
                        robot_idx = skill_num_filtered.index(min(skill_num_filtered))
                        new_solution.append(f"GoToObject(robots[{robot_idx}], '{obj}')")
                    new_solution.append(f"PickUpObject(robots[{robot_idx}], '{obj}')")
                    if len(close_action) > 0:
                        while len(close_action) > 0:
                            close = close_action.pop(0)
                            close_robot_idx = int(close.split("[")[1].split("]")[0])
                            close_locating = close.split("\'")[1]
                            if robot_locating[close_robot_idx] != close_locating:
                                new_solution.append(f"GoToObject(robots[{close_robot_idx}], '{close_locating}')")
                                robot_locating[close_robot_idx] = close_locating
                            new_solution.append(close)
                    new_solution.append(f"GoToObject(robots[{robot_idx}], '{recep}')")
                else:
                    if robot_locating[robot_idx] != recep:
                        new_solution.append(f"GoToObject(robots[{robot_idx}], '{recep}')")
                new_solution.append(f"PutObject(robots[{robot_idx}], '{obj}', '{recep}')")
                robot_locating[robot_idx] = recep
                robot_holding[robot_idx] = None
                
            else:
                obj = action.split("\'")[1]
                robot_idx = -1
                for i, robot in enumerate(robots):
                    if skill in robot["skills"]:
                        robot_idx = i
                        break
                if robot_idx == -1:
                    raise Exception("No robot can perform the skill")
                if skill == "BreakObject":  # obj is holding or locating depends
                    pickupables = [obj_['pickupable'] for obj_ in avail_objects[str(floorplan)] if obj_['objectType'] == obj]
                    if len(pickupables) == 0:
                        raise Exception("No object to break")
                    pickupable = pickupables[0]
                    if pickupable:
                        if robot_holding[robot_idx] != obj:
                            if robot_locating[robot_idx] != obj:
                                new_solution.append(f"GoToObject(robots[{robot_idx}], '{obj}')")
                            new_solution.append(f"PickUpObject(robots[{robot_idx}], '{obj}')")
                        if len(close_action) > 0:
                            while len(close_action) > 0:
                                close = close_action.pop(0)
                                close_robot_idx = int(close.split("[")[1].split("]")[0])
                                close_locating = close.split("\'")[1]
                                if robot_locating[close_robot_idx] != close_locating:
                                    new_solution.append(f"GoToObject(robots[{close_robot_idx}], '{close_locating}')")
                                    robot_locating[close_robot_idx] = close_locating
                                new_solution.append(close)
                        new_solution.append(action[:idx+1] + f"robots[{robot_idx}], " + action[idx+1:])
                        robot_locating[robot_idx] = obj
                        robot_holding[robot_idx] = obj
                    else:
                        if robot_locating[robot_idx] != obj:
                            new_solution.append(f"GoToObject(robots[{robot_idx}], '{obj}')")
                        new_solution.append(action[:idx+1] + f"robots[{robot_idx}], " + action[idx+1:])
                        robot_locating[robot_idx] = obj
                elif skill == "FillObjectWithLiquid" or skill == "EmptyLiquidFromObject":  # obj must be holding, CoffeeMachine or Faucet must be locating
                    liquid = action.split("\'")[3]
                    source = "Faucet" if liquid == "water" else "CoffeeMachine"
                    if robot_holding[robot_idx] != obj:
                        if robot_locating[robot_idx] != obj:
                            new_solution.append(f"GoToObject(robots[{robot_idx}], '{obj}')")
                        new_solution.append(f"PickUpObject(robots[{robot_idx}], '{obj}')")
                        if len(close_action) > 0:
                            while len(close_action) > 0:
                                close = close_action.pop(0)
                                close_robot_idx = int(close.split("[")[1].split("]")[0])
                                close_locating = close.split("\'")[1]
                                if robot_locating[close_robot_idx] != close_locating:
                                    new_solution.append(f"GoToObject(robots[{close_robot_idx}], '{close_locating}')")
                                    robot_locating[close_robot_idx] = close_locating
                                new_solution.append(close)
                        new_solution.append(f"GoToObject(robots[{robot_idx}], '{source}')")
                    else:
                        if robot_locating[robot_idx] != source:
                            new_solution.append(f"GoToObject(robots[{robot_idx}], '{source}')")
                    new_solution.append(action[:idx+1] + f"robots[{robot_idx}], " + action[idx+1:])
                    robot_locating[robot_idx] = source
                    robot_holding[robot_idx] = obj
                elif skill == "SliceObject":  # obj must be locating, Knife must be holding
                    tool = "Knife"
                    if robot_holding[robot_idx] != tool:
                        if robot_locating[robot_idx] != tool:
                            new_solution.append(f"GoToObject(robots[{robot_idx}], '{tool}')")
                        new_solution.append(f"PickUpObject(robots[{robot_idx}], '{tool}')")
                        if len(close_action) > 0:
                            while len(close_action) > 0:
                                close = close_action.pop(0)
                                close_robot_idx = int(close.split("[")[1].split("]")[0])
                                close_locating = close.split("\'")[1]
                                if robot_locating[close_robot_idx] != close_locating:
                                    new_solution.append(f"GoToObject(robots[{close_robot_idx}], '{close_locating}')")
                                    robot_locating[close_robot_idx] = close_locating
                                new_solution.append(close)
                        new_solution.append(f"GoToObject(robots[{robot_idx}], '{obj}')")
                    else:
                        if robot_locating[robot_idx] != obj:
                            new_solution.append(f"GoToObject(robots[{robot_idx}], '{obj}')")
                    new_solution.append(action[:idx+1] + f"robots[{robot_idx}], " + action[idx+1:])
                    robot_locating[robot_idx] = obj
                    robot_holding[robot_idx] = tool
                elif skill == "CloseObject" and len(new_solution) > 0 and new_solution[-1] == f"OpenObject(robots[{robot_idx}], '{obj}')":
                    close_action.append(f"CloseObject(robots[{robot_idx}], '{obj}')")  # must not close recep first if obj is not picked up
                else:  # obj must be locating
                    if robot_locating[robot_idx] != obj:
                        new_solution.append(f"GoToObject(robots[{robot_idx}], '{obj}')")
                    new_solution.append(action[:idx+1] + f"robots[{robot_idx}], " + action[idx+1:])
                    robot_locating[robot_idx] = obj
        
        new_solution.extend(close_action)
        task["solution"] = new_solution



if __name__ == "__main__":
    omnipotent = json.load(open("./dataset/sllm/test/omnipotent_0.json", "r"))
    single_robot_solution(omnipotent)
    json.dump(omnipotent, open("./dataset/sllm/test/omnipotent.json", "w"), indent=4)
    
    capacity_limited = json.load(open("./dataset/sllm/test/capacity_limited_0.json", "r"))
    single_robot_solution(capacity_limited)
    json.dump(capacity_limited, open("./dataset/sllm/test/capacity_limited.json", "w"), indent=4)
    
    
    avail_robots = json.load(open("./dataset/sllm/resource/robots.json", "r"))
    avail_objects = json.load(open("./dataset/sllm/resource/objects.json", "r"))
    
    skills_limited = json.load(open("./dataset/sllm/test/skills_limited_0.json", "r"))
    multi_robots_solution(skills_limited, avail_robots, avail_objects)
    json.dump(skills_limited, open("./dataset/sllm/test/skills_limited.json", "w"), indent=4)
    
    skills_limited_disruptive = json.load(open("./dataset/sllm/test/skills_limited_disruptive_0.json", "r"))
    multi_robots_solution(skills_limited_disruptive, avail_robots, avail_objects)
    json.dump(skills_limited_disruptive, open("./dataset/sllm/test/skills_limited_disruptive.json", "w"), indent=4)
    
    comprehensive = json.load(open("./dataset/sllm/test/comprehensive_0.json", "r"))
    multi_robots_solution(comprehensive, avail_robots, avail_objects)
    json.dump(comprehensive, open("./dataset/sllm/test/comprehensive.json", "w"), indent=4)