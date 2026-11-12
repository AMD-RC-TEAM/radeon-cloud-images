#!/bin/bash
# Smoke for PyTorch images on one W7900D (gfx1100). Exit 0 = pass. Runs inside the image.
set -euo pipefail
echo "== rocminfo"; rocminfo | grep -m1 -E 'gfx11[0-9]{2}'
echo "== torch"
python3 - <<'PY'
import time, torch
assert torch.cuda.is_available(), "no GPU visible to torch"
print("torch", torch.__version__, "hip", torch.version.hip, "device", torch.cuda.get_device_name(0))
a = torch.randn(4096, 4096, device="cuda", dtype=torch.bfloat16)
torch.cuda.synchronize(); t = time.time()
for _ in range(20): b = a @ a
torch.cuda.synchronize(); dt = time.time() - t
tflops = 20 * 2 * 4096**3 / dt / 1e12
print(f"bf16 matmul {tflops:.1f} TFLOPS")
assert torch.isfinite(b).all(), "non-finite matmul result"
assert tflops > 5, "matmul far too slow for a W7900D"
x = torch.randn(64, 128, device="cuda", requires_grad=True)
(x.square().sum()).backward(); assert x.grad is not None
print("autograd ok")
PY
echo "== notebook"
if python3 -c 'import jupyterlab' 2>/dev/null; then
  (jupyter lab --no-browser --ip=127.0.0.1 --port=18888 --ServerApp.token=smoke --allow-root >/tmp/jl.log 2>&1 &)
  for i in $(seq 1 60); do curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null && { echo "jupyter ok"; break; }; sleep 2; done
  curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null || { tail -20 /tmp/jl.log; exit 1; }
else
  echo "jupyterlab not in image (the RC launcher provides it); skipped"
fi
echo "SMOKE PASS"
