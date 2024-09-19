import json
from itertools import combinations, product

import sys
sys.path.insert(0, ".")

from dataset.sllm.script.dataset_config import skills, capacity_masses, capacity_nums


# combinations
skill_combinations = []
for i in range(0, len(skills) + 1):
    skill_combinations.append(list(combinations(range(len(skills)), i)))
capacity_combinations = list(product(capacity_nums, capacity_masses))


# name mapping
names = json.load(open("./dataset/sllm/resource/robot_names.json", "r"))

name_mapping = {}
for idx, skill_set in enumerate(skill_combinations):
    first_letter = chr(ord('A') + idx)
    for skill in skill_set:
        name = names[first_letter].pop(0)
        for num, mass in capacity_combinations:
            rbt_name = f"{name}_N{num}M{int(mass * 1000)}"
            name_mapping[rbt_name] = {
                "skills": [action for i in skill for action in skills[i]],
                "capacity_num": num,
                "capacity_mass": mass,
                "skill_set_idx": skill,
            }


json.dump(name_mapping, open("./dataset/sllm/resource/robots.json", "w"), indent=4)
