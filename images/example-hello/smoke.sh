#!/bin/bash
# EXAMPLE ONLY. Smoke for example-hello on ONE W7900D (gfx1100), run inside the image by the PR check and by every
# release. It must print "SMOKE PASS" last; anything else blocks the merge (and the release).
# Keep it fast and small: no large downloads. If you need a model, use a tiny one through HF_ENDPOINT (set by the
# smoke Job); the CI cache keeps it between runs.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"

# 1. The launch fast path: JupyterLab is baked in and nothing that was already installed changed.
jupyterlab_fast_path

# 2. The GPU: exactly one gfx1100 visible to the runtime.
echo "== rocminfo"; grep -m1 -E 'gfx1100' <<<"$(rocminfo)"

# 3. A tiny version of what users do with this image (here: one matmul and one import of our extra package).
echo "== workload"
python3 - <<'PY'
import torch, rich
assert torch.cuda.is_available() and torch.cuda.device_count() == 1, "expected exactly one visible GPU"
arch = getattr(torch.cuda.get_device_properties(0), "gcnArchName", "")
assert arch.startswith("gfx1100"), f"expected gfx1100, got {arch!r}"
a = torch.randn(1024, 1024, device="cuda", dtype=torch.float16)
b = a @ a
torch.cuda.synchronize()
assert torch.isfinite(b).all(), "non-finite matmul result"
print("torch", torch.__version__, "arch", arch, "rich", rich.__version__ if hasattr(rich, "__version__") else "ok")
PY

# 4. The notebook server starts and answers.
echo "== notebook"
(jupyter lab --no-browser --ip=127.0.0.1 --port=18888 --ServerApp.token=smoke --allow-root >/tmp/jl.log 2>&1 &)
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null && { echo "jupyter ok"; break; }; sleep 2; done
curl -sf "http://127.0.0.1:18888/api/status?token=smoke" >/dev/null || { tail -20 /tmp/jl.log; exit 1; }

echo "SMOKE PASS"
