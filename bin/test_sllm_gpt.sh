if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <model-name> <option> (e.g. $0 OpenAI/gpt-3.5-turbo 1)"
    echo "Option: 1 - omnipotent, 2 - capacity_limited, 3 - skills_limited, 4 - skills_limited_disruptive, 5 - comprehensive"
    exit 1
fi

model_name=$1

model_name_path=$(echo $model_name | sed 's/.*\///g')
if [ $2 -eq 1 ]; then
    task_category=omnipotent
elif [ $2 -eq 2 ]; then
    task_category=capacity_limited
elif [ $2 -eq 3 ]; then
    task_category=skills_limited
elif [ $2 -eq 4 ]; then
    task_category=skills_limited_disruptive
elif [ $2 -eq 5 ]; then
    task_category=comprehensive
else
    echo "Invalid option. Option: 1 - omnipotent, 2 - capacity_limited, 3 - skills_limited, 4 - skills_limited_disruptive, 5 - comprehensive"
    exit 1
fi

log_file="./logs/sllm/sllm-$task_category-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
# nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.use_feedback=False planner.cot=False task_category=$task_category start_from=4 num_tasks=1 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.use_feedback=False planner.cot=False task_category=$task_category 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=$task_category. Log file: $log_file, PID: $pid"
