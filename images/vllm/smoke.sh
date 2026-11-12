#!/bin/bash
# Smoke for vLLM images on one W7900D: start the server on a small cached model and get one completion.
# SMOKE_MODEL_DIR is mounted read-only by the smoke Pod (model cache); default model Qwen2.5-0.5B-Instruct.
set -euo pipefail
MODEL=${SMOKE_MODEL_DIR:-/models/Qwen2.5-0.5B-Instruct}
grep -m1 -E 'gfx11[0-9]{2}' <<<"$(rocminfo)"
python3 -c 'import vllm, torch; print("vllm", vllm.__version__, "torch", torch.__version__); assert torch.cuda.is_available()'
(vllm serve "$MODEL" --served-model-name smoke --port 18000 --max-model-len 2048 --gpu-memory-utilization 0.5 >/tmp/vllm.log 2>&1 &)
for i in $(seq 1 120); do curl -sf http://127.0.0.1:18000/health >/dev/null && break; sleep 5; done
curl -sf http://127.0.0.1:18000/health >/dev/null || { tail -40 /tmp/vllm.log; exit 1; }
OUT=$(curl -sf http://127.0.0.1:18000/v1/completions -H 'Content-Type: application/json' \
  -d '{"model":"smoke","prompt":"The capital of France is","max_tokens":8,"temperature":0}')
echo "$OUT"
echo "$OUT" | python3 -c 'import json,sys; t=json.load(sys.stdin)["choices"][0]["text"]; assert t.strip(), "empty completion"; print("completion:", t)'
echo "SMOKE PASS"
