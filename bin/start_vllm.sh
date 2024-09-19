if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <model-name> <port> <gpu-memory-utilization>"
    echo "(e.g. $0 meta-llama/Meta-Llama-3-8B-Instruct 8000 0.8)"
    echo "(e.g. $0 google/gemma-1.1-7b-it 8000 1)"
    exit 1
fi
echo hello

model_name=$1
port=$2
gpu_memory_utilization=$3

# log_file="./logs/vllm/vllm_$(echo $model_name | sed 's/.*\///g')_$(date +'%Y-%m-%d_%H-%M-%S').log"

# # nohup python -m vllm.entrypoints.openai.api_server --model $model_name --port $port --api-key token-abc123 --gpu-memory-utilization $gpu_memory_utilization --max-model-len 16384 --trust-remote-code --disable-log-requests >> $log_file 2>&1 &
# nohup python -m vllm.entrypoints.openai.api_server --model $model_name --port $port --api-key token-abc123 --gpu-memory-utilization $gpu_memory_utilization --trust-remote-code --disable-log-requests >> $log_file 2>&1 &
# pid=$!
# echo "Started VLLM server with PID $pid. Logs are in $log_file"

python -m vllm.entrypoints.openai.api_server \
    --model $model_name \
    --port $port \
    --api-key token-abc123 \
    --gpu-memory-utilization $gpu_memory_utilization \
    --trust-remote-code \
    --disable-log-requests

# python -m vllm.entrypoints.openai.api_server \
#     --model $model_name \
#     --port $port \
#     --api-key token-abc123 \
#     --gpu-memory-utilization $gpu_memory_utilization \
#     --trust-remote-code \
#     --disable-log-requests \
#     --max-model-len 20480
