import json
import copy
import random
from tqdm import trange

import sys
sys.path.insert(0, ".")

from src.sllm.sllm_env import MultiAgentEnv, Action
from dataset.sllm.script.dataset_config import skills, capacity_masses, capacity_nums



if __name__ == "__main__":
    omnipotent = json.load(open("./dataset/sllm/test/omnipotent_0.json", "r"))
    avail_robots = json.load(open("./dataset/sllm/resource/robots.json", "r"))
    env = MultiAgentEnv(time_scale=10000, all_robots=avail_robots)

    capacity_limited = copy.deepcopy(omnipotent)  # single robot with all skills and limited capacity
    skills_limited = copy.deepcopy(omnipotent)  # multiple robots with limited skills (necessary only) and unlimited capacity
    skills_limited_disruptive = copy.deepcopy(omnipotent)  # multiple robots with limited skills (necessary or unnecessary) and unlimited capacity
    comprehensive = copy.deepcopy(omnipotent)  # multiple robots with limited skills (necessary or unnecessary) and limited capacity

    for index in trange(len(omnipotent), desc="Processing"):
        task = omnipotent[index]
        floor_plan = task["floorplan"]
        robot_list = task["robot_list"]
        object_states = task["object_states"]
        solution_strs = task["solution"]
        solutions = [
            Action.from_str(solution_str, force_rbt_idx=0)
            for solution_str in solution_strs
        ]

        env.Reset(floor_plan=floor_plan, rbt_list=robot_list, final_states=object_states)
        for action in solutions:
            obs, reward, done, info = env.Step(action)
        results = env.GetResult()

        max_mass_index = 0
        max_num_index = 0
        skills_used = []
        while capacity_masses[max_mass_index] < env.current_max_mass:
            max_mass_index += 1
        while capacity_nums[max_num_index] < env.current_max_num:
            max_num_index += 1
        for i in range(len(skills)):
            for skill in skills[i]:
                if skill in env.current_actions_used:
                    skills_used.append(i)
                    break

        # print(
        #     f"\nSkills used: {skills_used}\n\
        #             Max mass: {capacity_masses[max_mass_index]}\n\
        #             Max num: {capacity_nums[max_num_index]}\n"
        # )

        # capacity_limited
        robot_available = {
            key: value
            for key, value in avail_robots.items()
            if value["capacity_mass"] == capacity_masses[max_mass_index]
            and value["capacity_num"] == capacity_nums[max_num_index]
            and len(value["skill_set_idx"]) == len(skills)
        }
        if len(robot_available) != 1:
            raise ValueError(
                f"No robot with all skills and corresponding capacity, found {len(robot_available)}"
            )
        capacity_limited[index]["robot_list"] = list(robot_available.keys())

        # skills_limited
        skills_splited = []
        if len(skills_used) == 0:
            skills_splited.append(set())
        elif len(skills_used) == 1:
            skills_splited.append(set())
            skills_splited.append(set(skills_used))
        elif len(skills_used) <= 3:
            for skill in skills_used:
                skills_splited.append(set([skill]))
        else:
            num0 = len(skills_used) // 3
            num1 = len(skills_used) // 3 + 1
            skills_splited.append(set(skills_used[:num0]))
            skills_splited.append(set(skills_used[num0 : num0 + num1]))
            skills_splited.append(set(skills_used[num0 + num1 :]))

        robot_available = {
            key: value
            for key, value in avail_robots.items()
            if value["capacity_mass"] == 100.0
            and value["capacity_num"] == 100
            and set(value["skill_set_idx"]) in skills_splited
        }
        robot_number = 1 if len(skills_used) == 0 else 2 if len(skills_used) <= 2 else 3
        if len(robot_available) != robot_number:
            raise ValueError(
                f"No robot with corresponding skills, found {len(robot_available)}"
            )
        skills_limited[index]["robot_list"] = list(robot_available.keys())
        random.shuffle(skills_limited[index]["robot_list"])

        # skills_limited_disruptive
        skills_splited = []
        skills_unused = [i for i in range(len(skills)) if i not in skills_used]
        if len(skills_used) == 0:
            skills_splited.append(set(skills_unused))
            skills_splited.append(set())
        elif len(skills_used) == 1:
            skills_splited.append(set(skills_used + skills_unused))
            skills_splited.append(set())
        elif len(skills_used) <= 3:
            for skill in skills_used:
                skills_splited.append(set([skill] + skills_unused))
        else:
            num0 = len(skills_used) // 3
            num1 = len(skills_used) // 3 + 1
            skills_splited.append(set(skills_used[:num0] + skills_unused))
            skills_splited.append(set(skills_used[num0 : num0 + num1] + skills_unused))
            skills_splited.append(set(skills_used[num0 + num1 :] + skills_unused))

        robot_available = {
            key: value
            for key, value in avail_robots.items()
            if value["capacity_mass"] == 100.0
            and value["capacity_num"] == 100
            and set(value["skill_set_idx"]) in skills_splited
        }
        robot_number = 2 if len(skills_used) <= 2 else 3
        if len(robot_available) != robot_number:
            raise ValueError(
                f"No robot with corresponding skills disruptive, found {len(robot_available)}"
            )
        skills_limited_disruptive[index]["robot_list"] = list(robot_available.keys())
        random.shuffle(skills_limited_disruptive[index]["robot_list"])

        # comprehensive
        robot_available = {
            key: value
            for key, value in avail_robots.items()
            if value["capacity_mass"] == capacity_masses[max_mass_index]
            and value["capacity_num"] == capacity_nums[max_num_index]
            and set(value["skill_set_idx"]) in skills_splited
        }
        if len(robot_available) != robot_number:
            raise ValueError(
                f"No robot with corresponding skills and capacity, found {len(robot_available)}"
            )
        comprehensive[index]["robot_list"] = list(robot_available.keys())
        random.shuffle(comprehensive[index]["robot_list"])

    with open("./dataset/sllm/test/capacity_limited_0.json", "w") as f:
        json.dump(capacity_limited, f, indent=4)
    with open("./dataset/sllm/test/skills_limited_0.json", "w") as f:
        json.dump(skills_limited, f, indent=4)
    with open("./dataset/sllm/test/skills_limited_disruptive_0.json", "w") as f:
        json.dump(skills_limited_disruptive, f, indent=4)
    with open("./dataset/sllm/test/comprehensive_0.json", "w") as f:
        json.dump(comprehensive, f, indent=4)
