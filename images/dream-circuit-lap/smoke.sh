#!/bin/bash
# Smoke for the Dream Circuit Lap image on one W7900D: what the course notebook relies on, and its one local render.
#  1. JupyterLab fast path, sshd, gfx1100 visible to torch.
#  2. The baked media match the kept manifest, a clip decodes with av, and the Noto Sans SC fonts load.
#  3. ComfyUI starts from $COMFY_DIR with both AMD cloud nodes registered (running them needs an H3 key, so only their
#     registration is checked).
#  4. The course's car edit graph (Qwen Image 2.1 int8 with the Qwen3-VL 8B int8 text encoder, the baked models) edits a
#     512x512 reference on the GPU in 8 steps and produces a non-blank PNG.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
openssh_baked
no_in_image_welcome
grep -m1 -E 'gfx11[0-9]{2}' <<<"$(rocminfo)"
python3 -c 'import torch; print("torch", torch.__version__); assert torch.cuda.is_available()'
python3 -c 'import os, sys; sys.path.insert(0, os.environ["COMFY_DIR"]); import comfyui_version as v; print("ComfyUI", v.__version__)'

python3 - <<'PY'
import json, os
import av
from PIL import ImageFont
cache = os.environ["DREAM_CIRCUIT_MEDIA_CACHE"]
files = json.load(open("/opt/dream-circuit-lap/manifest.json"))["files"]
bad = [n for n, f in files.items() if not os.path.isfile(f"{cache}/{n}") or os.path.getsize(f"{cache}/{n}") != f["bytes"]]
assert not bad, f"FAIL: media missing or wrong size: {bad}"
clip = next(n for n in files if n.endswith(".mp4"))
with av.open(f"{cache}/{clip}") as c:
    frame = next(c.decode(video=0))
for k in ("F1_FONT_REGULAR", "F1_FONT_BOLD"):
    ImageFont.truetype(os.environ[k], 40)
print(f"media: {len(files)} files in {cache}, {clip} decodes ({frame.width}x{frame.height}), fonts load")
PY

cd "$COMFY_DIR"
(python3 main.py --listen 127.0.0.1 --port 8188 >/tmp/comfyui.log 2>&1 &)
for i in $(seq 1 120); do curl -sf http://127.0.0.1:8188/system_stats >/dev/null && break; sleep 3; done
curl -sf http://127.0.0.1:8188/system_stats >/dev/null || { tail -40 /tmp/comfyui.log; echo "FAIL: ComfyUI did not start on 8188"; exit 1; }
! grep -q "IMPORT FAILED" /tmp/comfyui.log || { grep -A3 "IMPORT FAILED" /tmp/comfyui.log; echo "FAIL: a node failed to import"; exit 1; }
for node in AMDQwenImage21TextToImage AMDMiniMaxH3FirstLastFrameToVideo; do
  curl -sf "http://127.0.0.1:8188/object_info/$node" | grep -q "\"$node\"" || { echo "FAIL: node $node is not registered"; exit 1; }
done
echo "ComfyUI on 8188 with AMDQwenImage21TextToImage and AMDMiniMaxH3FirstLastFrameToVideo"

python3 - <<'PY'
import json, os, time, urllib.request
from PIL import Image, ImageDraw, ImageStat
comfy = os.environ["COMFY_DIR"]
ref = Image.new("RGB", (512, 512), (120, 160, 210))
d = ImageDraw.Draw(ref)
d.rectangle((0, 300, 512, 512), fill=(70, 70, 75))
d.rectangle((170, 330, 340, 400), fill=(20, 40, 120))
ref.save(f"{comfy}/input/rc_smoke_ref.png")
g = {
 "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "qwen_image_2.1_int8_convrot.safetensors", "weight_dtype": "default"}},
 "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_8b_int8_convrot.safetensors", "type": "qwen_image", "device": "default"}},
 "3": {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_2.1_vae_bf16.safetensors"}},
 "4": {"class_type": "LoadImage", "inputs": {"image": "rc_smoke_ref.png"}},
 "5": {"class_type": "TextEncodeQwenImage21", "inputs": {"clip": ["2", 0], "vae": ["3", 0], "images.image_1": ["4", 0], "resolution": 512,
       "prompt": "Turn the dark blue box on the road into a dark blue racing car, keep the sky and the road.", "negative_prompt": ""}},
 "6": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["5", 1], "latent_image": ["5", 2],
       "seed": 42, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
 "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["3", 0]}},
 "8": {"class_type": "SaveImage", "inputs": {"images": ["7", 0], "filename_prefix": "rc_smoke"}},
}
req = urllib.request.Request("http://127.0.0.1:8188/prompt", data=json.dumps({"prompt": g}).encode(), headers={"Content-Type": "application/json"})
pid = json.load(urllib.request.urlopen(req, timeout=60))["prompt_id"]
t0 = time.time()
while time.time() - t0 < 1200:
    h = json.load(urllib.request.urlopen(f"http://127.0.0.1:8188/history/{pid}", timeout=30))
    if pid in h:
        st = h[pid].get("status", {})
        assert st.get("status_str") == "success", f"prompt failed: {json.dumps(st)[:400]}"
        img = h[pid]["outputs"]["8"]["images"][0]
        break
    time.sleep(3)
else:
    raise SystemExit("FAIL: edit did not finish in 1200 s")
im = Image.open(f"{comfy}/output/{img['filename']}")
sd = ImageStat.Stat(im.convert("L")).stddev[0]
print(f"Qwen Image 2.1 edit: {im.size[0]}x{im.size[1]} in {time.time() - t0:.0f}s, luminance stddev {sd:.1f}")
assert im.size == (512, 512) and sd > 10, "edit output is blank"
PY
pkill -f "main.py --listen" || true
torch_gemm_floor   # fp32/bf16 matmul speed with the image defaults (TORCH_BLAS_PREFER_HIPBLASLT=0)
echo "SMOKE PASS"
