#!/bin/bash
# Smoke for vLLM images on one W7900D: start the server on a small cached model and get one completion.
# The model comes from SMOKE_MODEL_DIR if mounted, otherwise it is downloaded through $HF_ENDPOINT (set by the smoke Job).
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
MODEL=${SMOKE_MODEL_DIR:-/models/Qwen2.5-0.5B-Instruct}
grep -m1 -E 'gfx11[0-9]{2}' <<<"$(rocminfo)"
python3 -c 'import vllm, torch; print("vllm", vllm.__version__, "torch", torch.__version__); assert torch.cuda.is_available()'
if [ ! -f "$MODEL/config.json" ]; then
  MODEL=$(mktemp -d)/Qwen2.5-0.5B-Instruct
  echo "downloading Qwen/Qwen2.5-0.5B-Instruct via ${HF_ENDPOINT:-huggingface.co}"
  python3 -c 'import sys; from huggingface_hub import snapshot_download as s; s("Qwen/Qwen2.5-0.5B-Instruct", local_dir=sys.argv[1])' "$MODEL"
fi
(vllm serve "$MODEL" --served-model-name smoke --port 18000 --max-model-len 2048 --gpu-memory-utilization 0.5 >/tmp/vllm.log 2>&1 &)
for i in $(seq 1 120); do curl -sf http://127.0.0.1:18000/health >/dev/null && break; sleep 5; done
curl -sf http://127.0.0.1:18000/health >/dev/null || { tail -40 /tmp/vllm.log; exit 1; }
OUT=$(curl -sf http://127.0.0.1:18000/v1/completions -H 'Content-Type: application/json' \
  -d '{"model":"smoke","prompt":"The capital of France is","max_tokens":8,"temperature":0}')
echo "$OUT"
echo "$OUT" | python3 -c 'import json,sys; t=json.load(sys.stdin)["choices"][0]["text"]; assert t.strip(), "empty completion"; print("completion:", t)'
# The hk-dsl README quick start on this image (pip install hk-dsl && vllm serve Qwen/Qwen3-8B, one completion):
# guards the 11-13 regression where hk's plugin pulled aiter into the engine on gfx1100.
pkill -f "vllm serve" 2>/dev/null || true; sleep 5
(cd "$(mktemp -d)" && HK_VERSION=0.9.21 bash "$(dirname "$0")/hk_readme_smoke.sh")
echo "SMOKE PASS"
