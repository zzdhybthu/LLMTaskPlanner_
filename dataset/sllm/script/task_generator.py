import json
import ai2thor.controller
from ai2thor.platform import CloudRendering


floorplan = 425
controller = ai2thor.controller.Controller(height=1000, width=1000, scene=f'FloorPlan{floorplan}', platform=CloudRendering)
obj = [{
        'objectId': obj['objectId'],
        'objectType': obj['objectType'],
        'mass': obj['mass'],
        'receptacle': obj['receptacle'],
        'toggleable': obj['toggleable'],
        'breakable': obj['breakable'],
        'canFillWithLiquid': obj['canFillWithLiquid'],
        'dirtyable': obj['dirtyable'],
        'isHeatSource': obj['isHeatSource'],
        'isColdSource': obj['isColdSource'],
        'sliceable': obj['sliceable'],
        'openable': obj['openable'],
        'pickupable': obj['pickupable'],
        'receptacleObjectIds': obj['receptacleObjectIds'],
        'parentReceptacles': obj['parentReceptacles'],
        'isToggled': obj['isToggled'],
        'isBroken': obj['isBroken'],
        'fillLiquid': obj['fillLiquid'],
        'isDirty': obj['isDirty'],
        'isSliced': obj['isSliced'],
        'isOpen': obj['isOpen'],
        'isPickedUp': obj['isPickedUp'],
        "temperature": obj['temperature']
       } for obj in controller.last_event.metadata['objects']]

object = {
    "receptacle": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['receptacle'] ])),
    "toggleable": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['toggleable'] ])),
    "openable": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['openable'] ])),
    "breakable": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['breakable'] ])),
    "canFillWithLiquid": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['canFillWithLiquid'] ])) ,  
    "dirtyable": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['dirtyable'] ])),
    "canBeUsedUp": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['canBeUsedUp'] ])),
    "cookable": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['cookable'] ])),
    "isHeatSource": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['isHeatSource'] ])),
    "isColdSource": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['isColdSource'] ])),
    "sliceable": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['sliceable'] ])),
    "pickupable": list(set([obj['objectType'] for obj in controller.last_event.metadata['objects'] if obj['pickupable'] ]))
}
controller.stop()


json.dump(obj, open(f'objects_{floorplan}_prompt.json', 'w'), indent=4)
json.dump(object, open(f'objects_{floorplan}_prompt.json', 'a'), indent=4)

