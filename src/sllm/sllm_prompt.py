import json

def list2str(l):
    return f"{','.join(str(_) for _ in l)}" if len(l) > 0 else 'None'

def dict2str(d, sep=':'):
    return ','.join(f'{key}{sep}{value}' for key, value in d.items())

class SllmPrompt:
    @staticmethod
    def system_multi_complete(objs, liquids):
        return \
            SllmPrompt.scenario_multi() + '\n\n' + \
            SllmPrompt.actions_multi() + '\n\n' + \
            SllmPrompt.robots_multi() + '\n\n' + \
            SllmPrompt.objects_complete(obj=objs, liquid=liquids) + '\n\n' + \
            SllmPrompt.extra() + '\n\n' + \
            SllmPrompt.example_multi()
    @staticmethod
    def system_single_complete(objs, liquids):
        return \
            SllmPrompt.scenario_single() + '\n\n' + \
            SllmPrompt.actions_single() + '\n\n' + \
            SllmPrompt.robots_single() + '\n\n' + \
            SllmPrompt.objects_complete(obj=objs, liquid=liquids) + '\n\n' + \
            SllmPrompt.extra() + '\n\n' + \
            SllmPrompt.example_single()
    @staticmethod
    def system_multi_concise(objs, liquids):
        return \
            SllmPrompt.scenario_multi() + '\n\n' + \
            SllmPrompt.actions_multi() + '\n\n' + \
            SllmPrompt.robots_multi() + '\n\n' + \
            SllmPrompt.objects_concise(obj=objs, liquid=liquids) + '\n\n' + \
            SllmPrompt.extra() + '\n\n' + \
            SllmPrompt.example_multi()
    @staticmethod
    def system_single_concise(objs, liquids):
        return \
            SllmPrompt.scenario_single() + '\n\n' + \
            SllmPrompt.actions_single() + '\n\n' + \
            SllmPrompt.robots_single() + '\n\n' + \
            SllmPrompt.objects_concise(obj=objs, liquid=liquids) + '\n\n' + \
            SllmPrompt.extra() + '\n\n' + \
            SllmPrompt.example_single()
            
    @staticmethod
    def scenario_multi():
        return f"""#SCENARIO
There are one or multiple robots in the simulation,each with different skills and capabilities.
The robots are tasked with performing a series of actions in a simulated environment to complete a certain task.
You act as an AI assistant to help the robots decompose the tasks into actions step by step.
"""
    @staticmethod
    def scenario_single():
        return f"""#SCENARIO
There are one robot in the simulation,with some skills and capabilities.
The robot is tasked with performing a series of actions in a simulated environment to complete a certain task.
You act as an AI assistant to help this robot decompose the tasks into actions step by step.
"""
    @staticmethod
    def actions_multi():
            return f"""#ACTIONS
There are 13 actions possible available to robots in the simulation:
-GoToObject(robots[<id>],<obj>)
-PickUpObject(robots[<id>],<obj>)
-PutObject(robots[<id>],<obj>,<receptacle>)
-OpenObject(robots[<id>],<obj>)
-CloseObject(robots[<id>],<obj>)
-ToggleOnObject(robots[<id>],<obj>)
-ToggleOffObject(robots[<id>],<obj>)
-BreakObject(robots[<id>],<obj>)
-SliceObject(robots[<id>],<obj>)
-CleanObject(robots[<id>],<obj>)
-DirtyObject(robots[<id>],<obj>)
-FillObjectWithLiquid(robots[<id>],<obj>,<liquid>)
-EmptyLiquidFromObject(robots[<id>],<obj>)
"""
    @staticmethod
    def actions_single():
            return f"""#ACTIONS
There are 13 actions available to robot in the simulation:
-GoToObject(robots[<id>],<obj>)
-PickUpObject(robots[<id>],<obj>)
-PutObject(robots[<id>],<obj>,<receptacle>)
-OpenObject(robots[<id>],<obj>)
-CloseObject(robots[<id>],<obj>)
-ToggleOnObject(robots[<id>],<obj>)
-ToggleOffObject(robots[<id>],<obj>)
-BreakObject(robots[<id>],<obj>)
-SliceObject(robots[<id>],<obj>)
-CleanObject(robots[<id>],<obj>)
-DirtyObject(robots[<id>],<obj>)
-FillObjectWithLiquid(robots[<id>],<obj>,<liquid>)
-EmptyLiquidFromObject(robots[<id>],<obj>)
"""
    @staticmethod
    def robots_multi():
        return f"""#ROBOTS
There are multiple robots available in the simulation, numbered from 0 to n-1.Different robots have different skills and capabilities.
"capacity_num" is maximum number of objects a robot can pick up simultaneously.
"capacity_mass" is the maximum mass of each object a robot can carry.
"skills" is a list of actions that a robot can perform.
NOTE:When assigning tasks to robots:
    -Consider the skills of each robot to determine suitability for specific tasks.
    -Evaluate the carry capacity (both the number of objects in hand and mass they can handle) to ensure the robot can successfully carry and manipulate the objects involved in the task.
"""
    @staticmethod
    def robots_single():
        return f"""#ROBOTS
"capacity_num" is maximum number of objects the robot can pick up simultaneously.
"capacity_mass" is the maximum mass of each object the robot can carry.
NOTE:When assigning tasks to robots,Evaluate the carry capacity (both the number of objects in hand and mass they can handle) to ensure the robot can successfully carry and manipulate the objects involved in the task.
"""
    @staticmethod
    def objects_complete(obj, liquid):
        return f"""#OBJECTS
Below is a list of objects that robots can interact with in the simulation.Each object has specific properties that determine how it can be manipulated by the robots.
-All available objects and corresponding mass:{dict2str(obj['ObjectMass'], sep='=')}
-All objects above can be applied with "GoToObject" action.
    -Note robot is unable to find and interact with objects if they are contained in a closed receptacle.
-When performing "PickUpObject" action,the following objects can be picked up:{list2str(obj['PickUpObjects'])}
    -Remember to go to the object first before picking it up.
-When performing "PutObject" action,the following objects can be used as receptacles:{list2str(obj['PutObjects'])}
    -Remeber to pick up the object before putting it in a receptacle.
    -Make sure the receptacles are opened first before putting objects in them.
    -Here is initial receptacle states:{dict2str({k:v for k, v in obj['ReceptacleStates'].items() if len(v) > 0}, sep=' contains ')}
-When performing "OpenObject" or "CloseObject" action,the following objects can be opened or closed:{list2str(obj['OpenObjects'])}
    -Among them,the following objects are opened initially:{list2str(obj['OpenedObjects'])}
    -Remember to go to the object first before opening or closing it.
-When performing "ToggleOnObject" or "ToggleOffObject" action,the following objects can be toggled:{list2str(obj['ToggleOnObjects'])}
    -Among them,the following objects are toggled on initially:{list2str(obj['ToggledOnObjects'])}
    -Remember to go to the object first before toggling it on or off.
-When performing "BreakObject" action,the following objects can be broken:{list2str(obj['BreakObjects'])}
    -Among them,the following objects are broken initially:{list2str(obj['BrokenObjects'])}
    -Remember to pick up the object if it is pickupable before breaking it.
-When performing "SliceObject" action,the following objects can be sliced:{list2str(obj['SliceObjects'])}
    -Among them,the following objects are sliced initially:{list2str(obj['SlicedObjects'])}
    -Make sure to pick up a knife before slicing the object.
    -Remember to go to the object first before slicing it.
-When performing "CleanObject" or "DirtyObject" action,the following objects can be cleaned or dirtied:{list2str(obj['CleanObjects'])}
    -Among them,the following objects are dirty initially:{list2str(obj['DirtyedObjects'])}
    -Remember to go to the object first before cleaning or dirtying it.
-When performing "FillObjectWithLiquid" or "EmptyLiquidFromObject" action,the following objects can be filled with liquid or emptied:{list2str(obj['FillObjectWithLiquids'])}
    -Among them,the following objects are filled with liquid initially:{list2str(obj['FilledWithLiquidObjects'])}
    -Available liquids are:{list2str(liquid)}
    -Make sure to go to a coffee machine and toggle on it if the liquid is coffee,or go to a faucet and toggle on it if the liquid is water.
    -Remember to pick up the object before filling or emptying liquid from it.
-Heat source automatically heat up objects they contain if they are turned on.The following objects are heat sources:{list2str(obj['HeatSource'])}
-Cold source automatically cool down objects they contain if they are turned on.The following objects are cold sources:{list2str(obj['ColdSource'])}
"""
    @staticmethod
    def objects_concise(obj, liquid):
        return f"""#OBJECTS
Below is a list of objects that robots can interact with in the simulation.Each object has specific properties that determine how it can be manipulated by the robots.
Objects: {list2str(obj['ObjectMass'].keys())}
Liquids: {list2str(liquid)}
"""
    @staticmethod
    def extra():
        return f"""#IMPORTANT
-Each robot is capable of "GoToObject","PickUpObject" and "PutObject" action by default.
-Remember to go to the object first before performing any action on it.
-It is encouraged to assign tasks to robots in a way that minimizes the total time taken to complete the task.However,the primary goal is to ensure that all tasks are completed successfully.
-Perform action "Done()" immediately if the whole task is completed successfully. Do not perform any further actions after that.
-Do not repeat the same action multiple times when it is not necessary.
"""
    @staticmethod
    def example_multi():
        return """#EXAMPLE
-Example 1
Task Description:Fill a pot with water and place it on the stove burner.
Available Robots:robots = [{"skills":["FillObjectWithLiquid","EmptyLiquidFromObject"],"capacity_num":1,"capacity_mass":100.0},{"skills":["ToggleOnObject","ToggleOffObject"],"capacity_num":1,"capacity_mass":0.01}]
Please help the robots complete this task step by step.

Task Decomposition:
GoToObject(robots[0],'Pot')
PickUpObject(robots[0],'Pot')
GoToObject(robots[0],'Faucet')
GoToObject(robots[1],'Faucet')
ToggleOnObject(robots[1],'Faucet'),
FillObjectWithLiquid(robots[0],'Pot','water')
ToggleOffObject(robots[1],'Faucet')
GoToObject(robots[0],'StoveBurner')
PutObject(robots[0],'Pot','StoveBurner')
Done()

-Example 2
Task Description:Chill the bread,freeze it,then put it on the counter.
Available Robots:robots = [{"skills":[],"capacity_num":1,"capacity_mass":1.0},{"skills":["ToggleOnObject","ToggleOffObject","SliceObject","CleanObject","DirtyObject"],"capacity_num":1,"capacity_mass":1.0},{"skills":["OpenObject","CloseObject"],"capacity_num":1,"capacity_mass":0.01}]
Please help the robots complete this task step by step.

Task Decomposition:
GoToObject(robots[1],'Bread')
PickUpObject(robots[1],'Bread')
GoToObject(robots[1],'Fridge')
GoToObject(robots[2],'Fridge')
OpenObject(robots[2],'Fridge')
PutObject(robots[1],'Bread','Fridge')
CloseObject(robots[2],'Fridge')
OpenObject(robots[2],'Fridge')
GoToObject(robots[0],'Bread')
PickUpObject(robots[0],'Bread')
CloseObject(robots[2],'Fridge')
GoToObject(robots[0],'Countertop')
PutObject(robots[0],'Bread','CounterTop')
Done()
"""
    @staticmethod
    def example_single():
        return """#EXAMPLE
-Example 1
Task Description:Fill a pot with water and place it on the stove burner.
Available Robots:robots = [{"skills":["OpenObject","CloseObject","ToggleOnObject","ToggleOffObject","BreakObject","SliceObject","CleanObject","DirtyObject","FillObjectWithLiquid","EmptyLiquidFromObject"],"capacity_num":1,"capacity_mass":1.0}]
Please help the robots complete this task step by step.

Task Decomposition:
GoToObject(robots[0],'Pot')
PickUpObject(robots[0],'Pot')
GoToObject(robots[0],'Faucet')
ToggleOnObject(robots[0],'Faucet')
FillObjectWithLiquid(robots[0],'Pot','water')
ToggleOffObject(robots[0],'Faucet')
GoToObject(robots[0],'StoveBurner')
PutObject(robots[0],'Pot','StoveBurner')
Done()

-Example 2
Task Description:Chill the bread,freeze it,then put it on the counter.
Available Robots:robots = [{"skills":["OpenObject","CloseObject","ToggleOnObject","ToggleOffObject","BreakObject","SliceObject","CleanObject","DirtyObject","FillObjectWithLiquid","EmptyLiquidFromObject"],"capacity_num":1,"capacity_mass":1.0}]
Please help the robots complete this task step by step.

Task Decomposition:
GoToObject(robots[0],'Bread')
PickUpObject(robots[0],'Bread')
GoToObject(robots[0],'Fridge')
OpenObject(robots[0],'Fridge')
PutObject(robots[0],'Bread','Fridge')
CloseObject(robots[0],'Fridge')
OpenObject(robots[0],'Fridge')
PickUpObject(robots[0],'Bread')
CloseObject(robots[0],'Fridge')
GoToObject(robots[0],'Countertop')
PutObject(robots[0],'Bread','CounterTop')
Done()
"""

    @staticmethod
    def example_structured_all():
        """Returns a list of examples"""
        examples = json.load(open("./dataset/sllm/test/examples_obs.json", "r"))
        for example in examples:
            example["solution"].append("Done()")
            example["obs_list"].append("Congratulations! All task goals are completed.")
            example["reasoning_list"].append("Based on the feedback, all goals are completed. The task is done.")
        return examples

    @staticmethod
    def example_structured_multi():
        return SllmPrompt.example_structured_all()[:2]
    
    @staticmethod
    def example_structured_single():
        return SllmPrompt.example_structured_all()[-2:]

    @staticmethod
    def user(task_desc, robots):
        return f"""
Task Description:{task_desc}
Available Robots:robots = [{robots}]
Please help the robots complete this task step by step.
"""
    @staticmethod
    def no_score():
        return f"""#IMPORTANT
You should plan and only plan the first or the next single action at a time.
Choose the best action and give your answer directly.Do not add any additional content in your response.
e.g.GoToObject(robots[0],'Pot')
Do not add \" or \' before and after the action.
Only add \' before and after the object or receptacle or liquid.
"""
    @staticmethod
    def moa_aggregate_system_prompt(task_desc):
        return f"""
There are one or multiple robots in the simulation,each with different skills and capabilities.The robots are tasked with performing a series of actions in a simulated environment to {task_desc}.
You have been provided with a set of responses from various open-source models to the latest user query.Your task is to synthesize these responses into a single,high-quality response.
It is crucial to critically evaluate the information provided in these responses based on task goal,recognizing that some of it may be biased or incorrect.
Your response should not simply replicate the given answers but should offer a refined,accurate,and comprehensive reply to the instruction.Ensure your response is well-structured,coherent,and adheres to the highest standards of accuracy and reliability.
Point out clearly your choice of NEXT best action at the end of your response.
Responses from models:"""
