model_name=meta-llama/Meta-Llama-3-8B-Instruct
port=8000
model_name_path=$(echo $model_name | sed 's/.*\///g')

log_file="./logs/sllm/sllm-comprehensive-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.algo=baseline planner.use_score=True planner.use_feedback=True task_category=comprehensive 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=comprehensive. Log file: $log_file, PID: $pid"
sleep 3

log_file="./logs/sllm/sllm-comprehensive-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.algo=baseline planner.use_score=False planner.use_feedback=True task_category=comprehensive 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=comprehensive. Log file: $log_file, PID: $pid"
sleep 3

log_file="./logs/sllm/sllm-comprehensive-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.algo=react planner.use_score=True planner.use_feedback=True task_category=comprehensive 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=comprehensive. Log file: $log_file, PID: $pid"
sleep 3

log_file="./logs/sllm/sllm-comprehensive-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.algo=react planner.use_score=False planner.use_feedback=True task_category=comprehensive 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=comprehensive. Log file: $log_file, PID: $pid"
sleep 3

log_file="./logs/sllm/sllm-comprehensive-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.algo=react_reflect planner.use_score=True planner.use_feedback=True task_category=comprehensive 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=comprehensive. Log file: $log_file, PID: $pid"
sleep 3

log_file="./logs/sllm/sllm-comprehensive-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S').log"
nohup python -u src/evaluate.py --config-name=config_sllm planner.model_name=$model_name planner.port=$port planner.algo=react_reflect planner.use_score=False planner.use_feedback=True task_category=comprehensive 2>&1 | grep -v "HTTP Request: POST" >> $log_file &
pid=$!
echo "Started evaluation. Task_category=comprehensive. Log file: $log_file, PID: $pid"
sleep 3