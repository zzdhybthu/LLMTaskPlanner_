    
import json
import re
import logging
import time
import threading
import numpy as np
import typing
from typing import Dict, List, Literal, Optional, Any
from copy import deepcopy
from pydantic.dataclasses import dataclass
from tqdm import trange

log = logging.getLogger(__name__)
log.setLevel(logging.ERROR)



class BasicSimulator(object):
    
    def __init__(self, floor_plan: int, all_robots: Dict[str, Dict[str, Any]]):
        if floor_plan != 0:
            self._SetEnv(floor_plan)
        self.all_robots = all_robots
        self.all_objects = json.load(open('./dataset/sllm/resource/objects.json', 'r'))
       
        
        
    def _SetEnv(self, floor_plan: int):
        objects_raw = deepcopy(self.all_objects[str(floor_plan)])
        
        seen_types = set()
        new_objects = []
        for obj in objects_raw:
            obj_type = obj['objectType']
            if obj_type not in seen_types:
                new_objects.append({
                    'objectId': obj['objectId'],
                    'objectType': obj_type,
                    'mass': obj['mass'],
                    'temperature': obj['temperature'],
                    'receptacle': obj['receptacle'],
                    'isHeatSource': obj['isHeatSource'],
                    'isColdSource': obj['isColdSource'],
                    'pickupable': obj['pickupable'],
                    'openable': obj['openable'],
                    'toggleable': obj['toggleable'],
                    'breakable': obj['breakable'],
                    'sliceable': obj['sliceable'],
                    'dirtyable': obj['dirtyable'],
                    'canFillWithLiquid': obj['canFillWithLiquid'],
                    'parentReceptacles': obj['parentReceptacles'],
                    'receptacleObjectIds': obj['receptacleObjectIds'],
                    'isPickedUp': obj['isPickedUp'],
                    'isOpen': obj['isOpen'],
                    'isToggled': obj['isToggled'],
                    'isBroken': obj['isBroken'],
                    'isSliced': obj['isSliced'],
                    'isDirty': obj['isDirty'],
                    'fillLiquid': obj['fillLiquid'],
                })
                seen_types.add(obj_type)

        self.objects = new_objects
        self._CleanEnv()
    
    
    
    def _CleanEnv(self):
        for obj in self.objects:
            if not obj['receptacle'] and obj['receptacleObjectIds'] is not None:
                obj['receptacleObjectIds'] = None
            elif obj['receptacle'] and obj['receptacleObjectIds'] is None:
                obj['receptacleObjectIds'] = []
            if obj['parentReceptacles'] is None:
                obj['parentReceptacles'] = []
                
        for obj in self.objects:
            if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
                parent_id = obj['parentReceptacles'][0]
                parent_obj = self.__find_obj_by_id_exact(parent_id)
                if parent_obj is None:
                    parent_obj = self.__find_obj_by_id(parent_id)
                    obj['parentReceptacles'] = [parent_obj['objectId']]
                if obj['objectId'] not in parent_obj['receptacleObjectIds']:
                    parent_obj['receptacleObjectIds'].append(obj['objectId'])
                    
        for obj in self.objects:
            if obj['receptacleObjectIds'] is not None:
                for child_id in obj['receptacleObjectIds']:
                    child_obj = self.__find_obj_by_id_exact(child_id)
                    if child_obj is None:
                        obj['receptacleObjectIds'].remove(child_id)
                    else:
                        child_obj['parentReceptacles'] = [obj['objectId']]
                        if child_id in obj['parentReceptacles']:
                            if len(obj['receptacleObjectIds']) > len(child_obj['receptacleObjectIds']):
                                obj['parentReceptacles'] = []
                                child_obj['receptacleObjectIds'].remove(obj['objectId'])
                            else:
                                child_obj['parentReceptacles'] = []
                                obj['receptacleObjectIds'].remove(child_id)
               
        stove = self.__find_obj_by_type('StoveBurner')
        if stove is not None:
            stove['toggleable'] = True
            stove['isToggled'] = False
        
        self.current_max_mass = 0
        self.current_max_num = 0
    
    def _SetRobot(self, rbt_list: List[str]):

        rbt_num = len(rbt_list)
        self.robot_names = rbt_list
        robots_used = [self.all_robots[name] for name in self.robot_names]
        self.robot_positions = [None] * rbt_num
        self.robot_pickup_objs = [[] for _ in range(rbt_num)]
        self.robot_capacity_num = [rbt['capacity_num'] for rbt in robots_used]
        self.robot_skills = [rbt['skills'] for rbt in robots_used]
        self.robot_capacity_mass = [rbt['capacity_mass'] for rbt in robots_used]
        
        log.info(f"Robot number: {rbt_num}")
        for idx, rbt in enumerate(robots_used):
            log.info(f"Robot{idx} has capacity_num: {rbt['capacity_num']}, capacity_mass: {rbt['capacity_mass']}, skills: {rbt['skills']}")
    
    
    
    def _GetResult(self, ground_truth: list):

        gcr_task = 0
        gcr_success = 0
        for grd in ground_truth:
            obj_type = grd['objectType']
            recep_obj_types_grd = grd['receptacleObjectTypes']
            stat_grd = grd['state']
            obj = self.__find_obj_by_type(obj_type)
            
            if len(recep_obj_types_grd) > 0:
                recep_objs = [self.__find_obj_by_id(obj_id) for obj_id in obj['receptacleObjectIds']]
                recep_objs_grd = [self.__find_obj_by_type(recep_obj_type) for recep_obj_type in recep_obj_types_grd]
                for recep_obj in recep_objs_grd:
                    gcr_task += 1
                    if recep_obj in recep_objs:
                        gcr_success += 1
            
            for key, value in stat_grd.items():
                gcr_task += 1
                if obj[key] == value:
                    gcr_success += 1    
                    
        
        return gcr_task, gcr_success
            
            
    
    def _GoToObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 物品必须存在
        2. 物体的所有父物体必须已被打开或不具备可打开属性
        3. 根物品不能已经被机器人拾取

        完成动作：
        1. 将机器人的位置设置为物品的根物体
        """
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type} not found."
        
        parent_objs = []
        self.__parent_iter(obj, lambda x: parent_objs.append(x))
        top_recep = parent_objs[-1]
        if top_recep['isPickedUp']:
            return False, f"{obj_type} is has already been picked up by some robot."
        
        
        self.robot_positions[rbt_idx] = top_recep
        
        
        return True, f"Robot{rbt_idx} has moved to {obj_type}."



    def _PickUpObject(self, rbt_idx: int, obj_type: str):
        """"
        完成条件：
        1. 机器人必须有空间存放物品
        2. 物品必须存在
        3. 物品必须可拾取
        4. 物品必须在机器人的可达范围内，或者机器人持有物品
        5. 若物体被机器人持有，则不能是根物体
        6. 物体的所有父物体必须已被打开或不具备可打开属性
        7. 物体及子物体的质量之和不能超过机器人的容量
        
        完成动作：
        1. 将物品放入机器人的拾取列表中
        2. 将物品以及其所有子物体的isPickedUp属性设置为True
        3. 若捡起的物体不是根物体，将物体与其父物体解耦
        4. 将所有位于该物体的机器人的位置设置为 None
        """
        
        if len(self.robot_pickup_objs[rbt_idx]) >= self.robot_capacity_num[rbt_idx]:
            return False, f"Robot{rbt_idx}'s capacity is full."
        
        # # robot with limited mass capacity, used for dataset generation only
        # self.current_max_num = max(self.current_max_num, len(self.robot_pickup_objs[rbt_idx]))
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        if not obj['pickupable']:
            return False, f"{obj_type} is not pickupable."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if obj not in reachable_objs:
            return False, f"{obj_type} not within reach."
        
        if obj in self.robot_pickup_objs[rbt_idx]:
            return False, f"{obj_type} is already picked up."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."

        obj_mass = []
        self.__son_iter(obj, lambda x: obj_mass.append(x['mass']))
        if sum(obj_mass) > self.robot_capacity_mass[rbt_idx]:
            return False, f"Picking up {obj_type} exceeds the robot{rbt_idx}'s mass capacity."
        
        # # robot with limited mass capacity, used for dataset generation only
        # self.current_max_mass = max(self.current_max_mass, sum(obj_mass))
        

        self.robot_pickup_objs[rbt_idx].append(obj)
        
        self.__son_iter(obj, lambda x: x.update({'isPickedUp': True}))
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            parent_recep = self.__find_obj_by_id(obj['parentReceptacles'][0])
            parent_recep['receptacleObjectIds'].remove(obj['objectId'])
            obj['parentReceptacles'].clear()

        for _robot_pos in self.robot_positions:
            if _robot_pos is obj:
                _robot_pos = None
        
        
        return True, f"Robot{rbt_idx} has picked up {obj_type}."

        
        
    def _PutObject(self, rbt_idx: int, obj_type: str, recep_type: str):
        """
        完成条件：
        1. 物体必须存在
        2. 物体必须被机器人持有
        3. 容器必须存在
        4. 容器必须在机器人的可达范围内或机器人持有物体
        5. 容器必须具有receptacle属性
        6. 容器及其所有父物体必须已被打开或不具备可打开属性
        7. 物体不能是容器的父物体
        
        完成动作：
        1. 将物体与放置点耦合
        2. 将物体及子物体的isPickedUp属性设置为False
        3. 将物体从机器人的拾取列表中移除
        4. 若父物体中有热源或冷源，将所有子物体的温度设置为容器的温度，热源会覆盖冷源
        """
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        if obj not in self.robot_pickup_objs[rbt_idx]:
            return False, f"Robot{rbt_idx} is not holding the object."
        
        recep = self.__find_obj_by_type(recep_type)
        if not recep:
            return False, f"{recep_type} not found."

        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if recep not in reachable_objs:
            return False, f"{recep_type} not within reach."
        
        if not recep['receptacle']:
            return False, f"{recep_type} is not a receptacle object."
        
        is_closed = self.__check_obj_open_status(recep)
        if len(is_closed) > 0:
            if is_closed[0] == recep_type:
                return False, f"{recep_type} is not open."
            else:
                return False, f"{recep_type}'s parent receptacle {is_closed[0]} is not open."
        
        recep_parent_objs = []
        self.__parent_iter(recep, lambda x: recep_parent_objs.append(x))
        if obj in recep_parent_objs:
            return False, f"{obj_type} is the parent object of the receptacle."
        
        
        recep['receptacleObjectIds'].append(obj['objectId'])
        obj['parentReceptacles'].append(recep['objectId'])

        self.__son_iter(obj, lambda x: x.update({'isPickedUp': False}))
        
        self.robot_pickup_objs[rbt_idx].remove(obj)
        
        recep_parent_hot_source = [x for x in recep_parent_objs if x['isHeatSource'] and x['isToggled']]
        recep_parent_cold_source = [x for x in recep_parent_objs if x['isColdSource'] and x['isToggled']]
        if len(recep_parent_cold_source) > 0:
            for cold_source in recep_parent_cold_source:
                self.__son_iter(cold_source, lambda x: x.update({'temperature': 'Cold'}))
        if len(recep_parent_hot_source) > 0:
            for hot_source in recep_parent_hot_source:
                self.__son_iter(hot_source, lambda x: x.update({'temperature': 'Hot'}))

        
        return True, f"Robot{rbt_idx} has put {obj_type} into {recep_type}."



    def _OpenObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力打开物品
        2. 物品必须存在
        3. 物品必须在机器人的可达范围内，或机器人持有物品
        4. 物体的所有父物体必须已被打开或不具备可打开属性
        5. 物品必须可打开
        
        完成动作：
        1. 将物品的isOpen属性设置为True
        """
        
        if not 'OpenObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to open objects."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if obj not in reachable_objs:
            return False, f"{obj_type} not within reach."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
        
        if not obj['openable']:
            return False, f"{obj_type} is not openable."
        
        if obj['isOpen']:
            return True, f"{obj_type} is already open."
        
        
        obj.update({"isOpen": True})
        
        
        return True, f"Robot{rbt_idx} has opened {obj_type}."



    def _CloseObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力关闭物品
        2. 物品必须存在
        3. 物品必须在机器人的可达范围内，或机器人持有物品
        4. 物体的所有父物体必须已被打开或不具备可打开属性
        5. 物品必须可打开
        
        完成动作：
        1. 将物品的isOpen属性设置为False
        """
        
        if not 'CloseObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to close objects."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if obj not in reachable_objs:
            return False, f"{obj_type} not within reach."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
        
        if not obj['openable']:
            return False, f"{obj_type} is not openable."
        
        if not obj['isOpen']:
            return True, f"{obj_type} is already closed."
        
        
        obj.update({"isOpen": False})
        
        
        return True, f"Robot{rbt_idx} has closed {obj_type}."



    def _ToggleOnObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力切换物品
        2. 物品必须存在
        3. 物品必须在机器人的可达范围内，或机器人持有物品
        4. 物体的所有父物体必须已被打开或不具备可打开属性
        5. 物品必须可切换
        
        完成动作：
        1. 将物品的isToggled属性设置为True
        2. 若物品是热源，将物品及其所有子物体的温度设置为Hot
        3. 若物品是冷源，将物品及其所有子物体的温度设置为Cold
        """
        
        if not 'ToggleOnObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to toggle on objects."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if obj not in reachable_objs:
            return False, f"{obj_type} not within reach."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
        
        if not obj['toggleable']:
            return False, f"{obj_type} is not toggleable."
        
        if obj['isToggled']:
            return True, f"{obj_type} is already toggled."
        
        
        obj.update({"isToggled": True})
        
        
        if obj['isHeatSource']:
            self.__son_iter(obj, lambda x: x.update({'temperature': 'Hot'}))
        elif obj['isColdSource']:
            self.__son_iter(obj, lambda x: x.update({'temperature': 'Cold'}))
        
        
        return True, f"Robot{rbt_idx} has toggled on {obj_type}."



    def _ToggleOffObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力切换物品
        2. 物品必须存在
        3. 物品必须在机器人的可达范围内，或机器人持有物品
        4. 物体的所有父物体必须已被打开或不具备可打开属性
        5. 物品必须可切换
        
        完成动作：
        1. 将物品的isToggled属性设置为False
        """
        
        if not 'ToggleOffObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to toggle off objects."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if obj not in reachable_objs:
            return False, f"{obj_type} not within reach."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
        
        if not obj['toggleable']:
            return False, f"{obj_type} is not toggleable."
        
        if not obj['isToggled']:
            return True, f"{obj_type} is already toggled off."
        
        
        obj.update({"isToggled": False})
        
        
        return True, f"Robot{rbt_idx} has toggled off {obj_type}."


    def _BreakObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力破坏物品
        2. 物品必须存在
        3. 若物品不可被持有，则必须在机器人的可达范围内
        4. 若物品可被持有，则必须被机器人持有
        5. 物体的所有父物体必须已被打开或不具备可打开属性
        6. 物品必须可破坏
        
        完成动作：
        1. 将物品及所有可破坏的子物体的isBroken属性设置为True
        """
        
        if not 'BreakObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to break objects."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        if not obj['pickupable']:
            reachable_objs = self.__find_reachable_objs(rbt_idx)
            if obj not in reachable_objs:
                return False, f"{obj_type} not within reach."
        else:
            picked_up_objs = self.__get_picked_objs(rbt_idx)
            if obj not in picked_up_objs:
                return False, "Pickupable object is not picked up by robot."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
        
        if not obj['breakable']:
            return False, f"{obj_type} is not breakable."
        
        if obj['isBroken']:
            return True, f"{obj_type} is already broken."
        
        def _break_obj(obj):
            if obj['breakable']:
                obj.update({'isBroken': True})
        self.__son_iter(obj, _break_obj)
        
        
        return True, f"Robot{rbt_idx} has broken {obj_type}."


    def _SliceObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力切割物品
        2. 机器人必须手持刀具，且刀具是根物体
        3. 物品必须存在
        4. 物品必须在机器人的可达范围内，或机器人持有物品
        5. 物体的所有父物体必须已被打开或不具备可打开属性
        6. 物品必须可切割
        
        完成动作：
        1. 将物品及所有可切割的子物体的isSliced属性设置为True
        """
        
        if not 'SliceObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to slice objects."
        
        knife = self.__find_obj_by_type('Knife')
        if not knife in self.robot_pickup_objs[rbt_idx]:
            return False, f"Robot{rbt_idx} is not holding a knife."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if obj not in reachable_objs:
            return False, f"{obj_type} not within reach."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
        
        if not obj['sliceable']:
            return False, f"{obj_type} is not sliceable."
        
        if obj['isSliced']:
            return True, f"{obj_type} is already sliced."
        
        
        def _slice_obj(obj):
            if obj['sliceable']:
                obj.update({'isSliced': True})
        self.__son_iter(obj, _slice_obj)
        
        
        return True, f"Robot{rbt_idx} has sliced {obj_type}."


    def _CleanObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力清洁物品
        2. 物品必须存在
        3. 物品必须在机器人的可达范围内，或机器人持有物品
        4. 物体的所有父物体必须已被打开或不具备可打开属性
        5. 物品必须可清洁
        
        完成动作：
        1. 将物品的isDirty属性设置为False
        """
        
        if not 'CleanObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to clean objects."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if obj not in reachable_objs:
            return False, f"{obj_type} not within reach."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
        
        if not obj['dirtyable']:
            return False, f"{obj_type} is not dirtyable."
        
        if not obj['isDirty']:
            return True, f"{obj_type} is already clean."
        
        
        obj.update({"isDirty": False})
        
        
        return True, f"Robot{rbt_idx} has cleaned {obj_type}."



    def _DirtyObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力弄脏物品
        2. 物品必须存在
        3. 物品必须在机器人的可达范围内，或机器人持有物品
        4. 物体的所有父物体必须已被打开或不具备可打开属性
        5. 物品必须可弄脏
        
        完成动作：
        1. 将物品的isDirty属性设置为True
        """
        
        if not 'DirtyObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to dirty objects."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx) + self.__get_picked_objs(rbt_idx)
        if obj not in reachable_objs:
            return False, f"{obj_type} not within reach."
        
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
        
        if not obj['dirtyable']:
            return False, f"{obj_type} is not dirtyable."
        
        if obj['isDirty']:
            return True, f"{obj_type} is already dirty."
        
        
        obj.update({"isDirty": True})
        
        
        return True, f"Robot{rbt_idx} has dirtied {obj_type}."


    def _FillObjectWithLiquid(self, rbt_idx: int, obj_type: str, liquid_type: str):
        """
        完成条件：
        1. 机器人必须有能力向物品中注入液体
        2. 物品必须存在
        3. 物体必须被机器人持有
        4. 物体的所有父物体必须已被打开或不具备可打开属性
        5. 物体必须是可装液体的
        6. 若液体是water，则机器人必须在Faucet旁边，且Faucet必须是打开状态
        7. 若液体是coffee，则机器人必须在CoffeeMachine旁边，且CoffeeMachine必须是打开状态
        8. 不能是其它液体
        
        完成动作：
        1. 将物品的fillLiquid属性设置为liquid_type
        """
        
        if not 'FillObjectWithLiquid' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to fill objects with liquid."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        picked_up_objs = self.__get_picked_objs(rbt_idx)
        if obj not in picked_up_objs:
            return False, f"{obj_type} is not picked up by robot{rbt_idx}."

        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
            
        if not obj['canFillWithLiquid']:
            return False, f"{obj_type} cannot be filled with liquid."
        
        if obj['fillLiquid'] is not None:
            return True, f"{obj_type} is already filled with liquid."
        
        reachable_objs = self.__find_reachable_objs(rbt_idx)
        if liquid_type == 'water':
            faucet = self.__find_obj_by_type('Faucet')
            if not faucet:
                return False, "Faucet not found."
            if faucet not in reachable_objs:
                return False, "Faucet not within reach."
            if not faucet['isToggled']:
                return False, "Faucet is not turned on."
        elif liquid_type == 'coffee':
            coffee_machine = self.__find_obj_by_type('CoffeeMachine')
            if not coffee_machine:
                return False, "CoffeeMachine not found."
            if coffee_machine not in reachable_objs:
                return False, "CoffeeMachine not within reach."
            if not coffee_machine['isToggled']:
                return False, "CoffeeMachine is not turned on."
        else:
            return False, f"{liquid_type} is not a valid liquid type."
        
        
        obj.update({'fillLiquid': liquid_type})
        
        
        return True, f"Robot{rbt_idx} has filled {obj_type} with {liquid_type}."
        
            
        

    def _EmptyLiquidFromObject(self, rbt_idx: int, obj_type: str):
        """
        完成条件：
        1. 机器人必须有能力将物品中的液体倒出
        2. 物品必须存在
        3. 物体必须被机器人持有
        4. 物体的所有父物体必须已被打开或不具备可打开属性
        5. 物体必须是可装液体的
        
        完成动作：
        1. 将物品的fillLiquid属性设置为None
        """
        
        if not 'EmptyLiquidFromObject' in self.robot_skills[rbt_idx]:
            return False, f"Robot{rbt_idx} does not have the skill to empty liquid from objects."
        
        obj = self.__find_obj_by_type(obj_type)
        if not obj:
            return False, f"{obj_type} not found."
        
        picked_up_objs = self.__get_picked_objs(rbt_idx)
        if obj not in picked_up_objs:
            return False, f"{obj_type} is not picked up by robot{rbt_idx}."

        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            is_closed = self.__check_obj_open_status(self.__find_obj_by_id(obj['parentReceptacles'][0]))
            if len(is_closed) > 0:
                return False, f"{obj_type}'s parent receptacle {is_closed[0]} is not open."
            
        if not obj['canFillWithLiquid']:
            return False, f"{obj_type} cannot be filled with liquid."
        
        if obj['fillLiquid'] is None:
            return True, f"{obj_type} is already empty."
        
        
        obj.update({'fillLiquid': None})
        
        
        return True, f"Robot{rbt_idx} has emptied liquid from {obj_type}."
    
    
    
    def _GetObjects(self):
        return [obj['objectType'] for obj in self.objects]
    def _GetReceptacleObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['receptacle']]
    def _GetOpenedObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['openable'] and obj['isOpen']]
    def _GetClosedObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['openable'] and not obj['isOpen']]
    def _GetToggledOnObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['toggleable'] and obj['isToggled']]
    def _GetToggledOffObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['toggleable'] and not obj['isToggled']]
    def _GetBrokenObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['breakable'] and obj['isBroken']]
    def _GetUnbrokenObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['breakable'] and not obj['isBroken']]
    def _GetSlicedObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['sliceable'] and obj['isSliced']]
    def _GetUnslicedObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['sliceable'] and not obj['isSliced']]
    def _GetDirtyObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['dirtyable'] and obj['isDirty']]
    def _GetCleanObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['dirtyable'] and not obj['isDirty']]
    def _GetPickupableObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['pickupable']]
    def _GetFilledWithLiquidObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['canFillWithLiquid'] and obj['fillLiquid'] is not None]
    def _GetUnfilledWithLiquidObjects(self):
        return [obj['objectType'] for obj in self.objects if obj['canFillWithLiquid'] and obj['fillLiquid'] is None]
    def _GetHeatSource(self):
        return [obj['objectType'] for obj in self.objects if obj['isHeatSource']]
    def _GetColdSource(self):
        return [obj['objectType'] for obj in self.objects if obj['isColdSource']]
    def _GetRecepRelationship(self):
        return {obj['objectType']: [self.__find_obj_by_id(obj_id)['objectType'] for obj_id in obj['receptacleObjectIds']] for obj in self.objects if obj['receptacle']}
    def _GetObjectMass(self):
        return {obj['objectType']: round(obj['mass'], 2) for obj in self.objects}
    
    
    
    def __son_iter(self, obj: dict, func: callable, *args, **kwargs):
        """
        Iterates through all the children of an object.
        
        Args:
            obj (dict): The object whose children to iterate through.
            func (callable): The function to call on each child object.
            *args: Additional arguments to pass to the function.
            **kwargs: Additional keyword arguments to pass to the function.
        """
        func(obj, *args, **kwargs)
        if obj['receptacleObjectIds'] is not None:
            for obj_id in obj['receptacleObjectIds']:
                self.__son_iter(self.__find_obj_by_id(obj_id), func)

    def __parent_iter(self, obj: dict, func: callable, *args, **kwargs):
        """
        Iterates through all the parents of an object.
        
        Args:
            obj (dict): The object whose parents to iterate through.
            func (callable): The function to call on each parent object.
            *args: Additional arguments to pass to the function.
            **kwargs: Additional keyword arguments to pass to the function.
        """
        func(obj, *args, **kwargs)
        if obj['parentReceptacles'] is not None and len(obj['parentReceptacles']) > 0:
            self.__parent_iter(self.__find_obj_by_id(obj['parentReceptacles'][0]), func)



    def __find_obj_by_type(self, obj_type: str):
        """
        Finds an object by its type.
        
        Args:
            obj_type (str): The type of the object to be found.
            
        Returns:
            dict: The object with the specified type.
        """
        def __normalize_text(text: str):
            lower_text = text.lower()
            clean_text = re.sub(r'[^a-z]', '', lower_text)
            return clean_text
        
        for obj in self.objects:
            if __normalize_text(obj['objectType']) == __normalize_text(obj_type):
                return obj
        else:
            return None

    def __find_obj_by_id(self, obj_id: str):
        """
        Finds an object by its id.
        
        Args:
            obj_id (str): The id of the object to be found.
            
        Returns:
            dict: The object with the specified id.
        """
        for obj in self.objects:
            if obj['objectId'] == obj_id:
                return obj
        obj_type = obj_id[:obj_id.find('|')]
        return self.__find_obj_by_type(obj_type)
    
    def __find_obj_by_id_exact(self, obj_id: str):
        """
        Finds an object by its id.
        
        Args:
            obj_id (str): The id of the object to be found.
            
        Returns:
            dict: The object with the specified id.
        """
        for obj in self.objects:
            if obj['objectId'] == obj_id:
                return obj
        return None

    def __find_reachable_objs(self, rbt_idx: int):
        """
        Finds all objects reachable by the robot.
        
        Args:
            rbt_idx (int): The index of the robot.
            
        Returns:
            list: A list of objects reachable by the robot.
        """
        reachable_objs = []
        if self.robot_positions[rbt_idx] is not None:
            self.__son_iter(self.robot_positions[rbt_idx], lambda x: reachable_objs.append(x))
        return reachable_objs

    def __get_picked_objs(self, rbt_idx: int):
        """
        Gets all objects picked up by the robot.
        
        Args:
            rbt_idx (int): The index of the robot.
            
        Returns:
            list: A list of objects picked up by the robot.
        """
        picked_objs = []
        for obj in self.robot_pickup_objs[rbt_idx]:
            self.__son_iter(obj, lambda x: picked_objs.append(x))
        return picked_objs

    def __check_obj_open_status(self, obj: dict):
        """
        Checks if object is open.
        
        Args:
            obj (dict): The object to be checked.
            
        Returns:
            bool: True if the parent object is open, False otherwise.
        """
        is_open = {}
        self.__parent_iter(obj, lambda x: is_open.update({x['objectType']: not x['openable'] or x['isOpen']}))
        return [x for x in is_open.keys() if not is_open[x]]


ActionType = Literal["GoToObject", "PickUpObject", "PutObject", "OpenObject", "CloseObject", "ToggleOnObject", 
                    "ToggleOffObject", "BreakObject", "SliceObject", "CleanObject", "DirtyObject", 
                    "FillObjectWithLiquid", "EmptyLiquidFromObject",
                    "Done"]
ALL_ACTIONS: List[ActionType] = typing.get_args(ActionType) # type: ignore
LiquidType = Literal["coffee", "water"]
ALL_LIQUIDS: List[LiquidType] = typing.get_args(LiquidType) # type: ignore

@dataclass
class Action:
    action: ActionType
    rbt_idx: int
    obj: str
    recep: Optional[str] = None
    liquid: Optional[str] = None
    
    @staticmethod
    def from_str(action_str: str, force_rbt_idx: Optional[int] = None):
        """
            Params:
                `force_rbt_idx` is specified if the action is a solution.
                    A solution does not specify a robot idx but this class requires one.
            Usage:
                If action contains robot id, `Action.from_str("FillObjectWithLiquid(robots[i], 'Cup', 'water')")`
                Otherwise, you are parsing a solution, `Action.from_str("FillObjectWithLiquid('Cup', 'water')", force_rbt_idx=1)`
        """
        if "Done()" in action_str:
            return Action.Done()
        action: ActionType = action_str.split("(")[0] # type: ignore
        if force_rbt_idx is not None:
            rbt_idx = force_rbt_idx
        else:
            rbt_idx = int(action_str.split("[")[1].split("]")[0])
        obj = action_str.split("'")[1]
        recep = action_str.split("'")[3] if action == "PutObject" else None
        liquid = (
            action_str.split("'")[3] if action == "FillObjectWithLiquid" else None
        )
        return Action(action, rbt_idx, obj, recep, liquid)
    
    @staticmethod
    def Done():
        return Action("Done", 0, "")
    
    def is_done(self) -> bool:
        return self.action == "Done"
    
    def to_str(self) -> str:
        if self.is_done():
            return "Done()"
        if self.liquid and self.recep:
            raise ValueError("Cannot have both receptacle and liquid types.")
        elif self.recep and not self.liquid:
            return f"{self.action}(robots[{self.rbt_idx}],'{self.obj}','{self.recep}')"
        elif self.liquid and not self.recep:
            return f"{self.action}(robots[{self.rbt_idx}],'{self.obj}','{self.liquid}')"
        else: # both are None
            return f"{self.action}(robots[{self.rbt_idx}],'{self.obj}')"
    
    def __str__(self):
        return self.to_str()
    
# def select_robots_for_skills(robots: Dict[str, dict], skills: List[ActionType], prefer_k: int = 2, max_iter: int = 1000) -> List[str]:
#     """
#     A tool to select agents for a task.
#     Usage: get_robots_for_skills(env.all_robots, ["PickUpObject", "PutObject"])
#     The param `skills` is extraced from the `solution` from `new_tasks.json`. `Done` is not contained. `GoToObject` is neglected as every robot has this skill.
#     `prefer_k` means the number of robots you want to select. On failure a 1-robot solution is returned
#     Returns a list of solutions. Each solution is a list of robot names that can perform the given skills altogether.
#     """
#     robots = deepcopy(robots)
#     skills = deepcopy(skills)
#     while "GoToObject" in skills:
#         skills.remove("GoToObject")
#     robot_skills = [robot["skills"] for robot in robots.values()]
#     for skillset in robot_skills:
#         skillset.append("GoToObject")
#         skillset.append("Done")
#     robot_names = list(robots.keys())

