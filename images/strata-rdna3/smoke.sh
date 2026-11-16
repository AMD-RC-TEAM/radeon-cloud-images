#!/bin/bash
# Smoke for strata-rdna3 on one W7900D: JupyterLab fast path, gfx1100, --list/--plan for every
# preset, then a real serve of qwen3.6-35b-a3b-q4 (22.9 GB). That download + load may exceed
# the 1 hour / 48 Gi smoke envelope; the PR names the risk. Last line must be SMOKE PASS.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
welcome_once
welcome_jupyter_terminal
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
command -v strata-serve >/dev/null
command -v strata-dsv41 >/dev/null || test -s /etc/strata-dsv41-exe
/opt/strata/terminal/bin/strata --version
if [ -s /etc/strata-dsv41-exe ]; then
  "$(cat /etc/strata-dsv41-exe)" --version || true
fi
strata-serve --list
for m in deepseek-v4.1-flash-2.25 deepseek-v4.1-flash-2.00 qwen3.8-flash-next-iq3_s qwen3.6-35b-a3b-q4; do
  strata-serve --plan --model "$m"
done

SMOKE_MODEL=${SMOKE_STRATA_MODEL:-qwen3.6-35b-a3b-q4}
API_KEY=${API_KEY:-smokekeysmokekey12}
export API_KEY
LOG=$(mktemp)
# Exactly what a user types. API_KEY is what the upstream entrypoint already reads.
setsid env API_KEY="$API_KEY" strata-serve --model "$SMOKE_MODEL" >"$LOG" 2>&1 &
SP=$!
for i in $(seq 1 240); do
  curl -sf -m 2 http://127.0.0.1:8080/health >/dev/null && break
  kill -0 "$SP" 2>/dev/null || { tail -80 "$LOG"; echo "FAIL: strata-serve exited"; exit 1; }
  sleep 5
done
curl -sf -m 2 http://127.0.0.1:8080/health >/dev/null || { tail -80 "$LOG"; echo "FAIL: /health did not answer"; exit 1; }
python3 - <<'PY'
import json, os, urllib.request
key = os.environ["API_KEY"]
h = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8080/health"), timeout=30))
print("health:", h)
assert h.get("status") == "ok" or h.get("loaded") in (True, False), h
body = {"model": "qwen3.6-35b-a3b-q4", "prompt": "The capital of France is", "max_tokens": 8, "temperature": 0}
req = urllib.request.Request("http://127.0.0.1:8080/v1/completions",
                             data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
try:
    r = json.load(urllib.request.urlopen(req, timeout=300))
    text = r["choices"][0].get("text") or r["choices"][0].get("message", {}).get("content", "")
except Exception:
    body = {"model": "qwen3.6-35b-a3b-q4",
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
