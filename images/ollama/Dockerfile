# Ollama for Radeon PRO W7900 / W7900D (gfx1100) on the ROCm 7.2 / Ubuntu 24.04 base that Base and SGLang use. The public
# upstream image, pinned by digest; the pipeline mirrors it into Harbor and builds/smokes from there.
FROM docker.io/rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e

# The build sets this to a PyPI mirror reachable from the build cluster; it is not kept in the image.
ARG PIP_INDEX_URL
# apt mirror reachable from the build cluster (used by add_zstd.sh and add_openssh.sh); not kept in the image.
ARG APT_MIRROR=mirrors.aliyun.com

# zstd is needed to unpack the release archives below (add_zstd.sh installs it only if the base image lacks it).
COPY add_zstd.sh /tmp/add_zstd.sh
RUN sh /tmp/add_zstd.sh && rm -f /tmp/add_zstd.sh

# Ollama from its GitHub release (https://github.com/ollama/ollama/releases): ollama-linux-amd64.tar.zst and
# ollama-linux-amd64-rocm.tar.zst, extracted into /usr, pinned by version and SHA-256 (the digests GitHub shows for
# each asset). The README goes to /opt/ollama.
# The release archives (~2.5 GB) are downloaded through this proxy first: direct downloads from github.com ran at
# ~100 KB/s from the build cluster (about 6.6 h). Then github.com directly. Either way the file is checked by sha256.
# Set it empty to use github.com only.
ARG GITHUB_PROXY=https://gh-proxy.com/
ARG OLLAMA_VERSION=0.40.18
ARG OLLAMA_AMD64_SHA256=b82649006cb5b54ed1237fa2d1a26a7f939a4fd03150033759acbff7ff315adf
ARG OLLAMA_ROCM_SHA256=d404a0f936a69ecf7904f228f68cf65021fdf45e4b66db3fb9c8603abd206447
COPY fetch_ollama.py README.md /tmp/rc/
RUN python3 /tmp/rc/fetch_ollama.py ${OLLAMA_VERSION} ${OLLAMA_AMD64_SHA256} ${OLLAMA_ROCM_SHA256} \
 && install -D -m 644 /tmp/rc/README.md /opt/ollama/README.md \
 && rm -rf /tmp/rc

# OpenSSH server baked in, so Radeon Cloud's SSH setup finds sshd and skips its launch-time apt install
# (which depends on the Ubuntu archive being fast from the cluster). Host keys are generated per instance.
COPY add_openssh.sh /tmp/add_openssh.sh
RUN sh /tmp/add_openssh.sh && rm -f /tmp/add_openssh.sh

# Radeon Cloud's launch step pip-installs JupyterLab into any image that lacks a compatible one (18-188 s per launch).
# Bake it in, pinned, without changing anything already installed (add_jupyterlab.sh; the smoke verifies both).
COPY add_jupyterlab.sh /tmp/add_jupyterlab.sh
RUN sh /tmp/add_jupyterlab.sh && rm -f /tmp/add_jupyterlab.sh

# Models go to the platform's /workspace volume (persistent when the instance has "Persistent /workspace"), not to
# ~/.ollama. Only the path is set here: nothing is created under /workspace at build time, `ollama serve` creates it.
ENV OLLAMA_MODELS=/workspace/ollama/models

# JupyterLab terminals start "$SHELL -l" and fall back to sh when SHELL is unset (no history, no tab completion).
ENV SHELL=/bin/bash

# Ollama does not use torch, but this base ships PyTorch for JupyterLab users. Use rocBLAS, not hipBLASLt, for torch
# matmuls on the W7900D (gfx1100): fp32 GEMM is ~8x faster (22 vs 2.6 TFLOPS at 4096^3) and bf16 ~20% faster; fp32
# training was ~3x slower without it. smoke_lib.sh torch_gemm_floor checks it.
# Remove when hipBLASLt matches rocBLAS on gfx1100 at all sizes (re-measure with torch_gemm_floor and bigger shapes).
ENV TORCH_BLAS_PREFER_HIPBLASLT=0

# Keep the image environment (PATH, LD_LIBRARY_PATH, ROCm settings, OLLAMA_MODELS) in SSH sessions; see keep_image_env.sh.
# Last step: after every ENV.
COPY keep_image_env.sh /tmp/keep_image_env.sh
RUN sh /tmp/keep_image_env.sh && rm -f /tmp/keep_image_env.sh
