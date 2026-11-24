#!/bin/bash
# Smoke for the Base image on one W7900D: JupyterLab launch fast path (and nothing it installed changed), sshd baked in,
# an SSH session sees the image's Python and loads torch, the common packages import and `hf` runs, the GPU is gfx1100
# and usable from torch.
set -euo pipefail
. "$(dirname "$0")/smoke_lib.sh"
jupyterlab_fast_path
openssh_baked
ssh_keeps_image_env
no_in_image_welcome
grep -m1 -E 'gfx1100' <<<"$(rocminfo)"
test "$(command -v python3)" = /opt/venv/bin/python3
python3 -c 'import transformers, datasets, accelerate, sklearn, ipywidgets, huggingface_hub; print("common packages: transformers", transformers.__version__, "huggingface_hub", huggingface_hub.__version__)'
hf --help >/dev/null
command -v vim >/dev/null
python3 -c 'import torch; assert torch.cuda.is_available(); x = torch.randn(1024, 1024, device="cuda", dtype=torch.float16); print("torch", torch.__version__, "matmul ok", float((x @ x).float().abs().mean()) > 0)'
torch_gemm_floor   # fp32/bf16 matmul speed with the image defaults (TORCH_BLAS_PREFER_HIPBLASLT=0)
echo "SMOKE PASS"
