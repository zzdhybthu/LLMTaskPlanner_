import contextlib
import logging
from typing import List, Dict, Any
from omegaconf import OmegaConf
import os
import json
from datetime import datetime
from copy import deepcopy

from src.sllm.sllm_task_planner import SllmTaskPlanner, SllmReactPlanner
from src.sllm.sllm_env import MultiAgentEnv, Action


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class SllmEvaluator(object):
    def __init__(self, cfg):
        log.info(OmegaConf.to_yaml(cfg))
        self.cfg = cfg

    def evaluate(self):
        # if self.cfg.task_category == "all":
        #     omnipotent = json.load(open("./dataset/sllm/test/omnipotent.json", "r"))
        #     capacity_limited = json.load(open("./dataset/sllm/test/capacity_limited.json", "r"))
        #     skills_limited = json.load(open("./dataset/sllm/test/skills_limited.json", "r"))
        #     skills_limited_disruptive = json.load(open("./dataset/sllm/test/skills_limited_disruptive.json", "r"))
        #     comprehensive = json.load(open("./dataset/sllm/test/comprehensive.json", "r"))
        #     new_tasks = omnipotent + capacity_limited + skills_limited + skills_limited_disruptive + comprehensive
        # else:
        #     try:
        #         new_tasks = json.load(open(f"./dataset/sllm/test/{self.cfg.task_category}.json", "r"))
        #     except:
        #         raise FileNotFoundError(f"Fails to load tasks from ./dataset/sllm/test/{self.cfg.task_category}.json")
            
        new_tasks = json.load(open(f"./dataset/sllm/test/{self.cfg.task_category}.json", "r"))
        self.multi_agent = self.cfg.task_category.startswith("skills") or self.cfg.task_category == 'comprehensive'
        log.info('Use multi-agent mode.' if self.multi_agent else 'Use single-agent mode.')
        
        if self.cfg.num_tasks + self.cfg.start_from < len(new_tasks):
            log.info(f"Truncated to {self.cfg.num_tasks} tasks from the total of {len(new_tasks)}.")
            new_tasks = new_tasks[:self.cfg.num_tasks + self.cfg.start_from]

        if self.cfg.planner.algo.startswith("react"):
            self.planner = SllmReactPlanner(self.cfg)
        elif self.cfg.planner.algo == "baseline":
            self.planner = SllmTaskPlanner(self.cfg)
        else:
            raise ValueError(f"Unknown planner algo from {self.cfg.planner}")

        # deprecated. use self.env.all_robots instead
        self.avail_robots: Dict[str, Dict[str, Any]] = json.load(
            open("./dataset/sllm/resource/robots.json", "r")
        )
        for rbt in self.avail_robots.values():
            rbt.pop("skill_set_idx")
        self.avail_actions = json.load(
            open("./dataset/sllm/resource/actions.json", "r")
        )
        self.avail_liquids = json.load(
            open("./dataset/sllm/resource/liquids.json", "r")
        )
        self.env = MultiAgentEnv(time_scale=100, all_robots=self.avail_robots)
                
        test_results_whole: List[Dict[str, float]] = []
        for task in new_tasks[self.cfg.start_from:]:
            test_results_whole.append(self.evaluate_main(task))

        test_results: Dict[str, List[Dict[str, float]]] = {
            "whole": test_results_whole,
            "easy": [res for res in test_results_whole if res["level"] == "easy"],
            "moderate": [res for res in test_results_whole if res["level"] == "moderate"],
            "hard": [res for res in test_results_whole if res["level"] == "hard"],
        }
        
        KEYs = ["SR", "GCR", "SER", "TC", "PL", "CTC", "PTC", "TTC", "aTTFT", "Latency", "aTPOT", "aTPS"]
        overall_results: Dict[str, Dict[str, float]] = {key: {} for key in test_results.keys()}
        
        with contextlib.nullcontext("Beware of ZeroDivisionError, add meaningless terms"):
            for task_category, test_result in test_results.items():
                if len(test_result) == 0:
                    test_result.append({
                        **{key:0 for key in KEYs},
                        "task": "placeholder",
                    })
                for KEY in KEYs:
                    aKEY = "a" + KEY
                    overall_results[task_category].update({aKEY: sum([res[KEY] for res in test_result]) / len(test_result)})
                if test_result[-1]["task"] == "placeholder":
                    test_result.pop()
                overall_results[task_category].update({"num_tasks": len(test_result)})

        log.info(
            f"\n\
                Average Success Rate: {overall_results['whole']['aSR']}\n\
                Average Goal Completion Rate: {overall_results['whole']['aGCR']}\n\
                Average Success Execution Rate: {overall_results['whole']['aSER']}\n\
                Average Total Cost: {overall_results['whole']['aTC']}\n\
                Average Path Length: {overall_results['whole']['aPL']}\n\
                Average Completion Token Count: {overall_results['whole']['aCTC']}\n\
                Average Prompt Token Count: {overall_results['whole']['aPTC']}\n\
                Average Total Token Count: {overall_results['whole']['aTTC']}\n\
                Average (Overall) Time for First Token: {overall_results['whole']['aaTTFT']}\n\
                Average Latency: {overall_results['whole']['aLatency']}\n\
                Average (Overall) Time per Output Token: {overall_results['whole']['aaTPOT']}\n\
                Average (Overall) Tokens per Second: {overall_results['whole']['aaTPS']}\n\
            "
        )

        os.makedirs(self.cfg.result_path, exist_ok=True)
        date_time = datetime.now().strftime("%m-%d-%Y-%H-%M-%S")
        result_path = self.cfg.result_path + f'/sllm-{self.cfg.task_category}-' + (self.cfg.planner.model_name.split("/")[1] if "/" in self.cfg.planner.model_name else self.cfg.planner.model_name) + f'-{date_time}.json'
        log.info(f"Results saved to {result_path}")
        with open(result_path, "w") as f:
            save_dict = {
                "config": OmegaConf.to_container(self.cfg, resolve=True),
                "result": overall_results,
                "details": test_results_whole,
            }
            json.dump(save_dict, f, indent=4)

    def evaluate_main(self, task):
        log.info(task)
        floor_plan = task["floorplan"]
        level = task["level"]
        label = task["label"]
        task_desc = task["task"]
        robot_list = task["robot_list"]
        object_states = task["object_states"]

        obs, info = self.env.Reset(
            floor_plan=floor_plan, rbt_list=robot_list, final_states=object_states
        )
        log.info("Environment Reset!")

        env_objects = self.env.GetObjects()
        
        robot_desc: List[Dict[str, Any]] = [self.avail_robots[rbt] for rbt in robot_list]

        self.planner.Reset(
            task_desc=task_desc,
            actions=self.env.list_exec_actions(),
            objs=env_objects,
            robots=robot_desc,
            liquids=self.avail_liquids,
            multi_agent=self.multi_agent,
            detailed=self.cfg.planner.prompt_detail=="full",
        )

        num_steps = 0
        done = False
        actions: List[str] = []
        observations: List[str] = []
        while num_steps < self.cfg.max_action_num:
            num_steps += 1
            action = self.planner.Step(obs=obs if self.cfg.planner.use_feedback else "", prev_actions=actions, prev_obs=observations)
            if action.is_done():
                done = True
                log.info(f"Action: Done()")
                break
            try:
                obs, reward, done, info = self.env.Step(action)
                actions.append(action.to_str())
                observations.append(obs)
            except Exception as e:
                log.error(f"Error: {e}")
                log.warning(f"Some error occurred, action Done() will be taken.")
                break
            log.info(f"Action: {action.to_str()}    Obs: {obs}")
            log.debug(f"Reward: {reward}    Done: {done}    Info: {info}")
            if done:
                log.info(f"Task Completed!")

        results = self.env.GetResult()
        results.update(
            {
                "PL": num_steps,  # path length
                "CTC": self.planner.completion_tokens,  # completion token count
                "PTC": self.planner.prompt_tokens,  # prompt token count
                "TTC": self.planner.total_tokens,  # total token count
                "aTTFT": self.planner.aTTFT,  # average time for first token
                "Latency": self.planner.Latency,  # total latency
                "aTPOT": self.planner.aTPOT,  # average time per output token
                "aTPS": self.planner.aTPS,  # average tokens per second
                "task": task_desc,
                "floorPlan": floor_plan,
                "level": level,
                "label": label,
                "robots": robot_list,
                "object_states": object_states,
                "solution": actions,
                "observations": observations,
            }
        )

        log.info(f"\n\nResults: {results}\n\n")

        return results
