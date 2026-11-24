#!/bin/bash
# Smoke for PyTorch images on one W7900D (gfx1100). Exit 0 = pass. Runs inside the image.
# Same checks rc-ux runs by hand (11-12): exactly one GPU visible with a PCI bus id, gfx1100, fp16 matmul,
# and a few training steps whose loss goes down. Any failure means rc-current does not move.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
openssh_baked
no_in_image_welcome
echo "== rocminfo"; grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
echo "== torch"
python3 - <<'PY'
import time, torch
assert torch.cuda.is_available(), "no GPU visible to torch"
n = torch.cuda.device_count()
assert n == 1, f"expected exactly 1 GPU, got {n}"
p = torch.cuda.get_device_properties(0)
arch = getattr(p, "gcnArchName", "") or ""
bus = getattr(p, "pci_bus_id", None)
print("torch", torch.__version__, "hip", torch.version.hip, "device", p.name, "arch", arch, "pci_bus_id", bus)
assert arch.startswith("gfx1100"), f"expected gfx1100, got {arch!r}"
assert bus is not None, "no PCI bus id for the GPU"

def matmul(dtype):
    a = torch.randn(4096, 4096, device="cuda", dtype=dtype)
    torch.cuda.synchronize(); t = time.time()
    for _ in range(20): b = a @ a
    torch.cuda.synchronize(); dt = time.time() - t
    assert torch.isfinite(b).all(), f"non-finite {dtype} matmul result"
    return 20 * 2 * 4096**3 / dt / 1e12

for dtype in (torch.float16, torch.bfloat16):
    tf = matmul(dtype)
    print(f"{dtype} matmul {tf:.1f} TFLOPS")
    assert tf > 5, f"{dtype} matmul far too slow for a W7900D"

torch.manual_seed(0)
model = torch.nn.Sequential(torch.nn.Linear(256, 512), torch.nn.ReLU(), torch.nn.Linear(512, 10)).cuda()
opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
x = torch.randn(512, 256, device="cuda"); y = torch.randint(0, 10, (512,), device="cuda")
losses = []
for step in range(50):
    loss = torch.nn.functional.cross_entropy(model(x), y)
    opt.zero_grad(); loss.backward(); opt.step(); losses.append(loss.item())
print(f"training: 50 steps, loss {losses[0]:.3f} -> {losses[-1]:.3f}")
assert losses[-1] < losses[0] * 0.8, "loss did not go down"
PY
echo "== notebook"
if python3 -c 'import jupyterlab' 2>/dev/null; then
  (jupyter lab --no-browser --ip=127.0.0.1 --port=18888 --ServerApp.token=smoke --allow-root >/tmp/jl.log 2>&1 &)
  for i in $(seq 1 60); do curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null && { echo "jupyter ok"; break; }; sleep 2; done
  curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null || { tail -20 /tmp/jl.log; exit 1; }
else
  echo "jupyterlab not in image (the RC launcher provides it); skipped"
fi
torch_gemm_floor   # fp32/bf16 matmul speed with the image defaults (TORCH_BLAS_PREFER_HIPBLASLT=0)
echo "SMOKE PASS"
