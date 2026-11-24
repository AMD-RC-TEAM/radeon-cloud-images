#!/bin/bash
# Smoke for the ComfyUI image on one W7900D: the launch fast path, the start command, and one real render.
#  1. JupyterLab fast path (no pip install at launch), gfx1100 visible to torch.
#  2. `comfyui-start` serves ComfyUI on 8188, and a Stable Diffusion 1.5 fp16 txt2img prompt (512x512, 12 steps)
#     produces a non-blank PNG. The checkpoint is fetched at test time through $HF_ENDPOINT (not baked), with retries.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
openssh_baked
ssh_keeps_image_env
grep -m1 -E 'gfx11[0-9]{2}' <<<"$(rocminfo)"
python3 -c 'import torch; print("torch", torch.__version__); assert torch.cuda.is_available()'
python3 -c 'import sys; sys.path.insert(0, "/opt/ComfyUI"); import comfyui_version as v; print("ComfyUI", v.__version__)'
command -v comfyui-start >/dev/null || { echo "FAIL: comfyui-start missing"; exit 1; }

CKPT=/opt/ComfyUI/models/checkpoints/v1-5-pruned-emaonly-fp16.safetensors
for attempt in 1 2 3; do
  echo "checkpoint download attempt $attempt ($(date -u +%H:%M:%S)Z)"
  timeout 600 env HF_HUB_DOWNLOAD_TIMEOUT=60 python3 -c 'import os, shutil, sys; from huggingface_hub import hf_hub_download as d
p = d("Comfy-Org/stable-diffusion-v1-5-archive", "v1-5-pruned-emaonly-fp16.safetensors"); shutil.copy(p, sys.argv[1])' "$CKPT" && break
  echo "checkpoint download attempt $attempt failed or took over 10 min; retrying (the download resumes from its cache)"; sleep 10
done
[ -s "$CKPT" ] || { echo "FAIL: could not download the SD1.5 checkpoint"; exit 1; }
(comfyui-start >/tmp/comfyui.log 2>&1 &)
for i in $(seq 1 120); do curl -sf http://127.0.0.1:8188/system_stats >/dev/null && break; sleep 3; done
curl -sf http://127.0.0.1:8188/system_stats >/dev/null || { tail -40 /tmp/comfyui.log; echo "FAIL: ComfyUI did not start on 8188"; exit 1; }
curl -sf http://127.0.0.1:8188/system_stats | python3 -c 'import json,sys; d=json.load(sys.stdin)["devices"][0]; print("comfyui-start: ComfyUI on 8188, device:", d["name"], d["type"])'
! grep -q "IMPORT FAILED" /tmp/comfyui.log || { grep -A3 "IMPORT FAILED" /tmp/comfyui.log; echo "FAIL: a node failed to import"; exit 1; }
python3 - <<'PY'
import json, time, urllib.request
g = {
 "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "v1-5-pruned-emaonly-fp16.safetensors"}},
 "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "a red apple on a wooden table, studio photo", "clip": ["1", 1]}},
 "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry", "clip": ["1", 1]}},
 "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
 "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0],
       "seed": 42, "steps": 12, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
 "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
 "7": {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "rc_smoke"}},
}
req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=json.dumps({"prompt": g}).encode(), headers={"Content-Type": "application/json"})
pid = json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"]
t0 = time.time()
while time.time() - t0 < 900:
    h = json.load(urllib.request.urlopen(f"http://127.0.0.1:8188/history/{pid}", timeout=30))
    if pid in h:
        st = h[pid].get("status", {})
        assert st.get("status_str") == "success", f"prompt failed: {json.dumps(st)[:400]}"
        img = h[pid]["outputs"]["7"]["images"][0]
        break
    time.sleep(3)
else:
    raise SystemExit("FAIL: render did not finish in 900 s")
from PIL import Image, ImageStat
im = Image.open(f"/opt/ComfyUI/output/{img['filename']}")
sd = ImageStat.Stat(im.convert("L")).stddev[0]
print(f"SD1.5 fp16 render: {im.size[0]}x{im.size[1]} in {time.time() - t0:.0f}s, luminance stddev {sd:.1f}")
assert im.size == (512, 512) and sd > 10, "render is blank"
PY
pkill -f "main.py --listen" || true
torch_gemm_floor   # fp32/bf16 matmul speed with the image defaults (TORCH_BLAS_PREFER_HIPBLASLT=0)
echo "SMOKE PASS"
