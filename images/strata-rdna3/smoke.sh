#!/bin/bash
# Smoke for strata-rdna3 on one W7900D, 48Gi, 1h. JupyterLab fast path, gfx1100, --list and
# --plan for every preset, then a mandatory serve + completion of qwen3.6-35b-a3b-q4
# (1 GPU, 22.9 GB, resumable via /hf-cache). Last line must be SMOKE PASS.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
no_in_image_welcome
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
command -v strata-serve >/dev/null
command -v strata-dsv41 >/dev/null || test -s /etc/strata-dsv41-exe
/opt/strata/terminal/bin/strata --version
if [ -s /etc/strata-dsv41-exe ]; then
  "$(cat /etc/strata-dsv41-exe)" --version
fi

# Persistent cache on the CI node (HF_CACHE_HOSTPATH). Outside names the entrypoint migrates.
export STRATA_MODELS_ROOT=/hf-cache/strata-models
mkdir -p "$STRATA_MODELS_ROOT"

strata-serve --list
PRESETS="deepseek-v4.1-flash-2.25 deepseek-v4.1-flash-2.25-fast deepseek-v4.1-flash-2.00 deepseek-v4.1-flash-2.00-fast qwen3.8-flash-next-iq3_s qwen3.6-35b-a3b-q4"
for m in $PRESETS; do
  strata-serve --plan --model "$m"
done

SMOKE_MODEL=qwen3.6-35b-a3b-q4
echo "smoke: serving $SMOKE_MODEL (mandatory; cache $STRATA_MODELS_ROOT)"
API_KEY=${API_KEY:-smokekeysmokekey12}
export API_KEY
LOG=$(mktemp)
setsid env API_KEY="$API_KEY" STRATA_MODELS_ROOT="$STRATA_MODELS_ROOT" strata-serve --model "$SMOKE_MODEL" >"$LOG" 2>&1 &
SP=$!
health() {
  python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8080/health", timeout=2).read()' 2>/dev/null
}
for i in $(seq 1 500); do
  health && break
  kill -0 "$SP" 2>/dev/null || { tail -80 "$LOG"; echo "FAIL: strata-serve exited"; exit 1; }
  if [ $((i % 24)) -eq 0 ]; then
    echo "smoke: still waiting for /health (${i} x 5s)"
    tail -n 5 "$LOG" || true
  fi
  sleep 5
done
health || { tail -80 "$LOG"; echo "FAIL: /health did not answer"; exit 1; }
python3 - "$SMOKE_MODEL" <<'PY'
import json, os, sys, urllib.request
name = sys.argv[1]
key = os.environ["API_KEY"]
h = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8080/health"), timeout=30))
print("health:", h)
# Do not treat loaded in (True, False) as success. The server must answer a completion.
body = {"model": name, "prompt": "The capital of France is", "max_tokens": 8, "temperature": 0}
req = urllib.request.Request("http://127.0.0.1:8080/v1/completions",
                             data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
try:
    r = json.load(urllib.request.urlopen(req, timeout=300))
    text = r["choices"][0].get("text") or r["choices"][0].get("message", {}).get("content", "")
except Exception:
    body = {"model": name,
            "messages": [{"role": "user", "content": "The capital of France is"}],
            "max_tokens": 8, "temperature": 0}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    text = r["choices"][0]["message"]["content"]
assert str(text).strip(), f"empty completion: {r}"
print("completion:", text.strip()[:120])
PY
kill -- -"$SP" 2>/dev/null || true
echo "SMOKE PASS"
