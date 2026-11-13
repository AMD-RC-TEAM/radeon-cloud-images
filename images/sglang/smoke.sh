#!/bin/bash
# Smoke for SGLang images on one W7900D: the stack imports on gfx1100, an SGLang server on a 0.5B model answers one
# chat request, and `sglang serve` on Qwen-Image-2.1 (SGLang-Diffusion) returns one 512x512 image. The model comes from SMOKE_MODEL_DIR if it is mounted, otherwise it is downloaded
# through $HF_ENDPOINT (the smoke Job points it at a mirror reachable from the cluster).
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
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
sleep 10

# SGLang-Diffusion: what a user types, `sglang serve --model-path Qwen/Qwen-Image-2.1`, then one 512x512 image through the
# OpenAI-style images API. (11-13: this failed with KeyError: 'sglang.multimodal_gen' because the diffusion extras were
# missing.) The model is fetched first, with retries, so a slow mirror read does not fail the smoke.
python3 -c 'import sglang.multimodal_gen.runtime.entrypoints.cli.serve, moviepy, cache_dit; from diffusers import QwenImage21Pipeline; print("sglang diffusion: imports OK")'
DMODEL=Qwen/Qwen-Image-2.1
for attempt in 1 2 3; do
  HF_HUB_DOWNLOAD_TIMEOUT=60 python3 -c 'import sys; from huggingface_hub import snapshot_download as s; s(sys.argv[1])' "$DMODEL" > /dev/null 2>&1 && break
  echo "download attempt $attempt failed; retrying"; sleep 10
done
DLOG=$(mktemp); DPORT=30010
setsid sglang serve --model-path "$DMODEL" --host 127.0.0.1 --port "$DPORT" > "$DLOG" 2>&1 &
DP=$!
for i in $(seq 1 240); do
  curl -sf -m 2 "http://127.0.0.1:$DPORT/health" > /dev/null && break
  kill -0 "$DP" 2>/dev/null || { tail -60 "$DLOG"; echo "FAIL: diffusion server exited"; exit 1; }
  sleep 5
done
curl -sf -m 2 "http://127.0.0.1:$DPORT/health" > /dev/null || { tail -60 "$DLOG"; echo "FAIL: diffusion server did not start"; exit 1; }
python3 - "$DPORT" <<'PY'
import base64, io, json, sys, time, urllib.request
port = sys.argv[1]
body = {"model": "Qwen/Qwen-Image-2.1", "prompt": "a red apple on a wooden table, studio photo", "size": "512x512", "n": 1,
        "response_format": "b64_json"}
t0 = time.time()
req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/images/generations", data=json.dumps(body).encode(),
                             headers={"Content-Type": "application/json"})
r = json.load(urllib.request.urlopen(req, timeout=1500))
item = r["data"][0]
if item.get("b64_json"):
    data = base64.b64decode(item["b64_json"])
else:
    url = item["url"] if item["url"].startswith("http") else f"http://127.0.0.1:{port}{item['url']}"
    data = urllib.request.urlopen(url, timeout=120).read()
from PIL import Image, ImageStat
im = Image.open(io.BytesIO(data))
path = "/tmp/sglang-diffusion-smoke.png"; im.save(path)
sd = ImageStat.Stat(im.convert("L")).stddev[0]
print(f"sglang diffusion: Qwen-Image-2.1 {im.size[0]}x{im.size[1]} in {time.time() - t0:.0f}s -> {path}, luminance stddev {sd:.1f}")
assert sd > 10, "blank image"
PY
grep -iE "memory|vram|GiB" "$DLOG" | tail -3 || true
kill -- -"$DP" 2>/dev/null || true
echo "SMOKE PASS"
