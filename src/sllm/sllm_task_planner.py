from typing import List
import logging
from copy import deepcopy
import asyncio

from src.basic_planner import BasicPlanner
from src.sllm.sllm_prompt import SllmPrompt
from .sllm_env import Action

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class SllmTaskPlanner(BasicPlanner):
    def __init__(self, cfg):
        super().__init__()
        # self.current_path = os.path.dirname(os.path.realpath(__file__))
        self.cfg = cfg
        self.cfg.planner.use_score = (
            self.cfg.planner.use_score
            and not self.cfg.planner.model_name.startswith("OpenAI")
        )
        self.reset(model=cfg.planner.model_name, port=cfg.planner.port)
        self.wait_for_start()
        self.num_steps = 0
        self.action_list = []
        self.obs_list = []

    def Reset(
        self,
        task_desc,
        actions: List[Action],
        objs,
        robots,
        liquids,
        multi_agent=False,
        detailed=True,
    ):
        self.actions = [action.to_str() for action in actions]
        prompt_user = SllmPrompt.user(task_desc=task_desc, robots=robots)
        prompt_no_score = SllmPrompt.no_score()
        prompt_moa_system = SllmPrompt.moa_aggregate_system_prompt(task_desc=task_desc)

        self.messages = []
        self.messages.append(
            {
                "role": "system",
                "content": (
                    (
                        SllmPrompt.system_multi_complete(objs=objs, liquids=liquids)
                        if detailed
                        else SllmPrompt.system_multi_concise(objs=objs, liquids=liquids)
                    )
                    if multi_agent
                    else (
                        SllmPrompt.system_single_complete(objs=objs, liquids=liquids)
                        if detailed
                        else SllmPrompt.system_single_concise(objs=objs, liquids=liquids)
                    )
                ),
            }
        )
        if  not self.cfg.planner.use_score:
            self.messages[0]["content"] += SllmPrompt.no_score()
        self.messages.append({"role": "user", "content": prompt_user})
        self.messages.append({"role": "assistant", "content": "Task Decomposition:\n"})
        self.prompt_no_score = prompt_no_score
        self.prompt_moa_system = prompt_moa_system
        self.clear_usage()
        self.num_steps = 0

    def Step(self, obs, prev_actions=[], prev_obs=[]) -> Action:
        self.obs_list.append(obs)
        def append_message(m: List, role: str, content: str):
            if m[-1]["role"] == role:
                m[-1]["content"] += content
            else:
                m.append({"role": role, "content": content})

        def rectify(s: str) -> str:
            if s.find(".") != -1:
                s = s.split(".")[0]
            return (
                s.replace("\n", "")
                .replace(" ", "")
                .replace("*", "")
                .replace(",", "")
                .strip("'")
                .strip('"')
                .strip()
            )

        if obs != "":
            append_message(self.messages, "user", obs)
        m = deepcopy(self.messages)

        def use_step(m: List) -> str:
            if not self.cfg.planner.use_score:
                step = self.gen(messages=m)
                step = rectify(step)
            else:
                step = self.score(messages=m, guided_choice=self.actions)
            return step

        def use_cot(m: List):
            append_message(
                m, "user", " Let's think step by step to figure out the next action."
            )
            output = self.gen(messages=m)
            last_index = output.rfind(".")
            output = output[: last_index + 1] if last_index != -1 else output + "."
            log.info(f"Cot Output: {output}")
            append_message(m, "assistant", output)
            append_message(
                m,
                "user",
                " Now answer with only one best next action. So the answer is: ",
            )
            return use_step(m)

        def use_moa(m: List):
            append_message(
                m,
                "user",
                " Let's figure out the next action. What do you think we should do?",
            )
            step = asyncio.run(
                self.moa(
                    reference_models=self.cfg.planner.reference_models,
                    reference_ports=self.cfg.planner.reference_ports,
                    reference_messages=m,
                    aggregate_model=self.cfg.planner.model_name,
                    aggregate_system_prompt=self.prompt_moa_system,
                    aggregate_method="score" if self.cfg.planner.use_score else "gen",
                    guided_choice=self.actions,
                    prev_actions=prev_actions,
                    prev_obs=prev_obs,
                    max_tokens=self.cfg.planner.max_tokens,
                )
            )
            if not self.cfg.planner.use_score:
                step = rectify(step)
            return step

        if self.cfg.planner.prompt_method == "cot":
            step = use_cot(m)
        elif self.cfg.planner.prompt_method == "moa":
            step = use_moa(m)
        else:
            step = use_step(m)

        append_message(self.messages, "assistant", step + "\n")

        try:
            act = Action.from_str(step)
        except Exception as e:
            log.error(f"Error: {e}")
            log.warning(f"Invalid action: {step}, action Done() will be taken.")
            act = Action.from_str("Done()")
        self.num_steps += 1
        self.action_list.append(act)
        return act


class SllmReactPlanner(SllmTaskPlanner):
    def __init__(self, cfg):
        assert cfg.planner.algo.startswith("react"), f"Invalid planner algo: {cfg.planner.algo}"
        self.use_reflect = ("reflect" in cfg.planner.algo)
        self.reasoning_list = []
        super().__init__(cfg)

    def Step(self, obs: str) -> Action:
        self.obs_list.append(obs)
        assert obs != ""
        
        extra = "\nPlease "
        if "failed" in obs.lower() and self.use_reflect:
            extra += "reflect why you failed the last step in one sentence. Then in the same line, "
        extra += "explain in words what is your plan to achieve the goal, in one sentence."
        self.messages.append({"role": "user", "content": obs + extra})
        think = self.gen(messages=self.messages, stop="\n")
        self.messages.append({"role": "assistant", "content": think})
        

        if self.cfg.planner.model_name.startswith("OpenAI") or not self.cfg.planner.use_score:
            self.messages.append({"role": "user", "content": self.prompt_no_score})
            step = self.gen(messages=self.messages)
            import json
            print(json.dumps(self.messages, indent=4), f"at {self.num_steps}, length {len(self.messages)}, got action <{step}>") # print for debug
            step = step.replace("\n", "")
            step = step.replace(" ", "")
            step = step.strip("\'")
            step = step.strip("\"")
            
        else:
            self.messages.append({"role": "user", "content": self.prompt_no_score})
            step = self.score(messages=self.messages, guided_choice=[action.to_str() for action in self.actions])
        if self.num_steps % 4 != 0: # remove thought process, to save tokens
            p = self.messages.pop(-2)
            q = self.messages.pop(-2)
            # input(f"removed thought process, {p}, {q}")
        self.messages[-1]["content"] = f"Obs: {obs} Action: " # save tokens; obs ends with "." itself
        self.messages.append({"role": "assistant", "content": step + "\n"})
        
        try:
            act = Action.from_str(step)
        except Exception as e:
            log.error(f"Error: {e}")
            log.warning(f"Invalid action: {step}, action Done() will be taken.")
            act = Action.from_str("Done()")
        self.num_steps += 1
        self.action_list.append(act)
        return act
