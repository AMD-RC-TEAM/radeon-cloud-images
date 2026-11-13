#!/bin/bash
# Smoke for SGLang images on one W7900D: the stack imports on gfx1100, then an SGLang server on a 0.5B model
# answers one chat request. The model comes from SMOKE_MODEL_DIR if it is mounted, otherwise it is downloaded
# through $HF_ENDPOINT (the smoke Job points it at a mirror reachable from the cluster).
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
welcome_once
welcome_jupyter_terminal
MODEL=${SMOKE_MODEL_DIR:-/models/Qwen2.5-0.5B-Instruct}
PORT=30000
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
python3 -c 'import sglang, torch; print("sglang", sglang.__version__, "torch", torch.__version__); assert torch.cuda.is_available()'
python3 -c 'import importlib.metadata as m; print("sglang-radeon-rdna3", m.version("sglang-radeon-rdna3"))'
python3 -c 'import sgl_kernel, os; print("sgl_kernel", os.path.dirname(sgl_kernel.__file__))'
python3 - <<'PY'
from sglang.srt import server_args as sa
assert getattr(sa.ServerArgs, "_rc_rdna3_defaults", False), "rc_sglang_defaults did not load"
print("rc_sglang_defaults: loaded")
PY
if [ ! -f "$MODEL/config.json" ]; then
  MODEL=$(mktemp -d)/Qwen2.5-0.5B-Instruct
  echo "downloading Qwen/Qwen2.5-0.5B-Instruct via ${HF_ENDPOINT:-huggingface.co}"
  python3 -c 'import sys; from huggingface_hub import snapshot_download as s; s("Qwen/Qwen2.5-0.5B-Instruct", local_dir=sys.argv[1])' "$MODEL"
fi
LOG=$(mktemp)
# Exactly what a user types: no RDNA3 flags. The image's defaults (rc_sglang_defaults) must make this work.
setsid python3 -m sglang.launch_server --model-path "$MODEL" --served-model-name smoke --host 127.0.0.1 --port "$PORT" \
  --mem-fraction-static 0.5 > "$LOG" 2>&1 &
SP=$!
for i in $(seq 1 120); do
  curl -sf -m 2 "http://127.0.0.1:$PORT/health" > /dev/null && break
  kill -0 "$SP" 2>/dev/null || { tail -60 "$LOG"; echo "server exited"; exit 1; }
  sleep 5
done
curl -sf -m 2 "http://127.0.0.1:$PORT/health" > /dev/null || { tail -60 "$LOG"; exit 1; }
OUT=$(curl -sf -m 300 "http://127.0.0.1:$PORT/v1/chat/completions" -H 'Content-Type: application/json' \
  -d '{"model":"smoke","messages":[{"role":"user","content":"What is the capital of France? Answer in one word."}],"max_tokens":16,"temperature":0}')
echo "$OUT"
echo "$OUT" | python3 -c 'import json,sys; t=json.load(sys.stdin)["choices"][0]["message"]["content"]; assert t.strip(), "empty answer"; print("answer:", t)'
kill -- -"$SP" 2>/dev/null || true
echo "SMOKE PASS"
