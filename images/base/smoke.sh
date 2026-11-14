#!/bin/bash
# Smoke for the Base image on one W7900D: JupyterLab launch fast path, the GPU is gfx1100 and usable from torch,
# and the hk-dsl README quick start (pip install hk-dsl && vllm serve Qwen/Qwen3-8B, one completion) works.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
welcome_once
welcome_jupyter_terminal
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
python3 -c 'import torch; assert torch.cuda.is_available(); x = torch.randn(1024, 1024, device="cuda", dtype=torch.float16); print("torch", torch.__version__, "matmul ok", float((x @ x).float().abs().mean()) > 0)'
cd "$(mktemp -d)"
HK_VERSION=0.9.21 bash "$(dirname "$0")/hk_readme_smoke.sh"
echo "SMOKE PASS"
