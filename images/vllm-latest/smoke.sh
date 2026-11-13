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
python3 -c 'import vllm.platforms.rocm as r; assert getattr(r.RocmPlatform, "_rc_rdna3_defaults", False), "rc_vllm_defaults did not load"; print("rc_vllm_defaults: loaded")'
# serve <log> [extra args]: start the server on $MODEL and wait until it answers.
serve() {
  local log=$1; shift
  (vllm serve "$MODEL" --served-model-name smoke --port 18000 --max-model-len 2048 --gpu-memory-utilization 0.5 "$@" >"$log" 2>&1 &)
  for i in $(seq 1 120); do curl -sf http://127.0.0.1:18000/health >/dev/null && return 0; sleep 5; done
  tail -40 "$log"; return 1
}
stop() { pkill -f "vllm serve" 2>/dev/null || true; for i in $(seq 1 30); do pgrep -f "vllm serve" >/dev/null || break; sleep 2; done; }
# Greedy completions for a few prompts, one JSON list per server.
answers() {
  python3 - <<'PY'
import json, urllib.request
prompts = ["The capital of France is", "2 + 3 =", "The opposite of hot is", "Water freezes at a temperature of",
           "The largest planet in the solar system is", "def add(a, b):\n    return", "Monday, Tuesday,", "The chemical symbol for gold is"]
out = []
for p in prompts:
    req = urllib.request.Request("http://127.0.0.1:18000/v1/completions", headers={"Content-Type": "application/json"},
                                 data=json.dumps({"model": "smoke", "prompt": p, "max_tokens": 8, "temperature": 0}).encode())
    out.append(json.load(urllib.request.urlopen(req, timeout=120))["choices"][0]["text"])
assert all(t.strip() for t in out), f"empty completion: {out}"
print(json.dumps(out))
PY
}
# 1. Plain `vllm serve` (what users type) must run on ROCM_SEGMENTED_ATTN, the image default on gfx11.
serve /tmp/vllm.log
grep -q "segmented Triton attention" /tmp/vllm.log || { grep -i -m5 "backend" /tmp/vllm.log; echo "FAIL: default backend is not ROCM_SEGMENTED_ATTN"; exit 1; }
echo "default backend: ROCM_SEGMENTED_ATTN"
SEG=$(answers); echo "completion: $(python3 -c 'import json,sys; print(json.loads(sys.argv[1])[0])' "$SEG")"
stop
# 2. An explicit --attention-backend still wins, and the greedy answers agree with TRITON_ATTN (accuracy sanity).
serve /tmp/vllm-triton.log --attention-backend TRITON_ATTN
grep -q "Using TRITON_ATTN backend" /tmp/vllm-triton.log || { echo "FAIL: --attention-backend TRITON_ATTN was not honoured"; exit 1; }
! grep -q "segmented Triton attention" /tmp/vllm-triton.log || { echo "FAIL: segmented attention used despite --attention-backend"; exit 1; }
TRI=$(answers)
python3 - "$SEG" "$TRI" <<'PY'
import json, sys
seg, tri = json.loads(sys.argv[1]), json.loads(sys.argv[2])
same = sum(a.split()[:3] == b.split()[:3] for a, b in zip(seg, tri))
print(f"accuracy sanity: {same}/{len(seg)} greedy answers agree with TRITON_ATTN (first 3 words)")
assert same >= len(seg) - 1, list(zip(seg, tri))
PY
stop
# The hk-dsl README quick start on this image (pip install hk-dsl && vllm serve Qwen/Qwen3-8B, one completion):
# guards the 11-13 regression where hk's plugin pulled aiter into the engine on gfx1100.
(cd "$(mktemp -d)" && HK_VERSION=0.9.21 bash "$(dirname "$0")/hk_readme_smoke.sh")
echo "SMOKE PASS"