#     all_solutions: List[List[str]] = []

#     for i in reversed(range(len(robot_names))):
#         skillset = set(robot_skills[i])
#         if skillset.issuperset(set(skills)):
#             all_solutions.append([robot_names[i]])
#             robot_skills.pop(i)
#             robot_names.pop(i)
#         if not skillset.intersection(set(skills)):
#             robot_skills.pop(i)
#             robot_names.pop(i)


    
#     try:
#         for _ in trange(max_iter):    
#             arr = np.zeros((len(robot_names), len(skills)))
#             for i, robot in enumerate(robot_skills):
#                 for j, skill in enumerate(skills):
#                     arr[i, j] = skill in robot
#             indices = ec.get_exact_cover(arr)
#             names = [robot_names[i] for i in indices]
#             all_solutions.append(names)

#             for i in reversed(indices):
#                 robot_skills.pop(i)
#                 robot_names.pop(i)
#     except ec.wrapper.NoSolution:
#         pass    
#     solutions_by_len = {len(solution): solution for solution in all_solutions}
#     log.info(f"select_robots_for_skills: {all_solutions}")
#     # return list(all_solutions.values())
#     if 2 in solutions_by_len:
#         return solutions_by_len[2]
#     else:
#         return solutions_by_len[1]

class MultiAgentEnv(BasicSimulator):
    
    def __init__(self, time_scale: float=1.0, all_robots: Dict[str, Dict[str, Any]] = {}):
        """
        Initialize the simulator.
        
        Args:
            time_scale (float): The time scale of the simulator.
        
        """
        
        super().__init__(0, all_robots)
        self.exec_action = 0
        self.exec_success = 0
        self.exec_time = 0.0
        self.time_scale = time_scale
        self.lock = threading.Lock()



    def Reset(self, floor_plan: int, rbt_list: List[str], final_states: list):
        """
        Reset the robot and the environment.
        
        Args:
            floor_plan (int): The floor plan of the environment.
            rbt_list (list): The list of robot names.
            final_states (list): The final states of the objects.
            
        Returns:
            tuple: A tuple containing the observation string and info dictionary.
        """
        
        self.lock.acquire()
        self._SetEnv(floor_plan)
        self._SetRobot(rbt_list)
        self.exec_action = 0
        self.exec_success = 0
        self.exec_time = 0.0
        self.final_states = final_states
        self.lock.release()
        
        obs = ""
        info = {"action": "reset", "floor_plan": floor_plan, "robot_list": rbt_list}
        
        # # robot with limited skills, used for dataset generation only
        # self.current_actions_used = set()
        
        return obs, info
            
            

    def Step(self, action: Action):
        """
        Perform an action in the environment.
        
        Args:
            action (dict): The action to be performed.
            
        Returns:
            tuple: A tuple containing the observation string, reward, done flag, and info dictionary.
        """
        
        action_type = action.action
        rbt_idx = action.rbt_idx
        obj_type = action.obj
        recep_type = action.recep
        liquid_type = action.liquid
        
        if action_type not in ALL_ACTIONS: # actually pydantic has done this for you, in class Action
            return "Invalid action type.", -1, False, {}
        
        # # robot with limited skills, used for dataset generation only
        # if action_type != "Done" and action_type != "GoToObject":
        #     self.current_actions_used.add(action_type)
        
        self.lock.acquire()
        gcr_task0, gcr_success0 = self._GetResult(self.final_states)
        
        try:
            success, message = getattr(self, action_type)(rbt_idx, obj_type) if recep_type is None and liquid_type is None else getattr(self, action_type)(rbt_idx, obj_type, recep_type or liquid_type)
        except Exception as e:
            return str(e), 0, False, {}
        
        gcr_task, gcr_success = self._GetResult(self.final_states)
        self.lock.release()
        
        obs = message if success else f"Action failed. {message}"
        reward = -1 if not success else max(gcr_success - gcr_success0 + 1, 0)
        done = gcr_task == gcr_success
        info = {"action": action_type, "robot_index": rbt_idx, "object_type": obj_type, "receptacle_type": recep_type, "liquid_type": liquid_type}
        
        return obs, reward, done, info
    
    def list_exec_actions_by_skills(self, robot_skills: List[ActionType], rbt_idx=0) -> List[Action]:
        avail_exec_actions: List[Action] = []
        env_objects = self.GetObjects()
        for action in robot_skills:
            assert action in ALL_ACTIONS, f"Invalid action type: {action}."
            if action == "PutObject":
                avail_exec_actions.extend([
                    Action(action, rbt_idx, obj, recep=recep)
                    for obj in env_objects["PickUpObjects"]
                    for recep in env_objects["PutObjects"]
                ])
            elif action == "FillObjectWithLiquid":
                avail_exec_actions.extend([
                    Action(action, rbt_idx, obj, liquid=liq)
                    for obj in env_objects["FillObjectWithLiquids"]
                    for liq in ALL_LIQUIDS
                ])
            else:
                avail_exec_actions.extend([
                    Action(action, rbt_idx, obj)
                    for obj in env_objects[f"{action}s"]
                ])
        return avail_exec_actions
    
    def list_exec_actions(self) -> List[Action]:
        result: List[Action] = []
        for rbt_idx in range(len(self.robot_names)):
            result.extend(self.list_exec_actions_by_skills(self.robot_skills[rbt_idx] + ["GoToObject", "PickUpObject", "PutObject"], rbt_idx))
        result.append(Action.Done())
        return result

    def GetResult(self):
        """
        Get the result of the task.
            
        Returns:
            dict: The result of the task.
        """
        
        self.lock.acquire()
        gcr_task, gcr_success = self._GetResult(self.final_states)
        self.lock.release()
        
        GCR = 1 if gcr_task == 0 else gcr_success / gcr_task
        GCR = 1 if GCR > 1 else GCR
        SR = 1 if GCR == 1 else 0
        SER = 1 if self.exec_action == 0 else self.exec_success / self.exec_action
        TC = self.exec_time
        
        results = {
            "GCR": GCR,  # Goal Completion Rate
            "SR": SR,  # Success Rate
            "SER": SER,  # Success Execution Rate
            "TC": TC,  # Total Cost
        }
        
        log.info(f"Results: GCR={GCR}, SR={SR}, SER={SER}, TC={TC}.")
        
        return results
    
    
    
    def GetObjects(self):
        return {
            "GoToObjects": self._GetObjects(),
            "PickUpObjects": self._GetPickupableObjects(),
            "PutObjects": self._GetReceptacleObjects(),
            "OpenObjects": self._GetOpenedObjects() + self._GetClosedObjects(),
            "CloseObjects": self._GetClosedObjects() + self._GetOpenedObjects(),
            "ToggleOnObjects": self._GetToggledOnObjects() + self._GetToggledOffObjects(),
            "ToggleOffObjects": self._GetToggledOffObjects() + self._GetToggledOnObjects(),
            "BreakObjects": self._GetBrokenObjects() + self._GetUnbrokenObjects(),
            "SliceObjects": self._GetSlicedObjects() + self._GetUnslicedObjects(),
            "CleanObjects": self._GetCleanObjects() + self._GetDirtyObjects(),
            "DirtyObjects": self._GetDirtyObjects() + self._GetCleanObjects(),
            "FillObjectWithLiquids": self._GetFilledWithLiquidObjects() + self._GetUnfilledWithLiquidObjects(),
            "EmptyLiquidFromObjects": self._GetUnfilledWithLiquidObjects() + self._GetFilledWithLiquidObjects(),

            "ReceptacleStates": self._GetRecepRelationship(),
            "ObjectMass": self._GetObjectMass(),
            "HeatSource": self._GetHeatSource(),
            "ColdSource": self._GetColdSource(),
            
            "OpenedObjects": self._GetOpenedObjects(),
            "ClosedObjects": self._GetClosedObjects(),
            "ToggledOnObjects": self._GetToggledOnObjects(),
            "ToggledOffObjects": self._GetToggledOffObjects(),
            "BrokenObjects": self._GetBrokenObjects(),
            "UnbrokenObjects": self._GetUnbrokenObjects(),
            "SlicedObjects": self._GetSlicedObjects(),
            "UnslicedObjects": self._GetUnslicedObjects(),
            "DirtyedObjects": self._GetDirtyObjects(),
            "CleanedObjects": self._GetCleanObjects(),
            "FilledWithLiquidObjects": self._GetFilledWithLiquidObjects(),
            "UnfilledWithLiquidObjects": self._GetUnfilledWithLiquidObjects(),     
        }


        
    def GoToObject(self, rbt_idx: int, obj_type: str):
        log.info(f"GoToObject: Robot{rbt_idx} is going to {obj_type}.")
        self.exec_action += 1
        self.exec_time += 10
        time.sleep(10 / self.time_scale)
        success, message = self._GoToObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def PickUpObject(self, rbt_idx: int, obj_type: str):
        log.info(f"PickUpObject: Robot{rbt_idx} is picking up {obj_type}.")
        self.exec_action += 1
        self.exec_time += 2
        time.sleep(2)
        success, message = self._PickUpObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def PutObject(self, rbt_idx: int, obj_type: str, recep_type: str):
        log.info(f"PutObject: Robot{rbt_idx} is putting {obj_type} into {recep_type}.")
        self.exec_action += 1
        self.exec_time += 2
        time.sleep(2 / self.time_scale)
        success, message = self._PutObject(rbt_idx, obj_type, recep_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message
        
    def OpenObject(self, rbt_idx: int, obj_type: str):
        log.info(f"OpenObject: Robot{rbt_idx} is opening {obj_type}.")
        self.exec_action += 1
        self.exec_time += 3
        time.sleep(3 / self.time_scale)
        success, message = self._OpenObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def CloseObject(self, rbt_idx: int, obj_type: str):
        log.info(f"CloseObject: Robot{rbt_idx} is closing {obj_type}.")
        self.exec_action += 1
        self.exec_time += 3
        time.sleep(3 / self.time_scale)
        success, message = self._CloseObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def ToggleOnObject(self, rbt_idx: int, obj_type: str):
        log.info(f"ToggleOnObject: Robot{rbt_idx} is toggling on {obj_type}.")
        self.exec_action += 1
        self.exec_time += 1
        time.sleep(1 / self.time_scale)
        success, message = self._ToggleOnObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def ToggleOffObject(self, rbt_idx: int, obj_type: str):
        log.info(f"ToggleOffObject: Robot{rbt_idx} is toggling off {obj_type}.")
        self.exec_action += 1
        self.exec_time += 1
        time.sleep(1 / self.time_scale)
        success, message = self._ToggleOffObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def BreakObject(self, rbt_idx: int, obj_type: str):
        log.info(f"BreakObject: Robot{rbt_idx} is breaking {obj_type}.")
        self.exec_action += 1
        self.exec_time += 5
        time.sleep(5 / self.time_scale)
        success, message = self._BreakObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message
        
    def SliceObject(self, rbt_idx: int, obj_type: str):
        log.info(f"SliceObject: Robot{rbt_idx} is slicing {obj_type}.")
        self.exec_action += 1
        self.exec_time += 9
        time.sleep(9 / self.time_scale)
        success, message = self._SliceObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message
        
    def CleanObject(self, rbt_idx: int, obj_type: str):
        log.info(f"CleanObject: Robot{rbt_idx} is cleaning {obj_type}.")
        self.exec_action += 1
        self.exec_time += 8
        time.sleep(8 / self.time_scale)
        success, message = self._CleanObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def DirtyObject(self, rbt_idx: int, obj_type: str):
        log.info(f"DirtyObject: Robot{rbt_idx} is dirtying {obj_type}.")
        self.exec_action += 1
        self.exec_time += 5
        time.sleep(5 / self.time_scale)
        success, message = self._DirtyObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def FillObjectWithLiquid(self, rbt_idx: int, obj_type: str, liquid_type: str):
        log.info(f"FillObjectWithLiquid: Robot{rbt_idx} is filling {obj_type} with {liquid_type}.")
        self.exec_action += 1
        self.exec_time += 7
        time.sleep(7 / self.time_scale)
        success, message = self._FillObjectWithLiquid(rbt_idx, obj_type, liquid_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message

    def EmptyLiquidFromObject(self, rbt_idx: int, obj_type: str):
        log.info(f"EmptyLiquidFromObject: Robot{rbt_idx} is emptying liquid from {obj_type}.")
        self.exec_action += 1
        self.exec_time += 4
        time.sleep(4 / self.time_scale)
        success, message = self._EmptyLiquidFromObject(rbt_idx, obj_type)
        if success:
            self.exec_success += 1
        log.info(message)
        return success, message
  