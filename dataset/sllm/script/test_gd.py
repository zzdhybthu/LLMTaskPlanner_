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

def get_thoughts_realtime(setting, actions, obss):
    assert len(actions) == len(obss) + 1
    
    if len(obss) == 0:
        prompt = f"You have just started. Please generate a reasoning about why the next step is {actions[-1]}. For this first step first give me your general plan, then point out the exact next step plan. Do that in exact one line of two sentences."
    else:
        prompt = "History is like:\n"
        for action, obs in zip(actions, obss):
            prompt += f"Action: {action}\nObs: {obs}\n"
        prompt += f"Please generate a reasoning about why the next step is {actions[-1]}, in one line. Do not include the action in the reasoning. The reasoning should contain looking back to where we have achieved (except that it is the first step), make a general plan, then point out the exact next step plan."

    import openai
    client = openai.Client()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": setting},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content

def get_thoughts_throughout(setting, actions, obss):
    assert len(actions) == len(obss)
    
    prompt = "The whole game goes like:\n"
    episode = [
        {"action": action, "obs": obs}
        for action, obs in zip(actions, obss)
    ]
    episode = json.dumps({"steps": episode}, indent=4)
    prompt += episode
    prompt += "Please, for each step, generate another field called 'reasoning' preceeding the action and obs field given. The reasoning field should contain one line of two sentences. The first sentence describe a summary of what is achieved so far and how well it has aligned with the general plan. The second sentence describe the plan for the next step, like what is needed to be achieved in the next step, and what specific choices are needed for the specific action (like in a multiagent case which robot to command, what action is exactly needed).\n"
    prompt += "Return your answer as a parsable JSON object, a list of dictionaries, each dictionary containing 'reasoning', 'action', 'obs' fields in order."

    import openai
    client = openai.Client()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": setting},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    return response.choices[0].message.content

def evaluate(env: MultiAgentEnv, tasks, gen_reasoning=False):
    for task in tasks: 
        floor_plan = task['floorplan']
        robot_list = task['robot_list']
        object_states = task['object_states']
        solution = task['solution']
        task_desc = task['task']
        
        horizontal_line = f"{GREEN}{'#' * columns}{RESET}"
        print(f'{horizontal_line}\nTask: {task_desc}\n{horizontal_line}\n')
        
        env.Reset(floor_plan=floor_plan, rbt_list=robot_list, final_states=object_states)
        
        horizontal_line = f"{RED}{'=' * columns}{RESET}"
        obs_list = []
        robot_description = task['robot_description']
        setting = f"""
This is a manipulation task in a simulated environment. You should generate function-calling style actions to complete the given task.
Task Description: {task_desc}
Available Robots: robots = [{robot_description}]
"""
        for i, action in enumerate(solution):
            # reasoning = get_thoughts_realtime(task_desc, solution[:i+1], obs_list)
            obs, reward, done, info = env.Step(Action.from_str(action))
            obs_list.append(obs)
            if reward < 0:
                print(f'{horizontal_line}\nAction Failed!\n{horizontal_line}\nAction: {action}\nObs: {obs}\nReward: {reward}\nDone: {done}\nInfo: {info}\n{horizontal_line}\n') 
        task["obs_list"] = obs_list
        if gen_reasoning:
            trajectory = get_thoughts_throughout(setting, solution, obs_list)
            print(trajectory)
            # input("Press Enter to continue...")
            trajectory = json.loads(trajectory)["steps"]
            task["reasoning_list"] = [d["reasoning"] for d in trajectory]
        
        results = env.GetResult()
        
        horizontal_line = f"{YELLOW}{'*' * columns}{RESET}"
        if results['SR'] != 1:
            horizontal_line = f"{RED}{'*' * columns}{RESET}"
        print(f'{horizontal_line}\nResults: {results}\n{horizontal_line}\n')


def example_raw_to_good():
    example = json.load(open('./dataset/sllm/test/examples_raw.json', 'r'))
    for task in example:
        task["robot_list"] = []
        for robot in task["robot_description"]:
            robot_name_result = None
            for robot_name, info in avail_robots.items():
                if (robot["capacity_num"] == info["capacity_num"] and
                    robot["capacity_mass"] == info["capacity_mass"] and
                    ''.join(sorted(robot["skills"])) == ''.join(sorted(info["skills"]))
                ):
                    robot_name_result = robot_name
                    break
            if robot_name_result is None:
                print(f"Robot not found: {robot}")
            else:
                task["robot_list"].append(robot_name_result)
                print(f"Robot found: {robot_name_result} for {robot} matches {avail_robots[robot_name_result]}")
        task["object_states"] = []
    evaluate(env, example, gen_reasoning=True)
    json.dump(example, open('./dataset/sllm/test/examples_obs.json', 'w'), indent=4)

if __name__ == '__main__':
    avail_robots = json.load(open('./dataset/sllm/resource/robots.json', 'r'))
    env = MultiAgentEnv(time_scale=100, all_robots=avail_robots)
    
    # # select dataset to evaluate
    
    # omnipotent = json.load(open('./dataset/sllm/test/omnipotent.json', 'r'))
    # evaluate(env, omnipotent)
    
    # skills_limited = json.load(open('./dataset/sllm/test/skills_limited.json', 'r'))
    # evaluate(env, skills_limited)
    
    # skills_limited_disruptive = json.load(open('./dataset/sllm/test/skills_limited_disruptive.json', 'r'))
    # evaluate(env, skills_limited_disruptive)
    
    # comprehensive = json.load(open('./dataset/sllm/test/comprehensive.json', 'r'))
    # evaluate(env, comprehensive)

    example_raw_to_good()
