#!/bin/bash
# models=("Qwen/Qwen1.5-1.8B" "Qwen/Qwen1.5-1.8B-Chat" "Qwen/Qwen1.5-7B" "Qwen/Qwen1.5-7B-Chat" "mistralai/Mistral-7B-v0.1" "mistralai/Mistral-7B-Instruct-v0.2" "meta-llama/Meta-Llama-3-8B-Instruct" "meta-llama/Meta-Llama-3-8B" "google/gemma-2b" "google/gemma-1.1-2b-it" "google/gemma-7b" "google/gemma-1.1-7b-it")
models=("Qwen/Qwen1.5-7B" "Qwen/Qwen1.5-7B-Chat" "mistralai/Mistral-7B-v0.1" "mistralai/Mistral-7B-Instruct-v0.2" "meta-llama/Meta-Llama-3-8B-Instruct" "meta-llama/Meta-Llama-3-8B" "google/gemma-7b" "google/gemma-1.1-7b-it")
models=("Qwen/Qwen1.5-1.8B" "Qwen/Qwen1.5-1.8B-Chat" "google/gemma-2b" "google/gemma-1.1-2b-it")
for model in "${models[@]}"; do
    echo "Running $model"
    bash ./bin/start_vllm.sh $model 8000 0.5
    sleep 60
    bash ./bin/test_sllm.sh $model 8000
    sleep 3600
    ps aux | grep chenziyi | grep vllm.entrypoints.openai.api_server | grep -v grep | awk '{print $2}' | xargs kill
    sleep 5
    ps aux | grep chenziyi | grep src/evaluate.py | grep -v grep | awk '{print $2}' | xargs kill
    sleep 5
    echo "Finished $model"
    sleep 3
done