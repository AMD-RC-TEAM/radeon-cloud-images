#!/bin/bash
# $1 = vllm | sglang. Alternates TORCH_BLAS_PREFER_HIPBLASLT unset / 0, two rounds each.
ulimit -c 0; export HSA_DISABLE_COREDUMP_ON_EXCEPTION=1 HF_HOME=/hf-cache HF_HUB_OFFLINE=1 HOME=/tmp; cd /tmp
M=$(ls -d /hf-cache/hub/models--Qwen--Qwen3-8B/snapshots/*/ | head -1); echo "model $M"
python3 -c 'import torch;print("torch",torch.__version__)'
start() { if [ "$1" = vllm ]; then vllm serve "$M" --served-model-name m --port 18000 --max-model-len 4096 --gpu-memory-utilization 0.85 >/tmp/s.log 2>&1 &
          else python3 -m sglang.launch_server --model-path "$M" --served-model-name m --host 127.0.0.1 --port 18000 --mem-fraction-static 0.85 --context-length 4096 >/tmp/s.log 2>&1 & fi
  for i in $(seq 1 180); do curl -sf -m 2 http://127.0.0.1:18000/health >/dev/null && return 0; sleep 5; done; tail -30 /tmp/s.log; return 1; }
stop() { pkill -f "vllm serve|sglang.launch_server" ; for i in $(seq 1 60); do pgrep -f "vllm serve|sglang.launch_server" >/dev/null || break; sleep 2; done; pkill -9 -f "vllm|sglang"; sleep 5; }
for r in 1 2; do for b in unset 0; do
  if [ $b = unset ]; then unset TORCH_BLAS_PREFER_HIPBLASLT; else export TORCH_BLAS_PREFER_HIPBLASLT=0; fi
  if start $1; then echo "blas=$b round=$r $(timeout -s KILL 900 python3 /bench/serve_bench.py 18000 | grep SERVE_JSON)"; else echo "blas=$b round=$r START FAILED"; fi
  stop; done; done
echo "RUN DONE"