prompt = """
Here are an example task based on the environment.

{"task": "Slice the tomato", "robot list" : [1], "object_states" : [{"name": "Tomato", "contains": [], "state": {
        "isToggled": false,
        "isBroken": false,
        "fillLiquid": null,
        "isDirty": false,
        "isUsedUp": false,
        "isCooked": false,
        "temperature": "RoomTemp",
        "isSliced": true,
        "isOpen": false,
        "isPickedUp": false
        } 
        }]}

task is the task name.
robot list is robots available, which is all set to 1
object_states is the final state after task is finished, which is used to evaluate if task is successfully implemented.
contains include name of objects that is receptacled by the object. State can be 'isToggled', 'isBroken' and so on, which can be referred to in object properties above.
note state is state of object of corresponding name, not objects it contains.
note state should be integrated with all the properties.

available actions for robots are lists below:
action_list = ['GoToObject(obj)', // obj is object name, such as "Apple"
               'OpenObject(obj)',
               'CloseObject(obj)',
               'BreakObject(obj)',
               'SliceObject(obj)', 
               'CookObject(obj)',
               'SwitchOn(obj)',
               'SwitchOff(obj)',
               'CleanObject(obj)'
               'PickupObject(obj)',
               'DropObject', // DropObject in hand
               'ThrowObject', // ThrowObject in hand
               'PutObject(obj, recep)', // Put obj in recep, obj should be isPickedUp=true, one robot could only hold one object at a time
               'FillObjectWithLiquid(obj, liquid)', // liquid include water, coffee, wine
               'EmptyLiquidFromObject(obj)',
               'UseUpObject(obj)',
               ]




Now it's time for you to generate more tasks and corresponding solutions.
Tasks should be divided into 3 levels: easy, moderate and difficult.
easy tasks are straight forward to accomplish.
moderate tasks may involve more actions to accomplish.
difficult task describes tasks in an indirect way and involve much more actions to accomplish and could be creative.


give your new tasks and solutions in a json format.
More examples:
[
    {
        "floorplan": 6,
        "level": "easy",
        "task": "Open a cabinet",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Cabinet",
                "contains": [],
                "state": {
                    "isOpen": true
                }
            }
        ],
        "solution": [
            "GoToObject('Cabinet')",
            "OpenObject('Cabinet')"
        ]
    },
    {
        "floorplan": 6,
        "level": "moderate",
        "task": "Make a cup of coffee",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Cup",
                "contains": [],
                "state": {
                    "fillLiquid": "coffee"
                }
            },
            {
                "name": "CoffeeMachine",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            }
        ],
        "solution": [
            "GoToObject('Cup')",
            "PickupObject('Cup')",
            "GoToObject('CoffeeMachine')",
            "SwitchOn('CoffeeMachine')",
            "FillObjectWithLiquid('Cup', 'coffee')",
            "CloseObject('CoffeeMachine')"
        ]
    },
    {
        "floorplan": 6,
        "level": "moderate",
        "task": "Fill a cup with water and place it on the counter.",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Cup",
                "contains": [],
                "state": {
                    "fillLiquid": "water"
                }
            },
            {
                "name": "CounterTop",
                "contains": [
                    "Cup"
                ],
                "state": {}
            },
            {
                "name": "Faucet",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            }
        ],
        "solution": [
            "GoToObject('Cup')",
            "PickupObject('Cup')",
            "GoToObject('Faucet')",
            "OpenObject('Faucet')",
            "FillObjectWithLiquid('Cup', 'water')",
            "CloseObject('Faucet')",
            "GoToObject('CounterTop')",
            "PutObject('Cup', 'CounterTop')"
        ]
    },
    {
        "floorplan": 6,
        "level": "difficult",
        "task": "Prepare a dinner setting with a plate of sliced bread, a cup of water, and a knife on the counter.",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Bread",
                "contains": [],
                "state": {
                    "isSliced": true
                }
            },
            {
                "name": "Cup",
                "contains": [],
                "state": {
                    "fillLiquid": "water"
                }
            },
            {
                "name": "CounterTop",
                "contains": [
                    "Bread",
                    "Cup",
                    "Knife"
                ],
                "state": {}
            },
            {
                "name": "Faucet",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            }
        ],
        "solution": [
            "GoToObject('Knife')",
            "PickupObject('Knife')",
            "GoToObject('Bread')",
            "SliceObject('Bread')",
            "GoToObject('CounterTop')",
            "PutObject('Knife', 'CounterTop')",
            "GoToObject('Cup')",
            "PickupObject('Cup')",
            "GoToObject('Faucet')",
            "OpenObject('Faucet')",
            "FillObjectWithLiquid('Cup', 'water')",
            "CloseObject('Faucet')",
            "GoToObject('CounterTop')",
            "PutObject('Cup', 'CounterTop')",
            "GoToObject('Bread')",
            "PickupObject('Bread')",
            "GoToObject('CounterTop')",
            "PutObject('Bread', 'CounterTop')"
        ]
    },
    {
        "floorplan": 6,
        "level": "difficult",
        "task": "Prepare a bowl of salad using tomato, lettuce",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Tomato",
                "contains": [],
                "state": {
                    "isSliced": true
                }
            },
            {
                "name": "Lettuce",
                "contains": [],
                "state": {
                    "isSliced": true
                }
            },
            {
                "name": "Bowl",
                "contains": [
                    "Tomato",
                    "Lettuce"
                ],
                "state": {}
            }
        ],
        "solution": [
            "GoToObject('Knife')",
            "PickupObject('Knife')",
            "GoToObject('Tomato')",
            "SliceObject('Tomato')",
            "GoToObject('Lettuce')",
            "SliceObject('Lettuce')",
            "GoToObject('CounterTop')",
            "PutObject('Knife', 'CounterTop')",
            "GoToObject('Tomato')",
            "PickupObject('Tomato')",
            "GoToObject('Bowl')",
            "PutObject('Tomato', Bowl)",
            "GoToObject('Lettuce')",
            "PickupObject('Lettuce')",
            "PutObject('Lettuce', Bowl)"
        ]
    },
    {
        "floorplan": 6,
        "level": "difficult",
        "task": "Organize the kitchen by placing all western cutlery inside a drawer",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Drawer",
                "contains": [
                    "Knife",
                    "Spoon",
                    "Fork"
                ],
                "state": {}
            }
        ],
        "solution": [
            "GoToObject('Knife')",
            "PickupObject('Knife')",
            "GoToObject('Drawer')",
            "PutObject('Knife', 'Drawer')",
            "GoToObject('Spoon')",
            "PickupObject('Spoon')",
            "GoToObject('Drawer')",
            "PutObject('Spoon', 'Drawer')",
            "GoToObject('Fork')",
            "PickupObject('Fork')",
            "GoToObject('Drawer')",
            "PutObject('Fork', 'Drawer')"
        ]
    },
    {
        "floorplan": 9,
        "level": "easy",
        "task": "Turn off the light switch",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "LightSwitch",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            }
        ],
        "solution": [
            "GoToObject('LightSwitch')",
            "SwitchOff('LightSwitch')"
        ]
    },
    {
        "floorplan": 9,
        "level": "moderate",
        "task": "Clean a plate and place it in a garbage can",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Plate",
                "contains": [],
                "state": {
                    "isDirty": true
                }
            },
            {
                "name": "GarbageCan",
                "contains": [
                    "Plate"
                ],
                "state": {}
            }
        ],
        "solution": [
            "GoToObject('Plate')",
            "PickupObject('Plate')",
            "DirtyObject('Plate')",
            "GoToObject('GarbageCan')",
            "PutObject('Plate', 'GarbageCan')",
        ]
    },
    {
        "floorplan": 9,
        "level": "moderate",
        "task": "Make a slice of toast and put it on a plate",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Bread",
                "contains": [],
                "state": {
                    "isCooked": true
                }
            },
            {
                "name": "Plate",
                "contains": [
                    "Bread"
                ],
                "state": {}
            }
        ],
        "solution": [
            "GoToObject('Bread')",
            "PickupObject('Bread')",
            "GoToObject('Toaster')",
            "PutObject('Bread', 'Toaster')",
            "PickupObject('Bread')",
            "GoToObject('Plate')",
            "PutObject('Bread', 'Plate')"
        ]
    },
    {
        "floorplan": 9,
        "level": "difficult",
        "task": "Prepare a cooking station by placing a pot on the stove burner, filling it with water, and turning on the stove",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Pot",
                "contains": [],
                "state": {
                    "fillLiquid": "water"
                }
            },
            {
                "name": "StoveBurner",
                "contains": [
                    "Pot"
                ],
                "state": {
                    "isToggled": true
                }
            },
            {
                "name": "Faucet",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            }
        ],
        "solution": [
            "GoToObject('Pot')",
            "PickupObject('Pot')",
            "GoToObject('Faucet')",
            "OpenObject('Faucet')",
            "FillObjectWithLiquid('Pot', 'water')",
            "CloseObject('Faucet')",
            "GoToObject('StoveBurner')",
            "PutObject('Pot', 'StoveBurner')",
            "SwitchOn('StoveBurner')"
        ]
    },
    {
        "floorplan": 9,
        "level": "difficult",
        "task": "Set up a movie night snack bar on the dining table with coffee in a mug and a plate of fruit.",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "Mug",
                "contains": [],
                "state": {
                    "fillLiquid": "coffee"
                }
            },
            {
                "name": "Plate",
                "contains": ["Apple"],
                "state": {}
            },
            {
                "name": "DiningTable",
                "contains": [
                    "Bowl",
                    "Plate"
                ],
                "state": {}
            },
            {
                "name": "CoffeeMachine",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            }
        ],
        "solution": [
            "GoToObject('Mug')",
            "PickupObject('Mug')",
            "GoToObject('CoffeeMachine')",
            "PutObject('Mug', 'CoffeeMachine')",
            "SwitchOn('CoffeeMachine')",
            "FillObjectWithLiquid('Mug', 'coffee')",
            "SwitchOff('CoffeeMachine')",
            "PickupObject('Mug')",
            "GoToObject('DiningTable')",
            "PutObject('Mug', 'DiningTable')",
            "GoToObject('Apple')",
            "PickupObject('Apple')",
            "GoToObject('Plate')",
            "PutObject('Apple', 'Plate')",
            "PickupObject('Plate')",
            "GoToObject('DiningTable')",
            "PutObject('Plate', 'DiningTable')"
        ]
    },
    {
        "floorplan": 9,
        "level": "difficult",
        "task": "Set up a breakfast tray with a freshly brewed cup of coffee and a plate of cracked raw egg on the dining table.",
        "robot_list": [
            1
        ],
        "object_states": [
            {
                "name": "CoffeeMachine",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            },
            {
                "name": "Cup",
                "contains": [],
                "state": {
                    "fillLiquid": "coffee"
                }
            },
            {
                "name": "Egg",
                "contains": [],
                "state": {
                    "isBroken": true
                }
            },
            {
                "name": "Plate",
                "contains": [
                    "Egg"
                ],
                "state": {}
            },
            {
                "name": "DiningTable",
                "contains": [
                    "Cup",
                    "Plate"
                ],
                "state": {}
            }
        ],
        "solution": [
            "GoToObject('Cup')",
            "PickupObject('Cup')",
            "GoToObject('CoffeeMachine')",
            "PutObject('Cup', 'CoffeeMachine')",
            "SwitchOn('CoffeeMachine')",
            "FillObjectWithLiquid('Cup', 'coffee')",
            "SwitchOff('CoffeeMachine')",
            "PickupObject('Cup')",
            "GoToObject('DiningTable')",
            "PutObject('Cup', 'DiningTable')",
            "GoToObject('Egg')",
            "PickupObject('Egg')",
            "GoToObject('Plate')",
            "BreakObject('Egg')",
            "PutObject('Egg', 'Plate')",
            "PickupObject('Plate')",
            "GoToObject('DiningTable')",
            "PutObject('Plate', 'DiningTable')"
        ]
    },
    {
        "floorplan": 14,
        "level": "easy",
        "task": "Turn on the toaster",
        "robot_list": [1],
        "object_states": [
            {
                "name": "Toaster",
                "contains": [],
                "state": {
                    "isToggled": true
                }
            }
        ],
        "solution": [
            "GoToObject('Toaster')",
            "SwitchOn('Toaster')"
        ]
    },
    {
        "floorplan": 14,
        "level": "moderate",
        "task": "Place a clean plate in the cabinet",
        "robot_list": [1],
        "object_states": [
            {
                "name": "Plate",
                "contains": [],
                "state": {
                    "isDirty": false
                }
            },
            {
                "name": "Cabinet",
                "contains": ["Plate"],
                "state": {
                    "isOpen": false
                }
            }
        ],
        "solution": [
            "GoToObject('Plate')",
            "PickupObject('Plate')",
            "GoToObject('Cabinet')",
            "OpenObject('Cabinet')",
            "PutObject('Plate', 'Cabinet')",
            "CloseObject('Cabinet')"
        ]
    },
    {
        "floorplan": 14,
        "level": "moderate",
        "task": "Fill a pot with water and place it on the stove burner",
        "robot_list": [1],
        "object_states": [
            {
                "name": "Pot",
                "contains": [],
                "state": {
                    "fillLiquid": "water"
                }
            },
            {
                "name": "StoveBurner",
                "contains": ["Pot"],
                "state": {}
            },
            {
                "name": "Faucet",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            }
        ],
        "solution": [
            "GoToObject('Pot')",
            "PickupObject('Pot')",
            "GoToObject('Faucet')",
            "OpenObject('Faucet')",
            "FillObjectWithLiquid('Pot', 'water')",
            "CloseObject('Faucet')",
            "GoToObject('StoveBurner')",
            "PutObject('Pot', 'StoveBurner')"
        ]
    },
    {
        "floorplan": 14,
        "level": "difficult",
        "task": "Set up a cooking station by slicing tomatoes and potatoes, then place them in a bowl on the countertop",
        "robot_list": [1],
        "object_states": [
            {
                "name": "Tomato",
                "contains": [],
                "state": {
                    "isSliced": true
                }
            },
            {
                "name": "Potato",
                "contains": [],
                "state": {
                    "isSliced": true
                }
            },
            {
                "name": "Bowl",
                "contains": ["Tomato", "Potato"],
                "state": {}
            },
            {
                "name": "CounterTop",
                "contains": ["Bowl"],
                "state": {}
            }
        ],
        "solution": [
            "GoToObject('Knife')",
            "PickupObject('Knife')",
            "GoToObject('Tomato')",
            "SliceObject('Tomato')",
            "GoToObject('Potato')",
            "SliceObject('Potato')",
            "GoToObject('CounterTop')",
            "PutObject('Knife', 'CounterTop')",
            "GoToObject('Tomato')",
            "PickupObject('Tomato')",
            "GoToObject('Bowl')",
            "PutObject('Tomato', 'Bowl')",
            "GoToObject('Potato')",
            "PickupObject('Potato')",
            "GoToObject('Bowl')",
            "PutObject('Potato', 'Bowl')",
            "PickupObject('Bowl')",
            "GoToObject('CounterTop')",
            "PutObject('Bowl', 'CounterTop')"
        ]
    },
    {
        "floorplan": 14,
        "level": "difficult",
        "task": "Warm up a frozen apple using a microwave and place it on a plate",
        "robot_list": [1],
        "object_states": [
            {
                "name": "Apple",
                "contains": [],
                "state": {
                    "temperature": "RoomTemp"
                }
            },
            {
                "name": "Plate",
                "contains": ["Apple"],
                "state": {}
            },
            {
                "name": "Microwave",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            },
            {
                "name": "Fridge",
                "contains": [],
                "state": {
                    "isOpen": false
                }
            }
        ],
        "solution": [
            "GoToObject('Fridge')",
            "OpenObject('Fridge')",
            "PickupObject('Apple')",
            "CloseObject('Fridge')",
            "GoToObject('Microwave')",
            "OpenObject('Microwave')",
            "PutObject('Apple', 'Microwave')",
            "CloseObject('Microwave')",
            "SwitchOn('Microwave')",
            "SwitchOff('Microwave')",
            "OpenObject('Microwave')",
            "PickupObject('Apple')",
            "CloseObject('Microwave')",
            "GoToObject('Plate')",
            "PutObject('Apple', 'Plate')"
        ]
    },
    {
        "floorplan": 14,
        "level": "difficult",
        "task": "Vandalizing window and pan in the dark",
        "robot_list": [1],
        "object_states": [
            {
                "name": "Window",
                "contains": [],
                "state": {
                    "isBroken": true
                }
            },
            {
                "name": "Pan",
                "contains": [],
                "state": {
                    "isDirty": true
                }
            },
            {
                "name": "LightSwitch",
                "contains": [],
                "state": {
                    "isToggled": false
                }
            }
        ],
        "solution": [
            "GoToObject('LightSwitch')",
            "SwitchOff('LightSwitch')",
            "GoToObject('Window')",
            "BreakObject('Window')",
            "GoToObject('Pan')",
            "PickupObject('Pan')",
            "DirtyObject('Pan')"
        ]
    }
]

now floorplan is 425
remember not to duplicate the tasks and solutions. You can only use objects listed in the certain floorplan. 
it is encouraged to try objects not used in examples but in the certain floorplan. 

"""

with open(f'objects_{floorplan}_prompt.json', 'a') as f:
    f.write(prompt)