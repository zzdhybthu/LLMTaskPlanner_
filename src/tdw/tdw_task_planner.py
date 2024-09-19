import random
import re
from typing import List, Any, Dict, Tuple
import pandas as pd
from omegaconf import DictConfig
import logging

from src.basic_planner import BasicPlanner

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class TdwTaskPlanner(BasicPlanner):
    def __init__(self, cfg: DictConfig, agent_id: int):
        super().__init__()
        self.cfg = cfg
        self.reset(model=cfg.planner.model_name, port=cfg.planner.port)
        self.wait_for_start()

        self.rooms_explored: Dict[str, str] = None
        self.goal_desc: str = None
        self.current_room: str = None
        self.object_list: List[Dict[str, Any]] = None
        self.holding_objects: List[Dict[str, Any]] = None
        self.obj_per_room: Dict[str, List[List[Dict[str, Any]]]] = None
        self.rooms: List[str] = []
        self.agent_id = agent_id
        self.agent_name = "Alice" if agent_id == 0 else "Bob"
        self.oppo_name = "Alice" if agent_id == 1 else "Bob"
        self.oppo_pronoun = "she" if agent_id == 1 else "he"

        self.debug: bool = cfg.debug
        self.cot: bool = cfg.planner.cot
        self.max_tokens: int = cfg.planner.max_tokens
        self.sampling_params: Dict[str, Any] = {
            "temperature": cfg.planner.temperature,
            "top_p": cfg.planner.top_p,
        }
        self.single = "single" in cfg.planner.prompt_template_name
        df= pd.read_csv(f"src/tdw/prompt/prompt_{cfg.planner.prompt_template_name}.csv")
        self.prompt_template: str = (
            df["prompt"][0]
            .replace("$AGENT_NAME$", self.agent_name)
            .replace("$OPPO_NAME$", self.oppo_name)
        )
        self.communication = "com" in cfg.planner.prompt_template_name and "nocom" not in cfg.planner.prompt_template_name
        if self.communication:
            self.generator_prompt_template: str = (
                df["prompt"][1]
                .replace("$AGENT_NAME$", self.agent_name)
                .replace("$OPPO_NAME$", self.oppo_name)
            )
        else:
            self.generator_prompt_template = None

    def Reset(self, rooms_name: List[str], goal_objects: Dict[str, int]):
        self.rooms = rooms_name
        self.goal_desc = self._goal2description(goal_objects)
        self.clear_usage()

    def Step(
        self,
        current_step: int,
        current_room: str,
        rooms_explored: Dict[str, str],
        holding_objects: List[Dict[str, Any]],
        satisfied: List[Dict[str, Any]],
        object_list: List[Dict[str, Any]],
        obj_per_room: Dict[str, List[List[Dict[str, Any]]]],
        action_history: List[str],
        dialogue_history: List[str],
        opponent_grabbed_objects: List[Dict[str, Any]]=None,
        opponent_last_room: str=None,
    ):
        info = {}
        log.info(f"Current_step: {current_step}")
        self.current_room = current_room
        self.rooms_explored = rooms_explored
        self.holding_objects = holding_objects
        self.object_list = object_list
        self.obj_per_room = obj_per_room
        progress_desc = self._progress2text(current_step, satisfied, opponent_grabbed_objects, opponent_last_room)
        action_history_desc = ", ".join(
            action_history[-10:] if len(action_history) > 10 else action_history
        )
        dialogue_history_desc = "\n".join(
            dialogue_history[-3:] if len(dialogue_history) > 3 else dialogue_history
        )
        prompt = self.prompt_template.replace("$GOAL$", self.goal_desc)
        prompt = prompt.replace("$PROGRESS$", progress_desc)
        prompt = prompt.replace("$ACTION_HISTORY$", action_history_desc)
        message = None

        if self.communication:
            prompt = prompt.replace("$DIALOGUE_HISTORY$", dialogue_history_desc)
            if not action_history[-1].startswith("send a message"):
                gen_prompt = self.generator_prompt_template.replace(
                    "$GOAL$", self.goal_desc
                )
                gen_prompt = gen_prompt.replace("$PROGRESS$", progress_desc)
                gen_prompt = gen_prompt.replace("$ACTION_HISTORY$", action_history_desc)
                gen_prompt = gen_prompt.replace(
                    "$DIALOGUE_HISTORY$", dialogue_history_desc
                )
                gen_prompt = gen_prompt + f"\n{self.agent_name}:"
                chat_prompt = [{"role": "user", "content": gen_prompt}]
                message = self.gen(messages=chat_prompt, max_tokens=self.max_tokens, **self.sampling_params)
                if len(message) > 0 and message[0] != '"':
                    message = re.search(r'"([^"]+)"', message)
                    if message:
                        message = '"' + message.group(1) + '"'
                info["prompt_comm"] = gen_prompt
                info["output_comm"] = message
                if self.debug:
                    log.info(f"Prompt_comm: {gen_prompt}")
                    log.info(f"Message: {message}")

        available_plans, num, available_plans_list = self._get_available_plans(message)
        if num == 0 or (message is not None and num == 1):
            log.info("Warning! No available plans!")
            plan = None
            info.update({"num_available_actions": num, "plan": None})
            return plan, info

        prompt = prompt.replace("$AVAILABLE_ACTIONS$", available_plans)

        if self.cot:
            prompt = prompt + " Let's think step by step."
            if self.debug:
                log.debug(f"Cot_prompt:\n{prompt}")
            chat_prompt = [{"role": "user", "content": prompt}]
            output = self.gen(messages=chat_prompt, max_tokens=self.max_tokens, **self.sampling_params)
            ## truncate the unfinished cot
            last_index = output.rfind(".")
            if last_index != -1:
                output = output[: last_index + 1]
            else:
                output += "."
            # info['outputs_cot'] = outputs
            # info['usage_plan_stage_1'] = usage
            if self.debug:
                log.info(f"Output_plan_stage_1:\n{output}")
            chat_prompt = [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": output},
                {"role": "user", "content": "Answer with only one best next action. So the answer is option"},
            ]
            normal_prompt = prompt + " " + output + " Answer with only one best next action. So the answer is "
            if self.cfg.planner.use_score:
                output = self.score(messages=chat_prompt, guided_choice=available_plans_list, max_tokens=self.max_tokens, **self.sampling_params)
                # output.replace("_", " ")
            else:
                output = self.gen(messages=chat_prompt, max_tokens=self.max_tokens, **self.sampling_params)
            # info['usage_plan_stage_2'] = usage
            if self.debug:
                log.info(f"Output_plan_stage_2:\n{output}")
        else:
            normal_prompt = prompt
            chat_prompt = [{"role": "user", "content": prompt}]
            if self.debug:
                log.debug(f"Normal_prompt:\n{prompt}")
            if self.cfg.planner.use_score:
                output = self.score(messages=chat_prompt, guided_choice=available_plans_list, max_tokens=self.max_tokens, **self.sampling_params)
                # output.replace('_', ' ')
            else:
                output = self.gen(messages=chat_prompt, max_tokens=self.max_tokens, **self.sampling_params)
            # info['usage_step_1'] = usage
            if self.debug:
                log.info(f"Output_step_1:\n{output}")
        # plan, flags = self._parse_answer(available_plans_list, output)
        plan, flags = output, "AC"
        if self.debug:
            log.debug(f"Plan: {plan}")
        info.update(
            {
                "num_available_actions": num,
                "prompt_plan_stage_2": normal_prompt,
                "output_plan_stage_2": output,
                "parse_exception": flags,
                "plan": plan,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
            }
        )
        return plan, info



    def _goal2description(self, goals: Dict[str, int]) -> str:  # {predicate: count}
        s = "Transport "
        for object_name, count in goals.items():
            s += f"{count} {object_name}{'s' if count > 1 else ''}, "
        s = s[:-2] + f" to the bed."
        return s

    def _parse_answer(self, available_actions: List[str], text: str) -> Tuple[str, str]:
        flags = "AC"
        for action in available_actions:
            if action.startswith("send a message:"):
                action = "send a message"
            if action.lower() in text.lower():
                return action, flags
        sents = text.split("\n")  # Split by space
        words = []
        for sent in sents:
            words.extend(sent.split(" "))
        words = list(filter(None, words))  # Remove empty strings from the result

        for i, action in enumerate(available_actions):
            option = chr(ord("A") + i)
            # txt = text.lower()
            if (
                f"option {option}" in text
                or f"{option}." in words
                or f"{option}," in words
                or f"{option}\n" in text.split(" ")
                or f"Option {option}" in text
                or f"({option})" in words
                or f"action {option}" in text
                or (len(text) <= 2 and option in text)
            ):
                return action, flags
        log.warning(f"Fuzzy match! {text}")
        flags = "Fuzzy match"
        for i, action in enumerate(available_actions):
            if self.communication and i == 0:
                continue
            act = "None"
            name = "None"
            id = "None"
            if action.startswith("go to"):
                # act = 'go to'
                name = action.split(" ")[-2][1:-1]
                id = action.split(" ")[-1][1:-1]
            elif action.startswith("explore"):
                act = "explore"
                name = action.split(" ")[-2][1:-1]
                id = action.split(" ")[-1][1:-1]
            elif action.startswith("go grasp"):
                act = "grasp"
                name = action.split(" ")[-2][1:-1]
                id = action.split(" ")[-1][1:-1]
            elif action.startswith("put"):
                act = "put"
            elif action.startswith("transport"):
                act = "transport"
            option = chr(ord("A") + i)
            if name in text and id in text:
                return action, flags
        for i, action in enumerate(available_actions):
            if self.communication and i == 0:
                continue
            act = "None"
            name = "None"
            id = "None"
            if action.startswith("go to"):
                # act = 'go to'
                name = action.split(" ")[-2][1:-1]
                id = action.split(" ")[-1][1:-1]
            elif action.startswith("explore"):
                act = "explore"
                name = action.split(" ")[-2][1:-1]
                id = action.split(" ")[-1][1:-1]
            elif action.startswith("go grasp"):
                act = "grasp"
                name = action.split(" ")[-2][1:-1]
                id = action.split(" ")[-1][1:-1]
            elif action.startswith("put"):
                act = "put"
            elif action.startswith("transport"):
                act = "transport"
            option = chr(ord("A") + i)
            if f"{option} " in text or act in text or name in text or id in text:
                return action, flags
        if len(text) == 1:
            i = ord(text) - ord("A")
            if i in range(len(available_actions)):
                return available_actions[i]
        log.warning("No available action parsed!!! Random choose one")
        flags = "failed to parse"
        return random.choice(available_actions), flags


    def _progress2text(
        self,
        current_step: int,
        satisfied: List[Dict[str, Any]],
        opponent_grabbed_objects: List[Dict[str, Any]],
        opponent_last_room: str,
    ) -> str:
        s = f"I've taken {current_step}/3000 steps. "

        sss = {}
        for room, obj_list in self.obj_per_room.items():
            sr = ""
            s_obj = ""
            s_con = ""
            s_bed = ""
            objs = obj_list[0]
            cons = obj_list[1]
            if len(objs) > 0:
                if len(objs) == 1:
                    x = objs[0]
                    s_obj += f"a target object <{x['name']}> ({x['id']})"
                else:
                    ss = ", ".join([f"<{x['name']}> ({x['id']})" for x in objs])
                    s_obj += f"target objects " + ss

            if len(cons) > 0:
                if len(cons) == 1:
                    x = cons[0]
                    s_con = f"a container <{x['name']}> ({x['id']})"
                else:
                    ss = ", ".join([f"<{x['name']}> ({x['id']})" for x in cons])
                    s_con = f"containers " + ss
            if len(obj_list[2]) > 0:
                s_bed = "the goal position bed"
            if s_obj == "" and s_con == "" and s_bed == "":
                sr += "nothing"
            elif s_obj != "" and s_con != "" and s_bed == "":
                sr += s_obj + ", and " + s_con
            elif s_obj != "" and s_con == "" and s_bed != "":
                sr += s_obj + ", and " + s_bed
            elif s_obj == "" and s_con != "" and s_bed != "":
                sr += s_con + ", and " + s_bed
            elif s_obj != "" and s_con != "" and s_bed != "":
                sr += s_obj + ", " + s_con + ", and " + s_bed
            else:
                sr += s_obj + s_con + s_bed
            sss[room] = sr

        if len(satisfied) == 0:
            if len(self.object_list[2]) == 0:
                s += "I haven't found the goal position bed. "
            else:
                s += ""
        else:
            s += f"{'I' if self.single else 'We'}'ve already transported "
            unique_satisfied = []
            for x in satisfied:
                if x not in unique_satisfied:
                    unique_satisfied.append(x)
            if len([x for x in unique_satisfied if x["type"] == 0]) == 0:
                s += "nothing"
            s += ", ".join(
                [
                    f"<{x['name']}> ({x['id']})"
                    for x in unique_satisfied
                    if x["type"] == 0
                ]
            )
            s += " to the bed. "

        s_hold = ["", ""]
        for i, obj in enumerate(self.holding_objects):
            if obj["type"] == 0:
                s_hold[i] = f"a target object <{obj['name']}> ({obj['id']}). "
            elif obj["type"] == 1:
                ss = ""
                cnt = 0
                for j, o in enumerate(obj["contained"]):
                    if o is None:
                        break
                    cnt += 1
                    ss += f"<{obj['contained_name'][j]}> ({o}), "
                if cnt == 0:
                    ss = "nothing"
                else:
                    ss = f"target object{'s' if cnt > 1 else ''} {ss[:-2]}"
                s_hold[i] = (
                    f"a container <{obj['name']}> ({obj['id']}) with {ss} in it. "
                )

        if (
            self.holding_objects[0]["type"] == 0
            and self.holding_objects[1]["type"] == 0
        ):
            s += f"I'm holding two target objects <{self.holding_objects[0]['name']}> ({self.holding_objects[0]['id']}) and <{self.holding_objects[1]['name']}> ({self.holding_objects[1]['id']}). "
        elif s_hold[0] == "" and s_hold[1] == "":
            s += "I'm holding nothing. "
        elif s_hold[0] != "" and s_hold[1] != "":
            s += f"I'm holding {s_hold[0][:-2]}, and {s_hold[1]}"
        else:
            s += f"I'm holding {s_hold[0]}{s_hold[1]}"

        if self.current_room not in self.rooms_explored:
            pred_room = "none"
        else:
            pred_room = self.rooms_explored[self.current_room]
        if pred_room != "all" and sss[self.current_room] == "nothing":
            s += f"I'm in the {self.current_room}, where I've explored {pred_room} of it. "
        else:
            s += f"I'm in the {self.current_room}, where I've explored {pred_room} of it and found {sss[self.current_room]}. "
        ### opponent modeling
        if not self.single:
            s_hold = ["", ""]
            for i, obj in enumerate(opponent_grabbed_objects):
                if obj["type"] == 0:
                    s_hold[i] = f"a target object <{obj['name']}> ({obj['id']}). "
                elif obj["type"] == 1:
                    ss = ""
                    cnt = 0
                    for j, o in enumerate(obj["contained"]):
                        if o is None:
                            break
                        cnt += 1
                        ss += f"<{obj['contained_name'][j]}> ({o}), "
                    if cnt == 0:
                        ss = "nothing"
                    else:
                        ss = f"target object{'s' if cnt > 1 else ''} {ss[:-2]}"
                    s_hold[i] = (
                        f"a container <{obj['name']}> ({obj['id']}) with {ss} in it. "
                    )
            if (
                opponent_grabbed_objects[0]["type"] == 0
                and opponent_grabbed_objects[1]["type"] == 0
            ):
                ss = f"two target objects <{opponent_grabbed_objects[0]['name']}> ({opponent_grabbed_objects[0]['id']}) and <{opponent_grabbed_objects[1]['name']}> ({opponent_grabbed_objects[1]['id']}). "
            if s_hold[0] == "" and s_hold[1] == "":
                ss = "nothing. "
            elif s_hold[0] != "" and s_hold[1] != "":
                ss = f"{s_hold[0][:-2]}, and {s_hold[1]}"
            else:
                ss = f"{s_hold[0]}{s_hold[1]}"

            if opponent_last_room is None:
                s += f"I don't know where {self.oppo_name} is. "
            elif opponent_last_room == self.current_room:
                s += f"I also see {self.oppo_name} here in the {self.current_room}, {self.oppo_pronoun} is holding {ss}"
            else:
                s += f"Last time I saw {self.oppo_name} was in the {opponent_last_room}, {self.oppo_pronoun} was holding {ss}"

        for room in self.rooms:
            if room == self.current_room:
                continue
            # s += f"I've explored {self.rooms_explored[room] if room in self.rooms_explored else 'None'} of the {room}, and I found {sss[room]} there. "
            if room not in self.rooms_explored:
                pred_room = "none"
            else:
                pred_room = self.rooms_explored[room]
            if pred_room != "all" and sss[room] == "nothing":
                s += f"I've explored {pred_room} of the {room}. "
            else:
                s += f"I've explored {pred_room} of the {room}, and I found {sss[room]} there. "

        return s


    def _get_available_plans(self, message: str) -> Tuple[str, int, List[str]]:
        """
        go to room {}
        explore current room {}
        go grasp target object / container {}
        holding both container and object: put obj into the container
        holding any goal objects: transport holding objects to the bed
        send a message: ""
        """
        available_plans = []
        if self.communication and message is not None:
            available_plans.append(f"send a message: {message}")
        if self.holding_objects[0]["type"] is None or self.holding_objects[1]["type"] is None:
            for obj in self.object_list[0]:
                available_plans.append(f"go grasp target object <{obj['name']}> ({obj['id']})")
            if not (self.holding_objects[0]["type"] == 1 or self.holding_objects[1]["type"] == 1):
                for obj in self.object_list[1]:
                    available_plans.append(f"go grasp container <{obj['name']}> ({obj['id']})")
        else:
            if self.holding_objects[0]["type"] == 1 and self.holding_objects[0]["contained"][-1] is None and self.holding_objects[1]["type"] == 0:
                available_plans.append(f"put <{self.holding_objects[1]['name']}> ({self.holding_objects[1]['id']}) into the container <{self.holding_objects[0]['name']}> ({self.holding_objects[0]['id']})")
            elif self.holding_objects[1]["type"] == 1 and self.holding_objects[1]["contained"][-1] is None and self.holding_objects[0]["type"] == 0:
                available_plans.append(f"put <{self.holding_objects[0]['name']}> ({self.holding_objects[0]['id']}) into the container <{self.holding_objects[1]['name']}> ({self.holding_objects[1]['id']})")
        if any(obj["type"] is not None for obj in self.holding_objects) and len(self.object_list[2]) != 0:
            available_plans.append(f"transport objects I'm holding to the bed")
        for room in self.rooms:
            if room == self.current_room or room is None or room == "None":
                continue
            available_plans.append(f"go to {room}")
        if self.current_room not in self.rooms_explored or self.rooms_explored[self.current_room] != "all":
            available_plans.append(f"explore current room {self.current_room}")

        plans = ""
        for i, plan in enumerate(available_plans):
            plans += f"{chr(ord('A') + i)}. {plan}\n"
            # plan.replace(' ', '_')

        return plans, len(available_plans), available_plans