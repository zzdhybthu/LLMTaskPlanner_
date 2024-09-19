if [ "$#" -ne 2 ] && [ "$#" -ne 3 ]; then
    echo "Usage: $0 <model-name> <port> [algo] (e.g. $0 meta-llama/Meta-Llama-3-8B-Instruct 8000 baseline)"
    exit 1
fi

model_name=$1
port=$2
algo=${3:-baseline} # default to baseline

model_name_path=$(echo $model_name | sed 's/.*\///g')
log_file="./logs/sllm/sllm-omnipotent-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.use_feedback=False planner.cot=False task_category=omnipotent 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=omnipotent. Log file: $log_file, PID: $pid"
sleep 3
log_file="./logs/sllm/sllm-capacity_limited-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.use_feedback=False planner.cot=False task_category=capacity_limited 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=capacity_limited. Log file: $log_file, PID: $pid"
sleep 3
log_file="./logs/sllm/sllm-skills_limited-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.use_feedback=False planner.cot=False task_category=skills_limited 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=skills_limited. Log file: $log_file, PID: $pid"
sleep 3
log_file="./logs/sllm/sllm-skills_limited_disruptive-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.use_feedback=False planner.cot=False task_category=skills_limited_disruptive 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=skills_limited_disruptive. Log file: $log_file, PID: $pid"
sleep 3
log_file="./logs/sllm/sllm-comprehensive-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.use_feedback=False planner.cot=False task_category=comprehensive 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=comprehensive. Log file: $log_file, PID: $pid"

echo "All evaluations started."
