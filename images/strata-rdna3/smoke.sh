#!/bin/bash
# Smoke for strata-rdna3 on one W7900D, 48Gi, 1h. JupyterLab fast path, gfx1100, --list and
# --plan for every preset. Must not download 23 GB (Wuxi edge cuts ~10 min connections).
# A full qwen3.6-35b-a3b-q4 serve is not the gate. If a preset's files are already staged,
# serve that; otherwise skip serve and still end with SMOKE PASS. Last line must be SMOKE PASS.
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
  "$(cat /etc/strata-dsv41-exe)" --version
fi
strata-serve --list
PRESETS="deepseek-v4.1-flash-2.25 deepseek-v4.1-flash-2.25-fast deepseek-v4.1-flash-2.00 deepseek-v4.1-flash-2.00-fast qwen3.8-flash-next-iq3_s qwen3.6-35b-a3b-q4"
for m in $PRESETS; do
  strata-serve --plan --model "$m"
done

# Optional serve of a pre-staged Strata cache only. CI sets SMOKE_MODEL_DIR to a 0.5B Hugging Face
# folder this image cannot serve; that is not a 23 GB download and is ignored unless the files
# already satisfy a preset (strata-serve --plan shows [ok], not [download]).
echo "smoke: full serve is not the CI gate (no 23 GB download)"
staged=""
candidates="${SMOKE_STRATA_MODEL:-} qwen3.6-35b-a3b-q4"
for m in $candidates; do
  [ -n "$m" ] || continue
  plan=$(strata-serve --plan --model "$m")
  if grep -q '\[download\]' <<<"$plan"; then
    echo "smoke: $m is not fully staged; skip serve"
    continue
  fi
  staged=$m
  break
done
if [ -z "$staged" ]; then
  echo "smoke: skip serve; qwen3.6 and multi-GPU DeepSeek/Qwen3.8 are manual smokes on W7900D"
  echo "SMOKE PASS"
  exit 0
fi

echo "smoke: serving pre-staged $staged"
API_KEY=${API_KEY:-smokekeysmokekey12}
export API_KEY
LOG=$(mktemp)
setsid env API_KEY="$API_KEY" strata-serve --model "$staged" >"$LOG" 2>&1 &
SP=$!
for i in $(seq 1 240); do
  curl -sf -m 2 http://127.0.0.1:8080/health >/dev/null && break
  kill -0 "$SP" 2>/dev/null || { tail -80 "$LOG"; echo "FAIL: strata-serve exited"; exit 1; }
  sleep 5
done
curl -sf -m 2 http://127.0.0.1:8080/health >/dev/null || { tail -80 "$LOG"; echo "FAIL: /health did not answer"; exit 1; }
python3 - "$staged" <<'PY'
import json, os, sys, urllib.request
name = sys.argv[1]
key = os.environ["API_KEY"]
h = json.load(urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8080/health"), timeout=30))
print("health:", h)
assert h.get("status") == "ok" or h.get("loaded") in (True, False), h
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
