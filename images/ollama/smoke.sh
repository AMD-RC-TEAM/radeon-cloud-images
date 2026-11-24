#!/bin/bash
# Smoke for the Ollama image on one W7900D: the GPU is visible and the Ollama server starts and answers.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
openssh_baked
no_in_image_welcome
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
command -v ollama
(ollama serve >/tmp/ollama.log 2>&1 &)
for i in $(seq 1 60); do curl -sf http://127.0.0.1:11434/api/version >/dev/null && break; sleep 2; done
curl -sf http://127.0.0.1:11434/api/version || { tail -40 /tmp/ollama.log; echo "FAIL: ollama serve did not answer"; exit 1; }
echo
pkill -f "ollama serve" 2>/dev/null || true
echo "SMOKE PASS"
