from tqdm import trange
import json
import ai2thor.controller
from ai2thor.platform import CloudRendering


floor_plans = [6, 9, 14, 21, 207, 230, 306, 320, 404, 425]

objects = {}

for index in trange(len(floor_plans), desc="Processing"):
    controller = ai2thor.controller.Controller(height=1000, width=1000, scene=f'FloorPlan{floor_plans[index]}', platform=CloudRendering)
    objects_raw = controller.last_event.metadata['objects']
    controller.stop()
    objects[floor_plans[index]] = objects_raw
    
json.dump(objects, open("./dataset/sllm/resource/objects.json", "w"), indent=4)
