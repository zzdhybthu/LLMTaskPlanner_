if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <model-name> <port> <mode> (e.g. $0 meta-llama/Meta-Llama-3-8B-Instruct 8000 1)"
    echo "mode: 1=single, 2=multi-no-comm, 3=multi-comm"
    exit 1
fi

model_name=$1
port=$2
mode=$3

## NOTE: Set cot=True by default to enable chain-of-thought prompt, set False otherwise
## NOTE: Multi agents use and only use 2 agents with the same model by now.
## IMPORTANT: For some reason, TDW server use port 1071 regardless of the port number specified. In this case, we can't run multiple TDW evaluations at the same time.

model_name_path=$(echo $model_name | sed 's/.*\///g')
if [ $mode -eq 1 ] ; then  # Single agent evaluation
    log_file="./logs/tdw/eval-tdw-single-$(date +'%Y_%m_%d-%H_%M_%S').log"
    experiment_name="eval-tdw-single"
    run_id=single-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S')
    nohup python -u src/evaluate.py --config-name=config_tdw planner.model_name=$model_name planner.port=$port planner.prompt_template_name=single planner.cot=True experiment_name=$experiment_name run_id=$run_id agents=[h_agent] log_path=$log_file >> $log_file 2>&1 &
    pid=$!
    echo "Started single agent evaluation. Log file: $log_file, PID: $pid"

elif [ $mode -eq 2 ] ; then  # Multi-agent evaluation, without communication
    log_file="./logs/tdw/eval-tdw-multi-no-comm-$(date +'%Y_%m_%d-%H_%M_%S').log"
    experiment_name="eval-tdw-multi-no-comm"
    run_id=multi_nocomm-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S')
    nohup python -u src/evaluate.py --config-name=config_tdw planner.model_name=$model_name planner.port=$port planner.prompt_template_name=nocom planner.cot=True experiment_name=$experiment_name run_id=$run_id agents=[h_agent,h_agent] log_path=$log_file >> $log_file 2>&1 &
    pid=$!
    echo "Started multi-agent evaluation without communication. Log file: $log_file, PID: $pid"

elif [ $mode -eq 3 ] ; then  # Multi-agent evaluation, with communication
    log_file="./logs/tdw/eval-tdw-multi-comm-$(date +'%Y_%m_%d-%H_%M_%S').log"
    experiment_name="eval-tdw-multi-comm"
    run_id=multi_comm-$model_name_path-$(date +'%Y_%m_%d-%H_%M_%S')
    nohup python -u src/evaluate.py --config-name=config_tdw planner.model_name=$model_name planner.port=$port planner.prompt_template_name=com planner.cot=True experiment_name=$experiment_name run_id=$run_id agents=[h_agent,h_agent] log_path=$log_file >> $log_file 2>&1 &
    pid=$!
    echo "Started multi-agent evaluation with communication. Log file: $log_file, PID: $pid"
else 
    echo "Invalid mode: $mode"
fi