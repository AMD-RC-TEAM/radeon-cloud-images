# ComfyUI for Radeon PRO W7900 / W7900D (gfx1100): a clean ComfyUI on the PyTorch · Stable base (D-20261113-26).
# ComfyUI v0.45.0 at a pinned commit, its Python packages pinned, JupyterLab baked in. No custom nodes, no bundled
# models or workflows, no tunnel software (Radeon Cloud's rc-tunnel exposes 8188). Start it with `comfyui-start`.
FROM docker.io/rocm/pytorch:rocm7.14.1_ubuntu24.04_py3.12_pytorch_release_2.12.0@sha256:cc9b00f90b85c97b015b040fa55c8d1b404b7cacc6ad57d74ee3451c97508da1

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL
ARG COMFYUI_COMMIT=989d93d0d968e704c589ce0146bb18c77f6b50cc
ENV COMFY_PORT=8188

COPY requirements.txt fetch_src.py README.md comfyui-start /tmp/rc/
RUN python3 /tmp/rc/fetch_src.py tar comfyanonymous/ComfyUI ${COMFYUI_COMMIT} /opt/ComfyUI \
 && pip install --no-cache-dir --no-deps -r /tmp/rc/requirements.txt \
 && install -m 755 /tmp/rc/comfyui-start /usr/local/bin/comfyui-start \
 && install -D -m 644 /tmp/rc/README.md /opt/comfyui/README.md \
 && rm -rf /tmp/rc /root/.cache

# OpenSSH server baked in, so Radeon Cloud's SSH setup finds sshd and skips its launch-time apt install
# (which depends on the Ubuntu archive being fast from the cluster). Host keys are generated per instance.
ARG APT_MIRROR=mirrors.aliyun.com
COPY add_openssh.sh /tmp/add_openssh.sh
RUN sh /tmp/add_openssh.sh && rm -f /tmp/add_openssh.sh

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh

# JupyterLab terminals start "$SHELL -l" and fall back to sh when SHELL is unset (no history, no tab completion).
ENV SHELL=/bin/bash

# Use rocBLAS, not hipBLASLt, for torch matmuls on the W7900D (gfx1100): fp32 GEMM is ~8x faster (22 vs 2.6 TFLOPS at
# 4096^3) and bf16 ~20% faster; fp32 training was ~3x slower without it. smoke_lib.sh torch_gemm_floor checks it.
# Remove when hipBLASLt matches rocBLAS on gfx1100 at all sizes (re-measure with torch_gemm_floor and bigger shapes).
ENV TORCH_BLAS_PREFER_HIPBLASLT=0
